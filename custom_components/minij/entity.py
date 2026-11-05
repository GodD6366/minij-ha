"""实体基类。"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MinijCoordinator
from .const import CONF_DEVICE_ID, DOMAIN


class MinijEntity(CoordinatorEntity[MinijCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MinijCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
            name=entry.title,
            manufacturer="MINIJ",
            model="minij.washer.x44",
        )

    @property
    def status(self) -> dict:
        return self.coordinator.data or {}
