from typing import Annotated

import httpx
from azure.core.exceptions import AzureError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app.services.sharepoint.sharepoint_acl_graph import SharePointAclError
from app.services.sharepoint.sharepoint_acl_sync_service import SharePointAclSyncService


router = APIRouter(prefix="/documents", tags=["Documents"])


class SiteAclSyncRequest(BaseModel):
    site_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    dry_run: bool = False


@router.post("/acl/sync")
async def sync_site_acl(request: SiteAclSyncRequest):
    try:
        return await SharePointAclSyncService().sync(
            site_id=request.site_id,
            dry_run=request.dry_run,
        )
    except (SharePointAclError, httpx.HTTPError, AzureError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to start ACL sync. Check Graph permissions, site ID and Azure Search configuration.",
        ) from exc
