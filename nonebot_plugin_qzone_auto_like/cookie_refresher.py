"""
QQ空间 Cookie 自动刷新模块

通过 NapCat 的 get_cookies API 自动获取 QQ 空间 Cookie，
然后调用 onebot-qzone 桥接服务的 update_cookie API 动态更新 Cookie，
无需手动复制粘贴 Cookie，也无需重启桥接服务。

工作流程（v2.1 按需刷新）：
1. 先调用 onebot-qzone 的 check_cookie API（带网络探针）检测当前 Cookie 是否有效
2. 如果 Cookie 仍有效，直接跳过，不触发任何变更（防风控）
3. 如果 Cookie 已过期/无效：
   a. 调用 NapCat HTTP API: POST /get_cookies  (domain=user.qzone.qq.com)
   b. 从返回中提取 cookie 字符串（uin/p_uin/skey/p_skey 等）
   c. 调用 onebot-qzone HTTP API: POST /update_cookie  (cookie=...)
   d. onebot-qzone 内部自动写回 .env 并更新当前会话
4. 更新后可选再次调用 check_cookie 验证新 Cookie 确实有效

前提条件：
- NapCat 版本 >= v4.18.0（修复了 bkn 计算 bug）
- NapCat 已登录 QQ，且开启了 HTTP API
- onebot-qzone 桥接服务正在运行，版本支持 check_cookie 和 update_cookie API（v2.0.0+）
"""
import asyncio
import time
from typing import Optional, Tuple

import aiohttp
from nonebot.log import logger


# 必需的 Cookie 字段，缺一不可
REQUIRED_COOKIE_FIELDS = ("uin", "p_uin", "skey", "p_skey")


