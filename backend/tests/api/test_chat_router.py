import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.v1 import chat_router
from app.core.database import get_db
from app.main import app
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.azure.azure_search_service import AzureSearchService
from app.services.rag.rag_service import RagService


CHAT_CONFIG = {
    "model": "gpt-test",
    "system_prompt": "History: {{history}}\nContext: {{context}}\nQ: {{question}}",
    "temperature": 1.0,
    "max_tokens": 100,
}


def chunk(chunk_id, source_file, content, score=1.0):
    return {
        "score": score,
        "chunk_id": chunk_id,
        "content": content,
        "source_file": source_file,
        "source_url": f"https://sp/{source_file}",
        "drive_id": "d1",
        "drive_item_id": f"i-{chunk_id}",
    }


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        events.append((
            lines[0].removeprefix("event: "),
            json.loads(lines[1].removeprefix("data: ")),
        ))
    return events


def body(mode="INTERNAL", **extra):
    return {
        "conversation_id": "11111111-1111-1111-1111-111111111111",
        "question": "Quy trình nghỉ phép?",
        "microsoft_object_id": "user-1",
        "group_ids": ["g1"],
        "model_id": "22222222-2222-2222-2222-222222222222",
        "mode": mode,
        **extra,
    }


async def fake_db():
    yield None


