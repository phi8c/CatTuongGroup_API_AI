import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.prompt_code import PromptCode
from app.repositories.ai_prompt_repository import AIPromptRepository
from app.repositories.ai_model_repository import AIModelRepository
from app.services.llm.azure_openai_service import AzureOpenAIService


class MeetingAnalysisService:

    @staticmethod
    async def analyze(
        db: AsyncSession,
        transcript: str,
        model_id: UUID | None = None,
    ) -> dict:

        prompt = await (
            AIPromptRepository
            .get_by_code(
                db=db,
                code=PromptCode.MEETING_SUMMARY,
            )
        )

        if prompt is None:

            raise Exception(
                "Prompt MEETING_SUMMARY not found."
            )

        if model_id is not None:
            model = await AIModelRepository.get_by_id(
                db=db,
                id=model_id,
            )
        else:
            model = await AIModelRepository.get_first_active(db=db)

        if model is None:

            raise LookupError(
                "AI model not found." if model_id is not None
                else "No active AI model found."
            )

        user_prompt_template = (
            prompt.user_prompt
            or "{transcript}"
        )

        if "{transcript}" in user_prompt_template:
            user_prompt = user_prompt_template.replace(
                "{transcript}",
                transcript,
            )
        else:
            user_prompt = (
                f"{user_prompt_template}\n\n"
                f"{transcript}"
            )

        analysis_prompt = (
            f"{prompt.system_prompt}\n\n"
            f"Transcript:\n"
            f"{user_prompt}"
        )

        #
        # CHỖ NÀY gọi đúng method hiện tại
        # của AzureOpenAIService trong project.
        #

        response = await (
            AzureOpenAIService()
            .generate(
                model=model.model_name,
                prompt=analysis_prompt,
                temperature=0.0,
            )
        )

        if isinstance(
            response,
            dict,
        ):
            return response

        content = response.strip()

        if content.startswith(
            "```json"
        ):
            content = content[7:]

        if content.startswith(
            "```"
        ):
            content = content[3:]

        if content.endswith(
            "```"
        ):
            content = content[:-3]

        return json.loads(
            content.strip()
        )
