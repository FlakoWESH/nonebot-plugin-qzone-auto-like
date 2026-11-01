"""
QQ空间说说自动点赞与秒评插件（Alconna优化版）
功能：
1. 后台定时拉取QQ空间说说，自动点赞未点赞的说说
2. 可选自动秒评（通过 onebot-qzone 桥接服务 send_comment）
3. 命令查询自动点赞/秒评状态（限超级用户）
4. 自动从协议端（NapCat/SnowLuma）获取 QQ 空间 Cookie 并推送到桥接服务
架构与风控：
- 点赞/评论全部走 onebot-qzone 桥接服务（HTTP action），不依赖裸 Python 库
- 桥接服务统一管理请求指纹：User-Agent/Accept-Language 随机化、三级点赞 fallback、
  反爬检测、限流码识别，比进程内裸 HTTP 更不易被风控
- 点赞/秒评共享一次 FeedScanner 时间线扫描，减少请求次数
- 点赞勿扰名单 / 评论名单：评论默认只对名单内好友生效
- 批量去重、每日限额、随机延迟；成功后才落库，避免失败被永久跳过
- 秒评内容支持 {nickname} 模板变量
依赖：
- 点赞/秒评/Cookie 刷新均依赖 onebot-qzone 桥接服务（v2.0.0+，提供 send_like/send_comment/get_friend_feeds/check_cookie/update_cookie）
- 未启动桥接服务时插件仍可加载，仅互动功能不生效
"""
import asyncio
import random
from datetime import datetime

from arclet.alconna import Alconna
from nonebot import get_driver, get_plugin_config, require
from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMessage, on_alconna

from .bridge import BridgeAuthError, QzoneBridgeClient
from .config import QzoneAutoLikeConfig
from .cookie_refresher import CookieRefresher
from .feed import FeedScanner, QzonePost
from .policy import choose_template, render_template
from .selection import select_comment_candidates, select_like_candidates
from .storage import QzoneLikeStore

# ========== 插件元数据 ==========
__plugin_meta__ = PluginMetadata(
    name="QQ空间说说自动点赞与秒评",
    description="自动点赞QQ空间好友说说，可选秒评，支持Cookie自动刷新",
    usage=(
        "空间点赞状态 - 查询自动点赞/秒评状态（限超级用户）\n"
        "后台自动轮询QQ空间说说并点赞/评论（走桥接服务统一指纹）\n"
        "可选：自动从协议端获取 Cookie 推送到桥接服务"
    ),
    type="application",
    homepage="https://github.com/FlakoWESH/nonebot-plugin-qzone-auto-like",
    supported_adapters={"~onebot.v11"},
)

# ========== 加载配置与存储 ==========
config = get_plugin_config(QzoneAutoLikeConfig)
store = QzoneLikeStore(config.qzone_data_file)

# 后台任务状态标记
_task_started = False
_task_running = False

# 桥接客户端：点赞/秒评/Cookie 任一功能启用时都需要
_bridge: QzoneBridgeClient | None = None
if (
    config.qzone_enable_auto_like
    or config.qzone_enable_auto_comment
    or config.qzone_enable_auto_cookie
):
    _bridge = QzoneBridgeClient(
        base_url=config.qzone_bridge_url,
        token=config.qzone_bridge_token,
        timeout=config.qzone_cookie_request_timeout,
    )

# Cookie 自动刷新器（仅在启用时创建）
_cookie_refresher: CookieRefresher | None = None
if config.qzone_enable_auto_cookie:
    def _get_bot():
        """获取当前可用的 OneBot Bot 实例（供 CookieRefresher 复用连接）。"""
        try:
            from nonebot import get_bot
            return get_bot()
        except Exception:
            return None

    _cookie_refresher = CookieRefresher(
        napcat_url=config.qzone_napcat_url,
        napcat_token=config.qzone_napcat_token,
        bridge_client=_bridge,
        refresh_interval=config.qzone_cookie_refresh_interval,
        request_timeout=config.qzone_cookie_request_timeout,
        verify_after_update=config.qzone_cookie_verify_after_update,
        bot_getter=_get_bot,
    )
    logger.info("[qzone_auto_like] Cookie 自动刷新已启用（优先复用 OneBot 连接）")
else:
    logger.info("[qzone_auto_like] Cookie 自动刷新未启用")


