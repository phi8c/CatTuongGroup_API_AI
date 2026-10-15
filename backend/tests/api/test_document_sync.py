import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1 import document_router
from app.services.sync_jobs.sync_state import SyncState


@asynccontextmanager
async def fake_session():
    yield None


def make_request(body):
    request = MagicMock()

    if isinstance(body, Exception):
        request.json = AsyncMock(side_effect=body)
    else:
        request.json = AsyncMock(return_value=body)

    return request


def make_chunk(chunk_id, security_level="PUBLIC"):
    return {
        "id": chunk_id,
        "title": "doc.docx",
        "content": "content",
        "processed": False,
        "metadata": {
            "security_level": security_level,
            "department": "HR",
        },
    }


class PostIngestionPipelineTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        document_router._running_parent_ids.clear()
        document_router._pipeline_tasks.clear()
        document_router._failed_in_batch = False
        SyncState.status = "RUNNING"

    async def _drain(self):
        while document_router._pipeline_tasks:
            await asyncio.gather(*list(document_router._pipeline_tasks))

    async def test_success_updates_sensitivity_and_completes(self):
        chunks = [make_chunk("c1"), make_chunk("c2", "INTERNAL")]

        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            return_value=chunks,
        ), patch.object(
            document_router.AzureChunkRepository,
            "update_sensitivity",
        ) as update, patch.object(
            document_router,
            "AsyncSessionLocal",
            fake_session,
        ):
            response = await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            await self._drain()

        self.assertEqual(response, {"status": "accepted"})
        self.assertEqual(
            [c.kwargs for c in update.call_args_list],
            [
                {"chunk_id": "c1", "sensitivity": 1},
                {"chunk_id": "c2", "sensitivity": 2},
            ],
        )
        self.assertEqual(SyncState.status, "COMPLETED")
        self.assertEqual(document_router._running_parent_ids, set())

    async def test_no_chunks_completes_without_error(self):
        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            return_value=[],
        ), patch.object(
            document_router.AzureChunkRepository,
            "update_sensitivity",
        ) as update:
            await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            await self._drain()

        update.assert_not_called()
        self.assertEqual(SyncState.status, "COMPLETED")

    async def test_missing_parent_id_is_ignored(self):
        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
        ) as load:
            response = await document_router.sync_completed(
                make_request({}),
            )

        self.assertEqual(response["status"], "ignored")
        load.assert_not_called()
        self.assertEqual(SyncState.status, "FAILED")

    async def test_invalid_json_body_is_ignored(self):
        response = await document_router.sync_completed(
            make_request(json.JSONDecodeError("bad", "", 0)),
        )

        self.assertEqual(response["status"], "ignored")

    async def test_duplicate_callback_runs_pipeline_once(self):
        release = asyncio.Event()
        calls = []

        def load(parent_id):
            calls.append(parent_id)
            return []

        async def slow_to_thread(func, *args, **kwargs):
            await release.wait()
            return func(*args, **kwargs)

        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            side_effect=load,
        ), patch.object(
            document_router.asyncio,
            "to_thread",
            slow_to_thread,
        ):
            await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            second = await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            self.assertEqual(SyncState.status, "RUNNING")
            release.set()
            await self._drain()

        self.assertEqual(second, {"status": "accepted"})
        self.assertEqual(calls, ["p1"])
        self.assertEqual(SyncState.status, "COMPLETED")

    async def test_chunk_error_does_not_stop_other_chunks(self):
        chunks = [make_chunk("bad"), make_chunk("good")]

        def update(chunk_id, sensitivity):
            if chunk_id == "bad":
                raise RuntimeError("search down")

        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            return_value=chunks,
        ), patch.object(
            document_router.AzureChunkRepository,
            "update_sensitivity",
            side_effect=update,
        ) as update_mock, patch.object(
            document_router,
            "AsyncSessionLocal",
            fake_session,
        ):
            await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            await self._drain()

        self.assertEqual(update_mock.call_count, 2)
        self.assertEqual(SyncState.status, "FAILED")
        self.assertEqual(document_router._running_parent_ids, set())

    async def test_load_error_releases_state(self):
        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            side_effect=RuntimeError("search down"),
        ):
            await document_router.sync_completed(
                make_request({"parent_id": "p1"}),
            )
            await self._drain()

        self.assertEqual(SyncState.status, "FAILED")
        self.assertEqual(document_router._running_parent_ids, set())

    async def test_status_waits_for_all_parallel_pipelines(self):
        release = asyncio.Event()

        async def to_thread(func, *args, **kwargs):
            if args and args[0] == "slow":
                await release.wait()
            return func(*args, **kwargs)

        with patch.object(
            document_router.ChunkRepository,
            "get_unprocessed_chunks",
            return_value=[],
        ), patch.object(
            document_router.asyncio,
            "to_thread",
            to_thread,
        ):
            await document_router.sync_completed(
                make_request({"parent_id": "slow"}),
            )
            await document_router.sync_completed(
                make_request({"parent_id": "fast"}),
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertEqual(SyncState.status, "RUNNING")
            release.set()
            await self._drain()

        self.assertEqual(SyncState.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
