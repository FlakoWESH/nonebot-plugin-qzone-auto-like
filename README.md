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

NoneBot2 QQ 空间说说自动点赞插件，后台定时拉取 QQ 空间最新说说并自动点赞。基于 Alconna 命令解析器优化，依赖 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 库。

- **自动点赞说说**：后台定时轮询 QQ 空间，自动为最新说说点赞
- **防重复点赞**：记录已点赞的说说 ID，避免重复操作
- **可配置轮询间隔**：支持自定义轮询频率和每轮最大点赞数
- **点赞间隔控制**：单条说说之间可配置间隔，防止频率过高被风控
- **状态查询**：发送指令可查看自动点赞当前运行状态
- **Alconna 优化**：使用 Alconna 命令解析器，类型安全参数获取

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
<summary>安装可选依赖 onebot-qzone</summary>

自动点赞功能依赖 [onebot-qzone](https://github.com/Gu-Heping/onebot-qzone) 库，未安装时插件仍可正常加载，仅自动点赞不生效：

    uv add onebot-qzone

或从 GitHub 安装最新版：

    uv add git+https://github.com/Gu-Heping/onebot-qzone.git

</details>

## ⚙️ 配置

在 `.env` 文件中添加以下配置（均为可选，有默认值）：

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| QZONE_ENABLE_AUTO_LIKE | 否 | `true` | 是否启用自动点赞 |
| QZONE_LIKE_INTERVAL | 否 | `3600` | 轮询间隔（秒），默认每小时检查一次 |
| QZONE_MAX_LIKE_COUNT | 否 | `20` | 每轮最多点赞的说说数量 |
| QZONE_PER_LIKE_INTERVAL | 否 | `2.0` | 单条说说点赞之间的间隔（秒） |
| QZONE_QQ_NUMBER | 否 | 空（Bot 自身） | 要操作的 QQ 号，留空则使用 Bot 登录的 QQ |
| QZONE_DATA_FILE | 否 | `data/qzone_liked_posts.json` | 已点赞说说记录文件路径 |

## 🎉 使用

### 指令表

| 指令 | 说明 |
|:---:|:---:|
| 空间点赞状态 | 查看自动点赞当前运行状态 |

### 使用示例

```
空间点赞状态
```

### 运行机制

1. Bot 启动后自动开启后台定时任务
2. 每隔 `QZONE_LIKE_INTERVAL` 秒拉取一次 QQ 空间最新说说
3. 对比本地记录，找出未点赞的新说说
4. 逐条点赞，每条间隔 `QZONE_PER_LIKE_INTERVAL` 秒
5. 每轮最多点赞 `QZONE_MAX_LIKE_COUNT` 条
6. 已点赞的说说 ID 持久化到 `QZONE_DATA_FILE`，不会重复点赞

## ⚠️ 注意事项

1. **依赖安装**：自动点赞功能需要安装 `onebot-qzone` 库；未安装时插件正常加载但自动点赞不生效
2. **登录态要求**：QQ 空间操作依赖 Bot 的 QQ 登录态（Cookie），请确保协议端已正确登录
3. **频率控制**：建议轮询间隔不低于 1 小时（3600 秒），频繁请求可能触发 QQ 风控
4. **数据持久化**：已点赞记录保存在 `data/qzone_liked_posts.json`，删除后会重新点赞所有说说
5. **协议端兼容**：基于 OneBot v11 标准 API 开发，适配 go-cqhttp、NapCatQQ、Lagrange.Core 等主流协议端
