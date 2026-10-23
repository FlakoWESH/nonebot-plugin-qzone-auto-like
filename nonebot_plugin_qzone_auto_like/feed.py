"""好友时间线抓取与规范化。

从真寻版 qzone_auto_like/feed.py 移植，去掉 zhenxun logger 依赖，
改用 nonebot.log。QzonePost 与 normalize_posts 为纯数据/纯函数，
供秒评链路使用；FeedScanner 封装一次拉取。
"""
from __future__ import annotations

from dataclasses import dataclass

from nonebot.log import logger

from .bridge import QzoneBridgeClient


@dataclass(frozen=True)
class QzonePost:
    """规范化后的单条空间说说。"""

    tid: str
    uin: str
    nickname: str = ""
    content: str = ""


def _extract_tid(post: dict) -> str:
    return str(post.get("tid") or post.get("cellid") or "").strip()


def _extract_uin(post: dict) -> str:
    for key in ("user_id", "uin", "hostuin", "host_uin"):
        value = post.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _extract_nickname(post: dict) -> str:
    for key in ("nickname", "name", "remark", "screen_name"):
        value = post.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _extract_content(post: dict) -> str:
    for key in ("content", "summary", "text"):
        value = post.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_posts(data: dict | None) -> list[QzonePost]:
    """把桥接返回的 msglist 转成去重后的 QzonePost 列表。"""
    posts = data.get("msglist") if isinstance(data, dict) else None
    if not isinstance(posts, list):
        return []

    result: list[QzonePost] = []
    seen: set[str] = set()
    for post in posts:
        if not isinstance(post, dict):
            continue
        tid = _extract_tid(post)
        if not tid or tid in seen:
            continue
        seen.add(tid)
        result.append(
            QzonePost(
                tid=tid,
                uin=_extract_uin(post),
                nickname=_extract_nickname(post),
                content=_extract_content(post),
            )
        )
    return result


class FeedScanner:
    """一次拉取，供点赞与评论共用（NoneBot 版主要用于秒评）。"""

    def __init__(self, bridge: QzoneBridgeClient):
        self.bridge = bridge

    async def scan(self, num: int = 50) -> list[QzonePost]:
        data = await self.bridge.get_friend_feeds(num=num)
        posts = normalize_posts(data)
        if not posts:
            logger.warning("[qzone_auto_like] 时间线为空或返回结构异常")
        return posts
