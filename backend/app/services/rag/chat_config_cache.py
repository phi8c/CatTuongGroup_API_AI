import asyncio
import time

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.ai_model import AIModel
from app.models.ai_prompt import AIPrompt
from app.models.workspace import Workspace
from app.models.workspace_model_config import WorkspaceModelConfig
from app.models.workspace_rag_config import WorkspaceRagConfig


class ChatConfigCache:
    """
    Cache trong RAM cho cấu hình chat (prompt, model, temperature,
    max_tokens, top_k) để request chat không phải đọc DB.

    - Lần đầu: load đồng bộ.
    - Hết TTL: vẫn trả dữ liệu cũ, refresh ngầm ở background.
    - Không thấy model/prompt/workspace: refresh ngay 1 lần rồi tra lại.
    """

    TTL_SECONDS = 60

    # Không refresh dồn dập khi client gửi model_id/mode không tồn tại
    MIN_REFRESH_SECONDS = 5

    _data: dict | None = None

    _loaded_at = 0.0

    _lock: asyncio.Lock | None = None

    _refresh_task: asyncio.Task | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:

        if cls._lock is None:

            cls._lock = asyncio.Lock()

        return cls._lock

    @classmethod
    async def get(cls) -> dict:

        if cls._data is None:

            await cls.refresh()

        elif time.monotonic() - cls._loaded_at > cls.TTL_SECONDS:

            cls._schedule_refresh()

        return cls._data

    @classmethod
    def _schedule_refresh(cls):

        if cls._refresh_task is not None and not cls._refresh_task.done():

            return

        cls._refresh_task = asyncio.create_task(
            cls._refresh_in_background()
        )

    @classmethod
    async def _refresh_in_background(cls):

        try:

            await cls.refresh()

        except Exception as exc:

            print(
                "chat config refresh error =",
                repr(exc),
            )

    @classmethod
    async def refresh(cls):

        async with cls._get_lock():

            #
            # Request khác vừa load xong trong lúc chờ lock
            #

            if (
                cls._data is not None
                and time.monotonic() - cls._loaded_at < cls.MIN_REFRESH_SECONDS
            ):

                return

            cls._data = await cls._load()

            cls._loaded_at = time.monotonic()

    @classmethod
    def invalidate(cls):

        cls._data = None

        cls._loaded_at = 0.0

    @staticmethod
    async def _load() -> dict:

        async with AsyncSessionLocal() as db:

            prompts = (
                await db.execute(
                    select(
                        AIPrompt.code,
                        AIPrompt.system_prompt,
                    )
                    .where(
                        AIPrompt.is_active == True,
                    )
                )
            ).all()

            models = (
                await db.execute(
                    select(
                        AIModel.id,
                        AIModel.model_name,
                    )
                )
            ).all()

            model_configs = (
                await db.execute(
                    select(
                        Workspace.code,
                        WorkspaceModelConfig.temperature,
                        WorkspaceModelConfig.max_tokens,
                    )
                    .join(
                        WorkspaceModelConfig,
                        WorkspaceModelConfig.workspace_id == Workspace.id,
                    )
                )
            ).all()

            rag_configs = (
                await db.execute(
                    select(
                        Workspace.code,
                        WorkspaceRagConfig.top_k,
                    )
                    .join(
                        WorkspaceRagConfig,
                        WorkspaceRagConfig.workspace_id == Workspace.id,
                    )
                )
            ).all()

        return {
            "prompts": {
                code: system_prompt
                for code, system_prompt in prompts
            },
            "models": {
                str(model_id): model_name
                for model_id, model_name in models
            },
            "model_configs": {
                code: {
                    "temperature": float(temperature),
                    "max_tokens": int(max_tokens),
                }
                for code, temperature, max_tokens in model_configs
            },
            "top_k": {
                code: top_k
                for code, top_k in rag_configs
            },
        }

    @classmethod
    async def lookup(
        cls,
        section: str,
        key: str,
    ):

        value = (await cls.get())[section].get(key)

        if value is None:

            #
            # Có thể vừa được thêm qua API quản trị
            #

            await cls.refresh()

            value = cls._data[section].get(key)

        return value

    @classmethod
    async def get_top_k(
        cls,
        workspace_code: str,
    ) -> int | None:

        return (await cls.get())["top_k"].get(workspace_code)
