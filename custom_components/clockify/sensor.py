"""Sensors provided by Clockify."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ClockifyCoordinator
from .const import CONF_WORKSPACE_ID, CONF_WORKSPACE_NAME, DOMAIN

DESCRIPTIONS = (
    SensorEntityDescription(
        key="active_timer",
        name="Active timer",
        icon="mdi:timer-play-outline",
    ),
    SensorEntityDescription(
        key="today_duration",
        name="Time tracked today",
        icon="mdi:clock-check-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="time_entry_in_progress",
        name="Time-Entry in progress",
        icon="mdi:timer-play-outline",
    ),
    SensorEntityDescription(
        key="last_time_entry",
        name="Last Time-Entry",
        icon="mdi:clipboard-text-clock-outline",
    ),
    SensorEntityDescription(
        key="today_billable_seconds",
        name="Time tracked today (billable)",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="today_non_billable_seconds",
        name="Time tracked today (non-billable)",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="week_seconds",
        name="Time tracked this week",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="week_billable_seconds",
        name="Time tracked this week (billable)",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="week_non_billable_seconds",
        name="Time tracked this week (non-billable)",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up Clockify sensors."""
    coordinator: ClockifyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ClockifySensor(coordinator, entry, description)
        for description in DESCRIPTIONS
    )


class ClockifySensor(CoordinatorEntity[ClockifyCoordinator], SensorEntity):
    """Represent one Clockify timer or duration sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ClockifyCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        if description.key == "time_entry_in_progress":
            self._attr_suggested_object_id = "clockify_time_entry_in_progress"
        elif description.key == "last_time_entry":
            self._attr_suggested_object_id = "clockify_last_time_entry"
        workspace = entry.data.get(CONF_WORKSPACE_NAME, "Clockify")
        self._attr_unique_id = f"{entry.data[CONF_WORKSPACE_ID]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data[CONF_WORKSPACE_ID]))},
            name=f"Clockify-HA — {workspace}",
            manufacturer="Clockify",
            configuration_url="https://app.clockify.me/",
        )

    @property
    def native_value(self) -> str | float:
        """Return the active description or duration in hours."""
        key = self.entity_description.key
        duration_keys = {
            "today_duration": "today_seconds",
            "today_billable_seconds": "today_billable_seconds",
            "today_non_billable_seconds": "today_non_billable_seconds",
            "week_seconds": "week_seconds",
            "week_billable_seconds": "week_billable_seconds",
            "week_non_billable_seconds": "week_non_billable_seconds",
        }
        if key in duration_keys:
            seconds = int(self.coordinator.data[duration_keys[key]])
            return round(seconds / 3600, 2)
        if key == "last_time_entry":
            entry = self.coordinator.data["last_entry"]
            if not isinstance(entry, dict):
                return "not found"
            return str(entry.get("description") or "not found")
        active = self.coordinator.data["active_entry"]
        if key == "time_entry_in_progress":
            if not isinstance(active, dict):
                return "not running"
            interval = active.get("timeInterval")
            interval = interval if isinstance(interval, dict) else {}
            return str(interval.get("start") or "not running")
        if not isinstance(active, dict):
            return "Not tracking"
        return str(active.get("description") or "Tracking time")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose details useful to automations and dashboards."""
        if self.entity_description.key in {
            "today_duration",
            "today_billable_seconds",
            "today_non_billable_seconds",
            "week_seconds",
            "week_billable_seconds",
            "week_non_billable_seconds",
        }:
            return {"workspace": self.coordinator.workspace_id}
        if self.entity_description.key == "last_time_entry":
            return {}
        active = self.coordinator.data["active_entry"]
        if not isinstance(active, dict):
            return {"is_tracking": False}
        interval = active.get("timeInterval")
        interval = interval if isinstance(interval, dict) else {}
        project = active.get("project")
        project_name = project.get("name") if isinstance(project, dict) else None
        attributes = {
            "is_tracking": True,
            "started_at": interval.get("start"),
            "project": project_name,
            "workspace": self.coordinator.workspace_id,
        }
        if self.entity_description.key == "time_entry_in_progress":
            attributes.update(
                {
                    key: active.get(key)
                    for key in ("id", "userId", "description")
                    if key in active
                }
            )
        return attributes
