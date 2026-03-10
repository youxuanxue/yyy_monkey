"""核心发布模块."""

from importlib import import_module

_EXPORTS = {
    # 枚举与基类
    "Platform": ("media_publisher.core.base", "Platform"),
    "PublishTask": ("media_publisher.core.base", "PublishTask"),
    "ArticlePublishTask": ("media_publisher.core.base", "ArticlePublishTask"),
    "Publisher": ("media_publisher.core.base", "Publisher"),
    # 适配层
    "EpisodeAdapter": ("media_publisher.core.adapter", "EpisodeAdapter"),
    # 任务类
    "WeChatPublishTask": ("media_publisher.core.base", "WeChatPublishTask"),
    "YouTubePublishTask": ("media_publisher.core.base", "YouTubePublishTask"),
    "MediumPublishTask": ("media_publisher.core.base", "MediumPublishTask"),
    "TwitterPublishTask": ("media_publisher.core.base", "TwitterPublishTask"),
    "DevToPublishTask": ("media_publisher.core.base", "DevToPublishTask"),
    "TikTokPublishTask": ("media_publisher.core.base", "TikTokPublishTask"),
    "InstagramPublishTask": ("media_publisher.core.base", "InstagramPublishTask"),
    # 发布器
    "WeChatPublisher": ("media_publisher.core.wechat", "WeChatPublisher"),
    "YouTubePublisher": ("media_publisher.core.youtube", "YouTubePublisher"),
    "MediumPublisher": ("media_publisher.core.medium", "MediumPublisher"),
    "TwitterPublisher": ("media_publisher.core.twitter", "TwitterPublisher"),
    "DevToPublisher": ("media_publisher.core.devto", "DevToPublisher"),
    "TikTokPublisher": ("media_publisher.core.tiktok", "TikTokPublisher"),
    "InstagramPublisher": ("media_publisher.core.instagram", "InstagramPublisher"),
}


def __getattr__(name):
    if name in _EXPORTS:
        module_name, symbol_name = _EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, symbol_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
