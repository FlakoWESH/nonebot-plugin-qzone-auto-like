"""
QQ空间点赞记录存储模块（JSON文件实现）
用于记录已点赞的说说ID，避免重复点赞
数据结构：
{
    "liked_posts": ["post_id_1", "post_id_2", ...],
    "like_history": [
        {"qq_number": "123456", "post_id": "xxx", "like_time": "2026-09-12T10:00:00"}
    ]
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
    """QQ空间点赞记录存储器"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._liked_posts: Set[str] = set()
        self._like_history: List[dict] = []
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
                logger.info(
                    f"QQ空间点赞记录加载成功，已点赞说说 {len(self._liked_posts)} 条"
                )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"QQ空间点赞记录文件损坏，将重新创建: {e}")
                self._liked_posts = set()
                self._like_history = []
        else:
            self._liked_posts = set()
            self._like_history = []
        self._loaded = True

    def _save(self):
        """保存数据到文件"""
        self._ensure_dir()
        data = {
            "liked_posts": list(self._liked_posts),
            "like_history": self._like_history[-1000:],  # 只保留最近1000条
        }
        tmp_path = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.file_path)
        except IOError as e:
            logger.error(f"QQ空间点赞记录保存失败: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

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
