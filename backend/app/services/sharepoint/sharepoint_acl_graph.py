import asyncio
from urllib.parse import quote, urlsplit

import httpx

from app.core.settings import settings


class SharePointAclError(ValueError):
    pass


class SharePointAclGraph:
    BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.token = None

    async def authenticate(self):
        tenant = quote(settings.AZURE_TENANT_ID, safe="")
        response = await self.client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        if response.status_code != 200:
            raise SharePointAclError("Microsoft Graph authentication failed.")
        self.token = response.json().get("access_token")
        if not self.token:
            raise SharePointAclError("Microsoft Graph returned no access token.")

    async def _get(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "graph.microsoft.com"
            or not parsed.path.startswith("/v1.0/")
        ):
            raise SharePointAclError("Unexpected Graph pagination URL.")
        for attempt in range(3):
            response = await self.client.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
            )
            if response.status_code == 401 and attempt < 2:
                await self.authenticate()
                continue
            if response.status_code in {429, 503, 504} and attempt < 2:
                try:
                    delay = float(response.headers.get("Retry-After", "1"))
                except ValueError:
                    delay = 1
                await asyncio.sleep(max(0, min(delay, 5)))
                continue
            if response.status_code != 200:
                raise SharePointAclError(
                    f"Microsoft Graph read failed (HTTP {response.status_code})."
                )
            data = response.json()
            if not isinstance(data, dict):
                raise SharePointAclError("Invalid Microsoft Graph response.")
            return data

    async def collection(self, url):
        seen_pages = set()
        while url:
            if url in seen_pages:
                raise SharePointAclError("Repeated Graph pagination URL.")
            seen_pages.add(url)
            data = await self._get(url)
            values = data.get("value")
            if not isinstance(values, list) or not all(isinstance(x, dict) for x in values):
                raise SharePointAclError("Invalid Microsoft Graph collection.")
            for value in values:
                yield value
            url = data.get("@odata.nextLink")

    async def drives(self, site_id):
        async for drive in self.collection(
            f"{self.BASE}/sites/{quote(site_id, safe='')}/drives?$select=id,name"
        ):
            if not drive.get("id"):
                raise SharePointAclError("Graph library has no drive ID.")
            yield drive

    async def documents(self, drive_id):
        base = f"{self.BASE}/drives/{quote(drive_id, safe='')}"
        pending = [f"{base}/root/children?$select=id,name,file,folder,package,remoteItem"]
        seen = set()
        while pending:
            async for item in self.collection(pending.pop()):
                item_id = item.get("id")
                if not item_id:
                    raise SharePointAclError("Graph item has no drive item ID.")
                if item_id in seen:
                    continue
                seen.add(item_id)
                if item.get("remoteItem") is not None:
                    yield item
                elif item.get("folder") is not None or item.get("package") is not None:
                    pending.append(
                        f"{base}/items/{quote(item_id, safe='')}/children"
                        "?$select=id,name,file,folder,package,remoteItem"
                    )
                elif item.get("file") is not None:
                    yield item

    async def permissions(self, drive_id, item_id):
        url = (
            f"{self.BASE}/drives/{quote(drive_id, safe='')}/items/"
            f"{quote(item_id, safe='')}/permissions"
        )
        return [permission async for permission in self.collection(url)]
