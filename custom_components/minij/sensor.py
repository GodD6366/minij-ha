"""状态传感器。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinijCoordinator
from .const import DOMAIN
from .entity import MinijEntity


@dataclass(frozen=True, kw_only=True)
class MinijSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSORS: tuple[MinijSensorDescription, ...] = (
    MinijSensorDescription(
        key="program",
        name="程序",
        icon="mdi:washing-machine",
        value_fn=lambda s: s.get("current_mode"),
    ),
    MinijSensorDescription(
        key="status",
        name="状态",
        icon="mdi:state-machine",
        value_fn=lambda s: s.get("current_status"),
    ),
    MinijSensorDescription(
        key="stage",
        name="阶段",
        icon="mdi:water",
        value_fn=lambda s: s.get("current_process"),
    ),
    MinijSensorDescription(
        key="remaining",
        name="剩余时间",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _as_int(s.get("program_remain_time")),
    ),
    MinijSensorDescription(
        key="total",
        name="总时长",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda s: _as_int(s.get("program_total_time")),
    ),
)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MinijCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MinijSensor(coordinator, entry, desc) for desc in SENSORS)


class MinijSensor(MinijEntity, SensorEntity):
    entity_description: MinijSensorDescription

    def __init__(
        self, coordinator: MinijCoordinator, entry: ConfigEntry, description: MinijSensorDescription
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['device_id']}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.status)
