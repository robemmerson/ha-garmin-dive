"""Garmin Dive sensor entities."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity, GarminDiveSubDeviceEntity
from .gear import days_until_service, is_serviceable

if TYPE_CHECKING:
    from .coordinator import Dive, DiveDevice, GarminDiveCoordinator, GearItem


def _gear_serial(item: GearItem) -> str | None:
    detail = item.detail_raw or item.summary_raw
    sn = detail.get("serialNumber")
    return str(sn) if sn else None


def _gear_ant_channel(item: GearItem) -> str | None:
    detail = item.detail_raw or item.summary_raw
    ant = detail.get("antChannelId")
    return str(ant) if ant is not None else None


def _device_ant_channel(device: DiveDevice) -> str | None:
    ant = device.raw.get("antChannelId")
    return str(ant) if ant is not None else None


def _matching_device(coordinator: GarminDiveCoordinator, item: GearItem) -> DiveDevice | None:
    """Return the dive_device representing the same physical item as `item`.

    Match strategy:
      - For dive computers (Mk2i etc.) `serialNumber` is the only identifier
        the two endpoints share.
      - For transmitters (Descent T1) `/gear/{id}` returns the *printed*
        short serial while `/dive/devices` returns the full numeric serial,
        so they don't compare equal. The two endpoints DO agree on
        `antChannelId`, which is the authoritative join key for ANT+
        accessories.
    Try serial first, then antChannelId.
    """
    serial = _gear_serial(item)
    ant = _gear_ant_channel(item)
    for d in coordinator.data.devices:
        if serial is not None and d.serial_number is not None and str(d.serial_number) == serial:
            return d
        if ant is not None and _device_ant_channel(d) == ant:
            return d
    return None


def _matching_gear(
    coordinator: GarminDiveCoordinator,
    *,
    serial: str | None = None,
    ant_channel: str | None = None,
) -> GearItem | None:
    for g in coordinator.data.gear:
        if serial is not None and _gear_serial(g) == serial:
            return g
        if ant_channel is not None and _gear_ant_channel(g) == ant_channel:
            return g
    return None


def _connect_url(connect_activity_id: int | None) -> str | None:
    if connect_activity_id is None:
        return None
    return f"https://connect.garmin.com/modern/activity/{connect_activity_id}"


def _last_dive(coordinator: GarminDiveCoordinator) -> Dive | None:
    if not coordinator.data or not coordinator.data.dives:
        return None
    return coordinator.data.dives[0]


class LastDiveSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive"
    _attr_icon = "mdi:diving-scuba"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive"

    @property
    def native_value(self) -> str | None:
        d = _last_dive(self.coordinator)
        return d.name if d else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        raw = d.raw
        return {
            "id": d.id,
            "connect_activity_id": raw.get("connectActivityId"),
            "connect_url": _connect_url(raw.get("connectActivityId")),
            "start_time": raw.get("startTime"),
            "timezone": raw.get("timezone"),
            "max_depth": raw.get("maxDepth"),
            "bottom_time_minutes": ((raw["bottomTime"] / 60) if "bottomTime" in raw else None),
            "total_time_minutes": ((raw["totalTime"] / 60) if "totalTime" in raw else None),
            "surface_interval_hours": (
                (raw["surfaceInterval"] / 3600) if "surfaceInterval" in raw else None
            ),
            "tags": raw.get("diveTags"),
            "gases": raw.get("gases"),
            "location": raw.get("entryLoc"),
            "dive_type": raw.get("diveType"),
        }


class TotalDivesSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "total_dives"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_total_dives"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.total_dives if self.coordinator.data else 0


class CurrentYearDivesSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "current_year_dives"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_current_year_dives"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        year = date.today().year
        return sum(
            1
            for d in self.coordinator.data.dives
            if datetime.fromisoformat(d.start_time).year == year
        )


class LastDiveMaxDepthSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_max_depth"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:arrow-collapse-down"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_max_depth"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        return d.max_depth if d else None


class LastDiveBottomTimeSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_bottom_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_bottom_time"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        bt = d.raw.get("bottomTime")
        return bt / 60 if bt is not None else None


class LastDiveSurfaceIntervalSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_surface_interval"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_surface_interval"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        si = d.raw.get("surfaceInterval")
        return si / 3600 if si is not None else None


class DiveLogYearSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "dive_log_year"
    _attr_icon = "mdi:timeline-clock"

    # The full dive log lives in `dives` and can exceed HA's 16 KB attribute
    # threshold for the recorder. Tell the recorder to skip persisting it —
    # the live state machine still serves the full list to dashboards.
    _unrecorded_attributes = frozenset({"dives"})

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_dive_log_year"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        year = date.today().year
        return sum(
            1
            for d in self.coordinator.data.dives
            if datetime.fromisoformat(d.start_time).year == year
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {"dives": []}
        return {"dives": [self._dive_to_card(d) for d in self.coordinator.data.dives]}

    def _dive_to_card(self, d: Dive) -> dict[str, Any]:
        raw = d.raw
        start = datetime.fromisoformat(raw["startTime"])
        total_seconds = float(raw["totalTime"])
        end = (start + timedelta(seconds=total_seconds)).isoformat()
        return {
            "id": d.id,
            "name": d.name,
            "start": raw["startTime"],
            "end": end,
            "timezone": raw.get("timezone"),
            "max_depth": raw.get("maxDepth"),
            # average_depth: not present in /dive/summary; spec §13 leaves it
            # to a future per-dive detail call.
            "average_depth": None,
            "bottom_time": (raw.get("bottomTime") or 0) / 60,
            "total_time": total_seconds / 60,
            "surface_interval": (raw.get("surfaceInterval") or 0) / 3600,
            "tags": raw.get("diveTags") or [],
            "gases": raw.get("gases") or [],
            "location": raw.get("entryLoc"),
            "photos": dict(d.photos),
            "photos_all": [dict(p) for p in d.photos_all],
            "photo_count": d.photo_count,
            "connect_url": _connect_url(raw.get("connectActivityId")),
            "dive_computer": raw.get("activitySource"),
        }


class DivesByTagSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "dives_by_tag"
    _attr_icon = "mdi:tag-multiple"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_dives_by_tag"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return sum(self.coordinator.data.dive_tags.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.coordinator.data.dive_tags) if self.coordinator.data else {}


class GearCountSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "gear_count"
    _attr_icon = "mdi:bag-personal"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_gear_count"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.gear) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {"by_type": {}}
        return {"by_type": dict(Counter(g.gear_type for g in self.coordinator.data.gear))}


class _GearEntityBase(GarminDiveSubDeviceEntity):
    """Common locator for gear sub-device sensors."""

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        item = next(g for g in coordinator.data.gear if g.gear_id == gear_id)
        detail = item.detail_raw or item.summary_raw
        manufacturer = detail.get("brand")
        model = detail.get("model")
        serial = detail.get("serialNumber")
        device_match = _matching_device(coordinator, item)
        aliases: tuple[str, ...] = (
            (f"device_{device_match.serial_number}",) if device_match is not None else ()
        )
        super().__init__(
            coordinator,
            sub_device_id=str(gear_id),
            sub_device_name=item.name,
            manufacturer=manufacturer,
            model=model,
            serial_number=str(serial) if serial else None,
            entity_picture=item.photo_local_url,
            alias_sub_device_ids=aliases,
        )
        self._gear_id = gear_id

    def _detail(self) -> dict[str, Any]:
        item = next(g for g in self.coordinator.data.gear if g.gear_id == self._gear_id)
        return item.detail_raw or item.summary_raw


class GearServiceStatusSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_service_status"
    _attr_icon = "mdi:tools"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["not_due", "due", "overdue"]  # type: ignore[misc]

    # Garmin uses richer values (e.g. DUE_SOON, OVERDUE_BY_X_DAYS); collapse to
    # our three-state enum so HA doesn't reject the entity.
    _INDICATOR_MAP: ClassVar[dict[str, str]] = {
        "NOT_DUE": "not_due",
        "DUE": "due",
        "DUE_SOON": "due",
        "OVERDUE": "overdue",
        "PAST_DUE": "overdue",
    }

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_service_status"

    @property
    def native_value(self) -> str | None:
        ind = self._detail().get("dueIndicator")
        if not ind:
            return None
        mapped = self._INDICATOR_MAP.get(ind.upper())
        if mapped is not None:
            return mapped
        # Fall back to a prefix match for OVERDUE_BY_30D etc.
        upper = ind.upper()
        if upper.startswith("OVERDUE") or upper.startswith("PAST_DUE"):
            return "overdue"
        if upper.startswith("DUE"):
            return "due"
        if upper.startswith("NOT"):
            return "not_due"
        return None


class GearDaysUntilServiceSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_days_until_service"
    _attr_native_unit_of_measurement = "d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_days_until_service"

    @property
    def native_value(self) -> int | None:
        return days_until_service(
            next_service_date=self._detail().get("nextServiceDate"),
            today=date.today(),
        )


class GearDateSensor(_GearEntityBase, SensorEntity):
    """Generic date-valued gear sensor."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar"

    def __init__(
        self,
        coordinator: GarminDiveCoordinator,
        *,
        gear_id: int,
        translation_key: str,
        detail_field: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_translation_key = translation_key
        self._field = detail_field
        self._attr_unique_id = f"{self._account_id}_{gear_id}_{unique_suffix}"

    @property
    def native_value(self) -> date | None:
        v = self._detail().get(self._field)
        return date.fromisoformat(v) if v else None


class GearDivesWithSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_dives_with"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_dives_with"

    @property
    def native_value(self) -> int:
        stats = self._detail().get("stats", {}) or {}
        return int(stats.get("numAssociatedDives") or 0)


class GearTotalDiveTimeSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_total_dive_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_total_dive_time"

    @property
    def native_value(self) -> float:
        stats = self._detail().get("stats", {}) or {}
        seconds = float(stats.get("totalAssociatedDiveTime") or 0)
        return round(seconds / 3600, 3)


class GearPurchasePriceSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_purchase_price"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_purchase_price"
        currency = self._detail().get("purchaseCurrency") or "GBP"
        self._attr_native_unit_of_measurement = currency

    @property
    def native_value(self) -> float | None:
        v = self._detail().get("purchasePrice")
        return float(v) if v is not None else None


def build_gear_entities(coordinator: GarminDiveCoordinator) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    if not coordinator.data:
        return entities
    for item in coordinator.data.gear:
        gid = item.gear_id
        # Always-present sensors
        entities.append(GearDivesWithSensor(coordinator, gear_id=gid))
        entities.append(GearTotalDiveTimeSensor(coordinator, gear_id=gid))
        if "purchasePrice" in (item.detail_raw or {}):
            entities.append(GearPurchasePriceSensor(coordinator, gear_id=gid))
        if (item.detail_raw or {}).get("purchaseDate"):
            entities.append(
                GearDateSensor(
                    coordinator,
                    gear_id=gid,
                    translation_key="gear_purchase_date",
                    detail_field="purchaseDate",
                    unique_suffix="purchase_date",
                )
            )
        # Service-related sensors
        if is_serviceable(item.gear_type):
            entities.append(GearServiceStatusSensor(coordinator, gear_id=gid))
            if (item.detail_raw or {}).get("nextServiceDate"):
                entities.append(GearDaysUntilServiceSensor(coordinator, gear_id=gid))
                entities.append(
                    GearDateSensor(
                        coordinator,
                        gear_id=gid,
                        translation_key="gear_next_service_date",
                        detail_field="nextServiceDate",
                        unique_suffix="next_service_date",
                    )
                )
            if (item.detail_raw or {}).get("lastServiceDate"):
                entities.append(
                    GearDateSensor(
                        coordinator,
                        gear_id=gid,
                        translation_key="gear_last_service_date",
                        detail_field="lastServiceDate",
                        unique_suffix="last_service_date",
                    )
                )
    return entities


class _DiveComputerEntityBase(GarminDiveSubDeviceEntity):
    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        device_match = next(
            d
            for d in coordinator.data.devices
            if d.serial_number and str(d.serial_number) == serial
        )
        gear_match = _matching_gear(
            coordinator,
            serial=serial,
            ant_channel=_device_ant_channel(device_match),
        )
        aliases: tuple[str, ...] = (str(gear_match.gear_id),) if gear_match is not None else ()
        super().__init__(
            coordinator,
            sub_device_id=f"device_{serial}",
            sub_device_name=device_match.product_display_name,
            manufacturer="Garmin",
            model=device_match.product_display_name,
            serial_number=serial,
            entity_picture=device_match.raw.get("imageUrl"),
            alias_sub_device_ids=aliases,
        )
        self._serial = serial


class DiveComputerGearTrackingSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_gear_tracking_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["tracked", "dismissed"]  # type: ignore[misc]
    _attr_icon = "mdi:watch"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_gear_tracking"

    @property
    def native_value(self) -> str | None:
        device = next(
            d
            for d in self.coordinator.data.devices
            if d.serial_number and str(d.serial_number) == self._serial
        )
        v = device.raw.get("gearTrackingStatus")
        return v.lower() if v else None


class DiveComputerSerialSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_serial_number"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_serial"

    @property
    def native_value(self) -> str:
        return self._serial


class DiveComputerPartNumberSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_part_number"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:barcode"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_part_number"

    @property
    def native_value(self) -> str | None:
        device = next(
            d
            for d in self.coordinator.data.devices
            if d.serial_number and str(d.serial_number) == self._serial
        )
        return device.raw.get("partNumber")


def build_dive_computer_entities(
    coordinator: GarminDiveCoordinator,
) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    if not coordinator.data:
        return entities
    # Garmin's /dive/devices occasionally returns the same physical device
    # twice — typically a cached entry without serial alongside a live one,
    # but stale entries with mismatched serials also occur. antChannelId is
    # the authoritative key for ANT+ accessories; serialNumber for the rest.
    seen_serial: set[str] = set()
    seen_ant: set[str] = set()
    for device in coordinator.data.devices:
        if device.serial_number is None:
            continue  # need a serial to construct the dive-computer entities
        serial = str(device.serial_number)
        if serial in seen_serial:
            continue
        ant = _device_ant_channel(device)
        if ant is not None and ant in seen_ant:
            continue
        seen_serial.add(serial)
        if ant is not None:
            seen_ant.add(ant)
        entities.append(DiveComputerGearTrackingSensor(coordinator, serial=serial))
        entities.append(DiveComputerSerialSensor(coordinator, serial=serial))
        if device.raw.get("partNumber"):
            entities.append(DiveComputerPartNumberSensor(coordinator, serial=serial))
    return entities


# --- Platform setup --------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        LastDiveSensor(coordinator),
        TotalDivesSensor(coordinator),
        CurrentYearDivesSensor(coordinator),
        LastDiveMaxDepthSensor(coordinator),
        LastDiveBottomTimeSensor(coordinator),
        LastDiveSurfaceIntervalSensor(coordinator),
        DiveLogYearSensor(coordinator),
        DivesByTagSensor(coordinator),
        GearCountSensor(coordinator),
    ]
    entities.extend(build_gear_entities(coordinator))
    entities.extend(build_dive_computer_entities(coordinator))
    async_add_entities(entities)
