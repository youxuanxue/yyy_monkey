"""
媒体发布器基类和接口定义

提供统一的发布任务和发布器抽象接口，用于支持多平台发布。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Tuple


class Platform(Enum):
    """支持的平台枚举"""
    WECHAT = "wechat"
    YOUTUBE = "youtube"


@dataclass
class PublishTask(ABC):
    """
    发布任务基类
    
    所有平台的发布任务都应继承此类。
    """
    video_path: Path
    title: str = ""
    description: str = ""
    cover_path: Optional[Path] = None
    
    @abstractmethod
    def validate(self):
        """验证任务参数是否有效"""
        if not self.video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {self.video_path}")
        if self.cover_path and not self.cover_path.exists():
            raise FileNotFoundError(f"封面文件不存在: {self.cover_path}")
    
    @classmethod
    @abstractmethod
    def from_json(cls, video_path: Path, json_data: dict) -> "PublishTask":
        """从 JSON 数据创建发布任务"""
        pass


@dataclass
class WeChatPublishTask(PublishTask):
    """微信视频号发布任务"""
    hashtags: List[str] = field(default_factory=list)
    heji: str = ""  # 合集名称（可选）
    huodong: str = ""  # 活动名称（可选）

    def validate(self):
        """验证微信视频号任务参数"""
        super().validate()
        # 微信视频号短标题限制 16 字符
        if len(self.title) > 16:
            raise ValueError(f"微信视频号标题不能超过16字符: {self.title}")

    def get_full_description(self) -> str:
        """获取包含话题标签的完整描述"""
        desc = self.description.strip()
        if self.hashtags:
            hashtags_str = ' '.join(self.hashtags)
            if hashtags_str not in desc:
                desc = f"{desc}\n\n{hashtags_str}"
        return desc

    @classmethod
    def from_json(cls, video_path: Path, json_data: dict) -> "WeChatPublishTask":
        """从 JSON 数据创建微信视频号发布任务"""
        wechat_data = json_data.get('wechat', {})
        
        title = wechat_data.get('title', '')
        # 微信视频号短标题限制 16 字符
        if len(title) > 16:
            import logging
            logging.warning(f"标题超过16字符，将被截断: {title}")
            title = title[:16]
        
        return cls(
            video_path=video_path,
            title=title,
            description=wechat_data.get('description', ''),
            hashtags=wechat_data.get('hashtags', []),
            heji=wechat_data.get('heji', ''),
            huodong=wechat_data.get('huodong', ''),
        )


@dataclass
class YouTubePublishTask(PublishTask):
    """YouTube 发布任务"""
    tags: Optional[List[str]] = None
    category_id: str = "26"  # People & Blogs
    privacy_status: str = "private"  # "public", "unlisted", "private"
    made_for_kids: bool = False
    playlist_title: Optional[str] = None  # 播放列表名称

    def validate(self):
        """验证 YouTube 任务参数"""
        super().validate()
        if not self.title:
            raise ValueError("YouTube 标题不能为空")
        if not self.description:
            raise ValueError("YouTube 描述不能为空")
        if self.privacy_status not in ["public", "unlisted", "private"]:
            raise ValueError(f"无效的隐私设置: {self.privacy_status}")

    @classmethod
    def from_json(cls, video_path: Path, json_data: dict) -> "YouTubePublishTask":
        """从 JSON 数据创建 YouTube 发布任务"""
        youtube_data = json_data.get('youtube', {})
        
        # 如果没有 youtube 字段，尝试使用 wechat 字段作为后备
        if not youtube_data and 'wechat' in json_data:
            wechat_data = json_data['wechat']
            title = wechat_data.get('title', '')
            description = wechat_data.get('description', '')
            # 将微信话题标签转换为 YouTube 标签（去掉 #）
            hashtags = wechat_data.get('hashtags', [])
            tags = [tag.replace('#', '') for tag in hashtags if tag.startswith('#')]
            playlist_title = None
            privacy_status = "private"
        else:
            title = youtube_data.get('title', '')
            description = youtube_data.get('description', '')
            # 支持 hashtags 或 tags 字段
            tags = youtube_data.get('tags', youtube_data.get('hashtags', []))
            # 去掉标签中的 # 符号（如果有）
            tags = [tag.replace('#', '').strip() for tag in tags]
            playlist_title = youtube_data.get('playlists', None)
            privacy_status = youtube_data.get('privacy', 'private')
        
        return cls(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            made_for_kids=False,
            playlist_title=playlist_title
        )


class Publisher(ABC):
    """
    发布器抽象基类
    
    所有平台的发布器都应继承此类并实现其抽象方法。
    """
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化发布器
        
        Args:
            log_callback: 日志回调函数，用于在 GUI 中显示日志
        """
        self.log_callback = log_callback
    
    @abstractmethod
    def authenticate(self):
        """执行平台认证/登录"""
        pass
    
    @abstractmethod
    def publish(self, task: PublishTask) -> Tuple[bool, Optional[str]]:
        """
        发布视频到平台
        
        Args:
            task: 发布任务
            
        Returns:
            (success: bool, message: Optional[str]) - 成功状态和消息（如视频URL）
        """
        pass
    
    def _log(self, message: str, level: str = "INFO"):
        """
        记录日志
        
        Args:
            message: 日志消息
            level: 日志级别（INFO, WARNING, ERROR）
        """
        import logging
        logger = logging.getLogger(self.__class__.__name__)
        
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        
        if self.log_callback:
            self.log_callback(f"[{level}] {message}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pass
