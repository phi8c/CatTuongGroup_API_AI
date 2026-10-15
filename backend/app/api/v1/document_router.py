from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
    Request
)
import asyncio
from uuid import UUID
from pydantic import BaseModel
from app.services.azure.preview_document_service import (
    PreviewDocumentService
)

from app.services.sharepoint.sharepoint_service import (
    SharePointService
)
from sqlalchemy.ext.asyncio import (
    AsyncSession
)
from app.core.database import (
    get_db
)

from app.core.settings import (
    settings
)

from app.services.sync_jobs.sync_state import (
     SyncState
)

import httpx


from app.services.sharepoint.sharepoint_service import (
    SharePointService
)

from app.repositories.chunk_repository import (
    ChunkRepository
)

from app.services.ingestion.chunk_processor import (
    ChunkProcessor
)

from app.repositories.azure_chunk_repository import (
    AzureChunkRepository
)

from app.repositories.workspace_source_config_repository import (
    WorkspaceSourceConfigRepository )

from app.services.delta.delta_service import (
   DeltaService
)

from app.services.task.tracking_task_service import ( TrackingTaskService )

from app.services.sharepoint.azure_project_tracking_service import AzureProjectTrackingService
from app.services.sharepoint.project_tracking_reader_service import ProjectTrackingReaderService
from app.services.sharepoint.project_tracking_sync_service import ProjectTrackingSyncService

from app.core.database import (
    get_db,
    AsyncSessionLocal
)

from app.schemas.tracking_chat_request import TrackingChatRequest
from app.services.govern.executive_data_sync_service import ExecutiveDataSyncService
from app.schemas.execute_schema import ExecutiveDataRequest, ExecutiveDataChatRequest




router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


ROLE_MAPPING = {

    "CEO":
    "CEO",

    "HR_MANAGER":
    "Trưởng Phòng",

    "IT_MANAGER":
    "Trưởng Phòng",

    "SALE_MANAGER":
    "Trưởng Phòng",

    "HR_STAFF":
    "Chuyên viên",

    "IT_STAFF":
    "Chuyên viên",

    "SALE_STAFF":
    "Chuyên viên"

}

class DocumentPreviewRequest(BaseModel):
    drive_id: str
    drive_item_id: str


class DeltaCheckRequest(BaseModel):
    site_id: str | None = None
    drive_id: str | None = None
    folder_id: str | None = None
    
    
@router.post("/preview")
async def preview_document(
    payload: DocumentPreviewRequest,
):
    try:
        preview_url = (
            await PreviewDocumentService
            .get_document_preview_url(
                drive_id=payload.drive_id,
                drive_item_id=payload.drive_item_id,
            )
        )

        return {
            "preview_url": preview_url
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to generate document preview",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/upload")
async def upload_document(

    file: UploadFile =
    File(...),

    email: str =
    Form(...),

    role: str =
    Form(...),

    security_level: str =
    Form(...),

    document_type: str =
    Form(...)

):

    print(
        "email =",
        email
    )

    print(
        "role =",
        role
    )

    print(
        "security_level =",
        security_level
    )

    print(
        "document_type =",
        document_type
    )

    print(
        "file_name =",
        file.filename
    )

    department = (
        role
        .split("_")[0]
    )

    owner_role = (
        ROLE_MAPPING.get(
            role,
            "Chuyên viên"
        )
    )

    print(
        "department =",
        department
    )

    print(
        "owner_role =",
        owner_role
    )

    file_content = await (
        file.read()
    )

    upload_result = await (
        SharePointService
        .upload_file(
            department=
            department,

            file_name=
            file.filename,

            file_content=
            file_content
        )
    )
    
    print("in ra upload result", upload_result)

    if "id" not in upload_result:

        raise HTTPException(
            status_code=500,
            detail=upload_result
        )

    drive_item_id = (
        upload_result["id"]
    )

    list_item_id = await (
        SharePointService
        .get_list_item_id(
            drive_item_id
        )
    )

    print(
        "list_item_id =",
        list_item_id
    )

    print(
        "item_id =",
        list_item_id
    )

    metadata_result = await (
        SharePointService
        .update_metadata(

            item_id=
            list_item_id,

            department=
            department,

            owner_role=
            owner_role,

            security_level=
            security_level,

            document_type=
            document_type

        )
    )

    return {

        "status":
        "success",

        "email":
        email,

        "role":
        role,

        "department":
        department,

        "owner_role":
        owner_role,

        "item_id":
        list_item_id,

        "upload_result":
        upload_result,

        "metadata_result":
        metadata_result

    }
    
