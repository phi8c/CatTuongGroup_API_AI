import io
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from starlette.responses import StreamingResponse

from app.api.v1.contract_router import (
    analyze_contract_advanced,
    analyze_contract_advanced_company_rule,
    analyze_contract_advanced_legal,
    legal_chat,
)
from app.schemas.contract_advanced_request import (
    ContractLegalReviewRequest,
    LegalChatRequest,
)
from app.services.contract.legal_chat_service import LegalChatService
from app.services.contract.legal_contract_analysis_service import (
    LegalContractAnalysisService,
)
from app.services.contract.contract_advanced_service import (
    ContractAdvancedService,
)


class ContractAdvancedRouterTest(unittest.IsolatedAsyncioTestCase):

    async def test_temporary_file_is_removed(self):
        observed_path = None

        async def analyze(
            service,
            db,
            file_path,
            model_id,
        ):
            nonlocal observed_path
            observed_path = Path(file_path)
            self.assertTrue(observed_path.is_file())
            self.assertEqual(
                observed_path.read_bytes(),
                b"contract",
            )
            return {
                "company_rule_review": {"results": []},
                "legal_review": {"results": []},
            }

        upload = UploadFile(
            filename="contract.pdf",
            file=io.BytesIO(b"contract"),
        )

        with patch.object(
            ContractAdvancedService,
            "analyze",
            new=analyze,
        ):
            result = await analyze_contract_advanced(
                file=upload,
                model_id=uuid4(),
                db=None,
            )

        self.assertEqual(result["legal_review"], {"results": []})
        self.assertIsNotNone(observed_path)
        self.assertFalse(observed_path.exists())

    async def test_unsupported_file_type_is_rejected(self):
        upload = UploadFile(
            filename="contract.txt",
            file=io.BytesIO(b"contract"),
        )

        with self.assertRaises(HTTPException) as error:
            await analyze_contract_advanced(
                file=upload,
                model_id=uuid4(),
                db=None,
            )

        self.assertEqual(error.exception.status_code, 400)

    async def test_company_rule_endpoint_removes_temporary_file(self):
        observed_path = None

        async def analyze_company_rule(
            service,
            db,
            file_path,
            model_id,
        ):
            nonlocal observed_path
            observed_path = Path(file_path)
            self.assertTrue(observed_path.is_file())
            return {
                "company_rule_review": {"results": []},
                "contract_content": "Extracted contract",
            }

        upload = UploadFile(
            filename="contract.docx",
            file=io.BytesIO(b"contract"),
        )

        with patch.object(
            ContractAdvancedService,
            "analyze_company_rule",
            new=analyze_company_rule,
        ):
            result = await analyze_contract_advanced_company_rule(
                file=upload,
                model_id=uuid4(),
                db=None,
            )

        self.assertEqual(
            result["contract_content"],
            "Extracted contract",
        )
        self.assertNotIn("legal_checks", result)
        self.assertFalse(observed_path.exists())

    async def test_legal_endpoint_passes_extracted_contract(self):
        model_id = uuid4()
        request = ContractLegalReviewRequest(
            model_id=model_id,
            output_extract=" Contract body ",
        )

        calls = []

        async def analyze(service, **kwargs):
            calls.append(kwargs)
            yield {"event": "started", "data": {"total": 0}}
            yield {"event": "completed", "data": {"total": 0}}

        with patch.object(
            LegalContractAnalysisService,
            "analyze",
            new=analyze,
        ):
            result = await analyze_contract_advanced_legal(
                request=request,
                db=None,
            )

            self.assertIsInstance(result, StreamingResponse)
            body = "".join(
                [chunk async for chunk in result.body_iterator]
            )
        self.assertEqual(
            calls,
            [{
                "db": None,
                "model_id": model_id,
                "output_extract": "Contract body",
            }],
        )
        self.assertIn("event: started", body)
        self.assertIn("event: completed", body)

    async def test_legal_chat_endpoint_uses_json_request(self):
        model_id = uuid4()
        request = LegalChatRequest(
            model_id=model_id,
            question=" Question ",
            extracted_contract=" Contract body ",
        )

        with patch.object(
            LegalChatService,
            "chat",
            new=AsyncMock(
                return_value={
                    "answer": "Answer",
                    "retrieval_seeds": {},
                    "sources": [],
                }
            ),
        ) as chat:
            result = await legal_chat(request=request, db=None)

        chat.assert_awaited_once_with(
            db=None,
            model_id=model_id,
            question="Question",
            extracted_contract="Contract body",
        )
        self.assertEqual(result["answer"], "Answer")
