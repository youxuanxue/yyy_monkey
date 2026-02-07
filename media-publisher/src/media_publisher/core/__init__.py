"""核心发布模块"""

from .base import (
    Platform,
    PublishTask,
    ArticlePublishTask,
    WeChatPublishTask,
    YouTubePublishTask,
    MediumPublishTask,
    TwitterPublishTask,
    DevToPublishTask,
    TikTokPublishTask,
    InstagramPublishTask,
    Publisher,
)
from .adapter import EpisodeAdapter
from .wechat import WeChatPublisher
from .youtube import YouTubePublisher
from .medium import MediumPublisher
from .twitter import TwitterPublisher
from .devto import DevToPublisher
from .tiktok import TikTokPublisher
from .instagram import InstagramPublisher

__all__ = [
    # 枚举与基类
    "Platform",
    "PublishTask",
    "ArticlePublishTask",
    "Publisher",
    # 适配层
    "EpisodeAdapter",
    # 任务类
    "WeChatPublishTask",
    "YouTubePublishTask",
    "MediumPublishTask",
    "TwitterPublishTask",
    "DevToPublishTask",
    "TikTokPublishTask",
    "InstagramPublishTask",
    # 发布器
    "WeChatPublisher",
    "YouTubePublisher",
    "MediumPublisher",
    "TwitterPublisher",
    "DevToPublisher",
    "TikTokPublisher",
    "InstagramPublisher",
]
