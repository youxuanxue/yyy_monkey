"""
媒体发布工具

一键发布视频到多个短视频平台，支持微信视频号和YouTube Shorts。
支持自动填写标题、描述、标签等，以及合集、播放列表等高级功能。
"""

__version__ = "2.0.0"

from .core import (
    Platform,
    Publisher,
    PublishTask,
    WeChatPublisher,
    YouTubePublisher,
    WeChatPublishTask,
    YouTubePublishTask,
)

__all__ = [
    "Platform",
    "Publisher",
    "PublishTask",
    "WeChatPublisher",
    "YouTubePublisher",
    "WeChatPublishTask",
    "YouTubePublishTask",
]