@router.post("/sync")
async def sync_documents():
    
    
    
    SyncState.status = (
        "RUNNING"
    )


    async with httpx.AsyncClient(
        timeout=300
    ) as client:

        response = await client.post(
            settings.LOGIC_APP_URL,
            json={}
        )

        print(
            "logic_status =",
            response.status_code
        )

        print(
            "logic_body =",
            response.text
        )

    return {

        "status":
        "success",

        "logic_status":
        response.status_code

    }
    
@router.get(
    "/sync-status"
)
async def sync_status():

    return {

        "status":
        SyncState.status

    }
    
    
@router.post(
    "/sync-completed"
)
async def sync_completed(
    
    request: Request,


):

    print(
        "INGEST COMPLETED"
    )
    
    
    try:

        body = await request.json()

    except ValueError:

        body = {}

    parent_id = (
        body.get("parent_id")
        if isinstance(body, dict)
        else None
    )

    if not parent_id:

        print(
            "sync-completed: missing parent_id, skip pipeline"
        )

        _finish_sync(
            failed=True,
        )

        return {

            "status":
            "ignored",

            "reason":
            "missing parent_id"

        }

    #
    # Logic App có thể gọi lại callback cho cùng parent_id
    # khi pipeline trước còn đang chạy.
    #

    if parent_id in _running_parent_ids:

        print(
            "sync-completed: already running =",
            parent_id
        )

        return {

            "status":
            "accepted"

        }

    _running_parent_ids.add(
        parent_id
    )

    task = asyncio.create_task(

        run_post_ingestion_pipeline(

            parent_id

        )

    )

    _pipeline_tasks.add(task)

    task.add_done_callback(
        _pipeline_tasks.discard
    )

    return {

        "status":
        "accepted"

    }


#
# Post-ingestion state (in-process)
#

_running_parent_ids: set[str] = set()

_pipeline_tasks: set[asyncio.Task] = set()

_failed_in_batch = False


def _finish_sync(
    failed: bool,
):

    global _failed_in_batch

    if failed:

        _failed_in_batch = True

    #
    # Chỉ chốt trạng thái khi không còn pipeline nào đang chạy
    #

    if _running_parent_ids:

        return

    SyncState.status = (
        "FAILED"
        if _failed_in_batch
        else "COMPLETED"
    )

    _failed_in_batch = False


def _normalize_sensitivity(
    value,
) -> int:

    try:

        sensitivity = int(value)

    except (TypeError, ValueError):

        return 2

    if sensitivity not in (1, 2, 3):

        return 2

    return sensitivity


async def run_post_ingestion_pipeline(

    parent_id: str

):

    failed = False

    try:

        chunks = await asyncio.to_thread(

            ChunkRepository
            .get_unprocessed_chunks,

            parent_id,

        )

        if not chunks:

            print(
                "post-ingestion: no chunks for parent_id =",
                parent_id
            )

            return

        updated = 0

        async with (
            AsyncSessionLocal()
        ) as db:

            for chunk in chunks:

                try:

                    result = await (

                        ChunkProcessor
                        .process_chunk(

                            db=db,

                            chunk=chunk,

                            write_review_file=False,

                        )

                    )

                    await asyncio.to_thread(

                        AzureChunkRepository
                        .update_sensitivity,

                        chunk_id=
                        result["id"],

                        sensitivity=
                        _normalize_sensitivity(
                            result["sensitivity"]
                        ),

                    )

                    updated += 1

                except Exception as e:

                    failed = True

                    print(
                        "post-ingestion chunk error =",
                        chunk.get("id"),
                        e
                    )

        print(
            "updated chunks =",
            updated,
            "/",
            len(chunks)
        )

    except Exception as e:

        failed = True

        print(
            "post-ingestion error =",
            parent_id,
            e
        )

    finally:

        _running_parent_ids.discard(
            parent_id
        )

        _finish_sync(
            failed=failed,
        )

