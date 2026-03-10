"""
YouTube Shorts 发布核心模块

使用 YouTube Data API v3 自动化发布视频到 YouTube Shorts。
"""

import logging
import os
import socket
from pathlib import Path
from typing import Optional, Callable, Tuple
from media_publisher.shared.io import atomic_write_text

DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 7890


def _setup_proxy(logger_obj: Optional[logging.Logger] = None):
    """在调用点设置代理环境变量（禁止模块导入时副作用）。"""
    proxy_host = os.environ.get('PROXY_HOST', DEFAULT_PROXY_HOST)
    proxy_port = os.environ.get('PROXY_PORT', str(DEFAULT_PROXY_PORT))
    use_proxy = os.environ.get('USE_PROXY', 'true').lower() == 'true'
    
    if use_proxy:
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
        if logger_obj:
            logger_obj.info("YouTube 模块已设置代理环境变量: %s", proxy_url)

import httplib2
import requests
from google.auth.transport.requests import Request, AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


class RequestsHttpAdapter:
    """
    使用 requests 库的 httplib2.Http 兼容适配器。
    requests 会自动读取 HTTP_PROXY/HTTPS_PROXY 环境变量。
    """
    
    def __init__(self, credentials=None, timeout=1800):
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        
        # 从环境变量读取代理（requests 会自动使用，但我们显式设置确保生效）
        proxy_url = os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY', ''))
        if proxy_url:
            self.session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
    
    def request(self, uri, method="GET", body=None, headers=None,
                redirections=5, connection_type=None):
        """模拟 httplib2.Http.request 接口"""
        if headers is None:
            headers = {}
        
        # 添加认证头
        if self.credentials:
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            headers['Authorization'] = f'Bearer {self.credentials.token}'
        
        try:
            response = self.session.request(
                method=method,
                url=uri,
                data=body,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=(redirections > 0)
            )
            
            # 构造 httplib2 兼容的响应对象
            resp = httplib2.Response(response.headers)
            resp.status = response.status_code
            resp['status'] = str(response.status_code)
            
            return resp, response.content
            
        except requests.exceptions.Timeout as e:
            raise socket.timeout(str(e))
        except requests.exceptions.RequestException as e:
            raise socket.error(str(e))

from .base import Publisher, YouTubePublishTask

# Configure logging
logger = logging.getLogger(__name__)

# YouTube API 配置
# 需要 upload 权限上传视频，需要 youtube 权限管理播放列表
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',  # 上传视频
    'https://www.googleapis.com/auth/youtube',          # 管理播放列表、视频等
]
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'


