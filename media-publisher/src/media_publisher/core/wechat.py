"""
微信视频号发布核心模块

基于 Playwright 自动化发布视频到微信视频号。
"""

import logging
import time
from pathlib import Path
from typing import Optional, Callable, Tuple

from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright

from .base import Publisher, WeChatPublishTask

# Configure logging
logger = logging.getLogger(__name__)


def get_auth_file_path() -> Path:
    """获取认证文件路径（存储在用户主目录）"""
    auth_dir = Path.home() / ".media-publisher"
    auth_dir.mkdir(parents=True, exist_ok=True)
    return auth_dir / "wechat_auth.json"


class WeChatPublisher(Publisher):
    """
    微信视频号自动发布器
    
    使用 Playwright 自动化浏览器操作，完成视频上传和发布。
    """
    
    BASE_URL = "https://channels.weixin.qq.com"
    CREATOR_URL = "https://channels.weixin.qq.com/platform/post/create"

    def __init__(
        self, 
        headless: bool = False, 
        debug: bool = False,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        初始化发布器
        
        Args:
            headless: 是否使用无头模式（默认 False，显示浏览器窗口）
            debug: 是否生成调试文件（截图、HTML）
            log_callback: 日志回调函数，用于在 GUI 中显示日志
        """
        super().__init__(log_callback)
        self.headless = headless
        self.debug = debug
        self.auth_file_path = get_auth_file_path()
        self._playwright: Optional[Playwright] = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start(self):
        """启动 Playwright 浏览器"""
        self._log("正在启动浏览器...")
        self._playwright = sync_playwright().start()
        
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--start-maximized"]
        )
        
        # 加载认证状态
        if self.auth_file_path.exists():
            self._log(f"加载登录状态: {self.auth_file_path}")
            self._context = self._browser.new_context(
                storage_state=str(self.auth_file_path),
                no_viewport=True
            )
        else:
            self._log("未找到登录状态，需要扫码登录")
            self._context = self._browser.new_context(no_viewport=True)

        self._page = self._context.new_page()

    def close(self):
        """关闭浏览器"""
        if self._context:
            try:
                self._save_auth_state()
            except Exception as e:
                self._log(f"保存登录状态失败: {e}", "WARNING")
            self._context.close()
        
        if self._browser:
            self._browser.close()
        
        if self._playwright:
            self._playwright.stop()
        
        self._log("浏览器已关闭")

    def _save_auth_state(self):
        """保存浏览器登录状态"""
        if self._context:
            self._context.storage_state(path=str(self.auth_file_path))
            self._log(f"登录状态已保存: {self.auth_file_path}")

    def authenticate(self, timeout: int = 120):
        """
        检查登录状态，未登录则等待扫码
        
        Args:
            timeout: 等待登录超时时间（秒）
        """
        if not self._page:
            # 如果浏览器未启动，先启动
            self.start()

        self._log("正在打开微信视频号...")
        self._page.goto(self.BASE_URL, timeout=60000)
        self._page.wait_for_load_state("domcontentloaded")
        
        if "login" in self._page.url:
            self._log("请在浏览器中扫码登录...")
            self._page.wait_for_url(
                lambda url: "login" not in url, 
                timeout=timeout * 1000
            )
            self._log("登录成功！")
            self._page.wait_for_load_state("domcontentloaded")
            self._save_auth_state()
        else:
            self._log("已登录")

    def publish(self, task: WeChatPublishTask) -> Tuple[bool, Optional[str]]:
        """
        执行视频发布流程
        
        Args:
            task: 微信视频号发布任务
            
        Returns:
            (success, message) - 成功状态和消息
        """
        try:
            task.validate()
        except Exception as e:
            self._log(f"任务验证失败: {e}", "ERROR")
            return False, str(e)
        
        if not self._page:
            self._log("浏览器未启动", "ERROR")
            return False, "浏览器未启动"

        try:
            self._log("正在打开发布页面...")
            self._page.goto(self.CREATOR_URL, timeout=60000)
            self._page.wait_for_load_state("domcontentloaded")
            
            if self.debug:
                self._page.screenshot(path="debug_create_page.png")

            if "login" in self._page.url:
                error_msg = "登录已过期，请重新登录"
                self._log(error_msg, "ERROR")
                return False, error_msg

            # 1. 上传视频
            self._log(f"正在上传视频: {task.video_path.name}")
            # 先等待文件输入元素出现
            self._page.wait_for_selector('input[type="file"]', state="attached", timeout=60000)
            self._page.set_input_files('input[type="file"]', str(task.video_path), timeout=60000)

            # 等待上传开始
            self._log("等待视频上传...")
            time.sleep(10)

            # 2. 填写描述
            self._log("正在填写描述...")
            try:
                self._page.wait_for_selector(
                    'div.input-editor, div[data-placeholder="添加描述"]', 
                    state="visible", 
                    timeout=300000
                )
                
                editor = self._page.locator('div.input-editor, div[data-placeholder="添加描述"]').first
                editor.click()
                editor.type(task.get_full_description())
                self._log("描述已填写")
            except Exception as e:
                self._log(f"填写描述失败: {e}", "WARNING")

            # 3. 填写标题
            if task.title:
                self._log(f"正在填写标题: {task.title}")
                try:
                    title_input = self._page.locator('input.weui-desktop-form__input[placeholder*="概括视频主要内容"]')
                    if title_input.is_visible():
                        title_input.fill(task.title)
                        self._log("标题已填写")
                except Exception as e:
                    self._log(f"填写标题失败: {e}", "WARNING")

            # 4. 选择合集（如果指定）
            if task.heji:
                self._select_heji(task.heji)

            # 5. 参加活动（如果指定）
            if task.huodong:
                self._join_huodong(task.huodong)

            # 6. 勾选原创
            self._check_original()

            self._log("发布准备完成，请在浏览器中确认并点击发布按钮")
            
            if not self.headless:
                time.sleep(5)
            
            return True, "发布准备完成"
            
        except Exception as e:
            error_msg = f"发布过程中出错: {e}"
            self._log(error_msg, "ERROR")
            return False, error_msg

    def _select_heji(self, heji_name: str):
        """选择合集"""
        self._log(f"正在选择合集: {heji_name}")
        try:
            collection_selectors = [
                'text=选择合集',
                'text=合集',
                'button:has-text("合集")',
                '.collection-selector',
            ]
            
            for selector in collection_selectors:
                try:
                    btn = self._page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        time.sleep(1)
                        
                        # 查找合集
                        item = self._page.locator(f'text={heji_name}').first
                        if item.is_visible(timeout=3000):
                            item.click()
                            self._log(f"已选择合集: {heji_name}")
                            time.sleep(0.5)
                            return
                except Exception:
                    continue
            
            self._log("未能自动选择合集，请手动选择", "WARNING")
        except Exception as e:
            self._log(f"选择合集失败: {e}", "WARNING")

    def _join_huodong(self, huodong_name: str):
        """参加活动"""
        self._log(f"正在参加活动: {huodong_name}")
        try:
            # 点击活动显示区域
            activity_display_selectors = [
                '.activity-display',
                '.not-involve',
                'text=不参与活动',
            ]
            
            for selector in activity_display_selectors:
                try:
                    display = self._page.locator(selector).first
                    if display.is_visible(timeout=3000):
                        current_url = self._page.url
                        display.click()
                        time.sleep(2)
                        
                        # 检查是否跳转
                        if self._page.url != current_url:
                            self._page.goto(self.CREATOR_URL, timeout=60000)
                            self._page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                            continue
                        
                        break
                except Exception:
                    continue

            # 搜索活动
            search_selectors = [
                'input[placeholder="搜索活动"]',
                '.activity-filter-wrap input[placeholder*="搜索"]',
            ]
            
            for selector in search_selectors:
                try:
                    search_input = self._page.locator(selector).first
                    if search_input.is_visible(timeout=3000):
                        search_input.click()
                        search_input.fill(huodong_name)
                        time.sleep(1)
                        break
                except Exception:
                    continue

            # 点击活动
            time.sleep(2)
            activity_selectors = [
                f'.activity-item:has-text("{huodong_name}")',
                f'.option-item:has-text("{huodong_name}")',
                f'text={huodong_name}',
            ]
            
            for selector in activity_selectors:
                try:
                    items = self._page.locator(selector).all()
                    for item in items:
                        if item.is_visible(timeout=2000):
                            text = item.text_content() or ""
                            if huodong_name in text:
                                item.click()
                                self._log(f"已参加活动: {huodong_name}")
                                time.sleep(2)
                                return
                except Exception:
                    continue
            
            self._log("未能自动参加活动，请手动选择", "WARNING")
        except Exception as e:
            self._log(f"参加活动失败: {e}", "WARNING")

    def _check_original(self):
        """勾选原创"""
        self._log("正在勾选原创...")
        try:
            original_selectors = [
                'text=原创',
                'label:has-text("原创") input[type="checkbox"]',
                '.weui-desktop-checkbox:has-text("原创")',
            ]
            
            for selector in original_selectors:
                try:
                    checkbox = self._page.locator(selector).first
                    if checkbox.is_visible(timeout=2000):
                        checkbox.click()
                        self._log("已勾选原创")
                        return
                except Exception:
                    continue
            
            self._log("未能自动勾选原创，请手动勾选", "WARNING")
        except Exception as e:
            self._log(f"勾选原创失败: {e}", "WARNING")

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
