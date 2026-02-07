"""
TikTok 发布模块

使用 TikTok Content Posting API (FILE_UPLOAD 模式) 上传短视频。
API 文档: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Tuple

import requests

from .base import Publisher, TikTokPublishTask

logger = logging.getLogger(__name__)

# TikTok API 基础 URL
API_BASE = "https://open.tiktokapis.com/v2"


class TikTokPublisher(Publisher):
    """
    TikTok 短视频发布器
    
    使用 OAuth 2.0 认证，通过 Content Posting API 上传视频。
    注意: 视频上传后需用户在 TikTok App 内确认发布。
    """
    
    def __init__(
        self,
        credentials_path: str = "config/tiktok_credentials.json",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化 TikTok 发布器
        
        Args:
            credentials_path: TikTok OAuth 凭据 JSON 文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        self.credentials_path = self._find_config_file(credentials_path)
        self.access_token: Optional[str] = None
    
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
        加载 TikTok OAuth 2.0 Access Token
        
        凭据文件格式 (config/tiktok_credentials.json):
        {
            "access_token": "...",
            "client_key": "...",
            "client_secret": "..."
        }
        
        获取方式:
        1. 访问 https://developers.tiktok.com/
        2. 创建应用，申请 video.upload scope
        3. 完成 OAuth 2.0 授权流程获取 access_token
        4. 保存为 config/tiktok_credentials.json
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"TikTok 凭据文件未找到: {self.credentials_path}\n"
                "请按以下步骤获取凭据:\n"
                "1. 访问 https://developers.tiktok.com/\n"
                "2. 创建应用，申请 video.upload scope\n"
                "3. 完成 OAuth 2.0 授权流程\n"
                "4. 保存为 config/tiktok_credentials.json:\n"
                '   {"access_token": "...", "client_key": "...", '
                '"client_secret": "..."}'
            )
        
        with open(self.credentials_path, 'r', encoding='utf-8') as f:
            creds = json.load(f)
        
        self.access_token = creds.get('access_token')
        if not self.access_token:
            raise ValueError("TikTok 凭据文件缺少 access_token")
        
        self._log("TikTok OAuth 凭据已加载")
        
        # 验证 token（获取用户信息）
        self._verify_token()
    
    def _verify_token(self):
        """验证 Access Token"""
        try:
            resp = requests.get(
                f"{API_BASE}/user/info/",
                headers=self._headers(),
                params={"fields": "display_name,avatar_url"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('user', {})
                display_name = data.get('display_name', '未知')
                self._log(f"TikTok 认证成功: {display_name}")
            else:
                self._log(
                    f"TikTok Token 验证失败 (HTTP {resp.status_code}), "
                    "将在上传时重试",
                    "WARNING"
                )
        except Exception as e:
            self._log(f"TikTok Token 验证跳过: {e}", "WARNING")
    
    def _headers(self) -> dict:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def publish(self, task: TikTokPublishTask) -> Tuple[bool, Optional[str]]:
        """
        上传视频到 TikTok (FILE_UPLOAD 模式)
        
        流程:
        1. POST /v2/post/publish/video/init/ - 初始化上传，获取 upload_url
        2. PUT upload_url - 上传视频文件
        3. 用户在 TikTok App 内确认发布
        
        Args:
            task: TikTok 发布任务
            
        Returns:
            (success, publish_id) - 成功状态和发布 ID
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self.access_token:
            self._log("未认证，请先调用 authenticate()", "ERROR")
            return False, "未认证"
        
        video_size = task.video_path.stat().st_size
        self._log(f"正在上传视频: {task.video_path.name}")
        self._log(f"  文件大小: {video_size / (1024*1024):.1f} MB")
        self._log(f"  描述: {task.description[:80]}...")
        self._log(f"  隐私: {task.privacy}")
        
        # Step 1: 初始化上传
        self._log("Step 1: 初始化视频上传...")
        
        privacy_map = {
            "public": "PUBLIC_TO_EVERYONE",
            "friends": "MUTUAL_FOLLOW_FRIENDS",
            "private": "SELF_ONLY",
        }
        
        init_payload = {
            "post_info": {
                "title": task.description[:150],  # TikTok title 限 150 字符
                "privacy_level": privacy_map.get(task.privacy, "SELF_ONLY"),
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # 单块上传
                "total_chunk_count": 1,
            }
        }
        
        try:
            resp = requests.post(
                f"{API_BASE}/post/publish/video/init/",
                headers=self._headers(),
                json=init_payload,
                timeout=30,
            )
            
            if resp.status_code != 200:
                error_msg = f"初始化上传失败 (HTTP {resp.status_code}): {resp.text}"
                self._log(error_msg, "ERROR")
                return False, error_msg
            
            resp_data = resp.json().get('data', {})
            publish_id = resp_data.get('publish_id')
            upload_url = resp_data.get('upload_url')
            
            if not upload_url:
                error_msg = f"未获取到 upload_url: {resp.text}"
                self._log(error_msg, "ERROR")
                return False, error_msg
            
            self._log(f"  Publish ID: {publish_id}")
            
            # Step 2: 上传视频文件
            self._log("Step 2: 上传视频文件...")
            
            with open(task.video_path, 'rb') as video_file:
                upload_headers = {
                    "Content-Range": f"bytes 0-{video_size-1}/{video_size}",
                    "Content-Type": "video/mp4",
                }
                
                upload_resp = requests.put(
                    upload_url,
                    headers=upload_headers,
                    data=video_file,
                    timeout=300,  # 5 分钟超时
                )
            
            if upload_resp.status_code in [200, 201]:
                self._log("视频上传成功!")
                self._log(f"  Publish ID: {publish_id}")
                self._log("  请在 TikTok App 中确认发布")
                return True, publish_id
            else:
                error_msg = (
                    f"视频上传失败 (HTTP {upload_resp.status_code}): "
                    f"{upload_resp.text}"
                )
                self._log(error_msg, "ERROR")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "上传超时，请检查网络连接和视频文件大小"
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
