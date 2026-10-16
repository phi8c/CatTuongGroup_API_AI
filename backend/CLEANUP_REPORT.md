# CTG AI backend cleanup report

Scope: `D:/ctg_api_ai` only. No changes were applied to `D:/azure_auto`.
No database connection, SQL execution, Azure index update, commit, or push was performed.
Existing user changes to `.gitignore`, `pass_db.txt`, and the exporter were preserved.

## Removed source files

- `backend/app/api/dependencies/auth.py`
- `backend/app/api/v1/auth_router.py`
- `backend/app/api/v1/bot_router.py`
- `backend/app/api/v1/department_route.py`
- `backend/app/api/v1/permission_router.py`
- `backend/app/api/v1/planner_router.py`
- `backend/app/api/v1/policy_router.py`
- `backend/app/api/v1/role_router.py`
- `backend/app/api/v1/tag_role_rule_router.py`
- `backend/app/api/v1/tag_router.py`
- `backend/app/models/identity.py`
- `backend/app/models/microsoft_account.py`
- `backend/app/models/user_memories.py`
- `backend/app/models/user_model.py`
- `backend/app/prompts/semantic_tagging_prompt.py`
- `backend/app/repositories/department_repository.py`
- `backend/app/repositories/executive_data_repository.py`
- `backend/app/repositories/microsoft_account_repository.py`
- `backend/app/repositories/permission_repository.py`
- `backend/app/repositories/tag_repository.py`
- `backend/app/repositories/tag_role_rule_repository.py`
- `backend/app/repositories/test_cohere.py`
- `backend/app/repositories/test_gg_api.py`
- `backend/app/repositories/user_memory_repository.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/department.py`
- `backend/app/schemas/execute_schema.py`
- `backend/app/schemas/microsoft_profile.py`
- `backend/app/schemas/permission_request.py`
- `backend/app/schemas/policy_schema.py`
- `backend/app/schemas/role_schema.py`
- `backend/app/schemas/tag_role_rule_schema.py`
- `backend/app/schemas/tag_schema.py`
- `backend/app/services/auth/auth_service.py`
- `backend/app/services/bot/teams_bot_service.py`
- `backend/app/services/department/department_service.py`
- `backend/app/services/google/google_calendar_service.py`
- `backend/app/services/govern/azure_executive_data_service.py`
- `backend/app/services/govern/executive_data_ai_service.py`
- `backend/app/services/govern/executive_data_reader_service.py`
- `backend/app/services/govern/executive_data_sync_service.py`
- `backend/app/services/identity/cache_service.py`
- `backend/app/services/identity/graph_service.py`
- `backend/app/services/identity/identity_service.py`
- `backend/app/services/ingestion/semantic_tagger.py`
- `backend/app/services/jwt/jwt_service.py`
- `backend/app/services/llm/llm_factory.py`
- `backend/app/services/llm/ollama_service.py`
- `backend/app/services/microsoft/microsoft_auth_service.py`
- `backend/app/services/microsoft/planner_service.py`
- `backend/app/services/permission/permission_service.py`
- `backend/app/services/policy/policy_engine.py`
- `backend/app/services/session_memory/conversation_summary_service.py`
- `backend/app/workers/executive_data_worker.py`
- `backend/teams-package/color.png`
- `backend/teams-package/manifest.json`
- `backend/teams-package/outline.png`
- `backend/teams-package/teams-package.zip`

## Modified existing files

- `backend/app/api/v1/chat_router.py`
- `backend/app/api/v1/document_router.py`
- `backend/app/core/settings.py`
- `backend/app/main.py`
- `backend/app/models/sync_jobs.py`
- `backend/app/services/ingestion/sensitivity_classifier.py`
- `backend/app/services/task/tracking_task_service.py`
- `backend/requirements.lock.txt`
- `backend/scripts/build_ctg_init_sql.py`
- `backend/tests/api/test_contract_router.py`