class ChatRouterTest(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)
        self.llm_messages = []

        async def chat_stream(model, messages, temperature, max_completion_tokens):
            self.llm_messages.append(messages)
            for token in ["Nghỉ ", "phép ", "5 ngày."]:
                yield token

        self.patches = [
            patch.object(
                chat_router.ChatConfigCache,
                "get_top_k",
                AsyncMock(return_value=7),
            ),
            patch.object(
                RagService,
                "load_chat_config",
                AsyncMock(return_value=CHAT_CONFIG),
            ),
            patch.object(
                chat_router.RagService().llm,
                "chat_stream",
                chat_stream,
            ),
            patch.object(ConversationRepository, "create", AsyncMock()),
            patch.object(ConversationRepository, "get_by_id", AsyncMock()),
            patch.object(MessageRepository, "create", AsyncMock()),
            patch.object(MessageRepository, "get_recent_message", AsyncMock()),
        ]
        self.mocks = [p.start() for p in self.patches]

    def tearDown(self):
        for p in self.patches:
            p.stop()
        app.dependency_overrides.clear()

    def assert_no_db_writes(self):
        ConversationRepository.create.assert_not_called()
        ConversationRepository.get_by_id.assert_not_called()
        MessageRepository.create.assert_not_called()
        MessageRepository.get_recent_message.assert_not_called()

    def test_query_internal_uses_top_k_chunks_without_history_or_db_writes(self):
        chunks = [
            chunk("c1", "a.docx", "Nghỉ phép năm 12 ngày", 3),
            chunk("c2", "b.docx", "Đơn nghỉ phép gửi HR", 2),
            chunk("c3", "a.docx", "Nghỉ ốm cần giấy", 1),
        ]

        with patch.object(
            AzureSearchService, "retrieve", AsyncMock(return_value=chunks)
        ) as retrieve:
            response = self.client.post("/chat/query", json=body())

        self.assertEqual(response.status_code, 200)
        events = parse_sse(response.text)
        self.assertEqual(
            [e[0] for e in events],
            ["metadata", "answer", "answer", "answer", "done"],
        )
        retrieve.assert_awaited_once_with(
            question="Quy trình nghỉ phép?",
            top_k=7,
            user_object_id="user-1",
            group_ids=["g1"],
        )
        metadata, done = events[0][1], events[-1][1]
        self.assertEqual(metadata["conversation_id"], body()["conversation_id"])
        self.assertEqual(
            [s["source_file"] for s in metadata["sources"]],
            ["a.docx", "b.docx"],
        )
        self.assertEqual(done["answer"], "Nghỉ phép 5 ngày.")

        system_prompt = self.llm_messages[0][0]["content"]
        self.assertIn("Nghỉ phép năm 12 ngày", system_prompt)
        self.assertIn("Đơn nghỉ phép gửi HR", system_prompt)
        self.assertIn("Nghỉ ốm cần giấy", system_prompt)
        self.assertIn("History: \n", system_prompt)
        self.assertIn("Q: Quy trình nghỉ phép?", system_prompt)
        self.assertNotIn("{{", system_prompt)
        self.assert_no_db_writes()

    def test_helpdesk_uses_default_top_k_when_config_missing(self):
        chat_router.ChatConfigCache.get_top_k.return_value = None

        with patch.object(
            AzureSearchService, "retrieve_helpdesk", AsyncMock(return_value=[])
        ) as retrieve:
            response = self.client.post("/chat/helpdesk", json=body())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            retrieve.await_args.kwargs["top_k"],
            chat_router.HELPDESK_DEFAULT_TOP_K,
        )
        self.assertEqual(parse_sse(response.text)[-1][0], "done")
        self.assert_no_db_writes()

    def test_public_mode_skips_retrieval(self):
        async def chat_stream(model, messages, temperature, max_completion_tokens):
            for token in ['{"answer": "Xin', ' chào", "sources": [{"name": "Model Knowledge"}]}']:
                yield token

        with patch.object(
            AzureSearchService, "retrieve", AsyncMock()
        ) as retrieve, patch.object(
            chat_router.RagService().llm, "chat_stream", chat_stream
        ):
            response = self.client.post("/chat/query", json=body(mode="PUBLIC"))

        retrieve.assert_not_called()
        events = parse_sse(response.text)
        self.assertEqual(events[0][1]["sources"], None)
        self.assertEqual(events[-1][1]["answer"], "Xin chào")
        self.assertEqual(events[-1][1]["sources"], [{"name": "Model Knowledge"}])

    def test_missing_conversation_id_is_generated(self):
        with patch.object(AzureSearchService, "retrieve", AsyncMock(return_value=[])):
            response = self.client.post(
                "/chat/query",
                json={k: v for k, v in body().items() if k != "conversation_id"},
            )

        conversation_id = parse_sse(response.text)[0][1]["conversation_id"]
        self.assertEqual(len(conversation_id), 36)
        self.assert_no_db_writes()

    def test_missing_model_returns_404_before_stream(self):
        RagService.load_chat_config.side_effect = LookupError("AI Model not found.")

        with patch.object(AzureSearchService, "retrieve", AsyncMock(return_value=[])):
            response = self.client.post("/chat/query", json=body())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "AI Model not found.")

    def test_invalid_mode_returns_400(self):
        RagService.load_chat_config.side_effect = ValueError("Invalid chat mode.")

        with patch.object(AzureSearchService, "retrieve", AsyncMock(return_value=[])):
            response = self.client.post("/chat/query", json=body(mode="HELPDESK"))

        self.assertEqual(response.status_code, 400)

    def test_empty_object_id_returns_400_before_stream(self):
        with patch.object(AzureSearchService, "retrieve", AsyncMock()) as retrieve:
            response = self.client.post(
                "/chat/query",
                json=body(microsoft_object_id="  "),
            )

        self.assertEqual(response.status_code, 400)
        retrieve.assert_not_called()

    def test_retrieval_failure_emits_error_event(self):
        with patch.object(
            AzureSearchService,
            "retrieve",
            AsyncMock(side_effect=RuntimeError("search down")),
        ):
            response = self.client.post("/chat/query", json=body())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [e[0] for e in parse_sse(response.text)],
            ["error"],
        )
        self.assertEqual(self.llm_messages, [])

    def test_llm_failure_emits_error_event(self):
        async def broken(model, messages, temperature, max_completion_tokens):
            yield "Partial"
            raise RuntimeError("Azure down")

        with patch.object(
            AzureSearchService, "retrieve", AsyncMock(return_value=[])
        ), patch.object(chat_router.RagService().llm, "chat_stream", broken):
            response = self.client.post("/chat/query", json=body())

        self.assertEqual(
            [e[0] for e in parse_sse(response.text)],
            ["metadata", "answer", "error"],
        )


