import unittest

from fastapi.testclient import TestClient

from app.main import app


class AiBackendCleanupTest(unittest.TestCase):

    def test_startup_keeps_ai_endpoints_and_removes_retired_routes(self):
        with TestClient(app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
            paths = response.json()["paths"]

        for path in (
            "/chat/query", "/chat/helpdesk", "/meeting/analyze",
            "/contracts/analyze-advanced/company-rule",
            "/contracts/analyze-advanced/legal", "/contracts/legal-chat",
            "/documents/sync", "/documents/sync-completed",
        ):
            self.assertIn(path, paths)

        for path in paths:
            self.assertFalse(path.startswith((
                "/auth", "/planner", "/bot", "/tags", "/roles",
                "/policy", "/permissions", "/tag-role",
            )), path)
            self.assertNotIn("/executive-data", path)

    def test_chat_permission_contract_has_no_internal_login_dependency(self):
        schema = app.openapi()
        fields = schema["components"]["schemas"]["ChatRequest"]["properties"]
        self.assertIn("microsoft_object_id", fields)
        self.assertIn("group_ids", fields)
        self.assertNotIn("role_id", fields)
        for path in ("/chat/query", "/chat/helpdesk"):
            self.assertFalse(schema["paths"][path]["post"].get("security"))
