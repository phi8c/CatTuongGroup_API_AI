from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    Form,
)


from app.schemas.create_review_request import (
    CreateReviewRequest,
)

from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncSession
)

from app.core.database import (
    get_db
)

from app.schemas.recruitment_schema import (
    RecruitmentCampaignCreate,
    RecruitmentCampaignResponse,
    RecruitmentCampaignCreateResponse,
    
)

from app.schemas.recruit_campaign_chat_request import (

RecruitmentCampaignChatRequest

)

from app.services.recruitment.recruitment_service import (
    RecruitmentService
)


from app.services.recruitment.recruitment_campaign_service import (
    RecruitmentCampaignService
)


from app.services.recruitment.upload_candidate import (
    UploadCandidateService,
)
from app.services.recruitment.analyze_candidate_service import (
    AnalyzeCandidateService,
)
from app.schemas.analyze_candidate_request import (
    AnalyzeCandidateRequest,
)

from app.services.review.review_service import (
    ReviewService,
)
from app.enums.review_constants import ReviewFileLimit
from app.core.not_found_exception import NotFoundException

router = APIRouter(
    prefix="/recruitments",
    tags=["Recruitments"]
)


@router.post(
    "",
    response_model=RecruitmentCampaignCreateResponse
)
async def create_campaign(
    payload: RecruitmentCampaignCreate,
    db: AsyncSession = Depends(get_db)
):
    return await (
        RecruitmentService.create_campaign(
            db=db,
            role_id=payload.role_id,
            title=payload.title,
            job_description=payload.job_description
        )
    )
    
@router.post(
    "/{campaign_id}/candidates",
)
async def upload_candidate(
    campaign_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await UploadCandidateService.execute(
        db=db,
        campaign_id=campaign_id,
        file=file,
    )
    
@router.post(
    "/candidates/{candidate_id}/analyze",
)
async def analyze_candidate(
    candidate_id: UUID,
    request: AnalyzeCandidateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await AnalyzeCandidateService.execute(
        db=db,
        candidate_id=candidate_id,
        model_id=request.model_id,
    )

    return result

from app.schemas.review_dto import (
    ReviewResponse,
)


@router.post(
    "/analyze",
    response_model=ReviewResponse,
)
async def create_review(
    model_id: UUID = Form(...),
    files: list[UploadFile] = File(...),
    job_description: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    
    
    

    request = CreateReviewRequest(
        model_id=model_id,
        files=files,
        job_description=job_description,
    )
    
    if len(request.files) == ReviewFileLimit.MIN.value:
    
                raise NotFoundException(
                    "Please upload at least one file.",
                )
    
    if len(request.files) > ReviewFileLimit.MAX_FILE_REVIEW.value:
    
                raise NotFoundException(
                    f"Maximum {ReviewFileLimit.MAX_FILE_REVIEW.value} files are allowed.",
                )
    
    

    return await ReviewService.create_review(
        db=db,
        request=request,
    )
    
    
@router.post("/campaign/chat")
async def campaign_chat(
    model_id: str = Form(...),
    question: str = Form(...),
    data_cv: str = Form(...),
    job_description: str = Form(...),
    db: AsyncSession = Depends(get_db),
):

    answer = await (
        RecruitmentService
        .chat(
           db=db,
        model_id=model_id,
        question=question,
        data_cv=data_cv,
        job_description=job_description,
        )
    )

    return {

        

        "answer":
        answer,

    }
    
@router.get("/list-campaign")
async def get_campaigns(
    db: AsyncSession = Depends(
        get_db,
    ),
):

    return await (
        RecruitmentCampaignService
        .get_list(
            db=db,
        )
    )
@router.get("/{campaign_id}")
async def get_campaign_detail(
    campaign_id: UUID,

    db: AsyncSession = Depends(
        get_db,
    ),
):

    return await (
        RecruitmentCampaignService
        .get_detail(
            db=db,
            campaign_id=campaign_id,
        )
    )
    
@router.get(
    "/{campaign_id}/candidates/{task_id}"
)
async def get_candidate_detail(
    campaign_id: UUID,
    task_id: UUID,

    db: AsyncSession = Depends(
        get_db,
    ),
):

    return await (
        RecruitmentCampaignService
        .get_candidate_detail(
            db=db,
            campaign_id=campaign_id,
            task_id=task_id,
        )
    )

    



# @router.get(
#     "/jobs/{job_id}",
#     response_model=ReviewJobResultResponse,
# )
# async def get_review_job(
#     job_id: UUID,
#     db: AsyncSession = Depends(
#         get_db,
#     ),
# ) -> ReviewJobResultResponse:

#     return await ReviewService.get_result(
#         db=db,
#         job_id=job_id,
#     )
