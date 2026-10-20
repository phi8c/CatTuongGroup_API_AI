# Site ACL synchronization

`POST /documents/acl/sync` accepts JSON:

```json
{"site_id":"hostname,site-collection-id,web-id","dry_run":true}
```

Use the Graph site ID returned by the site's Graph endpoint, not a document's
numeric SharePoint list-item ID. `dry_run` defaults to `false`: omitting it applies
updates. Use `true` first to inspect the ACL and proposed changes without writes.
This is an administrative endpoint for the trusted integration boundary.

The scan enumerates all document libraries in that site and files in their nested
folders. Every Graph collection follows pagination. Remote shortcuts are reported
as skipped so the scan does not leave the requested site. All permission entries
returned by the file permissions endpoint are considered, including inherited
entries; `inheritedFrom` is not required or inferred.

Each file is matched ONLY by `drive_id` and `drive_item_id`. These fields must be
present and retrievable on the existing Azure Search index. They do not need to be filterable: the sync reads identity and ACL fields across the index once per request and matches both IDs locally. This increases read cost on large indexes; chunk text and vectors are not fetched. `chunk_id`
must be its document key. `allowed_user_ids`, `allowed_group_ids` and
`allowed_sharepoint_group_ids` must already be retrievable string collections.
This API does not change the index schema. No fallback to title, filename or
`parent_id` is performed because these can collide between libraries.

The response includes `site_id`, `dry_run`, `status`, `drives_scanned`,
`documents_scanned`, `documents_changed`, `chunks_updated`, `documents_failed`,
`documents_not_indexed`, `documents_with_warnings`,
`drive_errors`, `elapsed_seconds` and `results`. Each document result includes:

```json
{
  "drive_id":"b!library-id",
  "drive_item_id":"01DOCUMENTID",
  "name":"contract.docx",
  "status":"would_update",
  "acl":{
    "allowed_user_ids":["371fc795-833a-48ee-83c6-b0039a2b0d18"],
    "allowed_group_ids":[],
    "allowed_sharepoint_group_ids":[]
  },
  "indexed_chunks":10,
  "changed_chunks":10,
  "updated_chunks":0,
  "warnings":[],
  "elapsed_seconds":0.5
}
```

Document statuses are `unchanged`, `would_update`, `updated`, `not_indexed`,
`skipped`, `error`, or `partial_failure`. Individual document/drive errors do not
discard already completed results; the overall status becomes
`completed_with_errors`. Initial authentication/library-discovery failures return
HTTP 502. Failed merge results include `failed_chunk_ids`.

Every indexed chunk of each document is checked, with all SDK pages consumed.
IDs are compared as sets, so ordering/duplicates do not cause needless writes.
Changed chunks are merged in batches of 500 using ONLY the key and three ACL
fields. Collections are replaced, including empty arrays to revoke old grants.
Chunk text, embeddings, source identity and other metadata are not sent in merge
payloads. `merge_documents`, not upload/upsert, prevents recreating a removed chunk.
Per-batch/per-chunk failures are counted; retrying the site scan reconciles partial
or uncertain results. Graph errors never become an empty ACL.

## Scope and limitations

- Entra user/group Object IDs go into their respective ACL arrays. SharePoint
  numeric site-group IDs go only into `allowed_sharepoint_group_ids`.
- Existing chat retrieval uses ONLY Entra users/groups. This API does not expand
  SharePoint group membership or change chat permission semantics; site-group-only
  access is reported with `sharepoint_group_membership_not_expanded`.
- Anonymous/organization sharing links require possession of a link and cannot
  be represented as a tenant-wide principal grant. They are not expanded; a
  warning is returned. Specific-people links are included only if resolved Entra
  Object IDs are present. Link URLs, tokens and raw Graph permission responses
  are never returned.
- A principal with only a local SharePoint user ID/email cannot be guessed into
  an Entra Object ID. That document is an error and its ACL remains unchanged.
- This sync uses the sharing permissions exposed by Microsoft Graph. It is not
  a separate SharePoint REST role-assignment audit or an expansion of all classic
  SharePoint ACL rules. Validate real tenant permission samples in dry-run before
  using the API as an authoritative reconciliation job.
- Deleted files and pre-existing index chunks without source identity are not
  purged by this API. Files absent from the source scan are not modified.
- A scan is not an atomic cross-service snapshot. Do not run overlapping scans
  for the same site or concurrently overwrite ACL fields from ingestion.

## Configuration and verification

Uses existing `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` and
Azure Search settings. No new env keys or pip dependencies are introduced.
The app needs consented Microsoft Graph application permissions to enumerate
libraries/files and read their sharing permissions (for example `Files.Read.All`
or appropriate site permissions), plus Azure Search document-write credentials.

The implementation is verified with mocked Graph/Search responses. No live
permission synchronization is run during development/tests.

References:
- https://learn.microsoft.com/en-us/graph/api/driveitem-list-permissions
- https://learn.microsoft.com/en-us/graph/api/resources/permission
- https://learn.microsoft.com/en-us/graph/api/resources/sharinglink
- https://learn.microsoft.com/en-us/rest/api/searchservice/documents/
