"""
Twitter/X 发布模块

使用 X API v2 发布 Thread（推文串）。
API 文档: https://developer.x.com/en/docs/x-api/tweets/manage-tweets/api-reference/post-tweets
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Tuple, List

import requests
from requests_oauthlib import OAuth1

from .base import Publisher, TwitterPublishTask

logger = logging.getLogger(__name__)

# X API v2 基础 URL
API_BASE = "https://api.x.com/2"


class TwitterPublisher(Publisher):
    """
    Twitter/X Thread 发布器
    
    使用 OAuth 1.0a 认证，通过 X API v2 逐条发布推文并串联为 Thread。
    """
    
    def __init__(
        self,
        credentials_path: str = "config/twitter_credentials.json",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化 Twitter 发布器
        
        Args:
            credentials_path: Twitter API 凭据 JSON 文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        self.credentials_path = self._find_config_file(credentials_path)
        self.auth: Optional[OAuth1] = None
    
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
        加载 OAuth 1.0a 凭据
        
        凭据文件格式 (config/twitter_credentials.json):
        {
            "api_key": "...",
            "api_secret": "...",
            "access_token": "...",
            "access_token_secret": "..."
        }
        
        获取方式:
        1. 访问 https://developer.x.com/en/portal/dashboard
        2. 创建 Project + App
        3. 设置 User authentication (OAuth 1.0a, Read and Write)
        4. 生成 API Key, API Secret, Access Token, Access Token Secret
        5. 保存为 config/twitter_credentials.json
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Twitter 凭据文件未找到: {self.credentials_path}\n"
                "请按以下步骤获取凭据:\n"
                "1. 访问 https://developer.x.com/en/portal/dashboard\n"
                "2. 创建 Project + App\n"
                "3. 设置 User authentication (OAuth 1.0a, Read and Write)\n"
                "4. 生成 Keys and Tokens\n"
                "5. 保存为 config/twitter_credentials.json:\n"
                '   {"api_key": "...", "api_secret": "...", '
                '"access_token": "...", "access_token_secret": "..."}'
            )
        
        with open(self.credentials_path, 'r', encoding='utf-8') as f:
            creds = json.load(f)
        
        required_keys = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
        missing = [k for k in required_keys if not creds.get(k)]
        if missing:
            raise ValueError(f"Twitter 凭据文件缺少字段: {', '.join(missing)}")
        
        self.auth = OAuth1(
            creds['api_key'],
            creds['api_secret'],
            creds['access_token'],
            creds['access_token_secret'],
        )
        
        self._log("Twitter OAuth 1.0a 凭据已加载")
        
        # 验证凭据（可选，快速失败）
        self._verify_credentials()
    
    def _verify_credentials(self):
        """验证凭据是否有效"""
        try:
            resp = requests.get(
                f"{API_BASE}/users/me",
                auth=self.auth,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                username = data.get('username', '未知')
                self._log(f"Twitter 认证成功: @{username}")
            else:
                self._log(
                    f"Twitter 凭据验证失败 (HTTP {resp.status_code}), "
                    "将在发布时重试",
                    "WARNING"
                )
        except Exception as e:
            self._log(f"Twitter 凭据验证跳过: {e}", "WARNING")
    
    def _post_tweet(
        self, 
        text: str, 
        reply_to_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        发送单条推文
        
        Args:
            text: 推文内容
            reply_to_id: 要回复的推文 ID（用于 Thread 串联）
            
        Returns:
            (success, tweet_id) - 成功状态和新推文 ID
        """
        payload = {"text": text}
        
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
        
        resp = requests.post(
            f"{API_BASE}/tweets",
            auth=self.auth,
            json=payload,
            timeout=30,
        )
        
        if resp.status_code == 201:
            data = resp.json().get('data', {})
            tweet_id = data.get('id')
            return True, tweet_id
        else:
            error_detail = resp.text
            try:
                error_json = resp.json()
                if 'detail' in error_json:
                    error_detail = error_json['detail']
                elif 'errors' in error_json:
                    error_detail = str(error_json['errors'])
            except Exception:
                pass
            self._log(
                f"发推失败 (HTTP {resp.status_code}): {error_detail}", 
                "ERROR"
            )
            return False, None
    
    def publish(self, task: TwitterPublishTask) -> Tuple[bool, Optional[str]]:
        """
        发布 Thread（推文串）
        
        逻辑: 
        1. 发第一条推文
        2. 获取 tweet_id
        3. 后续每条带 reply.in_reply_to_tweet_id 串联
        4. 最后一条追加 hashtags
        
        Args:
            task: Twitter 发布任务
            
        Returns:
            (success, thread_url) - 成功状态和第一条推文 URL
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self.auth:
            self._log("未认证，请先调用 authenticate()", "ERROR")
            return False, "未认证"
        
        tweets = list(task.tweets)  # 复制，避免修改原始数据
        total = len(tweets)
        
        self._log(f"开始发布 Thread: {total} 条推文")
        
        # 如果有 hashtags，追加到最后一条推文
        if task.hashtags and tweets:
            hashtags_str = ' '.join(task.hashtags)
            last_tweet = tweets[-1]
            # 检查追加后是否超过 280 字符
            combined = f"{last_tweet}\n\n{hashtags_str}"
            if len(combined) <= 280:
                tweets[-1] = combined
            else:
                self._log(
                    "最后一条推文追加 hashtags 后超过 280 字符，hashtags 将被省略",
                    "WARNING"
                )
        
        first_tweet_id = None
        prev_tweet_id = None
        published_count = 0
        
        for i, tweet_text in enumerate(tweets):
            self._log(f"  [{i+1}/{total}] 正在发送...")
            
            success, tweet_id = self._post_tweet(
                text=tweet_text,
                reply_to_id=prev_tweet_id,
            )
            
            if not success:
                self._log(
                    f"Thread 在第 {i+1} 条中断，已成功发布 {published_count}/{total} 条",
                    "ERROR"
                )
                if first_tweet_id:
                    thread_url = f"https://x.com/i/status/{first_tweet_id}"
                    return False, thread_url
                return False, None
            
            if i == 0:
                first_tweet_id = tweet_id
            
            prev_tweet_id = tweet_id
            published_count += 1
            
            self._log(f"  [{i+1}/{total}] 发送成功 (ID: {tweet_id})")
            
            # 发送间隔，避免触发频率限制
            if i < total - 1:
                time.sleep(1.0)
        
        thread_url = f"https://x.com/i/status/{first_tweet_id}"
        self._log(f"Thread 发布完成! {published_count}/{total} 条")
        self._log(f"Thread URL: {thread_url}")
        
        return True, thread_url
    
    def __enter__(self):
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
