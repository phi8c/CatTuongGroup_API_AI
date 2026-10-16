
import asyncio
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.chunk_router import router as chunk_router
from app.api.v1.chat_router import router as chat_router
from app.api.v1.conversation_router import router as conversation
from app.api.v1.document_router import router as document_router
from app.api.v1.recruitment_candidate_router import (
    router as recruitment_candidate_router,
)
from app.api.v1.model_router import router as model_router
from app.api.v1.prompt_router import router as prompt_router
from app.api.v1.contract_router import router as contract_router
from app.api.v1.workspace_source_config_router import (
    router as workspace_source_config_router,
)
from app.api.v1.rag_config_router import router as rag_config_router
from app.api.v1.meeting_router import router as meeting_router

from app.services.azure.azure_search_service import AzureSearchService
from app.services.rag.chat_config_cache import ChatConfigCache
from app.services.llm.azure_openai_service import (
    get_shared_azure_openai_service,
)


app = FastAPI(
    root_path="/api",
    title="chatrag",
    version="1.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []

    for error in exc.errors():
        sanitized_error = dict(error)
        sanitized_error.pop("input", None)
        errors.append(sanitized_error)

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


async def warm_up_chat():
    try:
        await ChatConfigCache.refresh()
        await AzureSearchService.warm_up()

        await get_shared_azure_openai_service()._client.models.list()

        print("chat warm up done")

    except Exception as exc:
        print("chat warm up error =", repr(exc))


@app.on_event("startup")
async def start_chat_warm_up():
    enabled = os.getenv(
        "CHAT_WARMUP_ENABLED",
        "false",
    ).lower() in ("true", "1", "yes")

    if enabled:
        asyncio.create_task(warm_up_chat())


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chunk_router)
app.include_router(chat_router)
app.include_router(conversation)
app.include_router(document_router)
app.include_router(recruitment_candidate_router)
app.include_router(model_router)
app.include_router(prompt_router)
app.include_router(contract_router)
app.include_router(workspace_source_config_router)
app.include_router(rag_config_router)
app.include_router(meeting_router)
