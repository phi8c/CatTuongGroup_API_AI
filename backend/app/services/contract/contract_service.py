import json
from zipfile import Path
from pathlib import Path

from app.utils.extract.document_intelligent import (
    DocumentExtraction,
    DocumentExtractor,
)

from app.repositories.ai_model_repository import (
    AIModelRepository,
)

from app.repositories.ai_prompt_repository import (
    AIPromptRepository,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.enums.prompt_code import (
    PromptCode,
)

from app.services.llm.azure_openai_service import (
    AzureOpenAIService,
)

import hashlib
from datetime import datetime, timezone

from uuid import UUID

from app.core.settings import (
    settings,)



from app.models.contract_raw import ContractRaw
from app.repositories.contract_repository import ContractRepository
from app.models.contract_dashboard import ContractDashboard
from app.repositories.rag_config_repository import WorkspaceConfigRepository


class ContractService:

    def __init__(self):

        self.llm = AzureOpenAIService()

    async def analyze(
        self,
        db,
        file_path: str,
        model_id,
    ):

        #
        # Extract
        #

        extraction = (
            DocumentExtractor.extract(
                file_path,
            )
        )

        #
        # Prompt
        #

        prompt = await (
            AIPromptRepository
            .get_by_code(
                db=db,
                code=PromptCode.CONTRACT_ANALYZE,
            )
        )

        #
        # Model
        #

        model = await (
            AIModelRepository
            .get_by_id(
                db=db,
                id=model_id,
            )
        )

        #
        # Messages
        #

        messages = [

            {

                "role": "system",

                "content": prompt.system_prompt,

            },

            {

                "role": "user",

                "content":

f"""
Nội dung hợp đồng:

{extraction}
"""

            }

        ]

        #
        # AI
        #
        workspace_code = PromptCode.CONTRACT_ANALYZE.value
        
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

#         max_tokens = int(
#     model_config.max_tokens

# )   
        max_tokens = 6000
        
        
        result =  await self.llm.chat(

            model=model.model_name,

            messages=messages,

            temperature=temperature,
            max_completion_tokens=max_tokens

        )
        
        
        print("in ra result", result)
        
        
        
        analysis = json.loads(result)

        #
        # Save Raw
        #
        
        

        contract = await (
        ContractService
        ._save_raw(
            db=db,
            contract_name=analysis["contract_name"],
            source_file=extraction.file_name,
            extraction=extraction,
        )
    )

        #
        # Save Dashboard
        #
        
        print("in ra ", contract)
        print("in ra ", analysis)

        await (
            ContractService
            ._save_dashboard(
                db=db,
                contract=contract,
                analysis=analysis,
            )
        )

        await db.commit()

        return analysis
        
        
        
        
        
       
    
    
    @staticmethod
    async def _save_raw(
        db,
        contract_name: str,
        source_file: str,
        extraction: DocumentExtraction,
    ) -> ContractRaw:

        file_hash = hashlib.sha256(
            extraction.markdown.encode("utf-8")
        ).hexdigest()

        item = await (
            ContractRepository
            .get_raw_by_hash(
                db=db,
                file_hash=file_hash,
            )
        )

        if item is None:

            item = ContractRaw(

                contract_name=contract_name,

                source_file=source_file,

                file_hash=file_hash,

                extracted_content=extraction.markdown,

                created_at=datetime.now(
                    timezone.utc,
                ),

                updated_at=datetime.now(
                    timezone.utc,
                ),

            )

            await (
                ContractRepository
                .create_raw(
                    db=db,
                    item=item,
                )
            )

            await db.flush()

        else:

            item.contract_name = contract_name

            item.source_file = source_file

            item.file_hash = file_hash

            item.extracted_content = (
                extraction.markdown
            )

            item.updated_at = datetime.now(
                timezone.utc,
            )

            await (
                ContractRepository
                .update_raw(
                    db=db,
                    item=item,
                )
            )

        return item

        
    from app.models.contract_dashboard import (
    ContractDashboard,
)


    @staticmethod
    async def _save_dashboard(
        db,
        contract: ContractRaw,
        analysis: dict,
    ):

        item = await (
            ContractRepository
            .get_dashboard(
                db=db,
                contract_id=contract.id,
            )
        )

        if item is None:

            item = ContractDashboard(

                contract_id=contract.id,

                summary=analysis["summary"],

                clauses=analysis["clauses"],

                analyzed_at=datetime.now(
                    timezone.utc,
                ),

                created_at=datetime.now(
                    timezone.utc,
                ),

                updated_at=datetime.now(
                    timezone.utc,
                ),

            )

            await (
                ContractRepository
                .create_dashboard(
                    db=db,
                    item=item,
                )
            )

        else:

            item.summary = analysis[
                "summary"
            ]

            item.clauses = analysis[
                "clauses"
            ]

            item.analyzed_at = datetime.now(
                timezone.utc,
            )

            item.updated_at = datetime.now(
                timezone.utc,
            )

            await (
                ContractRepository
                .update_dashboard(
                    db=db,
                    item=item,
                )
            )
            
    @staticmethod
    async def chat(
        db: AsyncSession,
        question: str,
        model_id: UUID,
        contract_id: UUID | None = None,
    ):

        #
        # Prompt Detection
        #

        model = await (
            AIModelRepository
            .get_by_id(
                db=db,
                id=model_id,
            )
        )

        # detection_prompt = await (
        #     AIPromptRepository
        #     .get_by_code(
        #         db=db,
        #         code=PromptCode.DETECT_CONTRACT,
        #     )
        # )

        # #
        # # Danh sách contract
        # #

        # contracts = await (
        #     ContractRepository
        #     .get_contract_summaries(
        #         db=db,
        #     )
        # )

        # contract_text = json.dumps(
        #     contracts,
        #     ensure_ascii=False,
        #     indent=2,
        # )

        # #
        # # Build Prompt
        # #

        # prompt = (
        #     detection_prompt.system_prompt
        #     .replace(
        #         "{{contracts}}",
        #         contract_text,
        #     )
        #     .replace(
        #         "{{question}}",
        #         question,
        #     )
        # )

        # #
        # # Detection
        # #

        # result = await (
        #     AzureOpenAIService()
        #     .generate(
        #         model=model.model_name,
        #         prompt=prompt,
        #         temperature=0.2,
        #     )
        # )

        # detect = json.loads(result)

        # #
        # # Load Context
        # #

        # if detect["scope"] == "CONTRACT":

        #     context = await (
        #         ContractRepository
        #         .get_extracted_content(
        #             db=db,
        #             contract_id=UUID(
        #                 detect["contract_id"],
        #             ),
        #         )
        #     )

        # else:

        #     contracts = await (
        #         ContractRepository
        #         .get_all_summaries(
        #             db=db,
        #         )
        #     )

        #     context = "\n\n".join(contracts)

        # #
        # # Prompt Chat
        # #
        
        
        context = await (
            ContractRepository
            .get_extracted_content(
            db=db,
            contract_id=contract_id,
            
                        )
                    )

        chat_prompt = await (
            AIPromptRepository
            .get_by_code(
                db=db,
                code=PromptCode.CONTRACT_CHAT,
            )
        )

        messages = [

            {
                "role": "system",
                "content": chat_prompt.system_prompt,
            },

            {
                "role": "user",
                "content":
    f"""
    Câu hỏi:

    {question}

    ===================================

    Nội dung hợp đồng:

    {context}
    """,
            },

        ]

        #
        # Chat
        #
        
        
        workspace_code = PromptCode.CONTRACT_ANALYZE.value  
                        
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
            

        answer = await (
            AzureOpenAIService()
            .chat(
                model=model.model_name,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens
            )
        )

        return {
            "answer": answer,
    }
        
        
    @staticmethod
    async def get_contracts(
        db: AsyncSession,
    ):

        rows = await (
            ContractRepository
            .get_contracts(
                db=db,
            )
        )

        results = []

        for raw, dashboard in rows:

            results.append(

                {

                    "id": raw.id,

                    "contract_name": raw.contract_name,

                    "summary": dashboard.summary,

                    "created_at": raw.created_at,

                }

            )

        return results
    
    
    @staticmethod
    async def get_contract(
        db: AsyncSession,
        contract_id: UUID,
    ):

        row = await (
            ContractRepository
            .get_contract(
                db=db,
                contract_id=contract_id,
            )
        )

        if row is None:

            return None

        raw, dashboard = row

        return {

            "id": raw.id,

            "contract_name": raw.contract_name,

            "summary": dashboard.summary,

            "clauses": dashboard.clauses,

        }