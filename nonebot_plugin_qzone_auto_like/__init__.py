"""
QQ空间说说自动点赞插件（Alconna优化版）
功能：
1. 后台定时拉取QQ空间说说，自动点赞未点赞的说说
2. 命令查询自动点赞状态
优化点：
- 使用 Alconna 命令解析器替代 on_command
- 使用 UniMessage 统一消息发送，支持多行文本拼接
依赖：
- 运行时需安装 onebot-qzone 库（pip install onebot-qzone）
- 未安装时插件仍可加载，仅自动点赞功能不生效
"""
import asyncio

from arclet.alconna import Alconna
from nonebot import get_driver, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import UniMessage, on_alconna

from .config import QzoneAutoLikeConfig
from .storage import QzoneLikeStore

# ========== 插件元数据 ==========
__plugin_meta__ = PluginMetadata(
    name="QQ空间说说自动点赞",
    description="自动点赞QQ空间好友说说（Alconna优化版）",
    usage=(
        "空间点赞状态 - 查询自动点赞功能状态\n"
        "后台自动轮询QQ空间说说并点赞"
    ),
    type="application",
    homepage="https://github.com/nonebot/plugin-alconna",
    supported_adapters={"~onebot.v11"},
)

# ========== 加载配置与存储 ==========
config = get_plugin_config(QzoneAutoLikeConfig)
store = QzoneLikeStore(config.qzone_data_file)

# 后台任务状态标记
_task_started = False
_task_running = False


# ========== 核心：自动点赞循环 ==========
async def _auto_like_loop():
    """自动点赞后台循环任务"""
    global _task_running
    logger.info("[qzone_auto_like] 自动点赞后台任务已启动")

    while True:
        try:
            # 全局开关检查
            if not config.qzone_enable_auto_like:
                await asyncio.sleep(60)
                continue

            _task_running = True

            # 获取当前Bot实例
            try:
                from nonebot import get_bot

                bot = get_bot()
            except Exception:
                logger.warning("[qzone_auto_like] 未找到可用的Bot实例，等待重连...")
                _task_running = False
                await asyncio.sleep(30)
                continue

            qq_number = config.qzone_qq_number or bot.self_id

            logger.info(
                f"[qzone_auto_like] 开始一轮空间说说点赞 "
                f"QQ={qq_number} 最大数量={config.qzone_max_like_count}"
            )

            # 尝试导入 onebot-qzone 并执行点赞
            try:
                from onebot_qzone import QzoneSession
            except ImportError:
                logger.error(
                    "[qzone_auto_like] 未安装 onebot-qzone 库，"
                    "请执行: pip install onebot-qzone"
                )
                _task_running = False
                await asyncio.sleep(config.qzone_like_interval)
                continue

            try:
                # 登录QQ空间
                qzone = QzoneSession(qq_number)
                await qzone.login()

                # 获取好友说说时间线
                posts = await qzone.get_user_timeline(count=config.qzone_max_like_count)

                liked_count = 0
                for post in posts:
                    post_id = post.get("postid") or post.get("id")
                    if not post_id:
                        continue

                    # 跳过已点赞的说说
                    if await store.is_liked(post_id):
                        continue

                    # 执行点赞
                    await qzone.like(post_id)
                    await store.mark_liked(qq_number, post_id)
                    liked_count += 1
                    logger.debug(f"[qzone_auto_like] 已点赞说说 post_id={post_id}")

                    # 单条说说间隔，防止风控
                    await asyncio.sleep(config.qzone_per_like_interval)

                logger.info(
                    f"[qzone_auto_like] 本轮点赞完成 "
                    f"新点赞={liked_count} 条 "
                    f"累计已点赞={await store.get_liked_count()} 条"
                )

            except Exception as e:
                logger.error(f"[qzone_auto_like] 点赞过程出现错误: {e}")

            _task_running = False

            # 等待下一轮
            await asyncio.sleep(config.qzone_like_interval)

        except Exception as e:
            logger.error(f"[qzone_auto_like] 主循环异常: {e}")
            _task_running = False
            await asyncio.sleep(60)


# ========== 命令：查询自动点赞状态 ==========
# Alconna优化点：
# - on_alconna(Alconna("空间点赞状态")) 替代 on_command("空间点赞状态")
# - 无需定义参数，Alconna自动匹配命令
status_cmd = on_alconna(
    Alconna("空间点赞状态"),
    priority=5,
    block=True,
)


@status_cmd.handle()
async def query_status():
    """查询自动点赞功能状态

    Alconna优化点：
    - 使用 UniMessage.text() 拼接多行文本
    - 使用 .finish() 发送并结束事件
    - 替代原生的 matcher.finish("多行\n文本") 字符串拼接
    """
    enabled = config.qzone_enable_auto_like
    status_text = "已启用" if enabled else "已禁用"
    running_text = "运行中" if _task_running else "空闲中"
    liked_count = await store.get_liked_count()

    # 使用UniMessage构建多行状态消息
    result = (
        UniMessage.text("QQ空间自动点赞状态\n")
        + UniMessage.text(f"功能开关：{status_text}\n")
        + UniMessage.text(f"任务状态：{running_text}\n")
        + UniMessage.text(f"轮询间隔：{config.qzone_like_interval} 秒\n")
        + UniMessage.text(f"每轮上限：{config.qzone_max_like_count} 条\n")
        + UniMessage.text(f"累计已点赞：{liked_count} 条说说")
    )

    # 检查onebot-qzone是否安装
    try:
        from onebot_qzone import QzoneSession  # noqa: F401
    except ImportError:
        result += UniMessage.text(
            "\n\n⚠️ 未安装 onebot-qzone 库，自动点赞功能不可用\n"
            "请执行: pip install onebot-qzone"
        )

    await result.finish()


# ========== 启动钩子：启动后台任务 ==========
@get_driver().on_startup
async def _startup():
    """Bot启动时启动自动点赞后台任务"""
    global _task_started
    if not _task_started:
        _task_started = True
        asyncio.create_task(_auto_like_loop())
        logger.info("[qzone_auto_like] 后台任务已注册启动")
