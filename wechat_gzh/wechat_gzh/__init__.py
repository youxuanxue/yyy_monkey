"""
微信公众号工具集 (wechat-gzh)

包含以下功能：
1. API 客户端 - 通过微信公众号官方 API 获取用户信息
2. 自动留言 - 在已关注的公众号文章中自动留言

使用方法：
    # 获取用户信息
    uv run python -m wechat_gzh.get_users
    
    # 自动留言
    uv run python -m wechat_gzh.auto_comment
"""

from .api import WeChatAPI
from .config import COMMENT_TEXT, TIMING, HISTORY_FILE, LOG_DIR

__all__ = [
    "WeChatAPI",
    "COMMENT_TEXT",
    "TIMING",
    "HISTORY_FILE",
    "LOG_DIR",
]

__version__ = "0.1.0"
