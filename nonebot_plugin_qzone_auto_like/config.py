"""
qzone_auto_like 插件配置
"""
from pydantic import BaseModel


class QzoneAutoLikeConfig(BaseModel):
    """QQ空间说说自动点赞插件配置"""

    # ===== 自动点赞核心配置 =====

    # 是否启用自动点赞功能（默认关闭，自动点赞属于高风险操作，需显式开启）
    qzone_enable_auto_like: bool = False

    # 点赞轮询间隔（秒）
    qzone_like_interval: int = 600

    # 每次最多点赞说说数量
    qzone_max_like_count: int = 50

    # 单条说说点赞之间的最小随机延迟（秒），模拟真人行为防风控
    qzone_like_random_delay_min: float = 2.0

    # 单条说说点赞之间的最大随机延迟（秒）
    qzone_like_random_delay_max: float = 6.0

    # 每日最多点赞条数（0 表示不限制），防风控
    qzone_daily_like_limit: int = 200

    # ===== 自动秒评配置（需 onebot-qzone 桥接服务支持 send_comment） =====

    # 是否启用自动秒评（默认关闭，评论比点赞更易触发风控）
    qzone_enable_auto_comment: bool = False

    # 每轮最多评论条数
    qzone_comment_max_per_round: int = 5

    # 每日最多评论条数（0 表示不限制）
    qzone_comment_daily_limit: int = 50

    # 单条评论之间的最小随机延迟（秒），评论延迟建议比点赞更大
    qzone_comment_delay_min: float = 5.0

    # 单条评论之间的最大随机延迟（秒）
    qzone_comment_delay_max: float = 15.0

    # 全局秒评内容（支持 {nickname} 变量）
    qzone_comment_template: str = "QεQ"

    # 点赞记录数据文件路径
    qzone_data_file: str = "data/qzone_like_records.json"

    # QQ空间登录凭证（可选，留空则使用 Bot 自身 QQ 号）
    qzone_qq_number: str = ""

    # ===== Cookie 自动刷新配置 =====

    # 是否启用自动从 NapCat 获取 QQ 空间 Cookie（优先复用 OneBot 连接，无需额外 HTTP 服务）
    qzone_enable_auto_cookie: bool = False

    # NapCat HTTP API 地址（仅当 OneBot 连接不可用时作为回退）
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

    # 更新后是否调用 check_cookie API 验证新 Cookie 是否有效
    qzone_cookie_verify_after_update: bool = True
