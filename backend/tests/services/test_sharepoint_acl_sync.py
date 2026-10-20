import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.api.v1.document_acl_router import SiteAclSyncRequest
from app.repositories.azure_acl_repository import AzureAclRepository
from app.services.sharepoint.sharepoint_acl_graph import SharePointAclError, SharePointAclGraph
from app.services.sharepoint.sharepoint_acl_sync_service import (
    SharePointAclSyncService, normalize_acl, parse_permissions,
)


USER = "371fc795-833a-48ee-83c6-b0039a2b0d18"
GROUP = "3706fa25-5bfd-4c37-a883-c50756d1596c"


async def stream(items):
    for item in items:
        yield item


def acl(users=None, groups=None, site_groups=None):
    return {
        "allowed_user_ids": users or [],
        "allowed_group_ids": groups or [],
        "allowed_sharepoint_group_ids": site_groups or [],
    }


def permission(identity):
    return {"roles": ["read"], "grantedToV2": identity}


class AclParsingTest(unittest.TestCase):
    def test_extracts_users_groups_and_site_groups_without_conflating_ids(self):
        value, warnings = parse_permissions([
            permission({"user": {"id": USER}, "siteUser": {"id": "12"}}),
            permission({"group": {"id": GROUP}}),
            permission({"group": {"id": "7"}, "siteGroup": {"id": "7"}}),
            permission({"user": {"id": USER.upper()}}),
        ])
        self.assertEqual(value, acl([USER], [GROUP], ["7"]))
        self.assertIn("sharepoint_group_membership_not_expanded", warnings)

    def test_specific_people_link_and_legacy_identity(self):
        value, _ = parse_permissions([
            {"roles": ["write"], "link": {"scope": "users"},
             "grantedToIdentitiesV2": [{"user": {"id": USER}}]},
            {"roles": ["owner"], "grantedTo": {"group": {"id": GROUP}}},
        ])
        self.assertEqual(value, acl([USER], [GROUP]))

    def test_expired_permissions_are_not_granted(self):
        expired = permission({"user": {"id": USER}})
        expired["expirationDateTime"] = "2000-01-01T00:00:00.1234567Z"
        value, _ = parse_permissions([expired])
        self.assertEqual(value, acl())

    def test_unresolved_principal_is_not_silently_discarded(self):
        with self.assertRaises(SharePointAclError):
            parse_permissions([permission({"siteUser": {"id": "12"}})])

    def test_broad_links_are_reported_without_becoming_user_ids(self):
        value, warnings = parse_permissions([
            {"roles": ["read"], "link": {"scope": "organization"}},
            {"roles": ["read"], "link": {"scope": "anonymous"}},
        ])
        self.assertEqual(value, acl())
        self.assertEqual(len(warnings), 2)

    def test_collection_order_duplicates_and_guid_case_do_not_trigger_updates(self):
        self.assertEqual(normalize_acl(acl([USER, USER.upper()])), acl([USER]))

    def test_invalid_request_site_is_rejected(self):
        with self.assertRaises(ValueError):
            SiteAclSyncRequest(site_id="  ")


