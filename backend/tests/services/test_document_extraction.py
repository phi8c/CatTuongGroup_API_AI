import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils.extract.document_intelligent import DocumentExtractor
from app.services.contract.contract_service import DocumentExtractor as ContractExtractor
from app.services.recruitment.analyze_candidate_service import (
    DocumentExtractor as CandidateExtractor,
)


class AzureDocumentExtractionTest(unittest.TestCase):
    def test_contract_and_candidate_use_azure_extractor(self):
        self.assertIs(ContractExtractor, DocumentExtractor)
        self.assertIs(CandidateExtractor, DocumentExtractor)

    def test_markdown_and_text_survive_azure_extraction(self):
        for extension in (".pdf", ".docx"):
            for paragraphs in ([], [SimpleNamespace(content="Contract", role="title")]):
                with self.subTest(extension=extension, paragraphs=bool(paragraphs)):
                    document = SimpleNamespace(
                        content="# Contract", paragraphs=paragraphs,
                        tables=[], pages=[object()], figures=[],
                    )
                    client = MagicMock()
                    client.begin_analyze_document.return_value.result.return_value = document
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / ("sample" + extension)
                        path.write_bytes(b"test document")
                        with patch.object(DocumentExtractor, "_get_client", return_value=client):
                            result = DocumentExtractor.extract(str(path))
                    self.assertEqual(result.markdown, "# Contract")
                    self.assertEqual(result.text, "Contract" if paragraphs else "# Contract")
                    self.assertEqual(result.metadata["page_count"], 1)
                    self.assertEqual(result.file_name, "sample" + extension)
                    self.assertEqual(
                        client.begin_analyze_document.call_args.kwargs["output_content_format"],
                        "markdown",
                    )
