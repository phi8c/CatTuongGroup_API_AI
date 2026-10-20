-- CTG AI: fresh database schema generated offline from current ORM.

-- Contains no data or credentials. Not a migration for an existing database.

-- Historical ctg_init.sql / ctg_01_schema.sql are pre-cleanup snapshots.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE departments (
	id SERIAL NOT NULL, 
	name VARCHAR(50), 
	PRIMARY KEY (id)
);

CREATE TABLE position_levels (
	id SERIAL NOT NULL, 
	name VARCHAR(50), 
	priority INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE roles (
	id SERIAL NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR, 
	department_id INTEGER, 
	position_level_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE sensitivity_levels (
	id SERIAL NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	is_sensitive BOOLEAN NOT NULL, 
	priority INTEGER, 
	description TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE conversations (
	id UUID NOT NULL, 
	user_email VARCHAR(50), 
	title VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE ai_models (
	id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	model_name VARCHAR(150) NOT NULL, 
	display_name VARCHAR(150) NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE ai_prompts (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	system_prompt TEXT NOT NULL, 
	user_prompt TEXT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE contract_raw (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	contract_name VARCHAR(255) NOT NULL, 
	source_file VARCHAR(500) NOT NULL, 
	file_hash VARCHAR(255) NOT NULL, 
	extracted_content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE data_source_modes (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE document_types (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE embedding_models (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	model_name VARCHAR(255) NOT NULL, 
	provider VARCHAR(100) NOT NULL, 
	dimension INTEGER NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE executive_data_raw (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	dataset_name VARCHAR(255) NOT NULL, 
	source_file VARCHAR(500) NOT NULL, 
	sharepoint_site_id TEXT NOT NULL, 
	sharepoint_drive_id TEXT NOT NULL, 
	sharepoint_item_id TEXT NOT NULL, 
	last_modified TIMESTAMP WITH TIME ZONE, 
	file_hash VARCHAR(255) NOT NULL, 
	report_data JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE meeting_analyses (
	id UUID NOT NULL, 
	event_id TEXT NOT NULL, 
	online_meeting_id TEXT, 
	subject VARCHAR(500), 
	body_preview TEXT, 
	description TEXT, 
	organizer_name VARCHAR(255), 
	organizer_email VARCHAR(320), 
	start_time TIMESTAMP WITH TIME ZONE, 
	end_time TIMESTAMP WITH TIME ZONE, 
	location VARCHAR(500), 
	web_link TEXT, 
	join_url TEXT, 
	online_meeting_provider VARCHAR(100), 
	attendees JSON, 
	raw_data JSON, 
	has_transcript BOOLEAN NOT NULL, 
	analysis_status VARCHAR(50) NOT NULL, 
	summary TEXT, 
	key_points JSON, 
	decisions JSON, 
	action_items JSON, 
	risks JSON, 
	unresolved_issues JSON, 
	model_id UUID, 
	analyzed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_meeting_analyses_online_meeting_id ON meeting_analyses (online_meeting_id);

CREATE INDEX ix_meeting_analyses_end_time ON meeting_analyses (end_time);

CREATE UNIQUE INDEX ix_meeting_analyses_event_id ON meeting_analyses (event_id);

CREATE TABLE project_tracking_raw (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	project_code VARCHAR(100) NOT NULL, 
	project_name VARCHAR(255) NOT NULL, 
	sharepoint_site_id TEXT NOT NULL, 
	sharepoint_drive_id TEXT NOT NULL, 
	sharepoint_item_id TEXT NOT NULL, 
	source_file VARCHAR(500) NOT NULL, 
	last_modified TIMESTAMP WITH TIME ZONE, 
	project_hash VARCHAR(255) NOT NULL, 
	project_data JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_code)
);

CREATE TABLE sharepoint_delta_states (
	site_id VARCHAR(255) NOT NULL, 
	drive_id VARCHAR(255) NOT NULL, 
	delta_link TEXT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (site_id, drive_id)
);

CREATE TABLE sync_jobs (
	id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE tags (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR, 
	sensitivity_level INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE workspaces (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	workspace_name VARCHAR(255) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE department_sensitivity_permissions (
	id SERIAL NOT NULL, 
	owner_department_id INTEGER NOT NULL, 
	viewer_department_id INTEGER NOT NULL, 
	max_sensitivity_id INTEGER NOT NULL, 
	position_level_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_department_id) REFERENCES departments (id), 
	FOREIGN KEY(viewer_department_id) REFERENCES departments (id), 
	FOREIGN KEY(max_sensitivity_id) REFERENCES sensitivity_levels (id), 
	FOREIGN KEY(position_level_id) REFERENCES position_levels (id)
);

CREATE TABLE messages (
	id UUID NOT NULL, 
	conversation_id UUID NOT NULL, 
	role VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE TABLE contract_dashboard (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	contract_id UUID NOT NULL, 
	summary TEXT NOT NULL, 
	clauses JSONB NOT NULL, 
	analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (contract_id), 
	FOREIGN KEY(contract_id) REFERENCES contract_raw (id) ON DELETE CASCADE
);

CREATE TABLE conversation_summaries (
	id UUID NOT NULL, 
	conversation_id UUID NOT NULL, 
	summary TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_processed_message_count INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (conversation_id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE TABLE executive_data_dashboard (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	dataset_id UUID NOT NULL, 
	summary TEXT NOT NULL, 
	analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (dataset_id), 
	FOREIGN KEY(dataset_id) REFERENCES executive_data_raw (id) ON DELETE CASCADE
);

CREATE TABLE master_configs (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	embedding_model_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(embedding_model_id) REFERENCES embedding_models (id)
);

CREATE TABLE meeting_transcripts (
	id UUID NOT NULL, 
	meeting_id UUID NOT NULL, 
	transcript_id TEXT NOT NULL, 
	content TEXT, 
	content_type TEXT, 
	created_at_graph TIMESTAMP WITH TIME ZONE, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(meeting_id) REFERENCES meeting_analyses (id)
);

CREATE INDEX ix_meeting_transcripts_meeting_id ON meeting_transcripts (meeting_id);

CREATE UNIQUE INDEX ix_meeting_transcripts_transcript_id ON meeting_transcripts (transcript_id);

CREATE TABLE project_tracking_dashboard (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	project_code VARCHAR(100) NOT NULL, 
	summary TEXT NOT NULL, 
	overall_health_status VARCHAR(20) NOT NULL, 
	overall_health_title VARCHAR(255) NOT NULL, 
	progress_status VARCHAR(20) NOT NULL, 
	progress_title VARCHAR(255) NOT NULL, 
	budget_status VARCHAR(20) NOT NULL, 
	budget_title VARCHAR(255) NOT NULL, 
	risk_count INTEGER NOT NULL, 
	risk_total INTEGER NOT NULL, 
	task_analysis JSONB NOT NULL, 
	analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_code), 
	FOREIGN KEY(project_code) REFERENCES project_tracking_raw (project_code) ON DELETE CASCADE
);

CREATE TABLE recruitment_campaigns (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	role_id INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	job_description TEXT NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	cv_embedding VECTOR(1536), 
	cv_data JSONB NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE review_jobs (
	id UUID NOT NULL, 
	model_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	total_files INTEGER NOT NULL, 
	created_by UUID, 
	job_description TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(model_id) REFERENCES ai_models (id)
);

CREATE TABLE tag_role_rules (
	id SERIAL NOT NULL, 
	tag_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE workspace_model_configs (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id UUID NOT NULL, 
	model_id UUID NOT NULL, 
	temperature NUMERIC(3, 2) NOT NULL, 
	max_tokens INTEGER NOT NULL, 
	mcp_tool VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_id) REFERENCES ai_models (id)
);

CREATE TABLE workspace_source_configs (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id UUID NOT NULL, 
	data_source_mode_id UUID NOT NULL, 
	allow_user_override BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(data_source_mode_id) REFERENCES data_source_modes (id)
);

CREATE TABLE recruitment_candidates (
	id UUID NOT NULL, 
	campaign_id UUID NOT NULL, 
	candidate_name VARCHAR(255), 
	file_name VARCHAR(255) NOT NULL, 
	file_path TEXT NOT NULL, 
	file_size BIGINT, 
	mime_type VARCHAR(100), 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(campaign_id) REFERENCES recruitment_campaigns (id)
);

CREATE TABLE review_tasks (
	id UUID NOT NULL, 
	job_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	file_name VARCHAR(500) NOT NULL, 
	file_path TEXT NOT NULL, 
	file_size BIGINT NOT NULL, 
	mime_type VARCHAR(100) NOT NULL, 
	retry_count INTEGER NOT NULL, 
	review_result JSONB, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES review_jobs (id)
);

CREATE TABLE workspace_rag_configs (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	workspace_id UUID NOT NULL, 
	master_config_id UUID NOT NULL, 
	data_source TEXT NOT NULL, 
	chunking_strategy VARCHAR(255) NOT NULL, 
	top_k INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(master_config_id) REFERENCES master_configs (id)
);

CREATE TABLE recruitment_candidate_results (
	id UUID NOT NULL, 
	candidate_id UUID NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	score NUMERIC(5, 2) NOT NULL, 
	summary TEXT, 
	strengths JSONB, 
	weaknesses JSONB, 
	assessment TEXT, 
	reason TEXT, 
	raw_response JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES recruitment_candidates (id)
);

COMMIT;
