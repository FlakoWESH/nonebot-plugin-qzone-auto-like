"""
QQ空间 Cookie 自动刷新模块（NoneBot 版）

通过 NapCat 获取 QQ 空间 Cookie，再调用 onebot-qzone 桥接服务的 update_cookie
action 动态更新 Cookie，无需手动复制粘贴，也无需重启桥接服务。

Cookie 优先通过 NoneBot 已有的 OneBot 连接向 NapCat 请求（bot.call_api），
无需额外开启 NapCat HTTP API；仅当 OneBot 连接不可用时回退到 HTTP。

工作流程（按需刷新）：
1. 调用桥接服务 check_cookie（带网络探针）检测当前 Cookie 是否有效
2. Cookie 仍有效 -> 跳过，不触发任何变更（防风控）
3. Cookie 失效，或预检本身失败（fail-open）-> 执行完整刷新流程
4. 更新后可选再次 check_cookie 验证

前提条件：
- NapCat 版本 >= v4.18.0（修复了 bkn 计算 bug）
- NapCat 已登录 QQ，并已连接到 NoneBot
- onebot-qzone 桥接服务正在运行（v2.0.0+，支持 check_cookie / update_cookie）
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
from nonebot.log import logger

if TYPE_CHECKING:
    from .bridge import QzoneBridgeClient

# 必需的 Cookie 字段，缺一不可
REQUIRED_COOKIE_FIELDS = ("uin", "p_uin", "skey", "p_skey")


class CookieRefresher:
    """QQ空间 Cookie 自动刷新器（按需刷新）。"""

    def __init__(
        self,
        napcat_url: str,
        napcat_token: str,
        bridge_client: "QzoneBridgeClient",
        refresh_interval: int = 7200,
        request_timeout: int = 10,
        verify_after_update: bool = True,
        bot_getter: Callable[[], Any] | None = None,
    ):
        self.napcat_url = napcat_url.rstrip("/")
        self.napcat_token = napcat_token or ""
        self.bridge = bridge_client
        self.refresh_interval = refresh_interval
        self.request_timeout = request_timeout
        self.verify_after_update = verify_after_update
        self._bot_getter = bot_getter

        # 状态记录
        self._last_refresh_time: Optional[float] = None
        self._last_refresh_success: Optional[bool] = None
        self._last_error: Optional[str] = None
        self._refresh_count: int = 0
        # 预检结果缓存
        self._last_check_time: Optional[float] = None
        self._last_cookie_valid: Optional[bool] = None
        self._last_cookie_age_seconds: Optional[int] = None
        self._last_check_message: Optional[str] = None

        self._napcat_session: aiohttp.ClientSession | None = None

    async def _get_napcat_session(self) -> aiohttp.ClientSession:
        if self._napcat_session is None or self._napcat_session.closed:
            self._napcat_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            )
        return self._napcat_session

    async def close(self) -> None:
        if self._napcat_session is not None and not self._napcat_session.closed:
            await self._napcat_session.close()
        self._napcat_session = None
        await self.bridge.close()

    # ========== 预检：检查桥接服务当前 Cookie 是否有效 ==========

    async def check_cookie_on_bridge(self) -> dict:
        """调用桥接服务 check_cookie，检测当前 Cookie 是否有效。"""
        logger.debug("[qzone_cookie] 正在检测当前 Cookie 是否有效...")
        inner = await self.bridge.check_cookie(probe=True)
        result = {
            "valid": bool(inner.get("valid", False)),
            "expired": bool(inner.get("expired", True)),
            "message": inner.get("message", ""),
            "has_p_skey": bool(inner.get("has_p_skey", False)),
            "has_skey": bool(inner.get("has_skey", False)),
            "cookie_age_seconds": inner.get("cookie_age_seconds"),
        }
        self._last_check_time = time.time()
        self._last_cookie_valid = result["valid"]
        self._last_cookie_age_seconds = result.get("cookie_age_seconds")
        self._last_check_message = result["message"]
        return result

    # ========== 从 OneBot 连接获取 Cookie（优先） ==========

    async def fetch_cookie_from_bot(self) -> str:
        """通过 NoneBot 现有的 OneBot 连接向 NapCat 请求 QQ 空间 Cookie。"""
        bot = self._bot_getter() if self._bot_getter else None
        if bot is None:
            raise RuntimeError("当前没有可用的 OneBot Bot 连接")

        logger.info("[qzone_cookie] 正在通过 OneBot 连接获取 QQ 空间 Cookie")
        data = await bot.call_api("get_cookies", domain="user.qzone.qq.com")
        cookies_str = ""
        if isinstance(data, dict):
            cookies_str = str(data.get("cookies") or "")
        if not cookies_str:
            raise RuntimeError("OneBot get_cookies 返回数据中缺少 cookies 字段")

        missing = self._check_required_fields(cookies_str)
        if missing:
            raise RuntimeError(
                f"Cookie 缺少必要字段: {', '.join(missing)}。"
                f"请确认 NapCat 已正确登录 QQ 且版本 >= v4.18.0"
            )
        return cookies_str

    # ========== 从 NapCat HTTP 获取 Cookie（回退） ==========

    async def fetch_cookie_from_napcat(self) -> str:
        """调用 NapCat 的 HTTP get_cookies API 获取 QQ 空间 Cookie。"""
        url = f"{self.napcat_url}/get_cookies"
        headers = {"Content-Type": "application/json"}
        if self.napcat_token:
            headers["Authorization"] = f"Bearer {self.napcat_token}"

        logger.info(f"[qzone_cookie] 正在从 NapCat HTTP 获取 QQ 空间 Cookie: {url}")

        session = await self._get_napcat_session()
        async with session.post(
            url, json={"domain": "user.qzone.qq.com"}, headers=headers
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"NapCat API 返回 HTTP {resp.status}")
            data = await resp.json(content_type=None)

        retcode = data.get("retcode", -1)
        status = data.get("status", "")
        if retcode != 0 or status != "ok":
            raise RuntimeError(
                f"NapCat API 返回错误: retcode={retcode}, status={status}, "
                f"message={data.get('message', '未知错误')}"
            )

        cookies_str = (data.get("data") or {}).get("cookies", "")
        if not cookies_str:
            raise RuntimeError("NapCat API 返回数据中缺少 cookies 字段")

        missing = self._check_required_fields(cookies_str)
        if missing:
            raise RuntimeError(
                f"Cookie 缺少必要字段: {', '.join(missing)}。"
                f"请确认 NapCat 已正确登录 QQ 且版本 >= v4.18.0"
            )
        return cookies_str

    async def fetch_cookie(self) -> str:
        """获取 Cookie：优先走 OneBot 连接，失败时回退 NapCat HTTP API。"""
        errors: list[str] = []
        if self._bot_getter is not None:
            try:
                return await self.fetch_cookie_from_bot()
            except Exception as e:  # noqa: BLE001 - 回退到 HTTP
                errors.append(f"OneBot: {e}")
                logger.warning(
                    f"[qzone_cookie] 通过 OneBot 获取 Cookie 失败，"
                    f"尝试 HTTP 回退: {e}"
                )

        try:
            return await self.fetch_cookie_from_napcat()
        except Exception as e:
            errors.append(f"HTTP: {e}")
            raise RuntimeError("; ".join(errors)) from e

    @staticmethod
    def _check_required_fields(cookie_str: str) -> list[str]:
        """检查 Cookie 字符串是否包含所有必需字段。"""
        found: dict[str, str] = {}
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, _, value = pair.partition("=")
                found[key.strip()] = value.strip()
        return [f for f in REQUIRED_COOKIE_FIELDS if not found.get(f)]

    # ========== 单次刷新（按需） ==========

    async def refresh_once(self, force: bool = False) -> tuple[bool, Optional[str]]:
        """执行一次 Cookie 检查与刷新（按需刷新）。

        按需刷新机制：
        1. 先调用 check_cookie API 预检当前 Cookie
        2. Cookie 仍有效 -> 直接跳过（防风控）
        3. 预检失败 -> fail-open，保守地执行刷新
        4. 只有 Cookie 过期/无效时才执行完整刷新流程
        5. force=True 时跳过预检，强制执行刷新
        """
        try:
            # ===== 步骤1：预检当前 Cookie（按需刷新核心） =====
            if not force:
                try:
                    check_result = await self.check_cookie_on_bridge()
                except Exception as e:  # noqa: BLE001 - 预检失败不阻断刷新（fail-open）
                    logger.warning(
                        f"[qzone_cookie] Cookie 预检失败（{e}），改为直接刷新"
                    )
                else:
                    if check_result["valid"]:
                        age_min = ""
                        if check_result.get("cookie_age_seconds") is not None:
                            age_sec = check_result["cookie_age_seconds"]
                            age_min = f"，Cookie 年龄={round(age_sec / 60)} 分钟"
                        logger.info(
                            f"[qzone_cookie] 当前 Cookie 仍有效{age_min}，无需刷新，跳过。"
                        )
                        self._last_refresh_time = time.time()
                        self._last_refresh_success = True
                        self._last_error = None
                        return True, None

                    logger.info(
                        f"[qzone_cookie] 当前 Cookie 已失效："
                        f"{check_result['message']}，开始刷新..."
                    )

            # ===== 步骤2：获取最新 Cookie（优先 OneBot 连接，回退 HTTP） =====
            cookie_str = await self.fetch_cookie()
            logger.info(f"[qzone_cookie] 成功获取 Cookie，长度={len(cookie_str)}")

            # ===== 步骤3：校验 Cookie 完整性 =====
            missing = self._check_required_fields(cookie_str)
            if missing:
                raise RuntimeError(f"Cookie 不完整，缺少字段: {', '.join(missing)}")
            logger.info("[qzone_cookie] Cookie 校验通过，包含必需字段 uin/p_uin/skey/p_skey")

            # ===== 步骤4：热更新到 onebot-qzone =====
            inner = await self.bridge.update_cookie(cookie_str)
            logger.info(
                f"[qzone_cookie] Cookie 热更新成功！"
                f"QQ号={inner.get('user_id', 0)}, "
                f"昵称={inner.get('nickname', '')}, "
                f"{inner.get('message', 'Cookie 已更新')}"
            )

            # ===== 步骤5：更新后验证（可选） =====
            if self.verify_after_update:
                try:
                    verify_result = await self.check_cookie_on_bridge()
                    if verify_result["valid"]:
                        logger.info(
                            f"[qzone_cookie] Cookie 验证通过："
                            f"has_p_skey={verify_result['has_p_skey']}, "
                            f"has_skey={verify_result['has_skey']}"
                        )
                    else:
                        logger.warning(
                            f"[qzone_cookie] Cookie 验证失败："
                            f"{verify_result['message']}，"
                            f"请检查 update_cookie 是否真正生效"
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[qzone_cookie] 更新后验证失败：{e}")

            self._last_refresh_time = time.time()
            self._last_refresh_success = True
            self._last_error = None
            self._refresh_count += 1
            return True, None

        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            self._last_refresh_time = time.time()
            self._last_refresh_success = False
            self._last_error = error_msg
            logger.error(f"[qzone_cookie] Cookie 刷新失败: {error_msg}")
            return False, error_msg

    # ========== 调度器辅助 ==========

    def is_refresh_due(self) -> bool:
        """距离上次检查是否已达到 refresh_interval。"""
        if self._last_check_time is None:
            return True
        return (time.time() - self._last_check_time) >= self.refresh_interval

    async def maybe_refresh(self) -> None:
        """供调度器周期调用：到点才执行一次检查/刷新。"""
        if self.is_refresh_due():
            await self.refresh_once(force=False)

    # ========== 后台循环（兼容旧调用方式） ==========

    async def refresh_loop(self):
        """Cookie 自动刷新后台循环。"""
        logger.info(
            f"[qzone_cookie] Cookie 自动刷新任务已启动 "
            f"(间隔={self.refresh_interval}秒, bridge={self.bridge.base_url})"
        )

        await asyncio.sleep(5)

        success, err = await self.refresh_once(force=False)
        if success:
            logger.info("[qzone_cookie] 首次 Cookie 检查完成")
        else:
            logger.warning(f"[qzone_cookie] 首次 Cookie 检查失败: {err}，将在下次重试")

        while True:
            await asyncio.sleep(self.refresh_interval)
            await self.refresh_once(force=False)

    # ========== 状态查询 ==========

    def get_status(self) -> dict:
        """获取当前 Cookie 刷新状态。"""
        return {
            "last_refresh_time": self._last_refresh_time,
            "last_refresh_success": self._last_refresh_success,
            "last_error": self._last_error,
            "refresh_count": self._refresh_count,
            "napcat_url": self.napcat_url,
            "bridge_url": self.bridge.base_url,
            "refresh_interval": self.refresh_interval,
            "verify_after_update": self.verify_after_update,
            # 预检结果
            "last_check_time": self._last_check_time,
            "last_cookie_valid": self._last_cookie_valid,
            "last_cookie_age_seconds": self._last_cookie_age_seconds,
            "last_check_message": self._last_check_message,
        }
