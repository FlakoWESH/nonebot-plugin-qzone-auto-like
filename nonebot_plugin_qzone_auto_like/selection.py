"""候选筛选：纯函数，便于单元测试。

从真寻版 qzone_auto_like/selection.py 原样移植，无框架依赖。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .feed import QzonePost


def select_like_candidates(
    posts: list["QzonePost"],
    denied: set[str] | None = None,
    existing: set[str] | None = None,
    limit: int | None = None,
) -> list["QzonePost"]:
    """跳过已点赞和点赞勿扰名单中的作者。"""
    denied = denied or set()
    existing = existing or set()
    result: list["QzonePost"] = []
    for post in posts:
        if not post.tid or post.tid in existing:
            continue
        if post.uin and post.uin in denied:
            continue
        result.append(post)
        if limit is not None and len(result) >= limit:
            break
    return result


def select_comment_candidates(
    posts: list["QzonePost"],
    allowed: set[str] | None = None,
    existing: set[str] | None = None,
    self_qq: str = "",
    limit: int | None = None,
) -> list["QzonePost"]:
    """只评论评论名单内、未评论过、且不是自己的说说。"""
    allowed = allowed or set()
    existing = existing or set()
    result: list["QzonePost"] = []
    for post in posts:
        if not post.tid or post.tid in existing:
            continue
        if not post.uin or post.uin == self_qq or post.uin not in allowed:
            continue
        result.append(post)
        if limit is not None and len(result) >= limit:
            break
    return result