# ========== 点赞子任务（走桥接 send_like） ==========

async def _run_like_pass(qq_number: str, posts: list[QzonePost]) -> None:
    """对已拉取的时间线执行一轮点赞。

    点赞走桥接服务 send_like，由桥接层统一管理 UA 指纹与反爬。
    跳过已点赞、勿扰名单内作者的说说。
    """
    if _bridge is None:
        return

    # 每日限额检查
    daily_limit = config.qzone_daily_like_limit
    today_count = await store.get_today_liked_count(qq_number)
    if daily_limit > 0 and today_count >= daily_limit:
        logger.info(
            f"[qzone_auto_like] 已达每日点赞上限({daily_limit})，本轮跳过"
        )
        return

    # 计算已点赞集合（用差集得到）
    all_tids = [post.tid for post in posts]
    unliked = set(await store.filter_unliked(all_tids))
    existing = set(all_tids) - unliked

    denied = await store.get_like_denied()
    pending = select_like_candidates(
        posts,
        denied=denied,
        existing=existing,
        limit=config.qzone_max_like_count
        if config.qzone_max_like_count > 0
        else None,
    )

    if not pending:
        logger.info("[qzone_auto_like] 点赞：没有需要点赞的新说说")
        return

    # 每日限额截断
    if daily_limit > 0:
        remaining = daily_limit - today_count
        if remaining < len(pending):
            pending = pending[:remaining]

    delay_low, delay_high = sorted(
        (max(0.0, config.qzone_like_random_delay_min),
         max(0.0, config.qzone_like_random_delay_max))
    )

    liked = 0
    failed = 0
    last_tid = pending[-1].tid
    for post in pending:
        try:
            await _bridge.send_like(post.tid, post.uin)
            await store.mark_liked(qq_number, post.tid)
            liked += 1
            logger.debug(f"[qzone_auto_like] 已点赞说说 tid={post.tid}")
        except Exception as e:
            failed += 1
            logger.warning(f"[qzone_auto_like] 点赞失败 tid={post.tid}: {e}")
            continue

        if delay_high > 0 and post.tid != last_tid:
            await asyncio.sleep(random.uniform(delay_low, delay_high))

    if liked or failed:
        logger.info(
            f"[qzone_auto_like] 本轮点赞完成 点赞={liked} 失败={failed}"
        )


# ========== 秒评子任务（走桥接 send_comment） ==========

async def _run_comment_pass(qq_number: str, posts: list[QzonePost]) -> None:
    """对已拉取的时间线执行一轮秒评。

    核心安全设计（与真寻版一致）：
    - 只评论「评论名单」内的好友，名单默认空，为空时不评论任何人；
    - 已评论过的说说、自己的说说均跳过；
    - 每日限额 + 每轮上限 + 随机延迟，防风控。
    """
    if _bridge is None:
        return

    # 评论名单：为空则不评论（核心，避免对所有好友刷屏）
    allowed = await store.get_comment_allowed()
    if not allowed:
        logger.info(
            "[qzone_auto_like] 评论名单为空，本轮不评论任何人"
        )
        return

    # 每日限额检查
    daily_limit = config.qzone_comment_daily_limit
    today_commented = await store.get_today_commented_count(qq_number)
    if daily_limit > 0 and today_commented >= daily_limit:
        logger.info(
            f"[qzone_auto_like] 已达每日评论上限({daily_limit})，本轮跳过"
        )
        return

    # 计算已评论集合
    all_tids = [post.tid for post in posts]
    uncommented = set(await store.filter_uncommented(all_tids))
    existing = set(all_tids) - uncommented

    # 纯函数筛选：名单内 + 未评论 + 非自己
    pending = select_comment_candidates(
        posts,
        allowed=allowed,
        existing=existing,
        self_qq=qq_number,
        limit=config.qzone_comment_max_per_round
        if config.qzone_comment_max_per_round > 0
        else None,
    )

    if not pending:
        logger.info("[qzone_auto_like] 秒评：没有符合条件的说说需要评论")
        return

    # 每日限额截断
    if daily_limit > 0:
        remaining = daily_limit - today_commented
        if remaining < len(pending):
            pending = pending[:remaining]

    # 随机延迟区间（评论比点赞更保守）
    delay_low, delay_high = sorted(
        (max(0.0, config.qzone_comment_delay_min),
         max(0.0, config.qzone_comment_delay_max))
    )

    global_template = config.qzone_comment_template
    commented = 0
    failed = 0
    last_tid = pending[-1].tid
    for post in pending:
        content = render_template(
            choose_template(None, global_template), post.nickname
        )[:100]
        try:
            await _bridge.send_comment(post.tid, content, post.uin)
            await store.mark_commented(qq_number, post.tid, content)
            commented += 1
            logger.debug(f"[qzone_auto_like] 已评论说说 tid={post.tid}: {content}")
        except Exception as e:
            failed += 1
            logger.warning(f"[qzone_auto_like] 评论失败 tid={post.tid}: {e}")
            continue

        if delay_high > 0 and post.tid != last_tid:
            await asyncio.sleep(random.uniform(delay_low, delay_high))

    if commented or failed:
        logger.info(
            f"[qzone_auto_like] 本轮秒评完成 评论={commented} 失败={failed}"
        )


