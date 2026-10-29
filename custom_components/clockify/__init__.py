"""Clockify integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClockifyApi, ClockifyApiError, ClockifyAuthError
from .const import (
    CONF_API_HOST,
    CONF_API_KEY,
    CONF_WORKSPACE_ID,
    CONF_WORKSPACE_NAME,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .webhook import (
    async_remove_webhooks,
    async_setup_webhooks,
    async_unload_webhooks,
)

PLATFORMS = ["sensor"]



class ClockifyCoordinator(DataUpdateCoordinator[dict[str, object]]):
    """Fetch current timer, today's entries, and the most recent entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.api = ClockifyApi(
            async_get_clientsession(hass),
            entry.data[CONF_API_KEY],
            entry.data[CONF_API_HOST],
        )
        self.workspace_id = entry.data[CONF_WORKSPACE_ID]
        self.user_id = str(entry.data["user_id"])
        self.webhook_id: str | None = None
        self.webhook_retry_cancel: Callable[[], None] | None = None

    async def _async_update_data(self) -> dict[str, object]:
        timezone = ZoneInfo(self.hass.config.time_zone)
        now = datetime.now(timezone)
        start = datetime.combine(now.date(), time.min, tzinfo=timezone)
        end = datetime.combine(
            now.date() + timedelta(days=1), time.min, tzinfo=timezone
        )
        project_state = self.hass.states.get("input_text.default_clockify_project")
        project_id = (
            project_state.state
            if project_state and project_state.state not in {"unknown", "unavailable"}
            else None
        )
        week_start = start - timedelta(days=now.weekday())
        try:
            active, entries, week_entries, recent_entries = await asyncio.gather(
                self.api.get_active_entries(self.workspace_id),
                self.api.get_today_entries(
                    self.workspace_id, self.user_id, start, end
                ),
                self.api.get_today_entries(
                    self.workspace_id,
                    self.user_id,
                    week_start,
                    now + timedelta(seconds=1),
                ),
                self.api.get_last_entry(self.workspace_id, self.user_id, project_id),
            )
        except ClockifyAuthError as err:
            raise ConfigEntryAuthFailed("Clockify API key is no longer valid") from err
        except ClockifyApiError as err:
            raise UpdateFailed(str(err)) from err

        today_seconds = _duration_totals(entries, start, now, now)
        week_seconds = _duration_totals(week_entries, week_start, now, now)
        active_entry = active[0] if active else None
        last_entry = recent_entries[0] if recent_entries else None
        return {
            "active_entry": active_entry,
            "last_entry": last_entry,
            "today_seconds": today_seconds["total"],
            "today_billable_seconds": today_seconds["billable"],
            "today_non_billable_seconds": today_seconds["non_billable"],
            "week_seconds": week_seconds["total"],
            "week_billable_seconds": week_seconds["billable"],
            "week_non_billable_seconds": week_seconds["non_billable"],
            "updated_at": now,
        }


def _duration_totals(
    entries: list[dict[str, object]], start: datetime, end: datetime, now: datetime
) -> dict[str, int]:
    """Sum entry durations by billable status over a date range."""
    totals = {"total": 0, "billable": 0, "non_billable": 0}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        seconds = _entry_duration(entry, now, start, end)
        totals["total"] += seconds
        totals["billable" if entry.get("billable") is True else "non_billable"] += seconds
    return totals


