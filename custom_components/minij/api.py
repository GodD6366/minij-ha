"""MINIJ（小吉）云 API 客户端。

只依赖 aiohttp，方便在 HA 之外单独测试。
"""
from __future__ import annotations

import json
from typing import Any

import aiohttp

BASE_URL = "https://lilith.minij.com"
APP_VERSION = "2.3.3"
TIMEOUT = aiohttp.ClientTimeout(total=20)


class MinijError(Exception):
    """接口调用失败。"""


class MinijAuthError(MinijError):
    """token 失效或无权控制。"""


class MinijClient:
    def __init__(self, session: aiohttp.ClientSession, token: str, device_id: str) -> None:
        self._session = session
        self._token = token.strip()
        self.device_id = device_id.strip()

    def _headers(self) -> dict[str, str]:
        return {
            "token": self._token,
            "content-type": "application/json",
            "platform": "MINI_PROGRAM_IOS",
            "platformBrand": "miniProgram",
            "version": APP_VERSION,
            "Accept-Encoding": "gzip,compress,br,deflate",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                "MicroMessenger/8.0.80 NetType/WIFI Language/zh_CN"
            ),
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = BASE_URL + path
        try:
            async with self._session.request(
                method, url, params=params, json=payload, headers=self._headers(), timeout=TIMEOUT
            ) as resp:
                if resp.status in (401, 403):
                    raise MinijAuthError("token 失效或没有该设备的控制权限")
                text = await resp.text()
                if resp.status != 200:
                    raise MinijError(f"HTTP {resp.status}: {text[:200]}")
        except aiohttp.ClientError as err:  # noqa: PERF203
            raise MinijError(f"网络错误: {err}") from err
        except TimeoutError as err:
            raise MinijError("请求超时") from err

        try:
            body = json.loads(text)
        except ValueError as err:
            raise MinijError(f"返回非 JSON: {text[:200]}") from err

        if not body.get("success"):
            raise MinijError(f"{body.get('errorCode')}: {body.get('errorMessage')}")
        return body.get("data")

    # ---- 登录 ----
    async def send_sms(self, phone: str) -> None:
        await self._request(
            "POST",
            "/api/captcha/sendSmsCaptcha",
            payload={"phone": phone, "type": "login"},
        )

    async def login_by_phone(self, phone: str, code: str) -> dict[str, Any]:
        data = await self._request(
            "POST",
            "/api/login/loginByPhone",
            payload={"phone": phone, "captcha": code},
        )
        token = (data or {}).get("token")
        if not token:
            raise MinijAuthError("登录返回里没有 token")
        self._token = token
        await self.prepare_init()
        return data or {}

    async def prepare_init(self) -> None:
        try:
            await self._request(
                "POST", "/api/login/prepareInit", payload={"deviceId": ""}
            )
        except MinijError:
            # 初始化失败不影响后续读取
            pass

    async def get_devices(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/device/getUserBindDeviceList")
        return data or []

    # ---- 读 ----
    async def get_detail(self) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "/api/device/v3/getDeviceDetail",
            params={"deviceId": self.device_id, "bucketCode": ""},
        )
        return data or {}

    async def get_status(self) -> dict[str, Any]:
        detail = await self.get_detail()
        return detail.get("deviceCharacterMap") or {}

    async def get_modes(self) -> list[dict[str, Any]]:
        """返回扁平的程序列表。

        接口给的是 {frequentlyDeviceModeVOList, otherDeviceModeVOList, currentDeviceMode}，
        这里合并去重，方便上层直接按 id/名称取用。
        """
        data = await self._request(
            "GET",
            "/api/device/v2/getDeviceModeList",
            params={"deviceId": self.device_id, "bucketCode": ""},
        )
        if not isinstance(data, dict):
            return list(data or [])

        modes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [
            *(data.get("frequentlyDeviceModeVOList") or []),
            *(data.get("otherDeviceModeVOList") or []),
            data.get("currentDeviceMode") or {},
        ]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            key = str(item["id"])
            if key in seen:
                continue
            seen.add(key)
            modes.append(item)
        return modes

    async def get_user_mode(self, mode_id: str) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "/api/device/v2/getUserDeviceMode",
            params={
                "deviceId": self.device_id,
                "userDeviceModeId": str(mode_id),
                "bucketCode": "",
            },
        )
        return data or {}

    # ---- 写 ----
    async def estimate(self, mode_id: str, stats: list[dict[str, Any]]) -> int | None:
        data = await self._request(
            "POST",
            "/api/device/deviceStatsSetup",
            payload={"deviceId": self.device_id, "activateParam": self._activate_param(mode_id, stats)},
        )
        return data if isinstance(data, int) else None

    async def activate(self, mode_id: str, stats: list[dict[str, Any]]) -> None:
        await self._request(
            "POST",
            "/api/device/v2/deviceOperate",
            payload={
                "deviceId": self.device_id,
                "bucketCode": "",
                "operateType": "activate",
                "activateParam": self._activate_param(mode_id, stats),
            },
        )

    async def power_off(self) -> None:
        """停止。抓包确认的停止指令是 power_off。"""
        await self.operate("power_off")

    async def operate(self, operate_type: str) -> None:
        await self._request(
            "POST",
            "/api/device/v2/deviceOperate",
            payload={"deviceId": self.device_id, "bucketCode": "", "operateType": operate_type},
        )

    # ---- 工具 ----
    @staticmethod
    def _activate_param(mode_id: str, stats: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "userDeviceModeId": str(mode_id),
            "userDeviceModeStatsSimpleList": [
                {
                    "value": int(item["value"]),
                    "code": item["code"],
                    "userDeviceModeStatsId": item["userDeviceModeStatsId"],
                }
                for item in stats
            ],
        }

    @staticmethod
    def build_stats(user_mode: dict[str, Any], overrides: dict[str, int] | None = None) -> list[dict[str, Any]]:
        """把 getUserDeviceMode 的参数 schema 转成下发用的简化列表。

        overrides 按 code 覆盖取值，未覆盖的用接口给的当前值/默认值。
        """
        overrides = overrides or {}
        result: list[dict[str, Any]] = []
        for stat in user_mode.get("userDeviceModeStatsList") or []:
            code = stat.get("code")
            if code in overrides:
                value = overrides[code]
            else:
                value = stat.get("value")
                if value is None:
                    value = stat.get("defaultValue", 0)
            result.append(
                {
                    "code": code,
                    "value": int(value),
                    "userDeviceModeStatsId": stat["id"],
                }
            )
        return result
