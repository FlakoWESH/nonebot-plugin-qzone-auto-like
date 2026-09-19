"""
qzone_auto_like 插件配置
"""
from pydantic import BaseModel


class QzoneAutoLikeConfig(BaseModel):
    """QQ空间说说自动点赞插件配置"""

    # ===== 自动点赞核心配置 =====

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

    # QQ空间登录凭证（可选，留空则使用 Bot 自身 QQ 号）
    qzone_qq_number: str = ""

    # ===== Cookie 自动刷新配置 =====

    # 是否启用自动从 NapCat 获取 QQ 空间 Cookie（需 NapCat HTTP API 和 onebot-qzone 桥接服务）
    qzone_enable_auto_cookie: bool = False

    # NapCat HTTP API 地址
    qzone_napcat_url: str = "http://127.0.0.1:3000"

    # NapCat access token（如 NapCat 设置了鉴权则填写）
    qzone_napcat_token: str = ""

    # onebot-qzone 桥接服务 HTTP API 地址
    qzone_bridge_url: str = "http://127.0.0.1:5700"

    # onebot-qzone access token（如桥接服务设置了鉴权则填写）
    qzone_bridge_token: str = ""

    # Cookie 自动刷新间隔（秒），默认 2 小时
    qzone_cookie_refresh_interval: int = 7200

    # HTTP 请求超时时间（秒）
    qzone_cookie_request_timeout: int = 10
