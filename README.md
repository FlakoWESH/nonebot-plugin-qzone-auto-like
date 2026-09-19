<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ nonebot-plugin-qzone-auto-like ✨
[![LICENSE](https://img.shields.io/github/license/FlakoWESH/nonebot-plugin-qzone-auto-like.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-qzone-auto-like.svg)](https://pypi.python.org/pypi/nonebot-plugin-qzone-auto-like)
[![python](https://img.shields.io/badge/python-3.10|3.11|3.12|3.13-blue.svg)](https://www.python.org)
<br/>
[![ruff](https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![nonebot2](https://img.shields.io/badge/nonebot-2.0+-red.svg)](https://v2.nonebot.dev)
[![alconna](https://img.shields.io/badge/Alconna-powered-blue?style=flat-square)](https://github.com/nonebot/plugin-alconna)

</div>

## 📖 介绍

NoneBot2 QQ 空间说说自动点赞插件，后台定时拉取好友空间说说并自动点赞。支持从 NapCat 自动获取 QQ 空间 Cookie 并推送到 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 桥接服务。
> 本插件不会保存你的 QQ 密码，QQ 空间 Cookie 由 NapCat 在本地管理，插件仅在本地各服务之间传递。Cookie 不会发送到任何第三方。

### ✨ 功能特性

- **自动点赞说说**：Bot 启动后后台定时轮询好友空间时间线，对未点赞的说说自动点赞
- **Cookie 自动刷新**：通过 NapCat 的 `get_cookies` API 自动获取最新 QQ 空间 Cookie，定时推送到 onebot-qzone
- **防重复点赞**：本地记录已点赞的说说 ID，重启不丢失，不会重复点赞同一条
- **可配置轮询间隔**：自定义轮询频率和每轮最大点赞数
- **点赞间隔控制**：单条说说之间固定间隔，模拟人工操作，降低风控概率
- **状态查询**：在 QQ 中发送指令即可查看运行状态、累计点赞数、Cookie 刷新状态
- **优雅降级**：未启用 Cookie 自动刷新时插件仍可正常工作，仅需手动配置 Cookie
- **Alconna 优化**：使用 Alconna 命令解析器，类型安全参数获取

## 🔧 工作原理

```
┌──────────────────┐   NapCat HTTP API   ┌──────────┐
│                  │ ◄──────────────────► │  NapCat  │
│                  │   POST /get_cookies   │ (QQ登录)  │
│                  │                      └──────────┘
│  NoneBot2 插件   │
│ (qzone-auto-like)│   POST /update_cookie ┌──────────────────┐   QQ空间Web API   ┌──────────┐
│                  │ ◄──────────────────► │  onebot-qzone    │ ◄──────────────► │  QQ空间   │
│                  │   (动态更新Cookie)    │  (桥接服务)      │   Cookie 认证     │  服务器   │
└──────────────────┘                      └──────────────────┘                   └──────────┘
```

**三个组件的角色：**

| 组件 | 作用 |
|---|---|
| **NapCat** | 已登录 QQ 的协议端，提供 `get_cookies` API 获取 QQ 空间 Cookie |
| **onebot-qzone** | QQ 空间操作桥接服务（Node.js），提供 `update_cookie` API 接收新 Cookie，并暴露点赞/获取说说等 HTTP API |
| **本插件** | NoneBot2 插件，负责定时从 NapCat 获取 Cookie → 推送到 onebot-qzone，同时定时执行点赞操作 |

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-qzone-auto-like --upgrade

使用 **pypi** 源安装

    nb plugin install nonebot-plugin-qzone-auto-like --upgrade -i "https://pypi.org/simple"

使用 **清华源** 安装

    nb plugin install nonebot-plugin-qzone-auto-like --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-qzone-auto-like

安装仓库 master 分支

    uv add git+https://github.com/FlakoWESH/nonebot-plugin-qzone-auto-like@master
</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-qzone-auto-like

安装仓库 master 分支

    pdm add git+https://github.com/FlakoWESH/nonebot-plugin-qzone-auto-like@master
</details>

<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-qzone-auto-like

安装仓库 master 分支

    poetry add git+https://github.com/FlakoWESH/nonebot-plugin-qzone-auto-like@master
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_qzone_auto_like"]

</details>

<details>
<summary>前置依赖：部署 onebot-qzone 桥接服务</summary>

自动点赞功能依赖 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 桥接服务，它是一个独立的 Node.js 服务：

```bash
git clone https://github.com/Gu-Heping/onebot-qzone.git
cd onebot-qzone
npm install
cp .env.example .env  # 编辑 .env 配置端口和访问令牌
npm start
```

默认监听 `http://127.0.0.1:5700`。详见 [onebot-qzone 文档](https://github.com/Gu-Heping/onebot-qzone)。

</details>

## ⚙️ 配置

在 `.env` 文件中添加以下配置（均为可选，有默认值）：

### 自动点赞配置

| 配置项 | 类型 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| QZONE_ENABLE_AUTO_LIKE | bool | `true` | 是否启用自动点赞 |
| QZONE_LIKE_INTERVAL | int | `600` | 轮询间隔（秒），默认 10 分钟 |
| QZONE_MAX_LIKE_COUNT | int | `50` | 每轮最多点赞说说数量 |
| QZONE_PER_LIKE_INTERVAL | float | `1.0` | 单条说说点赞间隔（秒） |
| QZONE_QQ_NUMBER | str | `""` | 要操作的 QQ 号，留空则用 Bot 自身 |
| QZONE_DATA_FILE | str | `data/qzone_like_records.json` | 已点赞记录文件路径 |

### Cookie 自动刷新配置

| 配置项 | 类型 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| QZONE_ENABLE_AUTO_COOKIE | bool | `false` | 是否启用自动从 NapCat 获取 Cookie |
| QZONE_NAPCAT_URL | str | `http://127.0.0.1:3000` | NapCat HTTP API 地址 |
| QZONE_NAPCAT_TOKEN | str | `""` | NapCat access token（如设置了鉴权则填） |
| QZONE_BRIDGE_URL | str | `http://127.0.0.1:5700` | onebot-qzone 桥接服务地址 |
| QZONE_BRIDGE_TOKEN | str | `""` | onebot-qzone access token（如设置了鉴权则填） |
| QZONE_COOKIE_REFRESH_INTERVAL | int | `7200` | Cookie 刷新间隔（秒），默认 2 小时 |
| QZONE_COOKIE_REQUEST_TIMEOUT | int | `10` | HTTP 请求超时时间（秒） |

## 🔄 Cookie 自动刷新

启用 `QZONE_ENABLE_AUTO_COOKIE=true` 后，插件会自动完成以下流程，无需手动管理 Cookie：

```
每 2 小时自动执行：
  1. 调用 NapCat: POST /get_cookies  {domain: "user.qzone.qq.com"}
  2. 验证返回的 Cookie 包含 uin / p_uin / skey / p_skey
  3. 调用 onebot-qzone: POST /update_cookie  {cookie: "uin=...; p_skey=..."}
  4. onebot-qzone 自动更新会话并写回 .env
```

### 前提条件

1. **NapCat 版本 ≥ v4.18.0** —— 旧版本 `get_cookies` 返回的 `bkn` 计算有 bug，无法正常调用 QQ 空间 API
2. **NapCat 已开启 HTTP API** —— 在 NapCat 配置中启用 HTTP 服务端口（默认 3000）
3. **onebot-qzone 桥接服务正在运行** —— 默认监听 5700 端口
4. **NapCat 与本插件网络互通** —— 通常都在同一台机器上，默认地址即可

### 启用示例

在 `.env` 中添加：

```env
QZONE_ENABLE_AUTO_COOKIE=true
QZONE_NAPCAT_URL=http://127.0.0.1:3000
QZONE_BRIDGE_URL=http://127.0.0.1:5700
```

如果 NapCat 或 onebot-qzone 设置了访问令牌，也一并填写。重启 NoneBot2 后，发送"空间点赞状态"即可看到 Cookie 自动刷新状态。

## 🎉 使用

### 指令表

| 指令 | 说明 |
|:---:|:---:|
| 空间点赞状态 | 查看点赞状态 + Cookie 自动刷新状态 |

### 返回示例（已启用 Cookie 自动刷新）

```
QQ空间自动点赞状态
功能开关：已启用
任务状态：运行中
轮询间隔：600 秒
每轮上限：50 条
累计已点赞：128 条说说

─── Cookie 自动刷新 ───
刷新间隔：7200 秒
上次刷新：2026-09-18 14:30:00 ✅ 成功
累计刷新：12 次
```

### 运行机制

1. Bot 启动后自动注册后台定时任务
2. **Cookie 刷新任务**：每隔 `QZONE_COOKIE_REFRESH_INTERVAL` 秒，从 NapCat 获取最新 Cookie 并推送到 onebot-qzone
3. **点赞任务**：每隔 `QZONE_LIKE_INTERVAL` 秒拉取好友空间说说，跳过已点赞的，逐条点赞
4. 已点赞的说说 ID 持久化到 `QZONE_DATA_FILE`，不会重复点赞

## 🛡️ 防风控说明

| 机制 | 默认值 | 说明 |
|---|---|---|
| **轮询间隔** | 600 秒 | 每 10 分钟轮询一次，避免频繁请求 |
| **单次上限** | 50 条 | 每次最多点赞 50 条 |
| **点赞间隔** | 1 秒 | 模拟人工操作节奏 |
| **已点赞记录** | 永久保留 | 避免重复点赞 |
| **Cookie 自动刷新** | 7200 秒 | 每 2 小时自动续期 Cookie，避免过期 |
| **异常自动恢复** | 内置 | 出错后自动等待下一轮 |

## ❓ 常见问题

### Q1：Cookie 自动刷新显示"Cookie 缺少必要字段"

**原因**：NapCat 返回的 Cookie 中缺少 `uin`、`p_uin`、`skey`、`p_skey` 中的某个字段。

**排查步骤**：
1. 确认 NapCat 版本 ≥ v4.18.0
2. 确认 NapCat 已正确登录 QQ
3. 在浏览器中用同一 QQ 号访问[QQ空间](https://user.qzone.qq.com)，确认能正常打开
4. 如果刚登录 QQ，等待几分钟后再试

### Q2：Cookie 自动刷新显示"NapCat API 返回错误"

**排查步骤**：
1. 确认 NapCat 正在运行：`curl http://127.0.0.1:3000/get_login_info`
2. 确认 `QZONE_NAPCAT_URL` 地址和端口正确
3. 如果 NapCat 设置了访问令牌，确认 `QZONE_NAPCAT_TOKEN` 填写正确
4. 确认 NapCat 配置中开启了 HTTP API

### Q3：Cookie 刷新成功但点赞仍然失败

**可能原因**：
1. Cookie 虽然更新了，但 QQ 空间服务端还未生效（等待 1-2 分钟）
2. onebot-qzone 桥接服务需要重启才能加载新 Cookie
3. 账号被 QQ 空间风控

**解决方法**：
- 如果使用的是旧版 onebot-qzone（不支持 `update_cookie` API），需要手动重启 onebot-qzone 服务
- 新版 onebot-qzone 会自动热更新 Cookie，无需重启

### Q4：不启用 Cookie 自动刷新可以用吗？

可以。如果不启用 `QZONE_ENABLE_AUTO_COOKIE`，你需要手动在 onebot-qzone 的 `.env` 文件中配置 `QZONE_COOKIE_STRING`，Cookie 过期后需要手动更新。启用自动刷新后则无需手动干预。

### Q5：已点赞记录文件在哪里？

默认为 `data/qzone_like_records.json`。删除后下一轮会重新点赞最新说说。

## ⚠️ 注意事项

1. **三个服务**：本插件需要 NapCat（协议端）、onebot-qzone（桥接服务）、NoneBot2 三者协同工作
2. **Cookie 安全**：Cookie 仅在本地各服务之间通过 HTTP 传递，不会上传到任何第三方服务器
3. **频率控制**：建议轮询间隔不低于 5 分钟（300 秒），频繁请求可能触发 QQ 风控
4. **协议端兼容**：Cookie 自动刷新功能目前适配 NapCat（`get_cookies` API），其他协议端需手动配置 Cookie
5. **风险提示**：自动点赞属于自动化操作，请遵守 QQ 空间使用规则，因使用本插件导致的账号限制由使用者自行承担
