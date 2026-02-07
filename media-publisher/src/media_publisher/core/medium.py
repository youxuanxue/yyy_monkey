"""
Medium 发布模块

使用 Medium REST API 发布 Markdown 文章。
API 文档: https://github.com/Medium/medium-api-docs
"""

import logging
from pathlib import Path
from typing import Optional, Callable, Tuple

import requests

from .base import Publisher, MediumPublishTask

logger = logging.getLogger(__name__)

# Medium API 基础 URL
API_BASE = "https://api.medium.com/v1"


class MediumPublisher(Publisher):
    """
    Medium 文章发布器
    
    使用 Medium Integration Token 认证，通过 REST API 发布 Markdown 文章。
    """
    
    def __init__(
        self,
        token_path: str = "config/medium_token.txt",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化 Medium 发布器
        
        Args:
            token_path: Medium Integration Token 文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        self.token_path = self._find_config_file(token_path)
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
    
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
        使用 Integration Token 认证
        
        从 token 文件读取 token，然后调用 GET /v1/me 验证并获取 userId。
        
        Token 获取方式:
        1. 登录 Medium
        2. Settings > Security and apps > Integration tokens
        3. 生成并复制 token
        4. 保存到 config/medium_token.txt
        """
        if not self.token_path.exists():
            raise FileNotFoundError(
                f"Medium Token 文件未找到: {self.token_path}\n"
                "请按以下步骤获取 Token:\n"
                "1. 登录 Medium (https://medium.com)\n"
                "2. Settings > Security and apps > Integration tokens\n"
                "3. 输入描述，点击 Get token\n"
                "4. 复制 token 保存到: config/medium_token.txt"
            )
        
        self.token = self.token_path.read_text(encoding='utf-8').strip()
        if not self.token:
            raise ValueError("Medium Token 文件为空")
        
        self._log("正在验证 Medium Token...")
        
        resp = requests.get(
            f"{API_BASE}/me",
            headers=self._headers(),
            timeout=30,
        )
        
        if resp.status_code != 200:
            raise RuntimeError(
                f"Medium 认证失败 (HTTP {resp.status_code}): {resp.text}"
            )
        
        data = resp.json().get('data', {})
        self.user_id = data.get('id')
        self.username = data.get('username')
        
        if not self.user_id:
            raise RuntimeError("Medium 认证成功但未返回 userId")
        
        self._log(f"Medium 认证成功: @{self.username} (ID: {self.user_id})")
    
    def _headers(self) -> dict:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def publish(self, task: MediumPublishTask) -> Tuple[bool, Optional[str]]:
        """
        发布文章到 Medium
        
        Args:
            task: Medium 发布任务
            
        Returns:
            (success, article_url) - 成功状态和文章 URL
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self.user_id:
            self._log("未认证，请先调用 authenticate()", "ERROR")
            return False, "未认证"
        
        self._log(f"正在发布文章: {task.title}")
        self._log(f"  标签: {', '.join(task.tags)}")
        self._log(f"  状态: {task.publish_status}")
        if task.canonical_url:
            self._log(f"  Canonical URL: {task.canonical_url}")
        
        payload = {
            "title": task.title,
            "contentFormat": "markdown",
            "content": task.content,
            "tags": task.tags,
            "publishStatus": task.publish_status,
        }
        
        if task.canonical_url:
            payload["canonicalUrl"] = task.canonical_url
        
        try:
            resp = requests.post(
                f"{API_BASE}/users/{self.user_id}/posts",
                headers=self._headers(),
                json=payload,
                timeout=60,
            )
            
            if resp.status_code == 201:
                data = resp.json().get('data', {})
                article_url = data.get('url', '')
                article_id = data.get('id', '')
                
                self._log(f"文章发布成功!")
                self._log(f"  文章 ID: {article_id}")
                self._log(f"  文章 URL: {article_url}")
                self._log(f"  发布状态: {task.publish_status}")
                
                return True, article_url
            else:
                error_msg = f"发布失败 (HTTP {resp.status_code}): {resp.text}"
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
