class AzureAclRepository:
    ACL_FIELDS = (
        "allowed_user_ids",
        "allowed_group_ids",
        "allowed_sharepoint_group_ids",
    )
    BATCH_SIZE = 500

    def __init__(self, client):
        self.client = client
        self._chunks_by_source = None

    async def chunks(self, drive_id, item_id):
        # Source IDs are retrievable but not filterable on the deployed index.
        # Read only identity/ACL fields once per sync and match both IDs locally.
        if self._chunks_by_source is None:
            results = await self.client.search(
                search_text="*",
                select=["chunk_id", "drive_id", "drive_item_id", *self.ACL_FIELDS],
            )
            grouped = {}
            seen = set()
            # No top limit: consume all SDK pages before publishing the cache.
            async for chunk in results:
                source = (chunk.get("drive_id"), chunk.get("drive_item_id"))
                if not all(source):
                    continue
                if not chunk.get("chunk_id"):
                    raise ValueError("Index chunk source identity is invalid.")
                if chunk["chunk_id"] not in seen:
                    seen.add(chunk["chunk_id"])
                    grouped.setdefault(source, []).append(chunk)
            self._chunks_by_source = grouped
        return self._chunks_by_source.get((drive_id, item_id), [])

    async def replace_acl(self, chunk_ids, acl):
        succeeded = []
        failed = []
        for start in range(0, len(chunk_ids), self.BATCH_SIZE):
            batch = chunk_ids[start:start + self.BATCH_SIZE]
            payload = [
                {"chunk_id": chunk_id, **{field: acl[field] for field in self.ACL_FIELDS}}
                for chunk_id in batch
            ]
            try:
                results = await self.client.merge_documents(documents=payload)
                indexed = {result.key: result for result in results}
                for chunk_id in batch:
                    result = indexed.get(chunk_id)
                    if result is not None and result.succeeded:
                        succeeded.append(chunk_id)
                    else:
                        failed.append(chunk_id)
            except Exception:
                # The outcome can be unknown after a network timeout. Do not
                # report these chunks as updated; the next sync reconciles them.
                failed.extend(batch)
        return succeeded, failed
