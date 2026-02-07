"""
Episode 适配层

从 ep*.json 文件中读取 content + publish_config，
直接映射为各平台的 PublishTask / ArticlePublishTask，不做自动推断。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

from .base import (
    MediumPublishTask,
    DevToPublishTask,
    TwitterPublishTask,
    TikTokPublishTask,
    InstagramPublishTask,
    WeChatPublishTask,
    YouTubePublishTask,
)

logger = logging.getLogger(__name__)


class EpisodeAdapter:
    """
    ep*.json 适配器
    
    读取 ep*.json 文件，从 content + publish_config 提取各平台发布所需数据。
    遵循「不做自动推断」原则，所有字段从 JSON 显式读取。
    """
    
    def __init__(self, ep_json_path: str | Path):
        """
        加载 ep*.json 文件
        
        Args:
            ep_json_path: ep*.json 文件路径
        """
        self.path = Path(ep_json_path)
        if not self.path.exists():
            raise FileNotFoundError(f"ep*.json 文件不存在: {self.path}")
        
        with open(self.path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.content = self.data.get('content', {})
        self.publish_config = self.data.get('publish_config', {})
        self.series_info = self.data.get('series_info', {})
        self.meta = self.data.get('meta', {})
        self.cross_promotion = self.data.get('cross_promotion', {})
        
        logger.info(
            f"已加载: {self.path.name} "
            f"(系列: {self.series_info.get('series_name', '未知')}, "
            f"第{self.series_info.get('episode', '?')}集)"
        )
    
    @property
    def episode_number(self) -> int:
        """获取集数"""
        return self.series_info.get('episode', 0)
    
    @property
    def canonical_url(self) -> Optional[str]:
        """获取 canonical_url（可能为空，待 /journey 栏目上线后回填）"""
        url = self.publish_config.get('canonical_url', '')
        return url if url else None
    
    def to_medium_task(self, use_canonical_url: bool = False) -> MediumPublishTask:
        """
        构建 Medium 发布任务
        
        Args:
            use_canonical_url: 是否使用 canonical_url（默认 False，因为 /journey 栏目尚未上线）
        
        Returns:
            MediumPublishTask 实例
        """
        medium_config = self.publish_config.get('medium', {})
        overseas_blog = self.content.get('overseas_blog', {})
        
        return MediumPublishTask(
            title=medium_config.get('title', ''),
            content=overseas_blog.get('text', ''),
            tags=medium_config.get('tags', []),
            canonical_url=self.canonical_url if use_canonical_url else None,
            publish_status=medium_config.get('publish_status', 'draft'),
        )
    
    def to_devto_task(self, use_canonical_url: bool = False) -> DevToPublishTask:
        """
        构建 Dev.to 发布任务
        
        Args:
            use_canonical_url: 是否使用 canonical_url（默认 False）
        
        Returns:
            DevToPublishTask 实例
        """
        devto_config = self.publish_config.get('devto', {})
        overseas_blog = self.content.get('overseas_blog', {})
        
        return DevToPublishTask(
            title=devto_config.get('title', ''),
            body_markdown=overseas_blog.get('text', ''),
            tags=devto_config.get('tags', []),
            series=devto_config.get('series', None),
            canonical_url=self.canonical_url if use_canonical_url else None,
            published=devto_config.get('published', False),
        )
    
    def to_twitter_task(self) -> TwitterPublishTask:
        """
        构建 Twitter/X Thread 发布任务
        
        直接从 content.twitter_thread 读取推文和标签。
        
        Returns:
            TwitterPublishTask 实例
        """
        twitter_thread = self.content.get('twitter_thread', {})
        
        return TwitterPublishTask(
            title=f"Thread: {self.meta.get('title', '')}",
            tweets=twitter_thread.get('tweets', []),
            hashtags=twitter_thread.get('hashtags', []),
        )
    
    def to_tiktok_task(self, video_path: str | Path) -> TikTokPublishTask:
        """
        构建 TikTok 发布任务
        
        Args:
            video_path: 短视频文件路径
        
        Returns:
            TikTokPublishTask 实例
        """
        tiktok_config = self.publish_config.get('tiktok', {})
        
        return TikTokPublishTask(
            video_path=Path(video_path),
            description=tiktok_config.get('description', ''),
            privacy=tiktok_config.get('privacy', 'public'),
        )
    
    def to_instagram_task(self, video_path: str | Path) -> InstagramPublishTask:
        """
        构建 Instagram Reels 发布任务
        
        Args:
            video_path: 短视频文件路径
        
        Returns:
            InstagramPublishTask 实例
        """
        ig_config = self.publish_config.get('instagram', {})
        
        return InstagramPublishTask(
            video_path=Path(video_path),
            caption=ig_config.get('caption', ''),
            privacy=ig_config.get('privacy', 'public'),
        )
    
    def to_wechat_task(self, video_path: str | Path) -> WeChatPublishTask:
        """
        构建微信视频号发布任务（兼容已有逻辑）
        
        Args:
            video_path: 视频文件路径
        
        Returns:
            WeChatPublishTask 实例
        """
        wechat_video = self.content.get('wechat_video', {})
        text = wechat_video.get('text', '')
        
        # 从视频脚本中提取标签（最后一行通常是 #标签1 #标签2 格式）
        hashtags = []
        lines = text.strip().split('\n')
        if lines:
            last_line = lines[-1].strip()
            if last_line.startswith('#'):
                hashtags = [tag.strip() for tag in last_line.split('#') if tag.strip()]
                hashtags = [f"#{tag}" for tag in hashtags]
        
        return WeChatPublishTask(
            video_path=Path(video_path),
            title=self.meta.get('title', '')[:16],  # 微信标题限 16 字符
            description=text,
            hashtags=hashtags,
        )
    
    def to_youtube_task(self, video_path: str | Path) -> YouTubePublishTask:
        """
        构建 YouTube 发布任务（兼容已有逻辑）
        
        Args:
            video_path: 视频文件路径
        
        Returns:
            YouTubePublishTask 实例
        """
        short_video = self.content.get('short_video', {})
        
        return YouTubePublishTask(
            video_path=Path(video_path),
            title=self.meta.get('title', ''),
            description=short_video.get('text', ''),
            tags=self.meta.get('tags', []),
            privacy_status='private',
        )
    
    def get_available_platforms(self) -> dict:
        """
        返回该集可发布的平台及其任务类型概要
        
        Returns:
            dict: {platform_name: {has_content: bool, has_config: bool}}
        """
        return {
            'medium': {
                'has_content': bool(self.content.get('overseas_blog', {}).get('text')),
                'has_config': 'medium' in self.publish_config,
            },
            'devto': {
                'has_content': bool(self.content.get('overseas_blog', {}).get('text')),
                'has_config': 'devto' in self.publish_config,
            },
            'twitter': {
                'has_content': bool(self.content.get('twitter_thread', {}).get('tweets')),
                'has_config': 'twitter' in self.publish_config,
            },
            'tiktok': {
                'has_content': bool(self.content.get('short_video', {}).get('text')),
                'has_config': 'tiktok' in self.publish_config,
            },
            'instagram': {
                'has_content': bool(self.content.get('short_video', {}).get('text')),
                'has_config': 'instagram' in self.publish_config,
            },
            'wechat': {
                'has_content': bool(self.content.get('wechat_video', {}).get('text')),
                'has_config': True,  # 微信不依赖 publish_config
            },
            'youtube': {
                'has_content': bool(self.content.get('short_video', {}).get('text')),
                'has_config': True,  # YouTube 不依赖 publish_config
            },
        }
    
    def summary(self) -> str:
        """返回该集内容的摘要信息"""
        platforms = self.get_available_platforms()
        ready = [p for p, info in platforms.items() if info['has_content'] and info['has_config']]
        
        return (
            f"[EP{self.episode_number:02d}] {self.meta.get('title', '未知标题')}\n"
            f"  可发布平台: {', '.join(ready)}"
        )
