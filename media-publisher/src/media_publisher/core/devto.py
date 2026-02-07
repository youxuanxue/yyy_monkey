"""
Dev.to 发布模块

使用 Dev.to REST API 发布 Markdown 文章。
API 文档: https://developers.forem.com/api/v1
"""

import logging
from pathlib import Path
from typing import Optional, Callable, Tuple

import requests

from .base import Publisher, DevToPublishTask

logger = logging.getLogger(__name__)

# Dev.to API 基础 URL
API_BASE = "https://dev.to/api"


class DevToPublisher(Publisher):
    """
    Dev.to 文章发布器
    
    使用 API Key 认证，通过 REST API 发布 Markdown 文章。
    """
    
    def __init__(
        self,
        api_key_path: str = "config/devto_api_key.txt",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化 Dev.to 发布器
        
        Args:
            api_key_path: Dev.to API Key 文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        self.api_key_path = self._find_config_file(api_key_path)
        self.api_key: Optional[str] = None
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
        加载并验证 API Key
        
        API Key 获取方式:
        1. 登录 Dev.to (https://dev.to)
        2. Settings > Extensions > DEV Community API Keys
        3. 输入描述，点击 Generate API Key
        4. 复制 key 保存到 config/devto_api_key.txt
        """
        if not self.api_key_path.exists():
            raise FileNotFoundError(
                f"Dev.to API Key 文件未找到: {self.api_key_path}\n"
                "请按以下步骤获取 API Key:\n"
                "1. 登录 Dev.to (https://dev.to)\n"
                "2. Settings > Extensions > DEV Community API Keys\n"
                "3. 输入描述，点击 Generate API Key\n"
                "4. 复制 key 保存到: config/devto_api_key.txt"
            )
        
        self.api_key = self.api_key_path.read_text(encoding='utf-8').strip()
        if not self.api_key:
            raise ValueError("Dev.to API Key 文件为空")
        
        self._log("正在验证 Dev.to API Key...")
        
        resp = requests.get(
            f"{API_BASE}/users/me",
            headers=self._headers(),
            timeout=30,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            self.username = data.get('username', '未知')
            self._log(f"Dev.to 认证成功: @{self.username}")
        else:
            raise RuntimeError(
                f"Dev.to 认证失败 (HTTP {resp.status_code}): {resp.text}"
            )
    
    def _headers(self) -> dict:
        """构建请求头"""
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def publish(self, task: DevToPublishTask) -> Tuple[bool, Optional[str]]:
        """
        发布文章到 Dev.to
        
        Args:
            task: Dev.to 发布任务
            
        Returns:
            (success, article_url) - 成功状态和文章 URL
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self.api_key:
            self._log("未认证，请先调用 authenticate()", "ERROR")
            return False, "未认证"
        
        self._log(f"正在发布文章: {task.title}")
        self._log(f"  标签: {', '.join(task.tags)}")
        self._log(f"  系列: {task.series or '(无)'}")
        self._log(f"  发布状态: {'已发布' if task.published else '草稿'}")
        if task.canonical_url:
            self._log(f"  Canonical URL: {task.canonical_url}")
        
        article_data = {
            "title": task.title,
            "body_markdown": task.body_markdown,
            "tags": task.tags,
            "published": task.published,
        }
        
        if task.series:
            article_data["series"] = task.series
        
        if task.canonical_url:
            article_data["canonical_url"] = task.canonical_url
        
        payload = {"article": article_data}
        
        try:
            resp = requests.post(
                f"{API_BASE}/articles",
                headers=self._headers(),
                json=payload,
                timeout=60,
            )
            
            if resp.status_code == 201:
                data = resp.json()
                article_url = data.get('url', '')
                article_id = data.get('id', '')
                
                self._log(f"文章发布成功!")
                self._log(f"  文章 ID: {article_id}")
                self._log(f"  文章 URL: {article_url}")
                
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
