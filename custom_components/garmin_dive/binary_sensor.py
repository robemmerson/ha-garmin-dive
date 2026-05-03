"""Binary sensors for Garmin Dive."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator


class ServiceDueBinarySensor(GarminDiveAccountEntity, BinarySensorEntity):
    _attr_translation_key = "service_due"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_service_due"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        return any(
            (g.detail_raw or g.summary_raw).get("dueIndicator") in {"DUE", "OVERDUE"}
            for g in self.coordinator.data.gear
        )


class NewDiveAvailableBinarySensor(GarminDiveAccountEntity, BinarySensorEntity):
    _attr_translation_key = "new_dive_available"
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_icon = "mdi:diving-helmet"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_new_dive_available"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data or not self.coordinator.data.dives:
            return False
        latest = self.coordinator.data.dives[0].id
        ack = self.coordinator.latest_dive_acknowledged_id
        return ack != latest


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    async_add_entities(
        [
            ServiceDueBinarySensor(coordinator),
            NewDiveAvailableBinarySensor(coordinator),
        ]
    )
