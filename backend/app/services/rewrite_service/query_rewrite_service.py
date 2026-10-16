import logging

from app.core.settings import settings
from app.services.llm.azure_openai_service import get_shared_azure_openai_service


logger = logging.getLogger(__name__)


class QueryRewriteService:
    PROMPT = """
Bạn là bộ máy rewrite câu hỏi cho hệ thống RAG.

Nhiệm vụ:

- Dựa vào lịch sử hội thoại history.
- Nếu câu hỏi hiện tại thiếu ngữ cảnh không rõ ràng thì bổ sung.
- Nếu câu hỏi hiện tại đã đầy đủ thì giữ nguyên.
- Chỉ trả về câu hỏi hoàn chỉnh.
- Không giải thích.

History:
{history}

Question:
{question}
"""

    @staticmethod
    async def rewrite(history: str, question: str) -> str:
        prompt = QueryRewriteService.PROMPT.format(
            history=history,
            question=question,
        )
        try:
            result = await get_shared_azure_openai_service().generate(
                model=settings.AZURE_OPENAI_REWRITE_DEPLOYMENT,
                prompt=prompt,
            )
            return result.strip() or question
        except Exception:
            logger.exception("Azure query rewrite failed")
            return question
