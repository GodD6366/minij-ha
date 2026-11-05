"""选择实体：程序 + 烘干档位。"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinijCoordinator
from .const import DOMAIN, DRYING_LABELS
from .entity import MinijEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MinijCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MinijProgramSelect(coordinator, entry), MinijDryingSelect(coordinator, entry)])


class MinijProgramSelect(MinijEntity, SelectEntity):
    _attr_name = "洗衣程序"
    _attr_icon = "mdi:format-list-bulleted"
    _attr_has_entity_name = False

    def __init__(self, coordinator: MinijCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['device_id']}_program_select"
        self.entity_id = "select.minij_mode"

    @property
    def options(self) -> list[str]:
        names = [m.get("chineseName") for m in self.coordinator.modes if m.get("chineseName")]
        return list(dict.fromkeys(names)) or ["快洗"]

    @property
    def current_option(self) -> str:
        mode_id = self.coordinator.selected_mode_id
        if not mode_id:
            status = self.status
            current = status.get("current_mode")
            if current in self.options:
                return current
            mode_id = str(self.coordinator.modes[0].get("id")) if self.coordinator.modes else None
        name = self.coordinator.mode_name(mode_id) if mode_id else self.options[0]
        return name if name in self.options else self.options[0]

    async def async_select_option(self, option: str) -> None:
        for mode in self.coordinator.modes:
            if mode.get("chineseName") == option:
                self.coordinator.selected_mode_id = str(mode.get("id"))
                break
        self.async_write_ha_state()


class MinijDryingSelect(MinijEntity, SelectEntity):
    _attr_name = "烘干"
    _attr_icon = "mdi:tumble-dryer"
    _attr_has_entity_name = False

    def __init__(self, coordinator: MinijCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['device_id']}_drying_select"
        self.entity_id = "select.minij_drying"

    @property
    def options(self) -> list[str]:
        return list(DRYING_LABELS)

    @property
    def current_option(self) -> str:
        value = self.coordinator.selected_drying
        for label, val in DRYING_LABELS.items():
            if val == value:
                return label
        return next(iter(DRYING_LABELS))

    async def async_select_option(self, option: str) -> None:
        self.coordinator.selected_drying = DRYING_LABELS.get(option, 0)
        self.async_write_ha_state()
