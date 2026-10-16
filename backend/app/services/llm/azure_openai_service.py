from typing import Any, AsyncIterator

from openai import AsyncAzureOpenAI

from app.core.settings import settings


class LLMResponseTruncatedError(ValueError):
    pass


class AzureOpenAIService:

    def __init__(self) -> None:

        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT.strip(),
            api_key=settings.AZURE_OPENAI_API_KEY.strip(),
            api_version=settings.AZURE_OPENAI_API_VERSION.strip(),
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_completion_tokens: int = 2000,
    ) -> str:
        
        
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens
        )

        return (
            response
            .choices[0]
            .message.content
            or ""
        )

    async def chat_json(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_completion_tokens: int = 2000,
    ) -> str:

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            response_format={
                "type": "json_object",
            },
        )

        choice = response.choices[0]

        if choice.finish_reason == "length":
            raise LLMResponseTruncatedError(
                "LLM JSON response reached the output token limit."
            )

        return choice.message.content or ""

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_completion_tokens: int = 2000,
    ) -> AsyncIterator[str]:

        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            stream=True,
        )

        async for chunk in stream:

            if not chunk.choices:
                continue

            content = (
                chunk
                .choices[0]
                .delta
                .content
            )

            if content:
                yield content
        
    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.0,
    ) -> str:

        response = await self._client.chat.completions.create(

            model=model,

            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            temperature=temperature,

        )

        return (
            response
            .choices[0]
            .message.content
            or ""
        )


#
# Dùng chung 1 client (connection pool) cho mọi request chat
#

_shared_service: AzureOpenAIService | None = None


def get_shared_azure_openai_service() -> AzureOpenAIService:

    global _shared_service

    if _shared_service is None:

        _shared_service = AzureOpenAIService()

    return _shared_service
