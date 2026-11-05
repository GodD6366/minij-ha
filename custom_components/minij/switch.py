"""洗衣开关：主开关（HomeKit）+ 常用模式开关（HA 内直控）。"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinijCoordinator
from .api import MinijAuthError, MinijClient, MinijError
from .const import CONF_STOP_OPERATE_TYPE, DEFAULT_STOP_OPERATE_TYPE, DOMAIN, QUICK_MODES
from .entity import MinijEntity

_LOGGER = logging.getLogger(__name__)
NO_DRY = "无"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MinijCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [MinijMainSwitch(coordinator, entry)]

    by_name = {m.get("chineseName"): m for m in coordinator.modes}
    for name, slug in QUICK_MODES.items():
        mode = by_name.get(name)
        if not mode or not mode.get("id"):
            continue
        mode_id = str(mode["id"])
        entities.append(MinijModeSwitch(coordinator, entry, name, mode_id, None, slug))
        entities.append(MinijModeSwitch(coordinator, entry, f"{name}+烘干", mode_id, 2, f"{slug}_dry"))

    async_add_entities(entities)


class _MinijSwitchBase(MinijEntity, SwitchEntity):
    _attr_icon = "mdi:washing-machine"
    _attr_has_entity_name = False

    async def _start(self, mode_id: str, drying: int, label: str) -> None:
        if self.coordinator.running:
            raise HomeAssistantError("设备正在运行其他程序，请先停止再开始")
        try:
            user_mode = await self.coordinator.client.get_user_mode(mode_id)
            stats = MinijClient.build_stats(user_mode, {"dryingCompoundOption": drying})
            await self.coordinator.client.activate(mode_id, stats)
        except MinijAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinijError as err:
            raise HomeAssistantError(f"启动失败：{err}") from err

        _LOGGER.info("洗衣机启动：%s（烘干=%s）", label, drying)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def _stop(self) -> None:
        operate_type = self._entry.options.get(
            CONF_STOP_OPERATE_TYPE, DEFAULT_STOP_OPERATE_TYPE
        )
        try:
            await self.coordinator.client.operate(operate_type)
        except MinijAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinijError as err:
            raise HomeAssistantError(f"停止失败（{operate_type}）：{err}") from err
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict:
        status = self.status
        return {
            "程序": status.get("current_mode"),
            "状态": status.get("current_status"),
            "阶段": status.get("current_process"),
            "剩余分钟": status.get("program_remain_time"),
            "烘干": status.get("dry_status"),
        }


class MinijMainSwitch(_MinijSwitchBase):
    """HomeKit 用的主开关：开 = 按 HA 里选中的程序 + 烘干启动。"""

    _attr_name = "洗衣机"

    def __init__(self, coordinator: MinijCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['device_id']}_washer_main"
        self.entity_id = "switch.minij_washer"

    @property
    def is_on(self) -> bool:
        return self.coordinator.running

    async def async_turn_on(self, **kwargs) -> None:
        if self.is_on:
            return
        mode_id = self.coordinator.selected_mode_id
        if not mode_id:
            modes = self.coordinator.modes
            mode_id = str(modes[0]["id"]) if modes else None
        if not mode_id:
            raise HomeAssistantError("没有可用的洗衣程序")
        await self._start(
            mode_id, self.coordinator.selected_drying, self.coordinator.mode_name(mode_id)
        )

    async def async_turn_off(self, **kwargs) -> None:
        if not self.is_on:
            return
        await self._stop()

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs["将运行"] = (
            self.coordinator.mode_name(self.coordinator.selected_mode_id)
            if self.coordinator.selected_mode_id
            else None
        )
        attrs["烘干档"] = self.coordinator.selected_drying
        return attrs


class MinijModeSwitch(_MinijSwitchBase):
    def __init__(
        self,
        coordinator: MinijCoordinator,
        entry: ConfigEntry,
        name: str,
        mode_id: str,
        drying: int | None,
        object_id: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_unique_id = f"{entry.data['device_id']}_{object_id}"
        self.entity_id = f"switch.{object_id}"
        self._mode_id = mode_id
        self._mode_name = name.replace("+烘干", "")
        self._drying = drying

    @property
    def is_on(self) -> bool:
        if not self.coordinator.running:
            return False
        status = self.status
        if status.get("current_mode") != self._mode_name:
            return False
        dry = status.get("dry_status") or NO_DRY
        if self._drying is None:
            return dry == NO_DRY
        return dry != NO_DRY

    async def async_turn_on(self, **kwargs) -> None:
        if self.is_on:
            return
        await self._start(
            self._mode_id, self._drying if self._drying is not None else 0, self._attr_name
        )

    async def async_turn_off(self, **kwargs) -> None:
        if not self.is_on:
            return
        await self._stop()