Changes: unregister retired routers; remove executive governance endpoints from
the shared document router; remove unused Ollama imports and the uncalled local
summary service; retain the active chat history flow; remove obsolete config;
fix the pre-existing invalid SyncJob Base import; keep all other table definitions.
The SSE test now consumes the lazy stream while its mock is still active.

## Added files

- `tests/api/test_ai_backend_cleanup.py`: startup/OpenAPI and permission contract smoke tests.
- `scripts/build_ai_schema.py`: generate fresh schema using SQLAlchemy mock engine, offline.
- `database/ctg_ai_schema.sql`: fresh ORM schema, no user tables, no data or credentials.
- `docs/cleanup_dependency_graph.json`: per-module internal dependency graph.
- `CLEANUP_REPORT.md`: this report.

## Removed dependency pins

- `bcrypt==5.0.0`
- `botbuilder-core==4.17.1`
- `botbuilder-integration-aiohttp==4.17.1`
- `botbuilder-schema==4.17.1`
- `botframework-connector==4.17.1`
- `botframework-streaming==4.17.1`
- `cohere==7.0.4`
- `microsoft-agents-activity==1.1.0`
- `microsoft-agents-copilotstudio-client==1.1.0`
- `microsoft-agents-hosting-core==1.1.0`
- `passlib==1.7.4`
- `python-jose==3.5.0`

Shared Google GenAI, OpenAI, Groq, Azure SDKs, Supabase, Docling, and related
transitive dependencies remain. Query rewrite still uses cloud providers.
PyJWT and cryptography pins remain because shared packages can depend on them;
there is no internal JWT login/current-user dependency left in the chat APIs.
The existing environment was not reinstalled or upgraded.

## Removed ORM models

- `User` -> `users`.
- `MicrosoftAccount` -> `microsoft_accounts`: delegated login/Planner consumer removed.
- `UserMemory` -> `user_memories`: unused user-management code, had no primary key.
- `UserIdentity` was a plain DTO, not a SQLAlchemy table.

No live tables were dropped. No other existing table schema was removed.
`user_roles` and `ingestion_jobs` have no ORM or runtime SQL consumer in this repo.
The exporter now excludes users/user_roles and omits ingestion_jobs.triggered_by,
its constraints/indexes, and FKs to the excluded user tables. The exporter was NOT run.

## Tables still represented by ORM

This is the complete retained model table inventory, including dormant legacy definitions.

| Table | Outgoing FK targets |
|---|---|
| `ai_models` | none |
| `ai_prompts` | none |
| `contract_dashboard` | contract_raw.id |
| `contract_raw` | none |
| `conversation_summaries` | conversations.id |
| `conversations` | none |
| `data_source_modes` | none |
| `department_sensitivity_permissions` | departments.id, departments.id, position_levels.id, sensitivity_levels.id |
| `departments` | none |
| `document_types` | none |
| `embedding_models` | none |
| `executive_data_dashboard` | executive_data_raw.id |
| `executive_data_raw` | none |
| `master_configs` | embedding_models.id |
| `meeting_analyses` | none |
| `meeting_transcripts` | meeting_analyses.id |
| `messages` | conversations.id |
| `position_levels` | none |
| `project_tracking_dashboard` | project_tracking_raw.project_code |
| `project_tracking_raw` | none |
| `recruitment_campaigns` | roles.id |
| `recruitment_candidate_results` | recruitment_candidates.id |
| `recruitment_candidates` | recruitment_campaigns.id |
| `review_jobs` | ai_models.id |
| `review_tasks` | review_jobs.id |
| `roles` | none |
| `sensitivity_levels` | none |
| `sharepoint_delta_states` | none |
| `sync_jobs` | none |
| `tag_role_rules` | roles.id, tags.id |
| `tags` | none |
| `workspace_model_configs` | ai_models.id, workspaces.id |
| `workspace_rag_configs` | master_configs.id, workspaces.id |
| `workspace_source_configs` | data_source_modes.id, workspaces.id |
| `workspaces` | none |

