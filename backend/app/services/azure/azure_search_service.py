from azure.search.documents import (
    SearchClient
)

from azure.search.documents.aio import (
    SearchClient as AsyncSearchClient
)

from azure.search.documents.models import (
    VectorizedQuery
)

from azure.core.credentials import (
    AzureKeyCredential
)

from openai import (
    AzureOpenAI,
    AsyncAzureOpenAI,
)

from app.core.settings import settings


class AzureSearchService:

    @staticmethod
    def _escape_odata_value(value: str) -> str:

        return value.replace("'", "''")

    @staticmethod
    def build_acl_filter(
        user_object_id: str,
        group_ids: list[str],
    ) -> str:

        user_object_id = user_object_id.strip()

        if not user_object_id:
            raise ValueError("user_object_id must not be empty.")

        escaped_user_id = (
            AzureSearchService
            ._escape_odata_value(user_object_id)
        )
        filters = [
            "allowed_user_ids/any("
            f"u: u eq '{escaped_user_id}'"
            ")"
        ]
        normalized_group_ids = []
        seen_group_ids = set()

        for group_id in group_ids:
            group_id = str(group_id).strip()

            if not group_id or group_id in seen_group_ids:
                continue

            seen_group_ids.add(group_id)
            normalized_group_ids.append(
                AzureSearchService
                ._escape_odata_value(group_id)
            )

        if normalized_group_ids:
            group_filter = " or ".join(
                f"g eq '{group_id}'"
                for group_id in normalized_group_ids
            )
            filters.append(
                "allowed_group_ids/any("
                f"g: {group_filter}"
                ")"
            )

        return " or ".join(filters)
    
    
    
    
    # ------------------------------------------------------------
    # Chat retrieval:
    # - /chat/query: chunk khớp nhất -> toàn bộ chunk của document đó.
    # - /chat/helpdesk: top k chunk.
    # Client async được tạo 1 lần và dùng chung cho mọi request.
    # ------------------------------------------------------------

    _async_search_client: AsyncSearchClient | None = None

    _async_embedding_client: AsyncAzureOpenAI | None = None

    # Giới hạn số chunk khi lấy cả document (như logic cũ)
    MAX_DOCUMENT_CHUNKS = 1000

    # Chỉ lấy field cần dùng; không kéo text_vector (1536 số/chunk) về
    CHUNK_FIELDS = [
        "chunk_id",
        "parent_id",
        "title",
        "chunk",
        "source_file",
        "department",
        "owner_role",
        "security_level",
        "document_type",
        "sensitivity",
        "source_url",
        "drive_id",
        "drive_item_id",
    ]

    @classmethod
    def _get_async_search_client(cls) -> AsyncSearchClient:

        if cls._async_search_client is None:

            cls._async_search_client = AsyncSearchClient(
                endpoint=settings.AZURE_SEARCH_ENDPOINT,
                index_name=settings.AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
            )

        return cls._async_search_client

    @classmethod
    def _get_async_embedding_client(cls) -> AsyncAzureOpenAI:

        #
        # Client riêng cho embedding. Dùng chung client với chat stream thì
        # sau mỗi lượt stream, embedding phải mở lại kết nối (~1.2s thay vì ~0.4s).
        #

        if cls._async_embedding_client is None:

            cls._async_embedding_client = AsyncAzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_OPENAI_API_VERSION,
            )

        return cls._async_embedding_client

    @staticmethod
    async def warm_up():

        #
        # Mở sẵn kết nối TLS tới Azure OpenAI và Azure Search lúc khởi động,
        # tránh request chat đầu tiên phải chờ bắt tay (~2s).
        #

        await (
            AzureSearchService
            ._get_async_embedding_client()
            .embeddings
            .create(
                model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                input="warm up",
            )
        )

        results = await (
            AzureSearchService
            ._get_async_search_client()
            .search(
                search_text="*",
                filter="chunk_id eq '__warm_up__'",
                top=1,
            )
        )

        async for _ in results:
            pass

    @staticmethod
    def _to_chunk(doc) -> dict:

        return {
            "score": doc.get("@search.score"),
            "chunk_id": doc.get("chunk_id"),
            "parent_id": doc.get("parent_id"),
            "title": doc.get("title"),
            "content": doc.get("chunk"),
            "source_file": doc.get("source_file"),
            "department": doc.get("department"),
            "owner_role": doc.get("owner_role"),
            "security_level": doc.get("security_level"),
            "document_type": doc.get("document_type"),
            "sensitivity": doc.get("sensitivity"),
            "source_url": doc.get("source_url"),
            "drive_id": doc.get("drive_id"),
            "drive_item_id": doc.get("drive_item_id"),
        }

    @staticmethod
    async def search_top_k(
        question: str,
        top_k: int,
        user_object_id: str,
        group_ids: list[str],
        workspace: str | None = None,
        top: int | None = None,
    ) -> list[dict]:

        azure_filter = AzureSearchService.build_acl_filter(
            user_object_id=user_object_id,
            group_ids=group_ids,
        )

        if workspace:

            azure_filter = (
                f"(workspace eq '{AzureSearchService._escape_odata_value(workspace)}') "
                f"and ({azure_filter})"
            )

        embedding_response = await (
            AzureSearchService
            ._get_async_embedding_client()
            .embeddings
            .create(
                model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                input=question,
            )
        )

        vector_query = VectorizedQuery(
            vector=embedding_response.data[0].embedding,
            k_nearest_neighbors=top_k,
            fields="text_vector",
        )

        results = await (
            AzureSearchService
            ._get_async_search_client()
            .search(
                search_text=question,
                vector_queries=[vector_query],
                filter=azure_filter,
                top=top or top_k,
                select=AzureSearchService.CHUNK_FIELDS,
            )
        )

        return [
            AzureSearchService._to_chunk(doc)
            async for doc in results
        ]

    @staticmethod
    async def retrieve(
        question: str,
        top_k: int,
        user_object_id: str,
        group_ids: list[str],
    ):

        #
        # 1) Tìm chunk khớp nhất (hybrid, vector k = top_k, chỉ lấy 1 kết quả)
        #

        best_chunks = await AzureSearchService.search_top_k(
            question=question,
            top_k=top_k,
            user_object_id=user_object_id,
            group_ids=group_ids,
            top=1,
        )

        if not best_chunks:

            return []

        best = best_chunks[0]

        if not best.get("parent_id"):

            return best_chunks

        #
        # 2) Lấy toàn bộ chunk của document chứa chunk đó.
        #    Chỉ lọc (không chấm điểm), không kéo text_vector về.
        #

        acl_filter = AzureSearchService.build_acl_filter(
            user_object_id=user_object_id,
            group_ids=group_ids,
        )

        escaped_parent_id = AzureSearchService._escape_odata_value(
            str(best["parent_id"])
        )

        results = await (
            AzureSearchService
            ._get_async_search_client()
            .search(
                search_text="*",
                filter=(
                    f"(parent_id eq '{escaped_parent_id}') "
                    f"and ({acl_filter})"
                ),
                top=AzureSearchService.MAX_DOCUMENT_CHUNKS,
                select=AzureSearchService.CHUNK_FIELDS,
            )
        )

        other_chunks = []

        async for doc in results:

            if doc.get("chunk_id") == best["chunk_id"]:
                continue

            chunk = AzureSearchService._to_chunk(doc)
            chunk["score"] = None
            other_chunks.append(chunk)

        #
        # Index không có thứ tự chunk trong tài liệu,
        # nên đặt chunk khớp nhất lên đầu context.
        #

        return [best] + other_chunks

    @staticmethod
    def retrieve_contract_policy(
        question: str,
        top_k: int,
    ):

        if not question.strip():
            return []

        client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(
                settings.AZURE_SEARCH_KEY
            ),
        )

        openai_client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

        embedding_response = (
            openai_client
            .embeddings
            .create(
                model=(
                    settings
                    .AZURE_OPENAI_EMBEDDING_DEPLOYMENT
                ),
                input=question,
            )
        )

        vector_query = VectorizedQuery(
            vector=(
                embedding_response
                .data[0]
                .embedding
            ),
            k_nearest_neighbors=top_k,
            fields="text_vector",
        )

        results = client.search(
            search_text=question,
            vector_queries=[
                vector_query,
            ],
            filter=(
                "document_type eq 'CONTRACT_POLICY'"
            ),
            top=top_k,
        )

        return [
            {
                "score": doc.get("@search.score"),
                "chunk_id": doc.get("chunk_id"),
                "parent_id": doc.get("parent_id"),
                "title": doc.get("title"),
                "content": doc.get("chunk"),
                "source_file": doc.get("source_file"),
                "document_type": doc.get("document_type"),
                "source_url": doc.get("source_url"),
            }
            for doc in results
        ]

    @staticmethod
    async def retrieve_helpdesk(
        question: str,
        top_k: int,
        user_object_id: str,
        group_ids: list[str],
    ):

        return await AzureSearchService.search_top_k(
            question=question,
            top_k=top_k,
            user_object_id=user_object_id,
            group_ids=group_ids,
            workspace="HELPDESK",
        )