class SearchTopKTest(unittest.IsolatedAsyncioTestCase):

    async def test_embeds_question_and_returns_top_k_chunks(self):
        embeddings = MagicMock()
        embeddings.embeddings.create = AsyncMock(
            return_value=SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2])]
            )
        )

        docs = [
            {"@search.score": 2.0, "chunk_id": "c1", "chunk": "A", "source_file": "a.docx"},
            {"@search.score": 1.0, "chunk_id": "c2", "chunk": "B", "source_file": "b.docx"},
        ]

        async def results():
            for doc in docs:
                yield doc

        search_client = MagicMock()
        search_client.search = AsyncMock(return_value=results())

        with patch.object(
            AzureSearchService, "_get_async_embedding_client", return_value=embeddings
        ), patch.object(
            AzureSearchService, "_get_async_search_client", return_value=search_client
        ):
            chunks = await AzureSearchService.retrieve_helpdesk(
                question="VPN lỗi",
                top_k=5,
                user_object_id="u1",
                group_ids=["g1"],
            )

        self.assertEqual([c["chunk_id"] for c in chunks], ["c1", "c2"])
        self.assertEqual(chunks[0]["content"], "A")
        self.assertEqual(embeddings.embeddings.create.await_args.kwargs["input"], "VPN lỗi")

        search_kwargs = search_client.search.await_args.kwargs
        self.assertEqual(search_kwargs["search_text"], "VPN lỗi")
        self.assertEqual(search_kwargs["top"], 5)
        self.assertNotIn("text_vector", search_kwargs["select"])
        self.assertIn("chunk", search_kwargs["select"])
        self.assertEqual(search_kwargs["vector_queries"][0].k_nearest_neighbors, 5)
        self.assertTrue(search_kwargs["filter"].startswith("(workspace eq 'HELPDESK') and ("))
        self.assertIn("allowed_user_ids/any(u: u eq 'u1')", search_kwargs["filter"])


class RetrieveFullDocumentTest(unittest.IsolatedAsyncioTestCase):

    def make_clients(self, *search_results):
        embeddings = MagicMock()
        embeddings.embeddings.create = AsyncMock(
            return_value=SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2])]
            )
        )

        def as_async(docs):
            async def gen():
                for doc in docs:
                    yield doc
            return gen()

        search_client = MagicMock()
        search_client.search = AsyncMock(
            side_effect=[as_async(docs) for docs in search_results]
        )
        return embeddings, search_client

    async def retrieve(self, embeddings, search_client):
        with patch.object(
            AzureSearchService, "_get_async_embedding_client", return_value=embeddings
        ), patch.object(
            AzureSearchService, "_get_async_search_client", return_value=search_client
        ):
            return await AzureSearchService.retrieve(
                question="Hợp đồng BĐS",
                top_k=10,
                user_object_id="u1",
                group_ids=["g1"],
            )

    async def test_top1_chunk_then_whole_document_with_best_first(self):
        best = {"@search.score": 0.9, "chunk_id": "c2", "parent_id": "doc-1", "chunk": "B", "source_file": "a.docx"}
        document = [
            {"@search.score": 1.0, "chunk_id": "c1", "parent_id": "doc-1", "chunk": "A", "source_file": "a.docx"},
            {"@search.score": 1.0, "chunk_id": "c2", "parent_id": "doc-1", "chunk": "B", "source_file": "a.docx"},
            {"@search.score": 1.0, "chunk_id": "c3", "parent_id": "doc-1", "chunk": "C", "source_file": "a.docx"},
        ]
        embeddings, search_client = self.make_clients([best], document)

        chunks = await self.retrieve(embeddings, search_client)

        self.assertEqual([c["chunk_id"] for c in chunks], ["c2", "c1", "c3"])
        self.assertEqual(chunks[0]["score"], 0.9)
        self.assertIsNone(chunks[1]["score"])
        embeddings.embeddings.create.assert_awaited_once()

        first, second = [c.kwargs for c in search_client.search.await_args_list]
        self.assertEqual(first["top"], 1)
        self.assertEqual(first["vector_queries"][0].k_nearest_neighbors, 10)
        self.assertEqual(second["search_text"], "*")
        self.assertNotIn("vector_queries", second)
        self.assertEqual(second["top"], AzureSearchService.MAX_DOCUMENT_CHUNKS)
        self.assertTrue(second["filter"].startswith("(parent_id eq 'doc-1') and ("))
        self.assertIn("allowed_group_ids/any(g: g eq 'g1')", second["filter"])
        self.assertNotIn("text_vector", second["select"])

    async def test_no_match_returns_empty_without_second_search(self):
        embeddings, search_client = self.make_clients([])

        self.assertEqual(await self.retrieve(embeddings, search_client), [])
        self.assertEqual(search_client.search.await_count, 1)

    async def test_parent_id_is_escaped(self):
        best = {"chunk_id": "c1", "parent_id": "o'brien", "chunk": "A"}
        embeddings, search_client = self.make_clients([best], [best])

        await self.retrieve(embeddings, search_client)

        second = search_client.search.await_args_list[1].kwargs
        self.assertTrue(second["filter"].startswith("(parent_id eq 'o''brien')"))


