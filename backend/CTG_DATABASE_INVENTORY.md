# CTG Database Inventory (Phase 1 — Audit)

Phạm vi quét: `app/**` (models, repositories, services, workers, api, startup), `scripts/**`, `tests/**`, `a.py`, `run_server.py`.
Phương pháp: AST import graph của toàn bộ `app/` + grep `__tablename__`, `ForeignKey`, `relationship`, `text(...)`, `execute(...)`, SQL thô.

> **Phase 2 (đã xong):** đã xóa `Entity`, `EntityContext`, `EntityRelationship` khỏi source cùng toàn bộ router, service và repository GraphRAG. Sau khi import tất cả model, `Base.metadata` còn 37 bảng, không còn bảng hay FK nào trỏ tới `entities*`.

Kết quả quan trọng trước khi đọc bảng:

- **Không có Alembic và không có file `.sql` nào trong source.** `CODEBASE_STRUCTURE.md` có nhắc `alembic/`, nhưng thư mục này không tồn tại. Schema DB cũ được tạo ngoài repo, nên không có "migration lịch sử" để đối chiếu.
- **Chunk/embedding không nằm trong PostgreSQL** mà nằm trong **Azure AI Search index** (`AzureChunkRepository`, `AzureSearchService`).
- **Raw SQL trên PostgreSQL chỉ có 1 chỗ:** `entity_repository.py` (`FROM entities`), thuộc GraphRAG.
- **Raw SQL trên DuckDB** (không phải Postgres): `legal_documents`, `legal_search`, phục vụ Legal Review/Legal Chat.
- `app/models/__init__.py` chỉ đăng ký 7/39 model. `Base.metadata` hiện **không đầy đủ** và không thể dùng làm baseline nếu chưa import hết model.

## 1. Bảng PostgreSQL có SQLAlchemy model

Ký hiệu use case: CR = Contract Review/Legal, CHAT = Chat RAG, CV = Review CV, MTG = Meeting, PLN = Planner, UPL = Upload SharePoint, SYNC = Logic App Sync + callback, DELTA = SharePoint delta, CFG = API quản lý model/prompt/RAG config.