Runtime repositories continue to serve AI model/prompt/workspace configuration,
contract review, recruitment/CV, meetings, chat history, project tracking, and SharePoint delta.
Chunks/ACL/vector retrieval remain in Azure AI Search; legal_documents/legal_search
remain in DuckDB. This cleanup does not create or alter their schemas.

## Additional tables to review, not deleted

| Table | Reason and FK impact |
|---|---|
| microsoft_accounts | Old SSO/Planner token storage; historical dump has user_id -> users.id. Runtime model removed. |
| user_memories | No active consumers; runtime model removed; no outgoing FK declared. |
| tags | Retired semantic governance; inbound FK from tag_role_rules.tag_id. |
| tag_role_rules | Retired mapping; outgoing FK -> tags.id, roles.id. |
| department_sensitivity_permissions | Retired RBAC; outgoing FK -> departments.id (owner/viewer), position_levels.id, sensitivity_levels.id. |
| departments | Old RBAC metadata; inbound FK from department_sensitivity_permissions (two columns). |
| position_levels | Old RBAC metadata; inbound FK from department_sensitivity_permissions.position_level_id. |
| executive_data_raw | Retired governance; inbound FK from executive_data_dashboard.dataset_id. |
| executive_data_dashboard | Retired governance; outgoing FK -> executive_data_raw.id. |
| sync_jobs | Legacy uncalled job service; no outgoing/incoming FK in retained models. |

`roles` must stay: recruitment_campaigns.role_id references roles.id.
`sensitivity_levels` must stay: the post-ingestion sensitivity classifier still reads it.
Project tracking remains because its AI endpoints are outside the explicitly retired features.

The following requested protected ingestion tables have no models or runtime SQL
in this CTG repo: organizations, sharepoint_sites, document_libraries, source_documents,
document_versions, chunks, chunk_embeddings, document_permissions, chunk_permissions,
pipeline_definitions, ingestion_jobs, ingestion_stage_executions, processing_errors,
metadata_rules, search_indexes, indexing_states, audit_logs. No changes were made to them.

## Configuration retained for compatibility

EXECUTIVE_DATA_MODEL_ID remains because Meeting Analysis still uses it as fallback.
GEMINI_API_KEY/GOOGLE_API_KEY remain for cloud AI code; Google OAuth/calendar is removed.
Azure tenant/client credentials remain for application-level SharePoint/Graph access.
The .env file was not edited; obsolete keys there are ignored by Settings(extra='ignore').

## Validation

- 46 unittest tests passed, including the two new smoke tests.
- FastAPI TestClient startup and OpenAPI: 66 paths; key AI and ingestion endpoints present.
- Request validation for both Chat APIs: 422 for empty requests, expected.
- AST syntax and internal import graph: no missing modules.
- All retained ORM modules import, configure_mappers and sorted_tables succeed (35 tables).
- No runtime references to the removed local users/user_roles tables.
- Microsoft Graph /users/{id} URLs are intentionally retained (external Graph, not local DB).
- Full internal dependency graph is in docs/cleanup_dependency_graph.json.
- Protected retrieval/chat schema/RAG/query rewrite/meeting analysis files match HEAD.

## Outstanding items

1. Historical database/ctg_init.sql, ctg_01_schema.sql, and ctg_02_data_part*.sql
   remain unchanged and can still contain users and the Microsoft-account FK/data.
   Automatic approval review rejected modifying these data dumps. Do not treat them
   as post-cleanup init scripts. Use ctg_ai_schema.sql for an EMPTY database schema,
   or review a new export separately. The new schema contains no configuration seeds.
2. No Alembic migration history exists. The fresh schema is generated from ORM;
   it does not claim byte-for-byte compatibility with the previous database dump.
3. Actual Azure/Graph/LLM calls and database integration were not exercised.
4. A clean dependency installation was not performed; the existing venv ran the tests.
5. Dormant legacy ORM definitions stay until a separate table-removal decision.

## Recovery

Every modified/deleted pre-existing file was backed up before editing under:
`C:/Users/admin/AppData/Local/Temp/ctg-cleanup-originals-20261016`.
The four Teams bot assets were moved there and can be restored.


All-module import errors: `[]`.
