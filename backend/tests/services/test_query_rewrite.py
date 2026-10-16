import unittest
from unittest.mock import AsyncMock, patch

from app.core.settings import settings
from app.services.rewrite_service.query_rewrite_service import QueryRewriteService


class QueryRewriteTest(unittest.IsolatedAsyncioTestCase):

    async def test_rewrite_uses_azure_deployment_and_existing_prompt(self):
        service = AsyncMock()
        service.generate.return_value = "  contextual question  "
        with patch(
            "app.services.rewrite_service.query_rewrite_service.get_shared_azure_openai_service",
            return_value=service,
        ):
            result = await QueryRewriteService.rewrite("previous messages", "question")
        self.assertEqual(result, "contextual question")
        service.generate.assert_awaited_once_with(
            model=settings.AZURE_OPENAI_REWRITE_DEPLOYMENT,
            prompt=QueryRewriteService.PROMPT.format(history="previous messages", question="question"),
        )

    async def test_azure_failure_keeps_original_question(self):
        service = AsyncMock()
        service.generate.side_effect = RuntimeError("Azure unavailable")
        with patch(
            "app.services.rewrite_service.query_rewrite_service.get_shared_azure_openai_service",
            return_value=service,
        ), self.assertLogs("app.services.rewrite_service.query_rewrite_service", level="ERROR"):
            result = await QueryRewriteService.rewrite("history", "original")
        self.assertEqual(result, "original")

    async def test_empty_azure_response_keeps_original_question(self):
        service = AsyncMock()
        service.generate.return_value = "   "
        with patch(
            "app.services.rewrite_service.query_rewrite_service.get_shared_azure_openai_service",
            return_value=service,
        ):
            result = await QueryRewriteService.rewrite("history", "original")
        self.assertEqual(result, "original")
