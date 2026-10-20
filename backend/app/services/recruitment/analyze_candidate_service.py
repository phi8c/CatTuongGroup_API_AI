import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.not_found_exception import (
    NotFoundException,
)

from app.enums.prompt_code import (
    PromptCode,
)

from app.repositories.ai_model_repository import (
    AIModelRepository,
)

from app.repositories.ai_prompt_repository import (
    AIPromptRepository,
)

from app.repositories.recruitment_campaign_repository import (
    RecruitmentCampaignRepository,
)

from app.repositories.recruitment_candidate_repository import (
    RecruitmentCandidateRepository,
)

from app.repositories.recruitment_candidate_result_repository import (
    RecruitmentCandidateResultRepository,
)

from app.services.llm.azure_openai_service import (
    AzureOpenAIService,
)

from app.services.prompt.prompt_builder_azure import (
    PromptBuilderAzure,
)

from app.utils.extract.document_intelligent import (
    DocumentExtractor,
)

from app.utils.storage.supabase_storage import (
    SupabaseStorage,
)
from app.repositories.rag_config_repository import WorkspaceConfigRepository


class AnalyzeCandidateService:

    @staticmethod
    async def execute(
        db: AsyncSession,
        candidate_id: UUID,
        model_id: UUID,
    ):

        candidate = await RecruitmentCandidateRepository.get_by_id(
            db=db,
            id=candidate_id,
        )

        if candidate is None:
            raise NotFoundException(
                "Candidate not found."
            )

        campaign = await RecruitmentCampaignRepository.get_by_id(
            db=db,
            id=candidate.campaign_id,
        )

        if campaign is None:
            raise NotFoundException(
                "Campaign not found."
            )

        prompt = await AIPromptRepository.get_by_code(
            db=db,
            code=PromptCode.RECRUITMENT_DEFAULT,
        )

        if prompt is None:
            raise NotFoundException(
                "Prompt not found."
            )

        model = await AIModelRepository.get_by_id(
            db=db,
            id=model_id,
        )

        if model is None:
            raise NotFoundException(
                "Model not found."
            )

        existed = await RecruitmentCandidateResultRepository.get_by_candidate(
            db=db,
            candidate_id=candidate.id,
        )

        if existed is not None:
            return existed

        local_file = await SupabaseStorage.download_to_temp_file(
            candidate.file_path,
        )

        try:

            extraction = DocumentExtractor.extract(
                local_file,
            )

            system_prompt, user_prompt = PromptBuilderAzure.build(
                system_prompt=prompt.system_prompt,
                variables={
                    "job_description": campaign.job_description,
                    "cv_text": extraction.text,
                },
            )

            ai = AzureOpenAIService()
            
            
            
            workspace_code = PromptCode.EXECUTIVE_DATA.value
                            
            model_config = await (
                WorkspaceConfigRepository
                .get_model_config_by_workspace_code(
                    
                                    db=db,
                    
                                    workspace_code=
                                    workspace_code,
                    
                                )
                            )
                            
            temperature = float(
                    model_config.temperature
                )
            
            max_tokens = int(
                    model_config.max_tokens
                )
            max_tokens = model_config.max_tokens
            

            result = await ai.chat(
                model=model.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                
                temperature=temperature,
                max_completion_tokens=max_tokens
            )

            try:
                result_json = json.loads(result)
            except json.JSONDecodeError as ex:
                raise ValueError(
                    "Azure OpenAI did not return valid JSON."
                ) from ex

            return await RecruitmentCandidateResultRepository.create(
                db=db,
                candidate_id=candidate.id,
                model=model.model_name,
                score=result_json["score"],
                summary=result_json.get("summary"),
                strengths=result_json.get("strengths"),
                weaknesses=result_json.get("weaknesses"),
                assessment=result_json.get("assessment"),
                reason=result_json.get("reason"),
                raw_response=result_json,
            )

        finally:

            Path(
                local_file
            ).unlink(
                missing_ok=True,
            )