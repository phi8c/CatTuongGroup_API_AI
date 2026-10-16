from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.repositories.project_tracking_raw_repository import (
    ProjectTrackingRawRepository,
)

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.prompt_code import PromptCode

from app.repositories.ai_prompt_repository import (
    AIPromptRepository,
)


from app.services.llm.azure_openai_service import (
    AzureOpenAIService,
)
from uuid import UUID

from app.repositories.ai_model_repository import ( AIModelRepository)
from app.core.settings import settings
from app.repositories.rag_config_repository import WorkspaceConfigRepository


class TrackingTaskService:

    @staticmethod
    async def get_projects(
        db: AsyncSession,
    ):

        rows = await (
            ProjectTrackingRawRepository
            .get_dashboard_projects(
                db=db,
            )
        )

        results = []

        for raw, dashboard in rows:

            results.append(

                {

                    "project_code":
                    raw.project_code,

                    "project_name":
                    raw.project_name,

                    "progress": {

                        "status":
                        dashboard.progress_status,

                        "title":
                        dashboard.progress_title,

                    },

                    "budget": {

                        "status":
                        dashboard.budget_status,

                        "title":
                        dashboard.budget_title,

                    },

                    "risk": {

                        "count":
                        dashboard.risk_count,

                        "total":
                        dashboard.risk_total,

                    },

                }

            )

        return results
    
    @staticmethod
    async def get_project(
        db: AsyncSession,
        project_code: str,
    ):

        row = await (
            ProjectTrackingRawRepository
            .get_dashboard_project(
                db=db,
                project_code=project_code,
            )
        )

        if row is None:
            return None

        raw, dashboard = row

        return {

    "project_code": raw.project_code,

    "project_name": raw.project_name,

    "dashboard": {

        "summary": dashboard.summary,

        "overall_health": {

            "status": dashboard.overall_health_status,

            "title": dashboard.overall_health_title,

        },

        "progress": {

            "status": dashboard.progress_status,

            "title": dashboard.progress_title,

        },

        "budget": {

            "status": dashboard.budget_status,

            "title": dashboard.budget_title,

        },

        "risk": {

            "count": dashboard.risk_count,

            "total": dashboard.risk_total,

        },

        "task_analysis": dashboard.task_analysis,

    },

    "project": raw.project_data,

}
        
        
    @staticmethod
    async def chat(
        db: AsyncSession,
        question: str,
        model_id: UUID,
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

        detection_prompt = await (
            AIPromptRepository
            .get_by_code(
                db=db,
                code=PromptCode.DETECTION,
            )
        )
        print("detection_prompt", detection_prompt)

        #
        # Danh sách project
        #

        projects = await (
            ProjectTrackingRawRepository3
            .get_project_names(
                db=db,
            )
        )
        print("projects", projects)

        project_text = "\n".join(

            f'- {item["project_code"]} : {item["project_name"]}'

            for item in projects

        )
        print("project_text", project_text)

        #
        # Build Prompt
        #

        prompt = (
            detection_prompt.system_prompt
            .replace(
                "{{projects}}",
                project_text,
            )
            .replace(
                "{{question}}",
                question,
            )
        )
        print("prompt", prompt)

        #
        # Detection
        #

        result = await (
            AzureOpenAIService()
            .generate(
                model=model.model_name,
                prompt=prompt,
                
                temperature=0.2,
            )
            
        )

        detect = json.loads(result)
        print("in ra" , detect)
        
        
        print("=" * 100)
        print(result)
        print("=" * 100)

    

        #
        # Load Context
        #

        if detect["scope"] == "PROJECT":

            project = await (
                ProjectTrackingRawRepository
                .get_by_project_code(
                    db=db,
                    project_code=detect["project_codes"][0],
                )
            )

            context = project.project_data

        else:

            projects = await (
                ProjectTrackingRawRepository
                .get_all_project_data(
                    db=db,
                )
            )

            context = [

                item.project_data

                for item in projects

            ]

        #
        # Prompt Chat
        #

        chat_prompt = await (
            AIPromptRepository
            .get_by_code(
                db=db,
                code=PromptCode.PROJECT_TRACKING_CHAT,
            )
        )
        
        # model = await (
        #     AIModelRepository
        #     .get_by_id(
        #         db=db,
        #         id=model_id,
        #     )
        # )

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

Dữ liệu dự án:

{json.dumps(context, ensure_ascii=False, indent=2)}
                """,
            },

        ]

        #
        # Chat
        #
        
        
        workspace_code = PromptCode.PROJECT_TRACKING.value
                                
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
