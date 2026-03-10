"""
媒体发布工具

多平台内容发布工具，支持微信视频号、YouTube Shorts、Medium、Twitter/X、
Dev.to、TikTok、Instagram Reels。支持从 ep*.json 素材文件直接发布。
"""

__version__ = "3.0.0"

from importlib import import_module

_EXPORTS = {
    "Platform": ("media_publisher.core.base", "Platform"),
    "Publisher": ("media_publisher.core.base", "Publisher"),
    "PublishTask": ("media_publisher.core.base", "PublishTask"),
    "ArticlePublishTask": ("media_publisher.core.base", "ArticlePublishTask"),
    "WeChatPublishTask": ("media_publisher.core.base", "WeChatPublishTask"),
    "YouTubePublishTask": ("media_publisher.core.base", "YouTubePublishTask"),
    "MediumPublishTask": ("media_publisher.core.base", "MediumPublishTask"),
    "TwitterPublishTask": ("media_publisher.core.base", "TwitterPublishTask"),
    "DevToPublishTask": ("media_publisher.core.base", "DevToPublishTask"),
    "TikTokPublishTask": ("media_publisher.core.base", "TikTokPublishTask"),
    "InstagramPublishTask": ("media_publisher.core.base", "InstagramPublishTask"),
    "EpisodeAdapter": ("media_publisher.core.adapter", "EpisodeAdapter"),
    "WeChatPublisher": ("media_publisher.core.wechat", "WeChatPublisher"),
    "YouTubePublisher": ("media_publisher.core.youtube", "YouTubePublisher"),
    "MediumPublisher": ("media_publisher.core.medium", "MediumPublisher"),
    "TwitterPublisher": ("media_publisher.core.twitter", "TwitterPublisher"),
    "DevToPublisher": ("media_publisher.core.devto", "DevToPublisher"),
    "TikTokPublisher": ("media_publisher.core.tiktok", "TikTokPublisher"),
    "InstagramPublisher": ("media_publisher.core.instagram", "InstagramPublisher"),
}


def __getattr__(name):
    """Lazy export heavy symbols to avoid module-level side effects."""
    if name in _EXPORTS:
        module_name, symbol_name = _EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, symbol_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "__version__",
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
