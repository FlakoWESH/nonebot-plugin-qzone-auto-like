"""
QQ空间点赞/评论记录与名单存储模块（JSON文件实现）
用于记录已点赞/已评论的说说ID，避免重复操作；同时持久化评论名单与点赞勿扰名单。
数据结构：
{
    "liked_posts": ["post_id_1", ...],
    "like_history": [{"qq_number": "...", "post_id": "...", "like_time": "..."}],
    "commented_posts": ["post_id_1", ...],
    "comment_history": [{"qq_number": "...", "post_id": "...", "content": "...", "comment_time": "..."}],
    "comment_allowed": ["qq_1", ...],
    "like_denied": ["qq_2", ...]
}
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Set

from nonebot.log import logger


class QzoneLikeStore:
    """QQ空间点赞/评论记录与名单存储器"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._liked_posts: Set[str] = set()
        self._like_history: List[dict] = []
        self._commented_posts: Set[str] = set()
        self._comment_history: List[dict] = []
        self._comment_allowed: Set[str] = set()
        self._like_denied: Set[str] = set()
        self._loaded = False

    def _ensure_dir(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """从文件加载数据"""
        if self._loaded:
            return
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._liked_posts = set(data.get("liked_posts", []))
                self._like_history = data.get("like_history", [])
                self._commented_posts = set(data.get("commented_posts", []))
                self._comment_history = data.get("comment_history", [])
                self._comment_allowed = set(data.get("comment_allowed", []))
                self._like_denied = set(data.get("like_denied", []))
                logger.info(
                    f"QQ空间记录加载成功，已点赞 {len(self._liked_posts)} 条，"
                    f"已评论 {len(self._commented_posts)} 条，"
                    f"评论名单 {len(self._comment_allowed)} 人，"
                    f"勿扰名单 {len(self._like_denied)} 人"
                )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"QQ空间记录文件损坏，将重新创建: {e}")
                self._reset_all()
        else:
            self._reset_all()
        self._loaded = True

    def _reset_all(self):
        self._liked_posts = set()
        self._like_history = []
        self._commented_posts = set()
        self._comment_history = []
        self._comment_allowed = set()
        self._like_denied = set()

    def _save(self):
        """保存数据到文件"""
        self._ensure_dir()
        data = {
            "liked_posts": list(self._liked_posts),
            "like_history": self._like_history[-1000:],
            "commented_posts": list(self._commented_posts),
            "comment_history": self._comment_history[-1000:],
            "comment_allowed": sorted(self._comment_allowed),
            "like_denied": sorted(self._like_denied),
        }
        tmp_path = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.file_path)
        except IOError as e:
            logger.error(f"QQ空间记录保存失败: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

    # ========== 点赞记录 ==========

    async def is_liked(self, post_id: str) -> bool:
        """检查说说是否已点赞"""
        async with self._lock:
            self._load()
            return post_id in self._liked_posts

    async def mark_liked(self, qq_number: str, post_id: str):
        """标记说说已点赞"""
        async with self._lock:
            self._load()
            self._liked_posts.add(post_id)
            self._like_history.append(
                {
                    "qq_number": qq_number,
                    "post_id": post_id,
                    "like_time": datetime.now().isoformat(),
                }
            )
            self._save()

    async def get_liked_count(self) -> int:
        """获取已点赞说说总数"""
        async with self._lock:
            self._load()
            return len(self._liked_posts)

    async def get_today_liked_count(self, qq_number: str) -> int:
        """获取指定 QQ 号今日已点赞的说说数量"""
        async with self._lock:
            self._load()
            today = datetime.now().date().isoformat()
            return sum(
                1
                for h in self._like_history
                if h.get("qq_number") == str(qq_number)
                and h.get("like_time", "").startswith(today)
            )

    async def filter_unliked(self, post_ids: list[str]) -> list[str]:
        """批量过滤，返回尚未点赞的 post_id 列表（保持原顺序）"""
        async with self._lock:
            self._load()
            return [pid for pid in post_ids if pid and pid not in self._liked_posts]

    # ========== 评论记录 ==========

    async def is_commented(self, post_id: str) -> bool:
        """检查说说是否已评论"""
        async with self._lock:
            self._load()
            return post_id in self._commented_posts

    async def mark_commented(self, qq_number: str, post_id: str, content: str = ""):
        """标记说说已评论"""
        async with self._lock:
            self._load()
            self._commented_posts.add(post_id)
            self._comment_history.append(
                {
                    "qq_number": qq_number,
                    "post_id": post_id,
                    "content": content,
                    "comment_time": datetime.now().isoformat(),
                }
            )
            self._save()

    async def get_commented_count(self) -> int:
        """获取已评论说说总数"""
        async with self._lock:
            self._load()
            return len(self._commented_posts)

    async def get_today_commented_count(self, qq_number: str) -> int:
        """获取指定 QQ 号今日已评论的说说数量"""
        async with self._lock:
            self._load()
            today = datetime.now().date().isoformat()
            return sum(
                1
                for h in self._comment_history
                if h.get("qq_number") == str(qq_number)
                and h.get("comment_time", "").startswith(today)
            )

    async def filter_uncommented(self, post_ids: list[str]) -> list[str]:
        """批量过滤，返回尚未评论的 post_id 列表（保持原顺序）"""
        async with self._lock:
            self._load()
            return [pid for pid in post_ids if pid and pid not in self._commented_posts]

    # ========== 评论名单（默认空，为空时不评论任何人） ==========

    async def add_comment_allowed(self, qq: str) -> bool:
        """加入评论名单，返回是否为新增。"""
        value = str(qq).strip()
        async with self._lock:
            self._load()
            if value in self._comment_allowed:
                return False
            self._comment_allowed.add(value)
            self._save()
            return True

    async def remove_comment_allowed(self, qq: str) -> bool:
        """移出评论名单，返回是否存在过。"""
        value = str(qq).strip()
        async with self._lock:
            self._load()
            if value not in self._comment_allowed:
                return False
            self._comment_allowed.discard(value)
            self._save()
            return True

    async def get_comment_allowed(self) -> set[str]:
        """获取评论名单集合。"""
        async with self._lock:
            self._load()
            return set(self._comment_allowed)

    async def list_comment_allowed(self) -> list[str]:
        """获取排序后的评论名单。"""
        async with self._lock:
            self._load()
            return sorted(self._comment_allowed)

    async def count_comment_allowed(self) -> int:
        """获取评论名单人数。"""
        async with self._lock:
            self._load()
            return len(self._comment_allowed)

    async def clear_comment_allowed(self) -> int:
        """清空评论名单，返回清空人数。"""
        async with self._lock:
            self._load()
            removed = len(self._comment_allowed)
            self._comment_allowed.clear()
            self._save()
            return removed

    # ========== 点赞勿扰名单 ==========

    async def add_like_denied(self, qq: str) -> bool:
        """加入点赞勿扰名单，返回是否为新增。"""
        value = str(qq).strip()
        async with self._lock:
            self._load()
            if value in self._like_denied:
                return False
            self._like_denied.add(value)
            self._save()
            return True

    async def remove_like_denied(self, qq: str) -> bool:
        """移出点赞勿扰名单，返回是否存在过。"""
        value = str(qq).strip()
        async with self._lock:
            self._load()
            if value not in self._like_denied:
                return False
            self._like_denied.discard(value)
            self._save()
            return True

    async def get_like_denied(self) -> set[str]:
        """获取点赞勿扰名单集合。"""
        async with self._lock:
            self._load()
            return set(self._like_denied)

    async def list_like_denied(self) -> list[str]:
        """获取排序后的点赞勿扰名单。"""
        async with self._lock:
            self._load()
            return sorted(self._like_denied)

    async def count_like_denied(self) -> int:
        """获取点赞勿扰名单人数。"""
        async with self._lock:
            self._load()
            return len(self._like_denied)

    async def clear_like_denied(self) -> int:
        """清空点赞勿扰名单，返回清空人数。"""
        async with self._lock:
            self._load()
            removed = len(self._like_denied)
            self._like_denied.clear()
            self._save()
            return removed
