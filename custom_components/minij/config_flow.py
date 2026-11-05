"""配置流程：手机号 + 短信验证码登录，自动列出账号下的洗衣机。"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MinijAuthError, MinijClient, MinijError
from .const import (
    CONF_DEVICE_ID,
    CONF_PHONE,
    CONF_SCAN_INTERVAL,
    CONF_STOP_OPERATE_TYPE,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STOP_OPERATE_TYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MinijConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._phone: str | None = None
        self._token: str | None = None
        self._devices: list[dict] = []

    # ---- 第一步：手机号 ----
    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = user_input[CONF_PHONE].strip()
            client = MinijClient(async_get_clientsession(self.hass), "", "")
            try:
                await client.send_sms(phone)
            except MinijError as err:
                _LOGGER.warning("发送验证码失败: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._phone = phone
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PHONE): str}),
            errors=errors,
        )

    # ---- 第二步：验证码 ----
    async def async_step_code(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            client = MinijClient(async_get_clientsession(self.hass), "", "")
            try:
                await client.login_by_phone(self._phone, user_input["code"].strip())
                devices = await client.get_devices()
            except MinijAuthError:
                errors["base"] = "invalid_auth"
            except MinijError:
                errors["base"] = "cannot_connect"
            else:
                self._token = client.token
                self._devices = [d for d in devices if d.get("deviceType") == "washer"] or devices
                if not self._devices:
                    errors["base"] = "no_device"
                elif len(self._devices) == 1:
                    return self._create(self._devices[0])
                else:
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"phone": self._phone or ""},
        )

    # ---- 第三步：选设备 ----
    async def async_step_device(self, user_input=None):
        if user_input is not None:
            device = next(d for d in self._devices if d["deviceId"] == user_input[CONF_DEVICE_ID])
            return self._create(device)

        options = {
            d["deviceId"]: f"{d.get('deviceNickName') or d.get('deviceName')}（{d['deviceId']}）"
            for d in self._devices
        }
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(options)}),
        )

    def _create(self, device: dict):
        device_id = device["deviceId"]
        self.unique_id = device_id
        return self.async_create_entry(
            title=device.get("deviceNickName") or device.get("deviceName") or "小吉洗衣机",
            data={
                CONF_TOKEN: self._token,
                CONF_DEVICE_ID: device_id,
                CONF_PHONE: self._phone,
            },
        )

    # ---- 重新认证 ----
    async def async_step_reauth(self, entry_data):
        self._phone = entry_data.get(CONF_PHONE)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None and "phone" in user_input:
            phone = user_input["phone"].strip()
            client = MinijClient(async_get_clientsession(self.hass), "", "")
            try:
                await client.send_sms(phone)
            except MinijError:
                errors["base"] = "cannot_connect"
            else:
                self._phone = phone
                return await self.async_step_reauth_code()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("phone", default=entry.data.get(CONF_PHONE, "")): str}),
            errors=errors,
        )

    async def async_step_reauth_code(self, user_input=None):
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None:
            client = MinijClient(async_get_clientsession(self.hass), "", entry.data[CONF_DEVICE_ID])
            try:
                await client.login_by_phone(self._phone, user_input["code"].strip())
            except MinijError:
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_TOKEN: client.token, CONF_PHONE: self._phone},
                )
        return self.async_show_form(
            step_id="reauth_code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MinijOptionsFlow()


class MinijOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=15, max=600)),
                    vol.Required(
                        CONF_STOP_OPERATE_TYPE,
                        default=current.get(CONF_STOP_OPERATE_TYPE, DEFAULT_STOP_OPERATE_TYPE),
                    ): str,
                }
            ),
        )
