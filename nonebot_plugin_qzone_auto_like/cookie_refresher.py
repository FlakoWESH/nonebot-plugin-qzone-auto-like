"""
QQ空间 Cookie 自动刷新模块

通过 NapCat 的 get_cookies API 自动获取 QQ 空间 Cookie，
然后调用 onebot-qzone 桥接服务的 update_cookie API 动态更新 Cookie，
无需手动复制粘贴 Cookie，也无需重启桥接服务。

工作流程：
1. 调用 NapCat HTTP API: POST /get_cookies  (domain=user.qzone.qq.com)
2. 从返回中提取 cookie 字符串（uin/p_uin/skey/p_skey 等）
3. 调用 onebot-qzone HTTP API: POST /update_cookie  (cookie=...)
4. onebot-qzone 内部自动写回 .env 并更新当前会话

前提条件：
- NapCat 版本 >= v4.18.0（修复了 bkn 计算 bug）
- NapCat 已登录 QQ，且开启了 HTTP API
- onebot-qzone 桥接服务正在运行
"""
import asyncio
import time
from typing import Optional, Tuple

import aiohttp
from nonebot.log import logger


# 必需的 Cookie 字段，缺一不可
REQUIRED_COOKIE_FIELDS = ("uin", "p_uin", "skey", "p_skey")


class CookieRefresher:
    """QQ空间 Cookie 自动刷新器"""

    def __init__(
        self,
        napcat_url: str,
        napcat_token: str,
        bridge_url: str,
        bridge_token: str,
        refresh_interval: int = 7200,
        request_timeout: int = 10,
    ):
        self.napcat_url = napcat_url.rstrip("/")
        self.napcat_token = napcat_token
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token
        self.refresh_interval = refresh_interval
        self.request_timeout = request_timeout

        # 状态记录
        self._last_refresh_time: Optional[float] = None
        self._last_refresh_success: Optional[bool] = None
        self._last_error: Optional[str] = None
        self._refresh_count: int = 0

    # ========== 从 NapCat 获取 Cookie ==========

    async def fetch_cookie_from_napcat(self) -> str:
        """调用 NapCat 的 get_cookies API 获取 QQ 空间 Cookie

        Returns:
            Cookie 字符串，格式: "uin=...; p_uin=...; skey=...; p_skey=..."

        Raises:
            RuntimeError: 获取失败或 Cookie 不完整
        """
        url = f"{self.napcat_url}/get_cookies"
        headers = {"Content-Type": "application/json"}
        if self.napcat_token:
            headers["Authorization"] = f"Bearer {self.napcat_token}"

        payload = {"domain": "user.qzone.qq.com"}

        logger.info(f"[qzone_cookie] 正在从 NapCat 获取 QQ 空间 Cookie: {url}")

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"NapCat API 返回 HTTP {resp.status}")

                data = await resp.json()

                retcode = data.get("retcode", -1)
                status = data.get("status", "")
                if retcode != 0 or status != "ok":
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"NapCat API 返回错误: retcode={retcode}, status={status}, message={msg}"
                    )

                inner = data.get("data") or {}
                cookies_str = inner.get("cookies", "")

                if not cookies_str:
                    raise RuntimeError("NapCat API 返回数据中缺少 cookies 字段")

                # 校验必需字段
                missing = self._check_required_fields(cookies_str)
                if missing:
                    raise RuntimeError(
                        f"Cookie 缺少必要字段: {', '.join(missing)}。"
                        f"请确认 NapCat 已正确登录 QQ 且版本 >= v4.18.0"
                    )

                return cookies_str

    @staticmethod
    def _check_required_fields(cookie_str: str) -> list:
        """检查 Cookie 字符串是否包含所有必需字段"""
        found = {}
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, _, value = pair.partition("=")
                found[key.strip()] = value.strip()

        missing = []
        for field in REQUIRED_COOKIE_FIELDS:
            if not found.get(field):
                missing.append(field)
        return missing

    # ========== 将 Cookie 推送到 onebot-qzone ==========

    async def push_cookie_to_bridge(self, cookie_str: str) -> None:
        """调用 onebot-qzone 的 update_cookie API 更新 Cookie

        Args:
            cookie_str: Cookie 字符串

        Raises:
            RuntimeError: 更新失败
        """
        url = f"{self.bridge_url}/update_cookie"
        headers = {"Content-Type": "application/json"}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"

        payload = {"cookie": cookie_str}

        logger.info(f"[qzone_cookie] 正在更新 onebot-qzone Cookie: {url}")

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"onebot-qzone API 返回 HTTP {resp.status}")

                data = await resp.json()
                # onebot-qzone 返回格式: {"status": "ok", ...} 或 {"retcode": 0, ...}
                status = data.get("status", "")
                retcode = data.get("retcode", -1)

                if status != "ok" and retcode != 0:
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"onebot-qzone Cookie 更新失败: status={status}, retcode={retcode}, message={msg}"
                    )

                logger.info("[qzone_cookie] onebot-qzone Cookie 更新成功")

    # ========== 单次刷新 ==========

    async def refresh_once(self) -> Tuple[bool, Optional[str]]:
        """执行一次完整的 Cookie 刷新

        Returns:
            (是否成功, 错误信息)
        """
        try:
            # 1. 从 NapCat 获取 Cookie
            cookie_str = await self.fetch_cookie_from_napcat()
            cookie_len = len(cookie_str)
            logger.info(f"[qzone_cookie] 成功获取 Cookie，长度={cookie_len}")

            # 2. 推送到 onebot-qzone
            await self.push_cookie_to_bridge(cookie_str)

            self._last_refresh_time = time.time()
            self._last_refresh_success = True
            self._last_error = None
            self._refresh_count += 1
            return True, None

        except Exception as e:
            error_msg = str(e)
            self._last_refresh_time = time.time()
            self._last_refresh_success = False
            self._last_error = error_msg
            logger.error(f"[qzone_cookie] Cookie 刷新失败: {error_msg}")
            return False, error_msg

    # ========== 后台循环 ==========

    async def refresh_loop(self):
        """Cookie 自动刷新后台循环"""
        logger.info(
            f"[qzone_cookie] Cookie 自动刷新任务已启动 "
            f"(间隔={self.refresh_interval}秒, napcat={self.napcat_url}, bridge={self.bridge_url})"
        )

        # 启动后立即执行一次
        await asyncio.sleep(5)  # 等待系统初始化
        success, err = await self.refresh_once()
        if success:
            logger.info("[qzone_cookie] 首次 Cookie 刷新成功")
        else:
            logger.warning(f"[qzone_cookie] 首次 Cookie 刷新失败: {err}，将在下次重试")

        while True:
            await asyncio.sleep(self.refresh_interval)
            await self.refresh_once()

    # ========== 状态查询 ==========

    def get_status(self) -> dict:
        """获取当前 Cookie 刷新状态"""
        return {
            "last_refresh_time": self._last_refresh_time,
            "last_refresh_success": self._last_refresh_success,
            "last_error": self._last_error,
            "refresh_count": self._refresh_count,
            "napcat_url": self.napcat_url,
            "bridge_url": self.bridge_url,
            "refresh_interval": self.refresh_interval,
        }