class CookieRefresher:
    """QQ空间 Cookie 自动刷新器（v2.1 按需刷新）"""

    def __init__(
        self,
        napcat_url: str,
        napcat_token: str,
        bridge_url: str,
        bridge_token: str,
        refresh_interval: int = 7200,
        request_timeout: int = 10,
        verify_after_update: bool = True,
    ):
        self.napcat_url = napcat_url.rstrip("/")
        self.napcat_token = napcat_token
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token
        self.refresh_interval = refresh_interval
        self.request_timeout = request_timeout
        self.verify_after_update = verify_after_update

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

    # ========== 预检：检查桥接服务当前 Cookie 是否有效 ==========

    async def check_cookie_on_bridge(self) -> dict:
        """调用 onebot-qzone 的 check_cookie API 检测当前 Cookie 是否有效

        该 API 会发起一次网络探针请求 QQ 空间，真实检测 Cookie 状态。

        Returns:
            {
                "valid": bool,          # Cookie 是否有效
                "expired": bool,        # Cookie 是否过期
                "message": str,         # 状态描述
                "has_p_skey": bool,     # 是否有 p_skey
                "has_skey": bool,       # 是否有 skey
                "cookie_age_seconds": Optional[int],  # Cookie 年龄（秒）
            }

        Raises:
            RuntimeError: API 调用失败
        """
        url = f"{self.bridge_url}/check_cookie"
        headers = {"Content-Type": "application/json"}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"

        payload = {"probe": True}

        logger.debug(f"[qzone_cookie] 正在检测当前 Cookie 是否有效: {url}")

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"check_cookie API 返回 HTTP {resp.status}")

                data = await resp.json()
                retcode = data.get("retcode", -1)
                status = data.get("status", "")
                if retcode != 0 or status != "ok":
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"check_cookie API 返回错误: retcode={retcode}, status={status}, message={msg}"
                    )

                inner = data.get("data") or {}
                result = {
                    "valid": inner.get("valid", False),
                    "expired": inner.get("expired", True),
                    "message": inner.get("message", ""),
                    "has_p_skey": inner.get("has_p_skey", False),
                    "has_skey": inner.get("has_skey", False),
                    "cookie_age_seconds": inner.get("cookie_age_seconds"),
                }

        self._last_check_time = time.time()
        self._last_cookie_valid = result["valid"]
        self._last_cookie_age_seconds = result.get("cookie_age_seconds")
        self._last_check_message = result["message"]

        return result

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

    async def push_cookie_to_bridge(self, cookie_str: str) -> dict:
        """调用 onebot-qzone 的 update_cookie API 更新 Cookie

        Args:
            cookie_str: Cookie 字符串

        Returns:
            onebot-qzone 返回的数据（含 user_id, nickname, message）

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
                status = data.get("status", "")
                retcode = data.get("retcode", -1)

                if status != "ok" and retcode != 0:
                    msg = data.get("message", "未知错误")
                    raise RuntimeError(
                        f"onebot-qzone Cookie 更新失败: status={status}, retcode={retcode}, message={msg}"
                    )

                inner = data.get("data") or {}
                user_id = inner.get("user_id", 0)
                nickname = inner.get("nickname", "")
                message = inner.get("message", "Cookie 已更新")
                logger.info(
                    f"[qzone_cookie] Cookie 热更新成功！QQ号={user_id}, 昵称={nickname}, {message}"
                )
                return inner

    # ========== 单次刷新（按需） ==========

    async def refresh_once(self, force: bool = False) -> Tuple[bool, Optional[str]]:
        """执行一次 Cookie 检查与刷新

        按需刷新机制（v2.1）：
        1. 先调用 check_cookie API 预检当前 Cookie
        2. 如果 Cookie 仍有效，直接跳过，不触发任何变更（防风控）
        3. 只有 Cookie 过期/无效时才执行完整刷新流程
        4. force=True 时跳过预检，强制执行刷新

        Args:
            force: 是否强制刷新（跳过预检）

        Returns:
            (是否成功/是否跳过, 错误信息或跳过原因)
        """
        try:
            # ===== 步骤1：预检当前 Cookie（按需刷新核心） =====
            if not force:
                logger.info("[qzone_cookie] 正在检测当前 Cookie 是否有效...")
                check_result = await self.check_cookie_on_bridge()

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
                    f"[qzone_cookie] 当前 Cookie 已失效：{check_result['message']}，开始刷新..."
                )

            # ===== 步骤2：从 NapCat 获取最新 Cookie =====
            cookie_str = await self.fetch_cookie_from_napcat()
            logger.info(f"[qzone_cookie] 成功获取 Cookie，长度={len(cookie_str)}")

            # ===== 步骤3：校验 Cookie 完整性 =====
            missing = self._check_required_fields(cookie_str)
            if missing:
                raise RuntimeError(
                    f"Cookie 不完整，缺少字段: {', '.join(missing)}"
                )
            found_fields = set(cookie_str.split(";")[i].split("=")[0].strip()
                              for i in range(len(cookie_str.split(";"))) if "=" in cookie_str.split(";")[i])
            logger.info(f"[qzone_cookie] Cookie 校验通过，包含字段: {', '.join(sorted(found_fields) & set(REQUIRED_COOKIE_FIELDS))}")

            # ===== 步骤4：热更新到 onebot-qzone =====
            update_result = await self.push_cookie_to_bridge(cookie_str)

            # ===== 步骤5：更新后验证（可选） =====
            if self.verify_after_update:
                logger.info("[qzone_cookie] 正在验证更新后的 Cookie 是否有效...")
                verify_result = await self.check_cookie_on_bridge()
                if verify_result["valid"]:
                    logger.info(
                        f"[qzone_cookie] Cookie 验证通过：有效，"
                        f"has_p_skey={verify_result['has_p_skey']}，"
                        f"has_skey={verify_result['has_skey']}"
                    )
                else:
                    logger.warning(
                        f"[qzone_cookie] Cookie 验证失败：{verify_result['message']}，"
                        f"请检查 update_cookie 是否真正生效"
                    )

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

        # 启动后延迟几秒，等待系统初始化
        await asyncio.sleep(5)

        # 首次执行（带预检，有效则跳过）
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
        """获取当前 Cookie 刷新状态"""
        return {
            "last_refresh_time": self._last_refresh_time,
            "last_refresh_success": self._last_refresh_success,
            "last_error": self._last_error,
            "refresh_count": self._refresh_count,
            "napcat_url": self.napcat_url,
            "bridge_url": self.bridge_url,
            "refresh_interval": self.refresh_interval,
            "verify_after_update": self.verify_after_update,
            # 预检结果
            "last_check_time": self._last_check_time,
            "last_cookie_valid": self._last_cookie_valid,
            "last_cookie_age_seconds": self._last_cookie_age_seconds,
            "last_check_message": self._last_check_message,
        }
