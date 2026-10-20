from dataclasses import dataclass
from pathlib import Path
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from app.core.settings import (
    settings,
)


@dataclass
class DocumentExtraction:
    file_name: str
    file_path: str
    file_extension: str

    text: str

    paragraphs: list[dict[str, Any]]
    tables: list[dict[str, Any]]

    metadata: dict[str, Any]

    document: AnalyzeResult
    markdown: str = ""


class DocumentExtractor:
    """
    Document extractor using Azure Document Intelligence.

    Supported formats:
    - PDF
    - DOCX
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".docx",
    }

    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = DocumentIntelligenceClient(
                endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
                credential=AzureKeyCredential(
                    settings.AZURE_DOCUMENT_INTELLIGENCE_KEY,
                ),
            )
        return cls._client

    @staticmethod
    def extract(
        file_path: str,
    ) -> DocumentExtraction:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        extension = path.suffix.lower()

        if extension not in DocumentExtractor.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}"
            )

        with path.open("rb") as file:
            poller = DocumentExtractor._get_client().begin_analyze_document(
                model_id="prebuilt-layout",
                body=file,
                output_content_format="markdown",
            )

            document = poller.result()

        paragraphs = []

        for paragraph in document.paragraphs or []:
            paragraphs.append(
                {
                    "content": paragraph.content,
                    "role": getattr(
                        paragraph,
                        "role",
                        None,
                    ),
                }
            )

        tables = []

        for table in document.tables or []:
            rows = [
                [
                    ""
                    for _ in range(table.column_count)
                ]
                for _ in range(table.row_count)
            ]

            for cell in table.cells:
                rows[
                    cell.row_index
                ][
                    cell.column_index
                ] = cell.content

            tables.append(
                {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "rows": rows,
                }
            )

        text = "\n\n".join(
            paragraph["content"]
            for paragraph in paragraphs
            if paragraph["content"]
        )

        text = text or document.content or ""

        metadata = {
            "page_count": len(
                document.pages or []
            ),
            "paragraph_count": len(
                document.paragraphs or []
            ),
            "table_count": len(
                document.tables or []
            ),
            "figure_count": len(
                document.figures or []
            ),
        }

        return DocumentExtraction(
            file_name=path.name,
            file_path=str(path),
            file_extension=extension,
            text=text,
            paragraphs=paragraphs,
            tables=tables,
            metadata=metadata,
            document=document,
            markdown=document.content or text,
        )
