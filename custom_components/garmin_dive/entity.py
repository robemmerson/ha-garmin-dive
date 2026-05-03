"""Base entity classes for ha-garmin-dive."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator


class GarminDiveAccountEntity(CoordinatorEntity["GarminDiveCoordinator"]):
    """Entity attached to the per-account HA Device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._account_id = str(coordinator._auth.profile_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=f"Garmin Dive — {coordinator._auth.profile_display_name}",
            manufacturer="Garmin",
            model="Dive",
            entry_type=None,
        )


class GarminDiveSubDeviceEntity(CoordinatorEntity["GarminDiveCoordinator"]):
    """Entity attached to a sub-device (dive computer or gear item)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GarminDiveCoordinator,
        *,
        sub_device_id: str,
        sub_device_name: str,
        manufacturer: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        entity_picture: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = str(coordinator._auth.profile_id)
        self._sub_device_id = sub_device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._account_id}:{sub_device_id}")},
            via_device=(DOMAIN, self._account_id),
            name=sub_device_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
        )
        self._attr_entity_picture = entity_picture