# ========== 核心：自动互动循环（点赞/秒评共享一次扫描） ==========

async def _scan_with_cookie_retry(scan_num: int) -> list[QzonePost]:
    """拉取时间线；登录态失效时立即刷新 Cookie 并重试一次。"""
    try:
        return await FeedScanner(_bridge).scan(scan_num)
    except BridgeAuthError:
        if not config.qzone_enable_auto_cookie or _cookie_refresher is None:
            raise
        logger.warning("[qzone_auto_like] 桥接登录态失效，立即刷新 Cookie 后重试")
        refreshed, _err = await _cookie_refresher.refresh_once(force=True)
        if not refreshed:
            raise
        return await FeedScanner(_bridge).scan(scan_num)


async def _auto_like_loop():
    """自动点赞+秒评后台循环任务。"""
    global _task_running
    logger.info("[qzone_auto_like] 自动互动后台任务已启动")

    while True:
        try:
            # 全局开关检查（点赞或秒评任一启用即可运行）
            if not config.qzone_enable_auto_like and not config.qzone_enable_auto_comment:
                await asyncio.sleep(60)
                continue

            if _bridge is None:
                logger.warning("[qzone_auto_like] 桥接客户端未初始化，本轮跳过")
                await asyncio.sleep(config.qzone_like_interval)
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

            qq_number = config.qzone_qq_number or str(bot.self_id)

            # 一次拉取时间线，点赞和秒评共用（减少对桥接服务的请求次数）
            scan_num = config.qzone_max_like_count
            if config.qzone_enable_auto_comment:
                comment_scan = config.qzone_comment_max_per_round * 3
                scan_num = max(scan_num, comment_scan, 50)
            posts = await _scan_with_cookie_retry(scan_num)

            if posts:
                # ===== 点赞子任务 =====
                if config.qzone_enable_auto_like:
                    try:
                        await _run_like_pass(qq_number, posts)
                    except Exception as e:
                        logger.error(f"[qzone_auto_like] 点赞过程出错: {e}")

                # ===== 秒评子任务 =====
                if config.qzone_enable_auto_comment:
                    try:
                        await _run_comment_pass(qq_number, posts)
                    except Exception as e:
                        logger.error(f"[qzone_auto_like] 秒评过程出错: {e}")

            _task_running = False
            await asyncio.sleep(config.qzone_like_interval)

        except Exception as e:
            logger.error(f"[qzone_auto_like] 主循环异常: {e}")
            _task_running = False
            await asyncio.sleep(60)


# ========== 命令：查询自动互动状态（限超级用户） ==========
status_cmd = on_alconna(
    Alconna("空间点赞状态"),
    permission=SUPERUSER,
    priority=5,
    block=True,
)