@router.get("/sites")
async def get_sites():

    return await (
        SharePointService
        .get_sites()
    )
    
@router.get(
    "/sites/{site_id}/lists"
)
async def get_lists(
    site_id: str,
):
    return await (
        SharePointService
        .get_lists(site_id)
    )
    
@router.get(
    "/sites/{site_id}/lists/{list_id}/configuration"
)
@staticmethod
async def get_site_configuration(
    site_id: str,
    list_id: str,
):

    data = await SharePointService.get_rag_configuration(
        site_id,
        list_id
    )

    if not data["value"]:
        return None

    fields = data["value"][0]["fields"]

    return {
        "enable_rag": fields.get("EnableRAG", False),
        "auto_ingest": fields.get("AutoIngest", False),
        "sync_interval_minutes": fields.get(
            "SyncIntervalMinutes",
            5,
        ),
        "default_library": fields.get(
            "DefaultLibrary"
        ),
        "default_folder": fields.get(
            "DefaultFolder"
        ),
    }

@router.get("/upload-options")
async def get_upload_options():

    return await (
        SharePointService
        .get_upload_options()
    )
    
@router.post("/upload-sharepoint")
async def upload_document(
    file: UploadFile = File(...),
    email: str = Form(...),
    role: str = Form(...),
    site_id: str = Form(...),
    drive_id: str = Form(...),
    folder_id: str | None = Form(None),
    document_type: str = Form(...),
    workspace_code: str = Form(...),
    db: AsyncSession = Depends(get_db),
    
):

    print("email =", email)
    print("role =", role)
    print("site_id =", site_id)
    print("drive_id =", drive_id)
    print("folder_id =", folder_id)
    print("document_type =", document_type)
    print("file_name =", file.filename)

    department = role.split("_")[0]

    owner_role = ROLE_MAPPING.get(
        role,
        "Chuyên viên",
    )

    print("department =", department)
    print("owner_role =", owner_role)

    file_content = await file.read()

    upload_result = await SharePointService.upload_file_sharepoint(
        site_id=site_id,
        drive_id=drive_id,
        folder_id=folder_id,
        file_name=file.filename,
        file_content=file_content,
    )
    
    
    
    print("=" * 100)
    print("UPLOAD RESULT")
    print(upload_result)
    print("=" * 100)

    if "id" not in upload_result:

        raise HTTPException(
            status_code=500,
            detail=upload_result,
        )

    print("upload_result =", upload_result)

    if "id" not in upload_result:

        raise HTTPException(
            status_code=500,
            detail=upload_result,
        )
        
        
    source_mode = await (
    WorkspaceSourceConfigRepository
    .get_data_source_mode_by_document_type(
        
        
        db=db,
       
        workspace_code=workspace_code,
    )
    )

    if source_mode is None:
        raise Exception("Document type not found")

    security_level = source_mode.code

    drive_item_id = upload_result["id"]

    list_item_id = await (
    SharePointService
    .get_list_item_id(
        site_id=site_id,
        drive_id=drive_id,
        drive_item_id=drive_item_id,
    )
)
    print("list_item_id =", list_item_id)

    metadata_result = await SharePointService.update_metadata(
        site_id=site_id,
        item_id=list_item_id,
        department=department,
        owner_role=owner_role,
        security_level=security_level,
        document_type=document_type,
        workspace_code=workspace_code
    )

    return {
        "status": "success",
        "email": email,
        "role": role,
        "site_id": site_id,
        "drive_id": drive_id,
        "folder_id": folder_id,
        "department": department,
        "owner_role": owner_role,
        "item_id": list_item_id,
        "upload_result": upload_result,
        "metadata_result": metadata_result,
    }

