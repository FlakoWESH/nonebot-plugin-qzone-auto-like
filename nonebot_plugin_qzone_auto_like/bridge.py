"""onebot-qzone 桥接服务 HTTP 客户端（NoneBot 版）。

封装桥接服务的 Cookie 相关 action，统一 session 复用、鉴权和错误处理。
NoneBot 版点赞链路走 QzoneSession（进程内直接操作），因此本客户端只封装
Cookie 预检与热更新两个 action。
"""
from __future__ import annotations

from typing import Any

import aiohttp


class BridgeError(RuntimeError):
    """桥接服务调用失败。"""


class QzoneBridgeClient:
    """onebot-qzone 桥接服务的轻量 HTTP 客户端。"""

    def __init__(self, base_url: str, token: str = "", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.token = token or ""
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def call_data(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """调用 action，校验 retcode==0，返回 data 字段。"""
        session = await self._get_session()
        url = f"{self.base_url}/{action}"
        async with session.post(url, json=params or {}, headers=self._headers()) as resp:
            if resp.status == 401:
                raise BridgeError("桥接服务鉴权失败（401），请检查 bridge_token")
            if resp.status != 200:
                raise BridgeError(f"{action} 返回 HTTP {resp.status}")
            body = await resp.json(content_type=None)
        if not isinstance(body, dict):
            raise BridgeError(f"{action} 返回了非 JSON 对象")
        retcode = body.get("retcode", -1)
        if retcode != 0:
            raise BridgeError(
                f"{action} 失败: retcode={retcode}, message={body.get('message', '未知错误')}"
            )
        return body.get("data")

    async def check_cookie(self, probe: bool = True) -> dict[str, Any]:
        """带网络探针检测当前 Cookie 是否有效。"""
        data = await self.call_data("check_cookie", {"probe": probe})
        return data or {}

    async def update_cookie(self, cookie: str) -> dict[str, Any]:
        """热更新 Cookie，返回 user_id/nickname/message。"""
        data = await self.call_data("update_cookie", {"cookie": cookie})
        return data or {}