class ChatConfigCacheTest(unittest.IsolatedAsyncioTestCase):

    DATA = {
        "prompts": {"INTERNAL": "Context: {{context}}"},
        "models": {"22222222-2222-2222-2222-222222222222": "gpt-5.1"},
        "model_configs": {"CHAT_RAG": {"temperature": 1.0, "max_tokens": 2000}},
        "top_k": {"CHAT_RAG": 10},
    }

    def setUp(self):
        self.cache = chat_router.ChatConfigCache
        self.cache.invalidate()
        self.cache._lock = None
        self.cache._refresh_task = None

    def tearDown(self):
        self.cache.invalidate()

    async def test_load_chat_config_reads_cache_once(self):
        from app.enums.prompt_code import PromptCode

        load = AsyncMock(return_value=self.DATA)

        with patch.object(self.cache, "_load", load):
            for _ in range(3):
                config = await RagService().load_chat_config(
                    db=None,
                    model_id="22222222-2222-2222-2222-222222222222",
                    mode=PromptCode.INTERNAL,
                    workspace_code="CHAT_RAG",
                )

        self.assertEqual(load.await_count, 1)
        self.assertEqual(config["model"], "gpt-5.1")
        self.assertEqual(config["max_tokens"], 2000)
        self.assertEqual(await self.cache.get_top_k("CHAT_RAG"), 10)

    async def test_unknown_model_refreshes_at_most_once_then_404(self):
        from app.enums.prompt_code import PromptCode

        load = AsyncMock(return_value=self.DATA)

        with patch.object(self.cache, "_load", load):
            for _ in range(3):
                with self.assertRaises(LookupError):
                    await RagService().load_chat_config(
                        db=None,
                        model_id="33333333-3333-3333-3333-333333333333",
                        mode=PromptCode.INTERNAL,
                        workspace_code="CHAT_RAG",
                    )

        # 1 lần load đầu, các lần miss tiếp theo nằm trong MIN_REFRESH_SECONDS
        self.assertEqual(load.await_count, 1)

    async def test_expired_cache_returns_stale_and_refreshes_in_background(self):
        new_data = {**self.DATA, "top_k": {"CHAT_RAG": 5}}
        load = AsyncMock(side_effect=[self.DATA, new_data])

        with patch.object(self.cache, "_load", load):
            self.assertEqual(await self.cache.get_top_k("CHAT_RAG"), 10)
            self.cache._loaded_at -= self.cache.TTL_SECONDS + 1

            self.assertEqual(await self.cache.get_top_k("CHAT_RAG"), 10)
            await self.cache._refresh_task

            self.assertEqual(await self.cache.get_top_k("CHAT_RAG"), 5)


if __name__ == "__main__":
    unittest.main()