| Table | Model | Referenced by | Use case | KEEP/REMOVE/REVIEW | Reason |
|---|---|---|---|---|---|
| `entities` | `Entity` | entity_repository (ORM + raw SQL), graph_repository, entity_embedding_service, backfill_entity_embeddings | GraphRAG | **REMOVE** | Chỉ GraphRAG dùng. Có cột `Vector(1536)`. |
| `entity_contexts` | `EntityContext` | entity_context_repository | GraphRAG | **REMOVE** | Chỉ GraphRAG dùng. FK → `entities.id`. |
| `entity_relationships` | `EntityRelationship` | entity_relationship_repository, entity_repository, graph_repository, self_embodiment_repository | GraphRAG | **REMOVE** | Chỉ GraphRAG dùng. 2 FK → `entities.id`. |
| `ai_models` | `AIModel` | ai_model_repository, rag_config_repository, model_service | CR, CHAT, CV, MTG, CFG | **KEEP** | Model selection cho mọi nghiệp vụ AI. Là đích FK của `review_jobs`, `workspace_model_configs`. Cần seed. |
| `ai_prompts` | `AIPrompt` | ai_prompt_repository, ai_prompt_service | CR, CHAT, CV, MTG, CFG | **KEEP** | Prompt loading theo `PromptCode`. Cần seed các code đang dùng. |
| `contract_raw` | `ContractRaw` | contract_repository, contract_service | CR | **KEEP** | Lưu hợp đồng đã trích xuất. |
| `contract_dashboard` | `ContractDashboard` | contract_repository, contract_service | CR | **KEEP** | Kết quả phân tích hợp đồng. FK → `contract_raw.id` (CASCADE). |
| `workspaces` | `Workspace` | rag_config_repository, workspace_source_config_repository | CHAT, CR, CV, UPL, CFG | **KEEP** | Gốc của toàn bộ cấu hình RAG/model/source. Cần seed. |
| `workspace_model_configs` | `WorkspaceModelConfig` | rag_config_repository | CHAT, CR, CV, CFG | **KEEP** | temperature/max_tokens theo workspace. FK → `workspaces`, `ai_models`. |
| `workspace_rag_configs` | `WorkspaceRagConfig` | rag_config_repository | CHAT, CR, CV, CFG | **KEEP** | top_k, chunking. FK → `workspaces`, `master_configs`. |
| `master_configs` | `MasterConfig` | rag_config_repository | CHAT, CR, CV, CFG | **KEEP** | FK → `embedding_models`. |
| `embedding_models` | `EmbeddingModel` | rag_config_repository | CHAT, CR, CV, CFG | **KEEP** | Đích FK của `master_configs`. |
| `workspace_source_configs` | `WorkspaceSourceConfig` | workspace_source_config_repository | UPL, CHAT, CFG | **KEEP** | `/documents/upload-sharepoint` lấy `security_level` từ đây. FK → `workspaces`, `data_source_modes`. |
| `data_source_modes` | `DataSourceMode` | workspace_source_config_repository | UPL, CHAT, CFG | **KEEP** | Đích FK. Cần seed. |
| `document_types` | `DocumentType` | workspace_source_config_repository | UPL, CFG | **KEEP** | Danh mục loại tài liệu. Cần seed. |
| `sensitivity_levels` | `SensitivityLevel` | sensitivity_repository, permission_repository | SYNC (callback → ChunkProcessor → SensitivityClassifier) | **KEEP** | Callback Sync đọc danh sách level để phân loại chunk. Cần seed. |
| `sharepoint_delta_states` | `SharePointDeltaState` | sharepoint_delta_state_repository | DELTA (`/documents/delta/check`, sharepoint_delta_worker) | **KEEP** | Lưu `delta_link` của Microsoft Graph delta. |
| `meeting_analyses` | `MeetingAnalysis` | meeting_analysis_repository, meeting_analysis_service | MTG | **KEEP** | `model_id` không có FK (nên giữ như vậy hoặc thêm FK → `ai_models`). |
| `meeting_transcripts` | `MeetingTranscript` | meeting_transcript_repository, meeting_analysis_service | MTG | **KEEP** | FK → `meeting_analyses.id`. |
| `recruitment_campaigns` | `RecruitmentCampaign` | recruitment_campaign_repository, ingest_cv (dead) | CV | **KEEP** | **FK `role_id` → `roles.id`** (xem `roles`). Cột `cv_embedding Vector(1536)` không có writer nào còn sống (`ingest_cv` không được gọi) nên là ứng viên bỏ cột để khỏi cần pgvector. |
| `recruitment_candidates` | `RecruitmentCandidate` | recruitment_candidate_repository, recruitment_candidate_result_repository | CV | **KEEP** | FK → `recruitment_campaigns.id`. File CV nằm ở Supabase Storage. |
| `recruitment_candidate_results` | `RecruitmentCandidateResult` | recruitment_candidate_result_repository | CV | **KEEP** | FK → `recruitment_candidates.id`. |
| `review_jobs` | `ReviewJob` | review_job_repository, review_service, recruitment_campaign_repository | CV (queue_consumer, review_worker) | **KEEP** | FK → `ai_models.id`. `relationship` ↔ `review_tasks`. |
| `review_tasks` | `ReviewTask` | review_task_repository, review_service, recruitment_campaign_repository | CV | **KEEP** | FK → `review_jobs.id`. |
| `users` | `User` | api/dependencies/auth (`get_current_user`), user_repository, auth_service, planner_router | PLN, Auth | **REVIEW → KEEP tạm** | **Planner bắt buộc**: `/planner/tasks` dùng `get_current_user` (JWT → `users`). Không bỏ được khi chưa đổi cơ chế xác thực của Planner. |
| `microsoft_accounts` | `MicrosoftAccount` | microsoft_account_repository, auth_service, planner_service | PLN, Auth | **REVIEW → KEEP tạm** | Lưu refresh/access token delegated để gọi Planner. FK → `users.id`. |
| `conversations` | `Conversation` | conversation_repository | CHAT (history), conversation_router, bot_router | **REVIEW → KEEP tạm** | `/chat` và `/chat/helpdesk` đang đọc/ghi. Theo yêu cầu: refactor chat trước, sau đó mới bỏ. |
| `messages` | `Message` | message_repository | CHAT, conversation_router, bot_router | **REVIEW → KEEP tạm** | FK → `conversations.id`. Lý do giống `conversations`. |
| `conversation_summaries` | `ConversationSummary` | conversation_summary_repository | CHAT (session memory) | **REVIEW → KEEP tạm** | FK → `conversations.id`. Lý do giống `conversations`. |
| `roles` | `Role` | role_repository, permission_repository, policy_engine | role_router, permission_router, policy_router, **CV (FK)** | **REVIEW** | Không nằm trong danh sách giữ, nhưng **`recruitment_campaigns.role_id` có FK tới đây**. Hai lựa chọn: giữ bảng, hoặc đổi `role_id` thành cột thường/`position` text. |
| `tags` | `Tag` | tag_repository, policy_engine | tag_router, policy_router | **REVIEW (đề xuất REMOVE)** | Không có use case giữ nào dùng. `semantic_tagger` là dead code. |
| `tag_role_rules` | `TagRoleRule` | tag_role_rule_repository, policy_engine | tag_role_rule_router, policy_router | **REVIEW (đề xuất REMOVE)** | FK → `tags`, `roles`. |
| `departments` | `Department` | department_repository, permission_repository | permission_router, bot_router, department_route (không được mount) | **REVIEW (đề xuất REMOVE)** | Chỉ RBAC nội bộ và Teams bot dùng. |
| `position_levels` | `PositionLevel` | permission_repository | permission_router, bot_router | **REVIEW (đề xuất REMOVE)** | RBAC. |
| `department_sensitivity_permissions` | `DepartmentSensitivityPermission` | permission_repository, permission_service | permission_router, bot_router | **REVIEW (đề xuất REMOVE)** | RBAC. FK → `departments` (×2), `sensitivity_levels`, `position_levels`. |
| `executive_data_raw` | `ExecutiveDataRaw` | executive_data_repository, executive_data_sync_service | Governance (`/documents/executive-data/*`, executive_data_worker) | **REVIEW (đề xuất REMOVE)** | Governance, không nằm trong danh sách giữ. |
| `executive_data_dashboard` | `ExecutiveDataDashboard` | executive_data_repository, executive_data_sync_service | Governance | **REVIEW (đề xuất REMOVE)** | FK → `executive_data_raw.id`. |
| `project_tracking_raw` | `ProjectTrackingRaw` | project_tracking_raw_repository, project_tracking_sync_service | Project Tracking (`/documents/projects`, `/documents/sync/*`, `/documents/tracking/chat`, worker) | **REVIEW** | Không nằm trong danh sách giữ, cũng không nằm trong danh sách bỏ. Endpoint đang nằm chung trong `document_router`. |
| `project_tracking_dashboard` | `ProjectTrackingDashboard` | project_tracking_dashboard_repository, project_tracking_raw_repository | Project Tracking | **REVIEW** | FK → `project_tracking_raw.project_code`. |
| `user_memories` | `UserMemory` | user_memory_repository (không ai gọi) | — | **REMOVE** | Không có consumer còn sống. Model **không có primary key** nên SQLAlchemy sẽ lỗi khi mapper được cấu hình. |
| `sync_jobs` | `SyncJob` | sync_job_repository, sync_job_service (không ai gọi) | — | **REMOVE** | Dead code. Model import `app.core.database.models.base`, module **không tồn tại**. Trạng thái Sync thực tế nằm trong memory (`SyncState`). |

