from uuid import UUID
from typing import AsyncIterator

from app.enums.prompt_code import (
    PromptCode,
)

from app.services.llm.azure_openai_service import (
    get_shared_azure_openai_service,
)

from app.services.session_memory.session_memory_service import (
    SessionMemoryService,
)

from app.services.rag.chat_config_cache import ChatConfigCache


CHAT_MODES = (
    PromptCode.PUBLIC,
    PromptCode.INTERNAL,
    PromptCode.COMBINE,
)

class RagService:

    def __init__(self):

        self.llm = get_shared_azure_openai_service()

    async def ask(
        self,
        db,
        conversation_id: UUID,
        question: str,
        chunks: list,
        model_id: UUID,
        mode: PromptCode,
        workspace_code: str,
    ):

        #
        # Teams bot vẫn dùng history hội thoại
        #

        history = await (
            SessionMemoryService
            .build_context(
                db=db,
                conversation_id=conversation_id,
            )
        )

        chat_config = await self.load_chat_config(
            db=db,
            model_id=model_id,
            mode=mode,
            workspace_code=workspace_code,
        )

        answer = await self.llm.chat(
            model=chat_config["model"],
            messages=self.build_messages(
                chat_config=chat_config,
                question=question,
                chunks=chunks,
                history=history,
            ),
            temperature=chat_config["temperature"],
            max_completion_tokens=chat_config["max_tokens"],
        )

        return answer

    async def ask_stream(
        self,
        chat_config: dict,
        question: str,
        chunks: list,
    ) -> AsyncIterator[str]:

        async for token in self.llm.chat_stream(
            model=chat_config["model"],
            messages=self.build_messages(
                chat_config=chat_config,
                question=question,
                chunks=chunks,
            ),
            temperature=chat_config["temperature"],
            max_completion_tokens=chat_config["max_tokens"],
        ):

            yield token

    async def load_chat_config(
        self,
        db,
        model_id: UUID,
        mode: PromptCode,
        workspace_code: str,
    ) -> dict:

        #
        # Đọc từ cache trong RAM, không chạm DB ở đường nóng.
        # Tham số db giữ lại để không đổi chữ ký hàm.
        #

        if mode not in CHAT_MODES:

            raise ValueError("Invalid chat mode.")

        system_prompt = await ChatConfigCache.lookup(
            "prompts",
            mode.value,
        )

        if system_prompt is None:

            raise LookupError("Prompt not found.")

        model_name = await ChatConfigCache.lookup(
            "models",
            str(model_id),
        )

        if model_name is None:

            raise LookupError(
                "AI Model not found."
            )

        model_config = await ChatConfigCache.lookup(
            "model_configs",
            workspace_code,
        )

        if model_config is None:

            raise LookupError(
                "Model config not found."
            )

        return {
            "model": model_name,
            "system_prompt": system_prompt,
            "temperature": model_config["temperature"],
            "max_tokens": model_config["max_tokens"],
        }

    @staticmethod
    def build_messages(
        chat_config: dict,
        question: str,
        chunks: list,
        history: str = "",
    ) -> list[dict]:

        context = "\n\n".join(
            chunk["content"]
            for chunk in chunks
            if chunk.get("content")
        )

        system_prompt = (
            chat_config["system_prompt"]
            .replace(
                "{{history}}",
                history or "",
            )
            .replace(
                "{{context}}",
                context,
            )
            .replace(
                "{{question}}",
                question,
            )
        )

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ]
