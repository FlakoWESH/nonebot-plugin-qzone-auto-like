"""
QQ空间点赞/评论记录存储模块（JSON文件实现）
用于记录已点赞/已评论的说说ID，避免重复操作
数据结构：
{
    "liked_posts": ["post_id_1", ...],
    "like_history": [{"qq_number": "...", "post_id": "...", "like_time": "..."}],
    "commented_posts": ["post_id_1", ...],
    "comment_history": [{"qq_number": "...", "post_id": "...", "content": "...", "comment_time": "..."}]
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
    """QQ空间点赞/评论记录存储器"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._liked_posts: Set[str] = set()
        self._like_history: List[dict] = []
        self._commented_posts: Set[str] = set()
        self._comment_history: List[dict] = []
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
                logger.info(
                    f"QQ空间记录加载成功，已点赞 {len(self._liked_posts)} 条，"
                    f"已评论 {len(self._commented_posts)} 条"
                )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"QQ空间记录文件损坏，将重新创建: {e}")
                self._liked_posts = set()
                self._like_history = []
                self._commented_posts = set()
                self._comment_history = []
        else:
            self._liked_posts = set()
            self._like_history = []
            self._commented_posts = set()
            self._comment_history = []
        self._loaded = True

    def _save(self):
        """保存数据到文件"""
        self._ensure_dir()
        data = {
            "liked_posts": list(self._liked_posts),
            "like_history": self._like_history[-1000:],
            "commented_posts": list(self._commented_posts),
            "comment_history": self._comment_history[-1000:],
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
