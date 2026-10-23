"""与框架无关的纯逻辑：模板渲染、名单判定、参数解析。

从真寻版 qzone_auto_like/policy.py 移植，去掉 zhenxun 依赖，
可被 NoneBot 版的点赞/秒评服务直接调用。
"""
from __future__ import annotations

import re

DEFAULT_COMMENT_TEMPLATE = "QεQ"
DEFAULT_MONITOR_INTERVAL = 120
MIN_MONITOR_INTERVAL = 30
MAX_MONITOR_INTERVAL = 3600
MAX_TEMPLATE_LENGTH = 100

_QQ_RE = re.compile(r"(?<!\d)(\d{5,12})(?!\d)")
_DIGITS_RE = re.compile(r"\d+")


def normalize_template(text: str) -> str | None:
    """清理并校验用户输入的秒评内容，非法时返回 None。"""
    value = (text or "").strip().lstrip("+＋ \t")
    if not value:
        return None
    if len(value) > MAX_TEMPLATE_LENGTH:
        return None
    if any(ord(ch) < 32 for ch in value):
        return None
    return value


def parse_interval(text: str) -> int | None:
    """从文本中提取监控间隔，超出 30-3600 秒返回 None。"""
    match = _DIGITS_RE.search(text or "")
    if not match:
        return None
    value = int(match.group())
    if MIN_MONITOR_INTERVAL <= value <= MAX_MONITOR_INTERVAL:
        return value
    return None


def choose_template(personal: str | None, global_template: str | None) -> str:
    """个人模板优先，其次全局模板，最后内置默认值。"""
    for value in (personal, global_template):
        if value and value.strip():
            return value.strip()
    return DEFAULT_COMMENT_TEMPLATE


def render_template(template: str, nickname: str = "") -> str:
    """渲染模板变量；昵称缺失时使用"你"。"""
    name = (nickname or "").strip() or "你"
    return (template or DEFAULT_COMMENT_TEMPLATE).replace("{nickname}", name)


def format_qq_list(values: list[str], limit: int = 30) -> str:
    """格式化名单输出，避免单条消息过长。"""
    if not values:
        return "（空）"
    shown = values[:limit]
    text = "、".join(shown)
    if len(values) > limit:
        text += f" 等 {len(values)} 人"
    return text