## 2. Bảng ngoài PostgreSQL (vẫn là dependency dữ liệu)

| Kho | Table/Object | Referenced by | Use case | Quyết định | Ghi chú |
|---|---|---|---|---|---|
| DuckDB (`LEGAL_DB_PATH`) | `legal_documents` | legal_retrieval_service, legal_chat_retrieval_service, scripts/setup_local_legal_db.py | CR (legal review, legal chat) | **KEEP** | Không thuộc Postgres. Cần cung cấp file `.duckdb` khi deploy. |
| DuckDB | `legal_search` (+ FTS schema) | legal_retrieval_service, legal_chat_retrieval_service, scripts/setup_legal_fts.py | CR | **KEEP** | Tạo bằng `scripts/setup_legal_fts.py`. |
| Azure AI Search | index `AZURE_SEARCH_INDEX` (chunk_id, chunk, title, parent_id, sensitivity, department, …) | AzureChunkRepository, AzureSearchService | CHAT, SYNC | **KEEP** | Chunk và embedding nằm ở đây, không ở Postgres. |
| Supabase Storage | bucket `documents` (`cv/...`) | SupabaseStorage | CV | **KEEP (REVIEW nhà cung cấp)** | Client được tạo ngay lúc import, nên thiếu `SUPABASE_URL` thì router CV không import được. |
| In-memory | `SyncState.status` | document_router | SYNC | — | Không bền vững và không an toàn khi chạy nhiều worker. |

