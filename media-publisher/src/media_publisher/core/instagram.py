"""
Instagram Reels 发布模块

使用 Facebook Graph API 发布 Reels 短视频。
API 文档: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Tuple

import requests

from .base import Publisher, InstagramPublishTask

logger = logging.getLogger(__name__)

# Facebook Graph API 基础 URL
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class InstagramPublisher(Publisher):
    """
    Instagram Reels 发布器
    
    使用 Facebook Graph API (两步流程):
    1. 创建媒体容器 (POST /{ig-user-id}/media)
    2. 发布容器 (POST /{ig-user-id}/media_publish)
    
    前置条件:
    - Facebook Business 账号
    - Instagram Professional 账号（已关联 Facebook Page）
    - 长期 Access Token (Page Token)
    - 视频需上传到公网 URL
    """
    
    def __init__(
        self,
        credentials_path: str = "config/instagram_credentials.json",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化 Instagram 发布器
        
        Args:
            credentials_path: Instagram/Facebook 凭据 JSON 文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        self.credentials_path = self._find_config_file(credentials_path)
        self.access_token: Optional[str] = None
        self.ig_user_id: Optional[str] = None
    
    def _find_config_file(self, config_path: str) -> Path:
        """查找配置文件"""
        possible_paths = [
            Path(config_path),
            Path.cwd() / config_path,
            Path.cwd().parent / config_path,
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return Path(config_path)
    
    def authenticate(self):
        """
        加载 Facebook/Instagram 凭据
        
        凭据文件格式 (config/instagram_credentials.json):
        {
            "access_token": "...",
            "ig_user_id": "..."
        }
        
        获取方式:
        1. 创建 Facebook App (https://developers.facebook.com/)
        2. 关联 Instagram Professional 账号
        3. 获取长期 Page Access Token
        4. 获取 Instagram Business Account ID
        5. 保存为 config/instagram_credentials.json
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Instagram 凭据文件未找到: {self.credentials_path}\n"
                "请按以下步骤获取凭据:\n"
                "1. 创建 Facebook App (https://developers.facebook.com/)\n"
                "2. 关联 Instagram Professional 账号\n"
                "3. 获取长期 Page Access Token\n"
                "4. 获取 Instagram Business Account ID\n"
                "5. 保存为 config/instagram_credentials.json:\n"
                '   {"access_token": "...", "ig_user_id": "..."}'
            )
        
        with open(self.credentials_path, 'r', encoding='utf-8') as f:
            creds = json.load(f)
        
        self.access_token = creds.get('access_token')
        self.ig_user_id = creds.get('ig_user_id')
        
        if not self.access_token:
            raise ValueError("Instagram 凭据文件缺少 access_token")
        if not self.ig_user_id:
            raise ValueError("Instagram 凭据文件缺少 ig_user_id")
        
        self._log("Instagram 凭据已加载")
        
        # 验证凭据
        self._verify_credentials()
    
    def _verify_credentials(self):
        """验证凭据是否有效"""
        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/{self.ig_user_id}",
                params={
                    "fields": "username,name",
                    "access_token": self.access_token,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                username = data.get('username', '未知')
                self._log(f"Instagram 认证成功: @{username}")
            else:
                self._log(
                    f"Instagram 凭据验证失败 (HTTP {resp.status_code})",
                    "WARNING"
                )
        except Exception as e:
            self._log(f"Instagram 凭据验证跳过: {e}", "WARNING")
    
    def publish(self, task: InstagramPublishTask) -> Tuple[bool, Optional[str]]:
        """
        发布 Reels 到 Instagram (两步流程)
        
        注意: Instagram Graph API 要求视频通过公网 URL 提供，
        不支持直接上传本地文件。需要先将视频上传到公网存储。
        
        Args:
            task: Instagram 发布任务
            
        Returns:
            (success, media_id) - 成功状态和媒体 ID
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self.access_token or not self.ig_user_id:
            self._log("未认证，请先调用 authenticate()", "ERROR")
            return False, "未认证"
        
        if not task.video_url:
            self._log(
                "Instagram Reels 需要公网视频 URL (video_url)，"
                "不支持直接上传本地文件",
                "ERROR"
            )
            return False, "需要公网视频 URL"
        
        self._log(f"正在发布 Reels...")
        self._log(f"  视频 URL: {task.video_url}")
        self._log(f"  Caption: {task.caption[:80]}...")
        
        # Step 1: 创建媒体容器
        self._log("Step 1: 创建媒体容器...")
        
        container_params = {
            "media_type": "REELS",
            "video_url": task.video_url,
            "caption": task.caption,
            "access_token": self.access_token,
        }
        
        try:
            resp = requests.post(
                f"{GRAPH_API_BASE}/{self.ig_user_id}/media",
                params=container_params,
                timeout=60,
            )
            
            if resp.status_code != 200:
                error_msg = f"创建容器失败 (HTTP {resp.status_code}): {resp.text}"
                self._log(error_msg, "ERROR")
                return False, error_msg
            
            container_id = resp.json().get('id')
            if not container_id:
                error_msg = f"未获取到 container_id: {resp.text}"
                self._log(error_msg, "ERROR")
                return False, error_msg
            
            self._log(f"  Container ID: {container_id}")
            
            # Step 2: 等待视频处理完成
            self._log("Step 2: 等待视频处理...")
            
            max_wait = 120  # 最多等待 2 分钟
            waited = 0
            while waited < max_wait:
                status_resp = requests.get(
                    f"{GRAPH_API_BASE}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": self.access_token,
                    },
                    timeout=30,
                )
                
                if status_resp.status_code == 200:
                    status = status_resp.json().get('status_code')
                    if status == 'FINISHED':
                        self._log("  视频处理完成")
                        break
                    elif status == 'ERROR':
                        error_msg = "视频处理失败"
                        self._log(error_msg, "ERROR")
                        return False, error_msg
                    else:
                        self._log(f"  处理中... (状态: {status})")
                
                time.sleep(5)
                waited += 5
            
            if waited >= max_wait:
                error_msg = "视频处理超时 (2分钟)"
                self._log(error_msg, "ERROR")
                return False, error_msg
            
            # Step 3: 发布容器
            self._log("Step 3: 发布 Reels...")
            
            publish_resp = requests.post(
                f"{GRAPH_API_BASE}/{self.ig_user_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
                timeout=60,
            )
            
            if publish_resp.status_code == 200:
                media_id = publish_resp.json().get('id')
                self._log(f"Reels 发布成功!")
                self._log(f"  Media ID: {media_id}")
                return True, media_id
            else:
                error_msg = (
                    f"发布失败 (HTTP {publish_resp.status_code}): "
                    f"{publish_resp.text}"
                )
                self._log(error_msg, "ERROR")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "请求超时，请检查网络连接"
            self._log(error_msg, "ERROR")
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"网络错误: {e}"
            self._log(error_msg, "ERROR")
            return False, error_msg
    
    def __enter__(self):
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