def _entry_duration(
    entry: dict[str, object],
    now: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> int:
    """Return duration overlapping the requested local period."""
    interval = entry.get("timeInterval")
    if not isinstance(interval, dict):
        interval = entry
    start_value = interval.get("start")
    end_value = interval.get("end")
    if not isinstance(start_value, str):
        return 0
    try:
        started = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
        ended = (
            datetime.fromisoformat(end_value.replace("Z", "+00:00"))
            if isinstance(end_value, str)
            else now
        )
        start_bound = period_start or now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_bound = period_end or (start_bound + timedelta(days=1))
        started = max(started, start_bound)
        ended = min(ended, end_bound, now)
        return max(0, int((ended - started).total_seconds()))
    except (ValueError, TypeError):
        return 0



async def async_setup(hass: HomeAssistant, config: dict[str, object]) -> bool:
    """Register Clockify service actions."""

    async def get_coordinator(call: ServiceCall) -> ClockifyCoordinator:
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        workspace_id = call.data.get("workspace_id")
        if workspace_id:
            coordinators = [
                coordinator
                for coordinator in coordinators
                if coordinator.workspace_id == workspace_id
            ]
        if len(coordinators) != 1:
            raise HomeAssistantError(
                "Select a workspace_id when multiple Clockify workspaces are configured"
            )
        return coordinators[0]

    async def start_timer(call: ServiceCall) -> None:
        coordinator = await get_coordinator(call)
        project_state = hass.states.get("input_text.default_clockify_project")
        project_id = call.data.get("project_id") or (
            project_state.state
            if project_state and project_state.state not in {"unknown", "unavailable"}
            else None
        )
        if not project_id:
            raise HomeAssistantError("Provide project_id or set the Clockify project helper")
        active = coordinator.data.get("active_entry")
        if isinstance(active, dict):
            raise HomeAssistantError("A Clockify timer is already running")
        last_entry = coordinator.data.get("last_entry")
        description = call.data.get("description") or (
            last_entry.get("description") if isinstance(last_entry, dict) else ""
        )
        try:
            await coordinator.api.create_time_entry(
                coordinator.workspace_id,
                project_id=project_id,
                start=datetime.now(ZoneInfo(hass.config.time_zone)),
                description=str(description or ""),
            )
        except ClockifyApiError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def stop_timer(call: ServiceCall) -> None:
        coordinator = await get_coordinator(call)
        if not isinstance(coordinator.data.get("active_entry"), dict):
            raise HomeAssistantError("No Clockify timer is running")
        try:
            await coordinator.api.stop_time_entry(
                coordinator.workspace_id,
                coordinator.user_id,
                datetime.now(ZoneInfo(hass.config.time_zone)),
            )
        except ClockifyApiError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    def parse_entry_time(value: object, field: str) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as err:
                raise HomeAssistantError(
                    f"{field} must be an ISO 8601 datetime"
                ) from err
        else:
            raise HomeAssistantError(f"{field} must be an ISO 8601 datetime")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(hass.config.time_zone))
        return parsed

    async def create_time_entry(call: ServiceCall) -> None:
        coordinator = await get_coordinator(call)
        project_id = call.data.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise HomeAssistantError("Provide project_id")
        start = parse_entry_time(call.data.get("start"), "start")
        end = parse_entry_time(call.data.get("end"), "end")
        if end <= start:
            raise HomeAssistantError("end must be later than start")
        raw_tag_ids = call.data.get("tag_ids", [])
        if isinstance(raw_tag_ids, str):
            raw_tag_ids = [raw_tag_ids]
        if not isinstance(raw_tag_ids, list) or any(
            not isinstance(tag_id, str) or not tag_id for tag_id in raw_tag_ids
        ):
            raise HomeAssistantError("tag_ids must be a list of Clockify tag IDs")
        try:
            await coordinator.api.create_time_entry(
                coordinator.workspace_id,
                project_id=project_id,
                start=start,
                end=end,
                description=str(call.data.get("description") or ""),
                tag_ids=raw_tag_ids,
            )
        except ClockifyApiError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "start_timer", start_timer)
    hass.services.async_register(DOMAIN, "stop_timer", stop_timer)
    hass.services.async_register(DOMAIN, "create_time_entry", create_time_entry)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Clockify from a config entry."""
    workspace_name = entry.data.get(CONF_WORKSPACE_NAME, "workspace")
    expected_title = f"Clockify-HA — {workspace_name}"
    if entry.title != expected_title:
        hass.config_entries.async_update_entry(entry, title=expected_title)
    coordinator = ClockifyCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except UpdateFailed as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    (
        coordinator.webhook_id,
        coordinator.webhook_retry_cancel,
    ) = await async_setup_webhooks(
        hass, entry, coordinator.api, coordinator.async_request_refresh
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Clockify config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if coordinator.webhook_retry_cancel:
            coordinator.webhook_retry_cancel()
        async_unload_webhooks(hass, getattr(coordinator, "webhook_id", None))
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete Clockify subscriptions when the config entry is removed."""
    api = ClockifyApi(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.data[CONF_API_HOST],
    )
    await async_remove_webhooks(hass, entry, api)