class YouTubePublisher(Publisher):
    """
    YouTube Shorts 自动发布器
    
    使用 YouTube Data API v3 完成视频上传和发布。
    """
    
    def __init__(
        self, 
        credentials_path: str = "config/youtube_credentials.json", 
        token_path: str = "config/youtube_token.json",
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        初始化发布器
        
        Args:
            credentials_path: OAuth2 凭据文件路径
            token_path: OAuth2 令牌文件路径
            log_callback: 日志回调函数
        """
        super().__init__(log_callback)
        
        # 查找配置文件：先尝试相对路径，然后尝试从父目录查找
        self.credentials_path = self._find_config_file(credentials_path)
        # token 路径使用与 credentials 相同的目录
        self.token_path = self.credentials_path.parent / Path(token_path).name
        self.credentials: Optional[Credentials] = None
        self.youtube = None
    
    def _find_config_file(self, config_path: str) -> Path:
        """
        查找配置文件，支持多个可能的位置
        
        Args:
            config_path: 配置文件相对路径
            
        Returns:
            配置文件的绝对路径
        """
        # 尝试多个可能的位置
        possible_paths = [
            Path(config_path),  # 当前目录
            Path.cwd() / config_path,  # 工作目录
            Path.cwd().parent / config_path,  # 父目录（media-publisher 的父目录）
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # 如果都不存在，返回第一个路径（会在后续抛出错误）
        return Path(config_path)

    def authenticate(self):
        """
        使用 OAuth2 进行 YouTube API 认证
        
        如果令牌存在且有效，则使用它。否则运行 OAuth 流程。
        """
        # 在入口调用点设置代理，避免模块导入时产生全局副作用。
        _setup_proxy(logger)
        creds = None
        
        # 加载现有令牌
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                self._log("从令牌文件加载现有凭据")
            except Exception as e:
                self._log(f"从令牌文件加载凭据失败: {e}", "WARNING")

        # 如果没有有效凭据，让用户登录
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._log("正在刷新过期的凭据...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self._log(f"刷新凭据失败: {e}", "ERROR")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"凭据文件未找到: {self.credentials_path}\n"
                        "请从 Google Cloud Console 下载 OAuth2 凭据:\n"
                        "1. 访问 https://console.cloud.google.com/\n"
                        "2. 创建/选择项目\n"
                        "3. 启用 YouTube Data API v3\n"
                        "4. 创建 OAuth 2.0 凭据（桌面应用）\n"
                        "5. 重要: 添加授权重定向 URI: http://localhost:8080/\n"
                        "   (进入 OAuth 2.0 客户端 ID > 编辑 > 已授权的重定向 URI)\n"
                        "6. 下载并保存为 config/youtube_credentials.json"
                    )
                
                self._log("开始 OAuth2 授权流程...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES)
                # 使用固定端口 8080 - 确保在 Google Cloud Console 中添加 
                # http://localhost:8080/ 作为授权重定向 URI
                try:
                    creds = flow.run_local_server(port=8080, open_browser=True)
                except OSError as e:
                    if "Address already in use" in str(e):
                        self._log("端口 8080 已被占用。尝试使用随机端口...", "WARNING")
                        self._log("注意: 如果遇到 redirect_uri_mismatch 错误，你需要:", "WARNING")
                        self._log("1. 查看授权 URL 中显示的端口号", "WARNING")
                        self._log("2. 在 Google Cloud Console 中添加 http://localhost:<port>/ 到授权重定向 URI", "WARNING")
                        creds = flow.run_local_server(port=0, open_browser=True)
                    else:
                        raise
                except Exception as e:
                    error_str = str(e)
                    if "redirect_uri_mismatch" in error_str.lower() or "400" in error_str:
                        raise RuntimeError(
                            "OAuth redirect_uri_mismatch 错误！\n"
                            "解决方法：\n"
                            "1. 访问 Google Cloud Console: https://console.cloud.google.com/\n"
                            "2. 进入 APIs & Services > Credentials\n"
                            "3. 点击你的 OAuth 2.0 客户端 ID\n"
                            "4. 在 '已授权的重定向 URI' 中添加: http://localhost:8080/\n"
                            "5. 保存更改后重新运行脚本\n"
                            f"\n原始错误: {error_str}"
                        ) from e
                    raise
                self._log("OAuth2 认证成功")

            # 保存凭据供下次运行使用
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self.token_path, creds.to_json())
            self._log(f"凭据已保存到 {self.token_path}")

        self.credentials = creds
        
        # 设置 socket 默认超时（30分钟，适合大文件上传）
        socket.setdefaulttimeout(1800)  # 30分钟
        
        # 检查代理配置
        proxy_url = os.environ.get('HTTPS_PROXY', '')
        use_proxy = os.environ.get('USE_PROXY', 'true').lower() == 'true'
        
        if use_proxy and proxy_url:
            self._log(f"🌐 使用代理: {proxy_url} (通过 requests 库)")
        else:
            self._log("🌐 直连模式（未使用代理）")
        
        # 使用自定义的 requests 适配器（正确支持代理）
        http_adapter = RequestsHttpAdapter(credentials=creds, timeout=1800)
        
        # 使用带代理支持的 HTTP 适配器构建 API
        self.youtube = build(
            API_SERVICE_NAME, 
            API_VERSION, 
            http=http_adapter
        )
        self._log("YouTube API 客户端初始化完成（上传超时: 30分钟）")

    def find_or_create_playlist(self, playlist_title: str) -> str:
        """
        查找或创建播放列表
        
        Args:
            playlist_title: 播放列表标题
            
        Returns:
            播放列表 ID
        """
        if not self.youtube:
            raise RuntimeError("未认证。请先调用 authenticate()")
        
        try:
            # 搜索现有播放列表
            self._log(f"搜索播放列表: {playlist_title}")
            request = self.youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50
            )
            response = request.execute()
            
            # 检查播放列表是否存在
            for item in response.get('items', []):
                if item['snippet']['title'] == playlist_title:
                    playlist_id = item['id']
                    self._log(f"找到现有播放列表: {playlist_title} (ID: {playlist_id})")
                    return playlist_id
            
            # 如果未找到，创建新播放列表
            self._log(f"播放列表未找到。创建新播放列表: {playlist_title}")
            request = self.youtube.playlists().insert(
                part="snippet,status",
                body={
                    'snippet': {
                        'title': playlist_title,
                        'description': f'自动创建的播放列表: {playlist_title}',
                    },
                    'status': {
                        'privacyStatus': 'public'
                    }
                }
            )
            response = request.execute()
            playlist_id = response['id']
            self._log(f"创建新播放列表: {playlist_title} (ID: {playlist_id})")
            return playlist_id
            
        except HttpError as e:
            self._log(f"查找/创建播放列表失败: {e}", "ERROR")
            raise

    def add_video_to_playlist(self, video_id: str, playlist_id: str):
        """
        将视频添加到播放列表
        
        Args:
            video_id: YouTube 视频 ID
            playlist_id: YouTube 播放列表 ID
        """
        if not self.youtube:
            raise RuntimeError("未认证。请先调用 authenticate()")
        
        try:
            self._log(f"将视频 {video_id} 添加到播放列表 {playlist_id}")
            request = self.youtube.playlistItems().insert(
                part="snippet",
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }
            )
            response = request.execute()
            self._log("成功将视频添加到播放列表")
            
        except HttpError as e:
            self._log(f"添加视频到播放列表失败: {e}", "ERROR")
            raise

    def publish(self, task: YouTubePublishTask) -> Tuple[bool, Optional[str]]:
        """
        上传视频到 YouTube 作为 Short
        
        Args:
            task: YouTube 发布任务
            
        Returns:
            (success, video_url) - 成功状态和视频 URL
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, None

        if not self.youtube:
            error_msg = "未认证。请先调用 authenticate()"
            self._log(error_msg, "ERROR")
            return False, None

        try:
            self._log(f"正在上传视频: {task.video_path}")
            
            # 准备视频元数据
            body = {
                'snippet': {
                    'title': task.title,
                    'description': task.description,
                    'tags': task.tags or [],
                    'categoryId': task.category_id,
                },
                'status': {
                    'privacyStatus': task.privacy_status,
                    'selfDeclaredMadeForKids': task.made_for_kids,
                }
            }

            # 创建媒体上传对象（使用 2MB chunk size 以便更频繁地显示进度）
            media = MediaFileUpload(
                str(task.video_path),
                chunksize=2 * 1024 * 1024,  # 2MB chunks - 更频繁的进度更新
                resumable=True,
                mimetype='video/*'
            )

            # 插入视频
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            # 执行上传并跟踪进度
            response = None
            error = None
            retry = 0
            last_progress = -1
            
            # 获取文件大小用于显示
            import os
            file_size_mb = os.path.getsize(task.video_path) / (1024 * 1024)
            self._log(f"📤 开始上传 {file_size_mb:.1f} MB 文件...")
            
            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    
                    # 显示上传进度（每次 chunk 完成都显示）
                    if status:
                        progress = int(status.progress() * 100)
                        if progress != last_progress:
                            uploaded_mb = file_size_mb * status.progress()
                            self._log(f"📊 上传进度: {progress}% ({uploaded_mb:.1f}/{file_size_mb:.1f} MB)")
                            last_progress = progress
                    
                    if response is not None:
                        if 'id' in response:
                            video_id = response['id']
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            self._log(f"✅ 视频上传成功！")
                            self._log(f"视频 ID: {video_id}")
                            self._log(f"视频 URL: {video_url}")
                            
                            # 如果指定了播放列表，添加到播放列表
                            if task.playlist_title:
                                try:
                                    playlist_id = self.find_or_create_playlist(task.playlist_title)
                                    self.add_video_to_playlist(video_id, playlist_id)
                                    self._log(f"✅ 已将视频添加到播放列表: {task.playlist_title}")
                                except Exception as e:
                                    self._log(f"添加视频到播放列表失败: {e}", "WARNING")
                                    # 不要因为播放列表操作失败而使整个上传失败
                            
                            return True, video_url
                        else:
                            error_msg = f"上传失败: {response}"
                            self._log(error_msg, "ERROR")
                            return False, None
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        error = f"可重试的 HTTP 错误 {e.resp.status}:\n{e.content}"
                        self._log(error, "WARNING")
                        retry += 1
                        if retry > 5:  # 增加到5次重试
                            error_msg = f"上传失败，已重试 {retry} 次: {error}"
                            self._log(error_msg, "ERROR")
                            return False, None
                        self._log(f"等待 5 秒后重试 (第 {retry} 次)...")
                        import time
                        time.sleep(5)
                    else:
                        error_msg = f"HTTP 错误 {e.resp.status}:\n{e.content}"
                        self._log(error_msg, "ERROR")
                        return False, None
                except (socket.timeout, socket.error, TimeoutError, OSError) as e:
                    # 处理网络超时和连接错误
                    error = f"网络错误: {e}"
                    self._log(error, "WARNING")
                    retry += 1
                    
                    # 检查是否是连接超时（通常意味着需要 VPN）
                    error_str = str(e).lower()
                    if "timed out" in error_str or "operation timed out" in error_str:
                        if retry == 1:
                            self._log("💡 提示: 如果持续超时，请检查：", "WARNING")
                            self._log("   1. 是否需要开启 VPN/代理访问 YouTube", "WARNING")
                            self._log("   2. 检查网络连接是否稳定", "WARNING")
                            self._log("   3. 环境变量 HTTP_PROXY/HTTPS_PROXY 是否正确设置", "WARNING")
                    
                    if retry > 10:  # 增加到 10 次重试
                        error_msg = f"上传失败，已重试 {retry} 次: {error}"
                        self._log(error_msg, "ERROR")
                        self._log("❌ 建议：请确认 VPN/代理已开启并能访问 YouTube", "ERROR")
                        return False, None
                    
                    # 指数退避：5s, 10s, 15s, 20s...
                    wait_time = min(5 * retry, 30)
                    self._log(f"⏳ 等待 {wait_time} 秒后重试 (第 {retry}/10 次)...")
                    import time
                    time.sleep(wait_time)

        except HttpError as e:
            error_msg = f"HTTP 错误 {e.resp.status}:\n{e.content}"
            self._log(error_msg, "ERROR")
            return False, None
        except Exception as e:
            error_msg = f"上传过程中出错: {e}"
            self._log(error_msg, "ERROR")
            return False, None

    def __enter__(self):
        """上下文管理器入口"""
        self.authenticate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # YouTube API 客户端不需要清理
        pass