## 3. Bảng trong tài liệu ingestion — KHÔNG có trong source

`organizations`, `sharepoint_sites`, `document_libraries`, `source_documents`, `document_versions`, `chunks`, `chunk_embeddings`, `pipeline_definitions`, `ingestion_jobs`, `ingestion_stage_executions`, `processing_errors`, `metadata_rules`, `search_indexes`, `indexing_states`, `audit_logs`, `user_roles`, `document_permissions`, `chunk_permissions`.

Các bảng này không có model, repository, raw SQL hay migration nào trong repo, nên không có consumer. **Không tạo trong baseline CTG.** (`users` và `roles` trong tài liệu trùng tên với bảng ở mục 1 và đã được đánh giá ở đó.) Vì không có `organizations`, các bảng SharePoint hiện tại cũng không phụ thuộc FK vào nó.

## 4. Foreign key impact

| FK | Từ (bảng còn lại) | Tới | Ảnh hưởng |
|---|---|---|---|
| `entity_contexts.entity_id`, `entity_relationships.source/target_entity_id` | GraphRAG | `entities` | Bỏ cùng nhau. Không có bảng ngoài GraphRAG trỏ tới `entities`. |
| `recruitment_campaigns.role_id` | CV (KEEP) | `roles` (REVIEW) | **Rủi ro.** Bỏ `roles` sẽ làm hỏng CV nếu không refactor. |
| `microsoft_accounts.user_id` | PLN | `users` | Giữ hoặc bỏ cùng nhau. |
| `messages.conversation_id`, `conversation_summaries.conversation_id` | CHAT | `conversations` | Giữ hoặc bỏ cùng nhau. |
| `department_sensitivity_permissions.*` | RBAC | `departments`, `position_levels`, `sensitivity_levels` | Bỏ nhóm RBAC không ảnh hưởng `sensitivity_levels`, vì FK chỉ đi một chiều. |
| `tag_role_rules.tag_id/role_id` | RBAC | `tags`, `roles` | Bỏ cùng `tags`. |
| `contract_dashboard`→`contract_raw`, `meeting_transcripts`→`meeting_analyses`, `review_tasks`→`review_jobs`→`ai_models`, `workspace_*`→`workspaces`/`ai_models`/`master_configs`/`data_source_modes`, `master_configs`→`embedding_models` | KEEP | KEEP | Không ảnh hưởng. |

## 5. PostgreSQL extensions

| Extension | Dùng bởi | Quyết định |
|---|---|---|
| `vector` (pgvector) | `entities`, `entity_contexts`, `entity_relationships` (GraphRAG), `recruitment_campaigns.cv_embedding` | Sau khi bỏ GraphRAG, chỉ còn `cv_embedding` (không có writer còn sống). **Nếu bỏ cột này thì không cần pgvector.** |
| `gen_random_uuid()` | Nhiều `server_default` | Có sẵn từ PostgreSQL 13+. Bản cũ hơn cần `pgcrypto`. |

## 6. Vấn đề ORM cần xử lý ở Phase 3

1. `app/models/__init__.py` chỉ import 7 model, nên metadata thiếu phần lớn bảng.
2. `sync_jobs.py` import module không tồn tại; `user_memories.py` không có PK.
3. Trộn `DateTime` naive (conversations, messages, sharepoint_delta_states, conversation_summaries) với `DateTime(timezone=True)`.
4. Nhiều bảng có `created_at`/`updated_at` `nullable=False` nhưng không có default (ai_models, ai_prompts, workspaces, …), nên insert phải tự set giá trị.
5. Các cột `code` (`ai_models`, `ai_prompts`, `workspaces`, `data_source_modes`, `document_types`) không có unique constraint, dù code tra cứu theo `code`.
6. `roles.department_id`/`position_level_id` và `meeting_analyses.model_id` không có FK.
7. Không có migration lịch sử, nên không xác minh được ORM có khớp DB cũ hay không. Baseline CTG sẽ sinh từ ORM đã chuẩn hóa.
