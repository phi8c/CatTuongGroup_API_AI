import logging
import re
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

import httpx
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.search.documents.aio import SearchClient

from app.core.settings import settings
from app.repositories.azure_acl_repository import AzureAclRepository
from app.services.sharepoint.sharepoint_acl_graph import SharePointAclError, SharePointAclGraph


logger = logging.getLogger(__name__)


def normalize_acl(acl):
    normalized = {}
    for field in AzureAclRepository.ACL_FIELDS:
        values = acl.get(field) or []
        if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
            raise SharePointAclError("Invalid ACL collection in search index.")
        items = set()
        for value in values:
            value = value.strip()
            if value:
                if field != "allowed_sharepoint_group_ids":
                    try:
                        value = str(UUID(value))
                    except ValueError:
                        pass
                items.add(value)
        normalized[field] = sorted(items)
    return normalized


def parse_permissions(permissions):
    acl = {field: set() for field in AzureAclRepository.ACL_FIELDS}
    warnings = set()
    now = datetime.now(timezone.utc)
    for permission in permissions:
        if not isinstance(permission, dict):
            raise SharePointAclError("Invalid Graph permission object.")
        expires = permission.get("expirationDateTime")
        if expires:
            try:
                expires = re.sub(r"(\.\d{6})\d+", r"\1", expires)
                expiration = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if expiration.tzinfo is None:
                    raise ValueError("Missing expiration timezone")
            except (ValueError, TypeError):
                raise SharePointAclError("Invalid permission expiration timestamp.")
            if expiration <= now:
                continue
        roles = permission.get("roles")
        if not isinstance(roles, list) or not roles:
            raise SharePointAclError("Graph permission has no roles.")
        if not set(roles).intersection({"read", "write", "owner"}):
            raise SharePointAclError("Unsupported Graph permission role.")
        link = permission.get("link")
        if link:
            scope = link.get("scope")
            if scope in {"anonymous", "organization"}:
                warnings.add(f"sharing_link_{scope}_not_expanded")
                continue
            if scope == "existingAccess":
                continue
            if scope != "users":
                raise SharePointAclError("Unsupported sharing link scope.")
        identity = permission.get("grantedToV2") or permission.get("grantedTo")
        identities = permission.get("grantedToIdentitiesV2")
        if identities is None:
            identities = permission.get("grantedToIdentities", [])
        if not isinstance(identities, list):
            raise SharePointAclError("Invalid permission identities.")
        identities = list(identities)
        if identity:
            identities.append(identity)
        if not identities:
            raise SharePointAclError("Permission principal cannot be resolved to an ID.")
        for identity in identities:
            if not isinstance(identity, dict):
                raise SharePointAclError("Invalid permission principal.")
            recognized = False
            site_group = identity.get("siteGroup") or {}
            if site_group.get("id"):
                acl["allowed_sharepoint_group_ids"].add(str(site_group["id"]))
                warnings.add("sharepoint_group_membership_not_expanded")
                recognized = True
            for kind, field in (("user", "allowed_user_ids"), ("group", "allowed_group_ids")):
                principal = identity.get(kind)
                if principal is None:
                    continue
                try:
                    object_id = str(UUID(principal["id"]))
                except (ValueError, KeyError, TypeError, AttributeError):
                    if kind == "group" and recognized:
                        continue
                    raise SharePointAclError("Principal has no valid Entra object ID.")
                acl[field].add(object_id)
                recognized = True
            if identity.get("application") is not None:
                warnings.add("application_principal_not_used_for_user_retrieval")
                recognized = True
            if not recognized:
                raise SharePointAclError("Permission principal cannot be resolved to an Entra ID.")
    return {field: sorted(values) for field, values in acl.items()}, sorted(warnings)


