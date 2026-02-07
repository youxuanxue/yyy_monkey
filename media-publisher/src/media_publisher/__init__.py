"""
媒体发布工具

多平台内容发布工具，支持微信视频号、YouTube Shorts、Medium、Twitter/X、
Dev.to、TikTok、Instagram Reels。支持从 ep*.json 素材文件直接发布。
"""

__version__ = "3.0.0"

from .core import (
    Platform,
    Publisher,
    PublishTask,
    ArticlePublishTask,
    EpisodeAdapter,
    WeChatPublisher,
    YouTubePublisher,
    MediumPublisher,
    TwitterPublisher,
    DevToPublisher,
    TikTokPublisher,
    InstagramPublisher,
    WeChatPublishTask,
    YouTubePublishTask,
    MediumPublishTask,
    TwitterPublishTask,
    DevToPublishTask,
    TikTokPublishTask,
    InstagramPublishTask,
)

__all__ = [
    "Platform",
    "Publisher",
    "PublishTask",
    "ArticlePublishTask",
    "EpisodeAdapter",
    "WeChatPublisher",
    "YouTubePublisher",
    "MediumPublisher",
    "TwitterPublisher",
    "DevToPublisher",
    "TikTokPublisher",
    "InstagramPublisher",
    "WeChatPublishTask",
    "YouTubePublishTask",
    "MediumPublishTask",
    "TwitterPublishTask",
    "DevToPublishTask",
    "TikTokPublishTask",
    "InstagramPublishTask",
]
