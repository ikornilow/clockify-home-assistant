"""Small asynchronous client for the Clockify REST API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_BASE_TEMPLATE


class ClockifyApiError(Exception):
    """Clockify request failed."""


class ClockifyAuthError(ClockifyApiError):
    """Clockify rejected the API key."""


class ClockifyApi:
    """Clockify API methods used by this integration."""

    def __init__(
        self, session: ClientSession, api_key: str, api_host: str
    ) -> None:
        self._session = session
        self._base_url = API_BASE_TEMPLATE.format(host=api_host)
        self._headers = {"X-Api-Key": api_key}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{self._base_url}{path}", headers=self._headers, params=params
            ) as response:
                if response.status in (401, 403):
                    raise ClockifyAuthError("Clockify rejected the API key")
                if response.status >= 400:
                    raise ClockifyApiError(f"Clockify returned HTTP {response.status}")
                return await response.json()
        except (ClientError, TimeoutError) as err:
            raise ClockifyApiError("Unable to connect to Clockify") from err

    async def get_user(self) -> dict[str, Any]:
        return await self._get("/user")

    async def get_workspaces(self) -> list[dict[str, Any]]:
        return await self._get("/workspaces")

    async def get_active_entries(self, workspace_id: str) -> list[dict[str, Any]]:
        return await self._get(
            f"/workspaces/{workspace_id}/time-entries/status/in-progress",
            {"page": "1", "page-size": "1000"},
        )

    async def get_today_entries(
        self, workspace_id: str, user_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
            {
                "start": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "page": "1",
                "page-size": "1000",
                "hydrated": "true",
            },
        )

    async def create_time_entry(
        self,
        workspace_id: str,
        *,
        project_id: str,
        start: datetime,
        description: str,
        end: datetime | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a completed entry or start a timer in the selected workspace."""
        payload: dict[str, Any] = {
            "start": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "projectId": project_id,
            "description": description,
        }
        if end is not None:
            payload["end"] = end.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        if tag_ids:
            payload["tagIds"] = tag_ids
        return await self._request(
            "POST",
            f"/workspaces/{workspace_id}/time-entries",
            payload,
        )

    async def stop_time_entry(
        self, workspace_id: str, user_id: str, end: datetime
    ) -> None:
        """Stop the current timer."""
        await self._request(
            "PATCH",
            f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
            {"end": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        )

    async def get_last_entry(
        self, workspace_id: str, user_id: str, project_id: str | None
    ) -> list[dict[str, Any]]:
        """Return recent completed entries, optionally scoped to a project."""
        params = {"in-progress": "false"}
        if project_id:
            params["project"] = project_id
        return await self._get(
            f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
            params,
        )

    async def get_webhooks(self, workspace_id: str) -> list[dict[str, Any]]:
        """Return webhooks registered on a workspace."""
        response = await self._get(f"/workspaces/{workspace_id}/webhooks")
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            hooks = response.get("webhooks")
            if isinstance(hooks, list):
                return hooks
        return []

    async def create_webhook(
        self, workspace_id: str, *, name: str, event: str, url: str
    ) -> dict[str, Any]:
        """Subscribe to one Clockify event."""
        return await self._request(
            "POST",
            f"/workspaces/{workspace_id}/webhooks",
            {
                "name": name[:30],
                "triggerSource": [workspace_id],
                "triggerSourceType": "WORKSPACE_ID",
                "url": url,
                "webhookEvent": event,
            },
        )

    async def delete_webhook(self, workspace_id: str, webhook_id: str) -> None:
        """Delete a Clockify webhook."""
        await self._request(
            "DELETE", f"/workspaces/{workspace_id}/webhooks/{webhook_id}"
        )

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        """Send an authenticated Clockify API request."""
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                json=payload,
            ) as response:
                if response.status in (401, 403):
                    raise ClockifyAuthError("Clockify rejected the API key")
                if response.status >= 400:
                    raise ClockifyApiError(f"Clockify returned HTTP {response.status}")
                if response.status == 204:
                    return None
                return await response.json()
        except (ClientError, TimeoutError) as err:
            raise ClockifyApiError("Unable to connect to Clockify") from err
