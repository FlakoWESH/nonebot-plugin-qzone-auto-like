# nonebot-plugin-qzone-auto-like

NoneBot2 QQ空间说说自动点赞插件，后台定时拉取QQ空间好友说说并自动点赞。基于 Alconna 命令解析器优化，JSON 文件去重，零数据库依赖。

## 功能特性

- **后台自动点赞**：定时轮询QQ空间好友说说时间线，自动点赞未点赞的说说
- **已点赞去重**：JSON 文件记录已点赞说说ID，避免重复点赞
- **可配置轮询间隔**：点赞轮询间隔和单条说说间隔均可配置，防止风控
- **可配置每轮上限**：每轮最多点赞数量可配置，避免短时间内大量操作
- **状态查询命令**：发送命令查看自动点赞功能状态和统计信息
- **依赖容错**：未安装 `onebot-qzone` 库时插件仍可加载，仅自动点赞功能不生效
- **全局开关**：可通过配置项随时启用/禁用自动点赞功能

## 安装

### 使用 nb-cli（推荐）

```bash
nb plugin install nonebot-plugin-qzone-auto-like
```

### 使用 pip

```bash
pip install nonebot-plugin-qzone-auto-like
```

然后在 `pyproject.toml` 中添加：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_qzone_auto_like"]
```

### 额外依赖

自动点赞功能需要安装 `onebot-qzone` 库：

```bash
pip install onebot-qzone
```

> 注意：`onebot-qzone` 是第三方库，用于通过 OneBot 协议操作 QQ 空间。未安装时插件仍可加载，状态查询命令可用，但自动点赞功能不生效。

## 使用方法

### 查询自动点赞状态

```
空间点赞状态
```

返回信息包括：
- 功能开关状态（已启用/已禁用）
- 任务运行状态（运行中/空闲中）
- 轮询间隔
- 每轮点赞上限
- 累计已点赞说说数量
- onebot-qzone 库安装状态

### 自动点赞

无需手动触发，后台任务自动运行：
1. 按配置的间隔定时拉取QQ空间好友说说时间线
2. 跳过已点赞的说说（通过JSON文件去重）
3. 对未点赞的说说执行点赞操作
4. 记录已点赞说说ID
5. 单条说说之间按配置间隔等待，防止风控

## 配置项

在 `.env` 文件中添加以下配置（均为可选，有默认值）：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `QZONE_ENABLE_AUTO_LIKE` | bool | true | 是否启用自动点赞功能 |
| `QZONE_LIKE_INTERVAL` | int | 3600 | 点赞轮询间隔（秒），默认1小时 |
| `QZONE_MAX_LIKE_COUNT` | int | 20 | 每轮最多点赞的说说数量 |
| `QZONE_PER_LIKE_INTERVAL` | float | 2.0 | 单条说说之间的间隔（秒），防止风控 |
| `QZONE_QQ_NUMBER` | str | "" | 要操作的QQ号，留空则使用Bot自身QQ号 |
| `QZONE_DATA_FILE` | str | "data/qzone_liked_posts.json" | 已点赞说说记录JSON文件路径 |

## 注意事项

1. **onebot-qzone 依赖**：自动点赞功能依赖 `onebot-qzone` 库，需单独安装。该库为第三方实现，可用性取决于QQ空间接口的稳定性
2. **风控风险**：频繁点赞可能触发QQ风控，建议保持默认间隔（每轮间隔1小时，单条间隔2秒）
3. **QQ空间权限**：只能点赞可见的好友说说，私密说说无法点赞
4. **Bot 账号**：默认使用 Bot 自身QQ号操作空间，也可通过 `QZONE_QQ_NUMBER` 指定其他QQ号（需该QQ号已登录协议端）
5. **数据存储**：已点赞说说ID持久化到JSON文件，重启后不会重复点赞

## 依赖

- nonebot2 >= 2.0.0
- nonebot-adapter-onebot >= 2.0.0
- nonebot-plugin-alconna >= 0.50.0
- onebot-qzone（可选，自动点赞功能必需）

## 许可证

MIT
