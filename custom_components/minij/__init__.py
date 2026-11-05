"""MINIJ 小吉洗衣机集成入口。"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinijAuthError, MinijClient, MinijError
from .const import (
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]


class MinijCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """轮询设备状态。"""

    def __init__(self, hass: HomeAssistant, client: MinijClient, interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.modes: list[dict[str, Any]] = []
        self.selected_mode_id: str | None = None
        self.selected_drying: int = 0

    async def async_load_modes(self) -> None:
        try:
            self.modes = await self.client.get_modes()
        except MinijAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinijError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.get_status()
        except MinijAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinijError as err:
            raise UpdateFailed(str(err)) from err

    def mode_name(self, mode_id: str) -> str:
        for mode in self.modes:
            if str(mode.get("id")) == str(mode_id):
                return mode.get("chineseName") or mode.get("englishName") or mode_id
        return mode_id

    @property
    def running(self) -> bool:
        status = str((self.data or {}).get("current_status") or "")
        alias = str((self.data or {}).get("current_status_alias") or "")
        return status in ("工作中", "运行中") or alias in ("working", "running")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """v1（手填 token）→ v2（手机号登录）。"""
    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = MinijClient(session, entry.data[CONF_TOKEN], entry.data[CONF_DEVICE_ID])
    interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    coordinator = MinijCoordinator(hass, client, interval)
    await coordinator.async_load_modes()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
