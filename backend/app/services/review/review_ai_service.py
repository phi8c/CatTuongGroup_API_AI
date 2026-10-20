import json
from dataclasses import dataclass
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
from app.services.llm.azure_openai_service import (
    AzureOpenAIService,
)
from app.services.prompt.prompt_builder_azure import (
    PromptBuilderAzure,
)

from app.utils.extract.document_intelligent import (
    DocumentExtractor,
)



from app.repositories.rag_config_repository import WorkspaceConfigRepository




@dataclass(slots=True)
class ReviewAIResult:

    review_result: dict

    extraction: dict[str, str]


class ReviewAIService:

    @staticmethod
    def _build_extraction_response(
        extraction,
    ) -> dict[str, str]:

        return {
            "text": extraction.text,
        }

    @staticmethod
    async def execute(
        db: AsyncSession,
        model_id: UUID,
        file_path: str,
        job_description: str,
       
        prompt_code: PromptCode = (
            PromptCode.RECRUITMENT_DEFAULT
        ),
    ) -> ReviewAIResult:

        prompt = await (
            AIPromptRepository.get_by_code(
                db=db,
                code=prompt_code,
            )
        )

        if prompt is None:

            raise NotFoundException(
                "Prompt not found.",
            )

        model = await (
            AIModelRepository.get_by_id(
                db=db,
                id=model_id,
            )
        )

        if model is None:

            raise NotFoundException(
                "Model not found.",
            )

        extraction = (
            DocumentExtractor.extract(
                file_path,
            )
        )

        print("=" * 80)
        print(extraction.text[:1000])
        print("=" * 80)

        built_prompt = (
            PromptBuilderAzure.build(
                prompt=prompt.system_prompt,
                cv_text=extraction.text,
                job_description=job_description,
               
            )
        )
        
        

        print("=" * 80)
        print(built_prompt)
        print("=" * 80)

        ai = AzureOpenAIService()
        
        workspace_code = PromptCode.REVIEW_CV.value
                        
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
        

        result = await ai.chat(
            model=model.model_name,
            messages=[
                {
                    "role": "user",
                    "content": built_prompt,
                },
            ],
            temperature=temperature,
            max_completion_tokens=max_tokens
        )

        try:

            return ReviewAIResult(
                review_result=json.loads(
                    result,
                ),
                extraction=ReviewAIService._build_extraction_response(
                    extraction,
                ),
            )

        except json.JSONDecodeError as ex:

            raise ValueError(
                "Azure OpenAI did not return valid JSON.",
            ) from ex
            
            
            
    
