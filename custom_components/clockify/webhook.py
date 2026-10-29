"""Register and process Clockify webhooks through Home Assistant Cloud."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from aiohttp import web
from homeassistant.components import cloud, webhook

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .api import ClockifyApi, ClockifyApiError
from .const import CONF_WORKSPACE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)
EVENTS = ("NEW_TIMER_STARTED", "TIMER_STOPPED", "TIME_ENTRY_UPDATED")
OPTION_WEBHOOKS = "clockify_webhooks"


async def async_setup_webhooks(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: ClockifyApi,
    refresh: Callable[[], Any],
) -> tuple[str | None, Callable[[], None] | None]:
    """Create a Nabu Casa Cloud webhook and Clockify subscriptions."""
    webhook_id = f"clockify_{entry.entry_id.replace('-', '')}"
    webhook.async_register(
        hass,
        DOMAIN,
        "Clockify",
        webhook_id,
        _handler(hass, entry.entry_id, refresh),
        local_only=False,
        allowed_methods=["POST"],
    )
    try:
        url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
    except Exception as err:
        webhook.async_unregister(hass, webhook_id)
        _LOGGER.warning("Could not create Nabu Casa webhook: %s", err)
        return None, None

    if await _register_clockify_hooks(hass, entry, api, url):
        return webhook_id, None

    retry_cancel = _schedule_registration_retry(hass, entry, api, url)
    return webhook_id, retry_cancel


async def _register_clockify_hooks(
    hass: HomeAssistant, entry: ConfigEntry, api: ClockifyApi, url: str
) -> bool:
    """Register any missing Clockify events; return whether all are active."""
    webhook_ids = dict(entry.options.get(OPTION_WEBHOOKS, {}))
    if all(event in webhook_ids for event in EVENTS):
        return True
    try:
        hooks = await api.get_webhooks(entry.data[CONF_WORKSPACE_ID])
    except ClockifyApiError as err:
        _LOGGER.warning(
            "Clockify webhooks unavailable; polling remains active: %s", err
        )
        return False

    registered = {
        (hook.get("webhookEvent"), hook.get("url")): hook.get("id")
        for hook in hooks
        if isinstance(hook, dict)
    }
    for event in EVENTS:
        if event in webhook_ids:
            continue
        hook_id = registered.get((event, url))
        if not isinstance(hook_id, str):
            try:
                created = await api.create_webhook(
                    entry.data[CONF_WORKSPACE_ID],
                    name=f"HA Clockify {event}",
                    event=event,
                    url=url,
                )
            except ClockifyApiError as err:
                _LOGGER.warning(
                    "Could not register Clockify %s webhook; polling remains active: %s",
                    event,
                    err,
                )
                continue
            hook_id = created.get("id") if isinstance(created, dict) else None
        if isinstance(hook_id, str):
            webhook_ids[event] = hook_id
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, OPTION_WEBHOOKS: webhook_ids}
            )
    return all(event in webhook_ids for event in EVENTS)


def _schedule_registration_retry(
    hass: HomeAssistant, entry: ConfigEntry, api: ClockifyApi, url: str
) -> Callable[[], None]:
    """Retry incomplete webhook registration hourly without duplicate hooks."""
    timer: dict[str, Callable[[], None] | None] = {"cancel": None}

    async def retry(_now: Any) -> None:
        timer["cancel"] = None
        if not await _register_clockify_hooks(hass, entry, api, url):
            timer["cancel"] = async_call_later(hass, 3600, retry)

    timer["cancel"] = async_call_later(hass, 3600, retry)

    def cancel() -> None:
        if timer["cancel"] is not None:
            timer["cancel"]()

    return cancel

def async_unload_webhooks(hass: HomeAssistant, webhook_id: str | None) -> None:
    """Unregister the local webhook handler; Cloud URL is reused on restart."""
    if webhook_id:
        webhook.async_unregister(hass, webhook_id)


async def async_remove_webhooks(
    hass: HomeAssistant, entry: ConfigEntry, api: ClockifyApi
) -> None:
    """Remove Clockify and Nabu Casa subscriptions on integration removal."""
    workspace_id = entry.data[CONF_WORKSPACE_ID]
    for webhook_id in entry.options.get(OPTION_WEBHOOKS, {}).values():
        try:
            await api.delete_webhook(workspace_id, webhook_id)
        except ClockifyApiError as err:
            _LOGGER.warning("Could not delete Clockify webhook %s: %s", webhook_id, err)
    try:
        await cloud.async_delete_cloudhook(
            hass, f"clockify_{entry.entry_id.replace('-', '')}"
        )
    except Exception as err:
        _LOGGER.debug("Could not delete Nabu Casa webhook: %s", err)


def _handler(
    hass: HomeAssistant, entry_id: str, refresh: Callable[[], Any]
) -> Callable[[str, web.Request], Any]:
    """Build a handler tied to one config entry."""
    async def handle(_webhook_id: str, request: web.Request) -> web.Response:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return web.Response(status=410)
        try:
            payload = await request.json()
        except (ValueError, TypeError):
            return web.Response(status=400)
        workspace_id = payload.get("workspaceId") if isinstance(payload, dict) else None
        if workspace_id and workspace_id != entry.data[CONF_WORKSPACE_ID]:
            return web.Response(status=202)
        hass.async_create_task(refresh())
        return web.Response(status=202)

    return handle
