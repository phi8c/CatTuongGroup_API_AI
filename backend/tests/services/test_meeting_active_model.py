import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.ai_model_repository import AIModelRepository
from app.schemas.analyze_meeting_request import AnalyzeMeetingRequest
from app.services.azure.meeting_analysis_service import MeetingAnalysisService


class MeetingActiveModelTest(unittest.IsolatedAsyncioTestCase):

    async def test_repository_selects_only_one_active_model(self):
        result = MagicMock()
        selected = object()
        result.scalar_one_or_none.return_value = selected
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        self.assertIs(await AIModelRepository.get_first_active(db), selected)
        statement = db.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        self.assertIn("ai_models.is_active = true", sql)
        self.assertIn("LIMIT 1", sql)
        self.assertIn("ai_models.display_name ASC, ai_models.id ASC", sql)

    async def test_service_uses_active_model_when_id_is_missing(self):
        await self._check_selection(None)

    async def test_service_honors_explicit_model_id(self):
        await self._check_selection(uuid4())

    async def _check_selection(self, model_id):
        model = SimpleNamespace(model_name="azure-deployment")
        prompt = SimpleNamespace(system_prompt="Analyze", user_prompt="{transcript}")
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='{"summary":"ok"}')
        with patch("app.services.azure.meeting_analysis_service.AIPromptRepository.get_by_code", new=AsyncMock(return_value=prompt)), patch.object(
            AIModelRepository, "get_by_id", new=AsyncMock(return_value=model)
        ) as by_id, patch.object(
            AIModelRepository, "get_first_active", new=AsyncMock(return_value=model)
        ) as active, patch("app.services.azure.meeting_analysis_service.AzureOpenAIService", return_value=llm):
            result = await MeetingAnalysisService.analyze(None, "transcript", model_id)
        self.assertEqual(result, {"summary": "ok"})
        self.assertEqual(llm.generate.await_args.kwargs["model"], "azure-deployment")
        if model_id is None:
            active.assert_awaited_once_with(db=None)
            by_id.assert_not_awaited()
        else:
            by_id.assert_awaited_once_with(db=None, id=model_id)
            active.assert_not_awaited()

    async def test_no_active_model_does_not_call_azure(self):
        prompt = SimpleNamespace(system_prompt="Analyze", user_prompt="{transcript}")
        with patch("app.services.azure.meeting_analysis_service.AIPromptRepository.get_by_code", new=AsyncMock(return_value=prompt)), patch.object(
            AIModelRepository, "get_first_active", new=AsyncMock(return_value=None)
        ), patch("app.services.azure.meeting_analysis_service.AzureOpenAIService") as llm:
            with self.assertRaisesRegex(LookupError, "No active AI model"):
                await MeetingAnalysisService.analyze(None, "transcript")
        llm.assert_not_called()

    def test_request_accepts_missing_model_id(self):
        self.assertIsNone(AnalyzeMeetingRequest(transcript="transcript").model_id)
