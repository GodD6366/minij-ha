# MINIJ 小吉洗衣机 · Home Assistant 自定义集成

把 MINIJ（小吉）洗衣机接入 Home Assistant，并可桥接到 HomeKit。
基于小程序抓包还原的官方云接口 `lilith.minij.com`，纯云端轮询，不依赖米家。

## 功能

- 手机号 + 短信验证码登录，自动列出账号下的洗衣机，**不需要手动抓包**
- 主开关：开 = 按选中程序启动，关 = 停止（`power_off`，已抓包验证）
- 程序选择、烘干档位选择
- 常用模式快捷开关（快洗 / 强力 / 蒸煮洗，各带 +烘干 变体）
- 状态、阶段、剩余时间、总时长传感器

## 实体

| 实体 | 说明 |
| --- | --- |
| `switch.minij_washer` | 主开关（HomeKit 只桥这一个） |
| `select.minij_mode` | 洗衣程序（从设备程序表动态读取） |
| `select.minij_drying` | 烘干档位：无烘干 / 即穿 / 特干 / 30–180 分钟 |
| `switch.minij_quick` / `_dry` | 快洗 / 快洗+烘干 |
| `switch.minij_strong` / `_dry` | 强力 / 强力+烘干 |
| `switch.minij_boil` / `_dry` | 蒸煮洗 / 蒸煮洗+烘干 |
| `sensor.*_zhuang_tai` | 状态：工作中 / 休息中 |
| `sensor.*_jie_duan` | 阶段：主洗 / 漂洗 / 脱水 / 烘干 |
| `sensor.*_sheng_yu_shi_jian` | 剩余分钟 |
| `sensor.*_zong_shi_chang` | 总时长 |
| `sensor.*_cheng_xu` | 当前程序 |

快捷开关只在设备程序表里存在同名程序时创建，换机型也能用。

## 安装

### HACS（推荐）

1. HACS → 集成 → 右上角 ⋮ → 自定义仓库
2. 添加本仓库地址，类别选「集成」
3. 安装后重启 Home Assistant

### 手动

把 `custom_components/minij/` 复制到 `<config>/custom_components/minij/`，重启。

## 配置

1. 设置 → 设备与服务 → 添加集成 → 搜「小吉」
2. 输入手机号 → 收验证码 → 输入验证码
3. 账号下有多台设备时会让你选一台

token 有效期有限，失效后集成会提示重新认证，按提示重新走一次手机号登录即可。

## 接入 HomeKit

设置 → 设备与服务 → 添加集成 → **HomeKit Bridge**，包含域只勾 `switch`，
实体只选 `switch.minij_washer`。配对后「家庭」里就是一个开关：

- 开：按 HA 里选的程序 + 烘干档位启动
- 关：停止

HomeKit 没有洗衣机配件类型，只能以开关呈现；房间请在家庭 App 里长按配件自行设置。

## 选项

- 轮询间隔：默认 60 秒，最小 15 秒
- 停止指令 operateType：默认 `power_off`（抓包确认；个别机型不同可在此调整）

## 已知限制

- 非官方接口，厂商改版可能失效
- token 会过期，需要重新登录
- 云端轮询，状态最长滞后一个轮询周期
- 启动接口无幂等键，集成内已用「运行中禁止再次启动」做保护

## 参考

抓包确认的调用链：

```
POST /api/captcha/sendSmsCaptcha   {"phone": "...", "type": "login"}
POST /api/login/loginByPhone       {"phone": "...", "captcha": "..."} → data.token
POST /api/login/prepareInit        {"deviceId": ""}
GET  /api/device/getUserBindDeviceList
GET  /api/device/v3/getDeviceDetail?deviceId=...
GET  /api/device/v2/getDeviceModeList?deviceId=...
GET  /api/device/v2/getUserDeviceMode?deviceId=...&userDeviceModeId=...
POST /api/device/v2/deviceOperate  operateType=activate  (启动)
POST /api/device/v2/deviceOperate  operateType=power_off (停止)
```

请求头固定：`token`、`platform: MINI_PROGRAM_IOS`、`platformBrand: miniProgram`、`version: 2.3.3`。
接口无签名，仅靠 token 鉴权。