@router.get("/test-delta")
async def test_delta():

    upload_options = await (
        SharePointService
        .get_upload_options()
    )

    site = upload_options[0]

    drive = site["libraries"][0]

    return await (
        SharePointService
        .get_first_delta(
            drive_id=drive["id"]
        )
    )
    
@router.post("/delta/check")
async def check_delta(
    request: DeltaCheckRequest | None = None,
    db: AsyncSession = Depends(get_db),
):

    upload_options = await (
        SharePointService
        .get_upload_options()
    )

    changed = False
    print("in ra upload option", upload_options)
    selected_site_id = request.site_id if request else None
    selected_drive_id = request.drive_id if request else None
    selected_folder_id = request.folder_id if request else None

    if selected_folder_id:
        print("Checking selected folder:", selected_folder_id)

    for site in upload_options:

        if selected_site_id and site["id"] != selected_site_id:
            continue

        print("=" * 80)
        print("Checking site:", site["name"])

        for drive in site["libraries"]:

            if selected_drive_id and drive["id"] != selected_drive_id:
                continue

            print("Checking drive:", drive["name"])

            result = await (
            DeltaService
            .check(

                db=db,

                site_id=site["id"],

                drive_id=drive["id"],

            )
        )

            print("Changed =", result)

            if result:
                changed = True

    return {
        "changed": changed,
    }
    

@router.get(
    "/projects",
)
async def get_projects():

    return await (
        AzureProjectTrackingService
        .get_projects()
    )
    
@router.get(
    "/projects/{project_code}",
)
async def get_project_detail(

    project_code: str,

):

    result = await (

        ProjectTrackingReaderService
        .load_project(
            project_code=project_code,
        )

    )

    return result


@router.post("/sync/projects")
async def sync(

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        ProjectTrackingSyncService
        .sync_all(

            db=db,

        )

    )


@router.post("/sync/{project_code}")
async def sync_project(

    project_code: str,

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        ProjectTrackingSyncService
        .sync_project(

            db=db,

            project_code=project_code,

        )

    )
    
    
@router.get(
    "/project-tracking/projects",
)
async def get_projects(

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        TrackingTaskService
        .get_projects(

            db=db,

        )

    )


@router.get(
    "/project-tracking/projects/{project_code}",
)
async def get_project(

    project_code: str,

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        TrackingTaskService
        .get_project(

            db=db,

            project_code=project_code,

        )

    )
    
@router.post("/tracking/chat")
async def tracking_chat(

    request: TrackingChatRequest,

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        TrackingTaskService
        .chat(

            db=db,

            question=request.question,

            model_id=request.model_id,

        )

    )
    
    
@router.post("/executive-data/sync")
async def sync_executive_data(
    
    
    request: ExecutiveDataRequest,

    db: AsyncSession = Depends(
        get_db,
    ),
    

):

    return await (

        ExecutiveDataSyncService
        .sync_all(

            db=db,
            model_id=request.model_id,
            

        )

    )
    
@router.post(
    "/executive-data/chat",
)
async def executive_data_chat(

    request: ExecutiveDataChatRequest,

    db: AsyncSession = Depends(
        get_db,
    ),

):

    return await (

        ExecutiveDataSyncService
        .chat(

            db=db,

            question=request.question,

            model_id=request.model_id,

        )

    )
    
    
@router.get(
    "/sharepoint/folders",
)
async def get_upload_folders():

    return await (
        SharePointService
        .get_upload_folder_tree()
    )
