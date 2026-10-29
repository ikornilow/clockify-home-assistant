"""Config flow for Clockify."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ClockifyApi, ClockifyApiError, ClockifyAuthError
from .const import (
    API_HOSTS,
    CONF_API_HOST,
    CONF_API_KEY,
    CONF_WORKSPACE_ID,
    CONF_WORKSPACE_NAME,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Clockify workspace using an API key."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Validate the key and choose a workspace."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_host = user_input[CONF_API_HOST]
            api = ClockifyApi(
                async_get_clientsession(self.hass),
                user_input[CONF_API_KEY],
                api_host,
            )
            try:
                user = await api.get_user()
                workspaces = await api.get_workspaces()
            except ClockifyAuthError:
                errors["base"] = "invalid_auth"
            except ClockifyApiError:
                errors["base"] = "cannot_connect"
            else:
                if not user.get("id") or not workspaces:
                    errors["base"] = "no_workspaces"
                else:
                    self._api_key = user_input[CONF_API_KEY]
                    self._api_host = api_host
                    self._user_id = str(user["id"])
                    self._workspaces = workspaces
                    return await self.async_step_workspace()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(
                        CONF_API_HOST, default="api.clockify.me"
                    ): vol.In(API_HOSTS),
                }
            ),
            errors=errors,
        )

    async def async_step_workspace(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Select the workspace to track."""
        workspaces: list[dict[str, Any]] = self._workspaces
        choices = {
            str(workspace["id"]): str(workspace.get("name") or workspace["id"])
            for workspace in workspaces
            if workspace.get("id")
        }
        if user_input is not None:
            workspace_id = user_input[CONF_WORKSPACE_ID]
            workspace_name = choices[workspace_id]
            await self.async_set_unique_id(f"{self._user_id}_{workspace_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Clockify-HA — {workspace_name}",
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_API_HOST: self._api_host,
                    "user_id": self._user_id,
                    CONF_WORKSPACE_ID: workspace_id,
                    CONF_WORKSPACE_NAME: workspace_name,
                },
            )

        return self.async_show_form(
            step_id="workspace",
            data_schema=vol.Schema(
                {vol.Required(CONF_WORKSPACE_ID): vol.In(choices)}
            ),
        )
