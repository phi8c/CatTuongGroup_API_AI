# Local startup without real credentials

Use Python 3.12. From the backend directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CTG_ENV_FILE = ".env.example"
.\.venv\Scripts\python.exe run_server.py
```

Open http://127.0.0.1:18080/docs (or /openapi.json).
`.env.dummy` can also be selected with CTG_ENV_FILE.
The selection applies to both run_server.py and direct uvicorn startup.
Relative CTG_ENV_FILE paths are resolved against backend, regardless of the current directory.
Without CTG_ENV_FILE the order is .env, .env.example, then .env.dummy.
An explicitly selected missing file raises a clear error instead of using another file.
Existing process environment variables take precedence over env-file values.
CHAT_WARMUP_ENABLED=false in both templates prevents startup network calls.

The templates allow startup and API documentation without a database, Azure or Supabase.
Operations that read/write those services still need real configuration; they do not return simulated success.
Local legal analysis also needs the DuckDB dataset and FTS setup described by scripts/setup_local_legal_db.py.
Runtime upload directories are created by the application when needed.

Keep .env, pass_db.txt, data dumps, uploads, local databases and virtual environments out of Git.
The source directory app/services/temp must be committed: it contains TempFileService,
which is imported by the review API. It is separate from the runtime /temp directory.
.env.dummy and database/ctg_ai_schema.sql are public templates/schema and may be committed.
The historical database dumps remain ignored.

Verification (also run by the Windows build workflow):

```powershell
$env:CTG_ENV_FILE = ".env.example"
.\.venv\Scripts\python.exe -m unittest tests.api.test_local_startup
```

This test copies only source and templates into a temporary checkout without local data or
bytecode, blocks network connections, and checks startup and OpenAPI with each template.

## Windows executable from GitHub Actions

Push a backend/workflow change or run Build CTG AI Backend Windows manually.
The workflow installs dependencies in a clean Python 3.12 environment, runs startup tests,
builds the executable, creates the ZIP, extracts it into a separate folder, and starts
that exact packaged executable with automatic env selection and each public template.
The build artifact is uploaded only after OpenAPI and /docs respond successfully.
Failure logs are uploaded as CTG-build-diagnostics.

Extract the entire CTG-AI-Backend-Windows.zip and run AIBackend/AIBackend.exe.
Keep the _internal directory and .env.example next to the executable.
Python does not need to be installed on the target Windows x64 machine.
The packaged application starts using .env.example without real credentials.
For real services copy .env.example to .env next to AIBackend.exe and fill in the values.
Remove CTG_ENV_FILE from the process environment to let .env take precedence.
Startup validation does not validate actual Azure, SharePoint, Supabase or database operations.
