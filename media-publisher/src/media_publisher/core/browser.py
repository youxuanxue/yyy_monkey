"""
Playwright 浏览器会话管理

封装浏览器的启动、关闭、认证状态持久化。
支持按 user_name 隔离不同用户的认证状态。
"""

import logging
from pathlib import Path
from typing import Optional, Callable

from playwright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    Playwright,
    Browser,
)

logger = logging.getLogger(__name__)


class PlaywrightBrowser:
    """
    Playwright 浏览器会话管理

    提供通用的浏览器启动、关闭、认证状态持久化功能。
    各平台发布器通过组合本类来复用浏览器管理基础设施。

    认证文件路径规则:
        - user_name 为 None 时: ~/.media-publisher/{platform}_auth.json（向后兼容）
        - user_name 存在时:   ~/.media-publisher/{user_name}/{platform}_auth.json
    """

    def __init__(
        self,
        platform_name: str,
        user_name: Optional[str] = None,
        headless: bool = False,
        log_fn: Optional[Callable[..., None]] = None,
    ):
        """
        初始化浏览器会话

        Args:
            platform_name: 平台标识（如 "gzh", "wechat"），用于认证文件命名
            user_name: 用户名，用于隔离不同用户的认证状态
            headless: 是否使用无头模式（默认 False，显示浏览器窗口）
            log_fn: 日志函数，签名 (message: str, level: str = "INFO") -> None
        """
        self.platform_name = platform_name
        self.user_name = user_name
        self.headless = headless
        self._log_fn = log_fn
        self.auth_file_path = self._build_auth_path()

        self.has_stored_auth: bool = False  # 由 start() 设置

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def _log(self, message: str, level: str = "INFO"):
        """记录日志"""
        if self._log_fn:
            self._log_fn(message, level)
        else:
            log_method = getattr(logger, level.lower(), logger.info)
            log_method(message)

    def _build_auth_path(self) -> Path:
        """
        构建认证文件路径，按 user_name 隔离

        Returns:
            认证文件的完整路径
        """
        base = Path.home() / ".media-publisher"
        if self.user_name:
            auth_dir = base / self.user_name
        else:
            auth_dir = base
        auth_dir.mkdir(parents=True, exist_ok=True)
        return auth_dir / f"{self.platform_name}_auth.json"

    @property
    def context(self) -> Optional[BrowserContext]:
        """浏览器上下文（只读，由 start() 创建）"""
        return self._context

    def start(self):
        """
        启动 Playwright 浏览器

        1. 启动 Playwright 运行时
        2. 启动 Chromium 浏览器
        3. 创建浏览器上下文（如有认证文件则加载）
        4. 创建初始页面
        """
        self._log("正在启动浏览器...")
        self._playwright = sync_playwright().start()

        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--start-maximized"],
        )

        # 加载认证状态
        if self.auth_file_path.exists():
            self.has_stored_auth = True
            self._log(f"加载登录状态: {self.auth_file_path}")
            self._context = self._browser.new_context(
                storage_state=str(self.auth_file_path),
                no_viewport=True,
            )
        else:
            self.has_stored_auth = False
            self._log("未找到登录状态，需要扫码登录")
            self._context = self._browser.new_context(no_viewport=True)

        self.page = self._context.new_page()

    def close(self):
        """
        关闭浏览器

        1. 保存认证状态
        2. 关闭上下文
        3. 关闭浏览器
        4. 停止 Playwright 运行时
        """
        if self._context:
            try:
                self.save_auth_state()
            except Exception as e:
                self._log(f"保存登录状态失败: {e}", "WARNING")
            self._context.close()

        if self._browser:
            self._browser.close()

        if self._playwright:
            self._playwright.stop()

        self._log("浏览器已关闭")

    def save_auth_state(self):
        """保存浏览器认证状态到文件"""
        if self._context:
            self._context.storage_state(path=str(self.auth_file_path))
            self._log(f"登录状态已保存: {self.auth_file_path}")

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