class GraphAclTraversalTest(unittest.IsolatedAsyncioTestCase):
    async def test_traverses_nested_files_and_permissions_with_pagination(self):
        base = SharePointAclGraph.BASE
        pages = {
            "/v1.0/sites/site/drives": {"value": [{"id": "drive", "name": "Documents"}],
                "@odata.nextLink": base + "/sites/site/drives?next=1"},
            "/v1.0/sites/site/drives?next=1": {"value": [{"id": "other"}]},
            "/v1.0/drives/drive/root/children": {"value": [{"id": "folder", "folder": {}}],
                "@odata.nextLink": base + "/drives/drive/root/children?next=1"},
            "/v1.0/drives/drive/root/children?next=1": {"value": [{"id": "file-1", "file": {}}]},
            "/v1.0/drives/drive/items/folder/children": {"value": [{"id": "file-2", "file": {}}]},
            "/v1.0/drives/drive/items/file-1/permissions": {
                "value": [permission({"user": {"id": USER}})],
                "@odata.nextLink": base + "/drives/drive/items/file-1/permissions?next=1"},
            "/v1.0/drives/drive/items/file-1/permissions?next=1": {
                "value": [permission({"group": {"id": GROUP}})]},
        }

        def handler(request):
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            key = request.url.path
            if request.url.params.get("next"):
                key += "?next=" + request.url.params["next"]
            return httpx.Response(200, json=pages[key])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            graph = SharePointAclGraph(http)
            graph.token = "test-token"
            self.assertEqual(len([d async for d in graph.drives("site")]), 2)
            self.assertEqual({d["id"] async for d in graph.documents("drive")}, {"file-1", "file-2"})
            parsed, _ = parse_permissions(await graph.permissions("drive", "file-1"))
            self.assertEqual(parsed, acl([USER], [GROUP]))

    async def test_failed_permission_read_is_not_an_empty_acl(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(403, json={"error": {"message": "Denied"}})
        )) as http:
            graph = SharePointAclGraph(http)
            with self.assertRaises(SharePointAclError):
                await graph.permissions("drive", "file")

    async def test_external_next_link_is_rejected_without_sending_token(self):
        requests = []
        def handler(request):
            requests.append(str(request.url))
            return httpx.Response(200, json={"value": [], "@odata.nextLink": "https://example.com/steal"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            graph = SharePointAclGraph(http)
            with self.assertRaises(SharePointAclError):
                await graph.permissions("drive", "file")
        self.assertEqual(len(requests), 1)


class AzureAclRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_reads_all_chunks_without_filtering_nonfilterable_source_ids(self):
        rows = [{"chunk_id": str(i), "drive_id": "drive'1", "drive_item_id": "item'2"} for i in range(1205)]
        client = SimpleNamespace(search=AsyncMock(return_value=stream(rows)))
        result = await AzureAclRepository(client).chunks("drive'1", "item'2")
        self.assertEqual(len(result), 1205)
        kwargs = client.search.await_args.kwargs
        self.assertNotIn("filter", kwargs)
        self.assertNotIn("top", kwargs)
        self.assertNotIn("text_vector", kwargs["select"])

    async def test_matches_both_source_ids_and_reuses_one_scan(self):
        rows = [
            {"chunk_id": "a", "drive_id": "drive", "drive_item_id": "file"},
            {"chunk_id": "b", "drive_id": "other", "drive_item_id": "file"},
            {"chunk_id": "c", "drive_id": "drive", "drive_item_id": "other"},
            {"chunk_id": "legacy", "drive_id": None, "drive_item_id": None},
        ]
        client = SimpleNamespace(search=AsyncMock(return_value=stream(rows)))
        repo = AzureAclRepository(client)
        self.assertEqual(await repo.chunks("drive", "file"), [rows[0]])
        self.assertEqual(await repo.chunks("other", "file"), [rows[1]])
        self.assertEqual(await repo.chunks("missing", "file"), [])
        client.search.assert_awaited_once()

    async def test_merge_batches_replace_acl_only_and_report_partial_failures(self):
        batches = []
        async def merge(documents):
            batches.append(documents)
            return [SimpleNamespace(key=d["chunk_id"], succeeded=d["chunk_id"] != "bad") for d in documents]
        repo = AzureAclRepository(SimpleNamespace(merge_documents=AsyncMock(side_effect=merge)))
        ids = [str(i) for i in range(1001)] + ["bad"]
        good, bad = await repo.replace_acl(ids, acl())
        self.assertEqual(len(good), 1001)
        self.assertEqual(bad, ["bad"])
        self.assertEqual([len(b) for b in batches], [500, 500, 2])
        self.assertEqual(set(batches[0][0]), {"chunk_id", *AzureAclRepository.ACL_FIELDS})
        self.assertEqual(batches[0][0]["allowed_user_ids"], [])


class SharePointAclSyncTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = SharePointAclSyncService()
        self.graph = SimpleNamespace(permissions=AsyncMock(return_value=[permission({"user": {"id": USER}})]))
        self.repo = SimpleNamespace(chunks=AsyncMock(), replace_acl=AsyncMock(return_value=(["different"], [])))
        self.doc = {"id": "file", "name": "same-name.docx"}

    async def test_updates_every_changed_chunk_not_only_first_chunk(self):
        self.repo.chunks.return_value = [
            {"chunk_id": "same", **acl([USER])},
            {"chunk_id": "different", **acl([], [GROUP])},
        ]
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["updated_chunks"], 1)
        self.repo.replace_acl.assert_awaited_once_with(["different"], acl([USER]))

    async def test_dry_run_never_writes(self):
        self.repo.chunks.return_value = [{"chunk_id": "different", **acl()}]
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, True)
        self.assertEqual(result["status"], "would_update")
        self.repo.replace_acl.assert_not_awaited()

    async def test_successful_empty_permission_list_revokes_existing_grants(self):
        self.graph.permissions.return_value = []
        self.repo.chunks.return_value = [{"chunk_id": "different", **acl([USER], [GROUP], ["7"])}]
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
        self.repo.replace_acl.assert_awaited_once_with(["different"], acl())
        self.assertEqual(result["status"], "updated")

    async def test_graph_failure_and_unresolved_user_do_not_write(self):
        for response in [SharePointAclError("Denied"), [permission({"siteUser": {"id": "7"}})]]:
            self.graph.permissions.side_effect = response if isinstance(response, Exception) else None
            self.graph.permissions.return_value = response
            result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
            self.assertEqual(result["status"], "error")
        self.repo.replace_acl.assert_not_awaited()

    async def test_unindexed_document_is_reported_without_name_fallback(self):
        self.repo.chunks.return_value = []
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
        self.assertEqual(result["status"], "not_indexed")
        self.repo.chunks.assert_awaited_once_with("drive", "file")
        self.repo.replace_acl.assert_not_awaited()

    async def test_identical_acl_is_not_written(self):
        self.repo.chunks.return_value = [{"chunk_id": "same", **acl([USER, USER])}]
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
        self.assertEqual(result["status"], "unchanged")
        self.repo.replace_acl.assert_not_awaited()

    async def test_partial_merge_is_not_reported_as_success(self):
        self.repo.chunks.return_value = [{"chunk_id": "different", **acl()}]
        self.repo.replace_acl.return_value = ([], ["different"])
        result = await self.service.sync_document(self.graph, self.repo, "drive", self.doc, False)
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["updated_chunks"], 0)

    async def test_site_continues_after_document_error(self):
        graph = self.graph
        graph.drives = lambda site_id: stream([{"id": "drive"}])
        graph.documents = lambda drive_id: stream([{"id": "bad"}, {"id": "good"}])
        graph.permissions.side_effect = [SharePointAclError("Denied"), []]
        self.repo.chunks.return_value = []
        result = await self.service.sync_site(graph, self.repo, "site", True)
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["documents_scanned"], 2)
        self.assertEqual(result["documents_failed"], 1)
        self.assertEqual(result["results"][1]["status"], "not_indexed")

    async def test_remote_shortcut_is_not_followed(self):
        result = await self.service.sync_document(self.graph, self.repo, "drive", {"id": "remote", "remoteItem": {}}, False)
        self.assertEqual(result["status"], "skipped")
        self.graph.permissions.assert_not_awaited()
