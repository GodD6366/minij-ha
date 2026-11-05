"""常量。"""
from __future__ import annotations

DOMAIN = "minij"

CONF_TOKEN = "token"
CONF_PHONE = "phone"
CONF_DEVICE_ID = "device_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEFAULT_MODE_ID = "default_mode_id"
CONF_DRYING = "drying"
CONF_STOP_OPERATE_TYPE = "stop_operate_type"

DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MODE_ID = "3171701"  # 快洗
DEFAULT_STOP_OPERATE_TYPE = "power_off"

# 烘干档位：0 无烘干 / 2 即穿 / 3 特干 / 4~9 = 30~180 分钟
DRYING_LABELS: dict[str, int] = {
    "无烘干": 0,
    "即穿": 2,
    "特干": 3,
    "30 分钟": 4,
    "60 分钟": 5,
    "90 分钟": 6,
    "120 分钟": 7,
    "150 分钟": 8,
    "180 分钟": 9,
}

DRYING_OPTIONS = {
    "0": "无烘干",
    "2": "即穿",
    "3": "特干",
    "4": "30 分钟",
    "5": "60 分钟",
    "6": "90 分钟",
    "7": "120 分钟",
    "8": "150 分钟",
    "9": "180 分钟",
}

RUNNING_STATES = {"工作中", "运行中", "working", "running"}

# 快速模式开关：程序名 -> entity_id 后缀（程序 ID 运行时按名字从设备程序表里查）
QUICK_MODES: dict[str, str] = {
    "快洗": "minij_quick",
    "强力": "minij_strong",
    "蒸煮洗": "minij_boil",
}