class SharePointAclSyncService:
    async def sync(self, site_id, dry_run=False):
        async with httpx.AsyncClient(timeout=60) as http:
            graph = SharePointAclGraph(http)
            await graph.authenticate()
            async with SearchClient(
                endpoint=settings.AZURE_SEARCH_ENDPOINT,
                index_name=settings.AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
            ) as search:
                return await self.sync_site(graph, AzureAclRepository(search), site_id, dry_run)

    async def sync_site(self, graph, repository, site_id, dry_run):
        started = perf_counter()
        summary = {
            "site_id": site_id,
            "dry_run": dry_run,
            "status": "completed",
            "drives_scanned": 0,
            "documents_scanned": 0,
            "documents_changed": 0,
            "chunks_updated": 0,
            "documents_failed": 0,
            "documents_not_indexed": 0,
            "documents_with_warnings": 0,
            "drive_errors": [],
            "results": [],
        }
        # Read the full library list before applying any updates.
        drives = [drive async for drive in graph.drives(site_id)]
        seen_drives = set()
        for drive in drives:
            drive_id = drive["id"]
            if drive_id in seen_drives:
                continue
            seen_drives.add(drive_id)
            summary["drives_scanned"] += 1
            try:
                async for document in graph.documents(drive_id):
                    summary["documents_scanned"] += 1
                    result = await self.sync_document(graph, repository, drive_id, document, dry_run)
                    summary["results"].append(result)
                    summary["documents_changed"] += int(result["changed_chunks"] > 0)
                    summary["chunks_updated"] += result["updated_chunks"]
                    summary["documents_failed"] += int(result["status"] in {"error", "partial_failure"})
                    summary["documents_not_indexed"] += int(result["status"] == "not_indexed")
                    summary["documents_with_warnings"] += int(bool(result["warnings"]))
            except Exception as exc:
                summary["drive_errors"].append({
                    "drive_id": drive_id,
                    "error": self.error_message(exc),
                })
        if summary["documents_failed"] or summary["drive_errors"]:
            summary["status"] = "completed_with_errors"
        summary["elapsed_seconds"] = round(perf_counter() - started, 3)
        logger.info(
            "[SHAREPOINT_ACL] site=%s documents=%d changed=%d updated_chunks=%d total=%.3fs",
            site_id, summary["documents_scanned"], summary["documents_changed"],
            summary["chunks_updated"], summary["elapsed_seconds"],
        )
        return summary

    @staticmethod
    def error_message(exc):
        if isinstance(exc, SharePointAclError):
            return str(exc)
        if isinstance(exc, HttpResponseError):
            return (
                f"Azure Search failed (HTTP {exc.status_code}). "
                "Verify source ID filters and retrievable ACL fields."
            )
        return "Upstream or index operation failed; retry or check server configuration."

    async def sync_document(self, graph, repository, drive_id, document, dry_run):
        started = perf_counter()
        result = {
            "drive_id": drive_id,
            "drive_item_id": document["id"],
            "name": document.get("name"),
            "status": "unchanged",
            "indexed_chunks": 0,
            "changed_chunks": 0,
            "updated_chunks": 0,
            "warnings": [],
        }
        try:
            if document.get("remoteItem") is not None:
                result.update(status="skipped", warnings=["remote_item_outside_site_not_followed"])
                return result
            permissions = await graph.permissions(drive_id, document["id"])
            acl, warnings = parse_permissions(permissions)
            result.update(acl=acl, warnings=warnings)
            chunks = await repository.chunks(drive_id, document["id"])
            result["indexed_chunks"] = len(chunks)
            if not chunks:
                result["status"] = "not_indexed"
                return result
            changed = [chunk["chunk_id"] for chunk in chunks if normalize_acl(chunk) != acl]
            result["changed_chunks"] = len(changed)
            if changed:
                if dry_run:
                    result["status"] = "would_update"
                else:
                    succeeded, failed = await repository.replace_acl(changed, acl)
                    result["updated_chunks"] = len(succeeded)
                    result["status"] = "partial_failure" if failed else "updated"
                    if failed:
                        result["failed_chunk_ids"] = failed
        except Exception as exc:
            result.update(status="error", error=self.error_message(exc))
        finally:
            result["elapsed_seconds"] = round(perf_counter() - started, 3)
            logger.info(
                "[SHAREPOINT_ACL] drive=%s item=%s status=%s chunks=%d changed=%d updated=%d total=%.3fs",
                drive_id, document["id"], result["status"], result["indexed_chunks"],
                result["changed_chunks"], result["updated_chunks"], result["elapsed_seconds"],
            )
        return result
