from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import asyncio

from app.workers.sharepoint_delta_worker import (
    sharepoint_delta_worker,
)
from app.workers.meeting_analysis_worker import (
    MeetingAnalysisWorker,
)

from app.api.v1.role_router import router as role_router
from app.api.v1.tag_router import router as tag_router

from app.api.v1.tag_role_rule_router import (
    router as tag_role_rule_router
)
from app.api.v1.policy_router import (
    router as policy_router
)
from app.api.v1.chunk_router import (
    router as chunk_router
)

from app.api.v1.chat_router import (
    router as chat_router
)

from app.api.v1.permission_router import (
    router as permission_router
)
from app.api.v1.bot_router import (

    router as bot_router

)
from app.api.v1.conversation_router import (
    router as conversation
)
from app.api.v1.document_router import (
    router as document_router
)
from app.api.v1.recruitment_candidate_router import (
    router as recruitment_candidate_router
)  

from app.api.v1.model_router import (
    router as model_router
) 

from app.api.v1.auth_router import (
    router as auth_router
)

from app.api.v1.planner_router import (
    router as planner_router
)
from app.api.v1.prompt_router import (
    router as prompt_router
)

from app.api.v1.contract_router import (
    router as contract_router)

from app.workers.project_tracking_worker import (
    ProjectTrackingWorker,
)

from app.api.v1.workspace_source_config_router import (
    router as workspace_source_config_router,
)

from app.api.v1.rag_config_router import (
    router as rag_config_router,
)

from app.api.v1.meeting_router import (
    router as meeting_router,
)

from fastapi.middleware.cors import (

    CORSMiddleware

)



from app.startup.queue_consumer import start_queue_consumers
from app.workers.executive_data_worker import ExecutiveDataWorker









app = FastAPI(
    
    
    root_path="/api",

    title=
    "chatrag",


    version=
    "1.0",


    servers=[

        {

            "url":

            "https://unwell-kinsman-legwork.ngrok-free.dev",


            "description":

            "Ngrok public API"

        }

    ]

)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []

    for error in exc.errors():
        sanitized_error = dict(error)
        sanitized_error.pop(
            "input",
            None,
        )
        errors.append(
            sanitized_error,
        )

    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
        },
    )


# @app.on_event("startup")
# async def startup():
#     asyncio.create_task(
#         sharepoint_delta_worker(),
#     )

#     await start_queue_consumers()



app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:5173"

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)




# @app.on_event("startup")
# async def startup():
#     asyncio.create_task(
#         MeetingAnalysisWorker.run(),
#     )




# @app.on_event("startup")
# async def startup():

  

#     asyncio.create_task(
#         ProjectTrackingWorker.run()
#     )



# @app.on_event("startup")
# async def startup():
#     asyncio.create_task(
#         sharepoint_delta_worker()
#     )



# @app.on_event("startup")
# async def startup():

#     #
#     # SharePoint Delta
#     #

#     asyncio.create_task(
#         sharepoint_delta_worker(),
#     )

#     #
#     # Queue
#     #

#     await start_queue_consumers()

#     #
#     # Project Tracking
#     #

#     asyncio.create_task(
#         ProjectTrackingWorker.run(),
#     )

#     #
#     # Executive Data
#     #

#     asyncio.create_task(
#         ExecutiveDataWorker.run(),
#     )

app.include_router(role_router)
app.include_router(tag_router)
app.include_router(tag_role_rule_router)
app.include_router(policy_router)
app.include_router(chunk_router)
app.include_router(chat_router)
app.include_router(permission_router)
app.include_router(bot_router)
app.include_router(conversation)
app.include_router(document_router)
app.include_router(recruitment_candidate_router)
app.include_router(model_router)
app.include_router(auth_router)
app.include_router(planner_router)
app.include_router(prompt_router)
app.include_router(contract_router)
app.include_router(workspace_source_config_router)
app.include_router(rag_config_router)
app.include_router(meeting_router)