@status_cmd.handle()
async def query_status():
    """查询自动点赞/秒评功能状态"""
    like_enabled = config.qzone_enable_auto_like
    comment_enabled = config.qzone_enable_auto_comment
    running_text = "运行中" if _task_running else "空闲中"
    liked_count = await store.get_liked_count()
    commented_count = await store.get_commented_count()
    comment_allowed_count = await store.count_comment_allowed()
    like_denied_count = await store.count_like_denied()

    result = (
        UniMessage.text("QQ空间自动互动状态\n")
        + UniMessage.text(f"秒赞：{'已启用' if like_enabled else '已禁用'}"
                          f"（勿扰 {like_denied_count} 人）\n")
        + UniMessage.text(f"秒评：{'已启用' if comment_enabled else '已禁用'}"
                          f"（评论名单 {comment_allowed_count} 人）\n")
        + UniMessage.text(f"任务状态：{running_text}\n")
        + UniMessage.text(f"轮询间隔：{config.qzone_like_interval} 秒\n")
        + UniMessage.text(f"点赞每日上限：{config.qzone_daily_like_limit or '不限'} 条\n")
        + UniMessage.text(f"评论每日上限：{config.qzone_comment_daily_limit or '不限'} 条\n")
        + UniMessage.text(f"累计已点赞：{liked_count} 条\n")
        + UniMessage.text(f"累计已评论：{commented_count} 条\n")
        + UniMessage.text(f"执行通道：桥接服务 {config.qzone_bridge_url}")
    )

    # 今日计数
    try:
        from nonebot import get_bot
        bot = get_bot()
        qq_number = config.qzone_qq_number or str(bot.self_id)
        today_likes = await store.get_today_liked_count(qq_number)
        today_comments = await store.get_today_commented_count(qq_number)
        result += UniMessage.text(f"\n今日：赞 {today_likes} 条 / 评 {today_comments} 条")
    except Exception:
        pass

    # Cookie 自动刷新状态
    if _cookie_refresher is not None:
        cookie_status = _cookie_refresher.get_status()
        result += UniMessage.text("\n\n─── Cookie 自动刷新 ───\n")
        result += UniMessage.text(f"刷新间隔：{cookie_status['refresh_interval']} 秒\n")
        result += UniMessage.text(f"获取方式：优先 OneBot 连接，HTTP 回退\n")

        if cookie_status["last_check_time"]:
            check_time = datetime.fromtimestamp(
                cookie_status["last_check_time"]
            ).strftime("%Y-%m-%d %H:%M:%S")
            valid_text = "✅ 有效" if cookie_status["last_cookie_valid"] else "❌ 失效"
            result += UniMessage.text(f"最近预检：{check_time} {valid_text}\n")
            if cookie_status["last_check_message"]:
                result += UniMessage.text(f"预检信息：{cookie_status['last_check_message']}\n")

        if cookie_status["last_refresh_time"]:
            last_time = datetime.fromtimestamp(
                cookie_status["last_refresh_time"]
            ).strftime("%Y-%m-%d %H:%M:%S")
            if cookie_status["last_refresh_success"]:
                result += UniMessage.text(f"上次刷新：{last_time} ✅ 成功\n")
            else:
                result += UniMessage.text(
                    f"上次刷新：{last_time} ❌ 失败\n"
                    f"错误：{cookie_status['last_error'] or '未知'}\n"
                )
        else:
            result += UniMessage.text("上次刷新：尚未执行\n")

        result += UniMessage.text(f"累计刷新：{cookie_status['refresh_count']} 次")
    else:
        result += UniMessage.text("\n\nCookie 自动刷新：未启用")

    await result.finish()


# ========== 启动钩子：启动后台任务 ==========
driver = get_driver()


@driver.on_startup
async def _startup():
    """Bot启动时启动自动互动后台任务和Cookie刷新任务"""
    global _task_started
    if not _task_started:
        _task_started = True
        asyncio.create_task(_auto_like_loop())
        logger.info("[qzone_auto_like] 自动互动后台任务已注册启动")

        if _cookie_refresher is not None:
            asyncio.create_task(_cookie_refresher.refresh_loop())
            logger.info("[qzone_auto_like] Cookie 自动刷新后台任务已注册启动")


@driver.on_bot_connect
async def _on_bot_connect(_bot: Bot) -> None:
    """Bot 连接后立即刷新 Cookie。"""
    if _cookie_refresher is None:
        return
    if not config.qzone_enable_auto_cookie:
        return
    logger.info("[qzone_auto_like] Bot 已连接，立即检查/刷新 Cookie")
    await _cookie_refresher.maybe_refresh()


@driver.on_shutdown
async def _shutdown():
    if _cookie_refresher is not None:
        await _cookie_refresher.close()
    if _bridge is not None:
        await _bridge.close()
