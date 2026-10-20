import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.sharepoint.sharepoint_acl_graph import SharePointAclError
from app.services.sharepoint.sharepoint_acl_sync_service import SharePointAclSyncService


class DocumentAclRouterTest(unittest.TestCase):
    def test_endpoint_passes_site_and_dry_run_and_exposes_summary(self):
        expected = {"site_id": "site", "dry_run": True, "status": "completed", "results": []}
        with patch.dict(os.environ, {"CHAT_WARMUP_ENABLED": "false"}), patch.object(
            SharePointAclSyncService, "sync", new=AsyncMock(return_value=expected)
        ) as sync, TestClient(app) as client:
            response = client.post("/documents/acl/sync", json={"site_id": " site ", "dry_run": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        sync.assert_awaited_once_with(site_id="site", dry_run=True)

    def test_invalid_request_does_not_call_graph_or_index(self):
        with patch.object(SharePointAclSyncService, "sync", new=AsyncMock()) as sync, TestClient(app) as client:
            for data in [{}, {"site_id": ""}, {"site_id": "   "}]:
                response = client.post("/documents/acl/sync", json=data)
                self.assertEqual(response.status_code, 422)
        sync.assert_not_awaited()

    def test_upstream_error_returns_502_without_credentials(self):
        with patch.object(
            SharePointAclSyncService, "sync", new=AsyncMock(side_effect=SharePointAclError("Forbidden"))
        ), TestClient(app) as client:
            response = client.post("/documents/acl/sync", json={"site_id": "site"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("Forbidden", response.text)
