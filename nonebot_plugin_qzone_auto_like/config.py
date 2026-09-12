"""
qzone_auto_like 插件配置
"""
from pydantic import BaseModel


class QzoneAutoLikeConfig(BaseModel):
    """QQ空间说说自动点赞插件配置"""

    # 是否启用自动点赞功能
    qzone_enable_auto_like: bool = True

    # 点赞轮询间隔（秒）
    qzone_like_interval: int = 600

    # 每次最多点赞说说数量
    qzone_max_like_count: int = 50

    # 单条说说点赞间隔（秒），防止风控
    qzone_per_like_interval: float = 1.0

    # 点赞记录数据文件路径
    qzone_data_file: str = "data/qzone_like_records.json"

    # QQ空间登录凭证（可选，也可通过onebot-qzone自动获取）
    qzone_qq_number: str = ""
