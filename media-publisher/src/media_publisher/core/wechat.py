"""
微信视频号发布核心模块

基于 Playwright 自动化发布视频到微信视频号。
支持单条发布和批量发布（存草稿模式）。
"""

import logging
import re
import time
from pathlib import Path
from typing import Optional, Callable, List, Tuple

from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright

from .base import Publisher, WeChatPublishTask
from media_publisher.shared.io import atomic_write_json
from media_publisher.shared.security import sanitize_identifier

# Configure logging
logger = logging.getLogger(__name__)


def get_auth_file_path(account: Optional[str] = None) -> Path:
    """
    获取认证文件路径（存储在用户主目录）
    
    Args:
        account: 账号名称。指定后认证文件按账号隔离，如 wechat_auth_奶奶讲故事.json
    """
    auth_dir = Path.home() / ".media-publisher"
    auth_dir.mkdir(parents=True, exist_ok=True)
    safe_account = sanitize_identifier(account, field_name="account")
    if safe_account:
        return auth_dir / f"wechat_auth_{safe_account}.json"
    return auth_dir / "wechat_auth.json"


class WeChatPublisher(Publisher):
    """
    微信视频号自动发布器
    
    使用 Playwright 自动化浏览器操作，完成视频上传和发布。
    """
    
    BASE_URL = "https://channels.weixin.qq.com"
    CREATOR_URL = "https://channels.weixin.qq.com/platform/post/create"
    DRAFT_LIST_URL = "https://channels.weixin.qq.com/platform/post/draftListManager"

    def __init__(
        self, 
        headless: bool = False, 
        debug: bool = False,
        log_callback: Optional[Callable[[str], None]] = None,
        account: Optional[str] = None
    ):
        """
        初始化发布器
        
        Args:
            headless: 是否使用无头模式（默认 False，显示浏览器窗口）
            debug: 是否生成调试文件（截图、HTML）
            log_callback: 日志回调函数，用于在 GUI 中显示日志
            account: 视频号账号名称，用于区分多账号登录状态
        """
        super().__init__(log_callback)
        self.headless = headless
        self.debug = debug
        self.account = account
        self.auth_file_path = get_auth_file_path(account)
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
            state = self._context.storage_state()
            atomic_write_json(self.auth_file_path, state)
            self._log(f"登录状态已保存: {self.auth_file_path}")

    def _check_need_login(self) -> bool:
        """
        导航到需要登录才能访问的页面，判断是否真的需要登录。
        仅用 URL 判断（登录页 URL 一定包含 login），不看页面文案，避免误判营销页。
        返回 True 表示需要登录，False 表示已登录。
        """
        if not self._page:
            return False
        self._page.goto(self.CREATOR_URL, timeout=60000)
        self._page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        return "login" in self._page.url

    def _current_url(self) -> str:
        """用 JS 读取当前 URL，比 page.url 更即时，能反映导航后的实际地址。"""
        try:
            return self._page.evaluate("window.location.href") or ""
        except Exception:
            return self._page.url or ""

    def _wait_for_login_done(self, timeout: int = 120) -> bool:
        """
        等待用户扫码登录完成。
        用 JS evaluate 轮询 window.location.href（比 page.url / wait_for_url 更可靠）：
        一旦 URL 在 channels.weixin.qq.com 且不含 login 即视为成功。
        每隔 2 秒打印一次当前 URL，方便排查。
        """
        self._log("请在浏览器中扫码登录（完成后会自动继续，最多等待 %d 秒）..." % timeout)
        start = time.time()
        last_log = 0
        while time.time() - start < timeout:
            cur = self._current_url()
            if "channels.weixin.qq.com" in cur and "login" not in cur:
                self._log(f"已离开登录页，当前: {cur}")
                return True
            # 每 10 秒打印一次当前 URL，帮助排查
            if time.time() - last_log >= 10:
                self._log(f"等待扫码中... 当前URL: {cur}")
                last_log = time.time()
            time.sleep(2)
        self._log(f"等待超时，当前URL: {self._current_url()}", "WARNING")
        return False

    def authenticate(self, timeout: int = 120):
        """
        检查登录状态，未登录则等待扫码。
        导航到创建页（需要登录），通过 URL 是否含 login 判断是否需要扫码，避免误判首页。
        """
        if not self._page:
            self.start()

        account_label = f" [{self.account}]" if self.account else ""
        self._log(f"正在打开微信视频号{account_label}...")
        if self._check_need_login():
            if not self._wait_for_login_done(timeout=timeout):
                self._log("等待登录超时", "WARNING")
            else:
                self._log(f"登录成功！当前页面: {self._page.url}")
                self._save_auth_state()
        else:
            self._log("已登录")

    def publish(self, task: WeChatPublishTask) -> Tuple[bool, Optional[str]]:
        """
        执行视频发布流程（保存到草稿箱）
        
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
            self._page.wait_for_selector('input[type="file"]', state="attached", timeout=60000)
            self._page.set_input_files('input[type="file"]', str(task.video_path), timeout=60000)

            # 等待视频上传完成（未完成则不再点击存草稿，直接返回失败）
            if not self._wait_for_upload_complete():
                return False, "视频上传超时，请检查网络后重试"

            # 2. 填写描述（上传完成后描述框已经可见，直接操作）
            self._log("正在填写描述...")
            try:
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

            # 7. 等待后保存草稿
            self._log("等待 10 秒后保存草稿...")
            time.sleep(10)
            return self._save_draft()
            
        except Exception as e:
            error_msg = f"发布过程中出错: {e}"
            self._log(error_msg, "ERROR")
            return False, error_msg

    def publish_batch(self, tasks: List[WeChatPublishTask]) -> List[Tuple[bool, Optional[str]]]:
        """
        批量发布视频到草稿箱（共享同一个浏览器会话）
        
        Args:
            tasks: 微信视频号发布任务列表
            
        Returns:
            每个任务的 (success, message) 列表
        """
        results = []
        total = len(tasks)
        
        for i, task in enumerate(tasks, 1):
            self._log(f"\n{'='*40}")
            self._log(f"批量发布进度: [{i}/{total}] {task.video_path.name}")
            self._log(f"{'='*40}")
            
            success, msg = self.publish(task)
            results.append((success, msg))
            
            if success:
                self._log(f"[{i}/{total}] 已保存草稿: {task.title}")
            else:
                self._log(f"[{i}/{total}] 失败: {msg}", "ERROR")
            
            if i < total:
                self._log("等待 3 秒后继续下一个...")
                time.sleep(3)
        
        return results

    # 草稿箱宿主页（platform 路径是真正触发 get_draft_list API 的页面；
    # micro/content 路径是 platform 内部嵌入的子页面，直接导航不会发出 API 请求）
    DRAFT_API_HOST_PAGE = (
        "https://channels.weixin.qq.com/platform/post/draftListManager"
    )

    def get_draft_page_text(self, login_timeout: int = 120) -> str:
        """
        打开草稿箱页面，拦截 get_draft_list API 响应获取草稿数据。

        注意：微信视频号草稿箱是 iframe 嵌套结构，platform 页面内嵌一个
        micro/content iframe。必须在 browser context 级别监听才能捕获
        iframe 发出的 API 请求（page 级别只能看到主框架请求）。
        """
        if not self._page or not self._context:
            self._log("浏览器未启动", "ERROR")
            return ""

        all_drafts: list = []
        total_count_holder = [0]

        def _on_response(response):
            """在 context 级别监听所有响应（含 iframe）。"""
            if "get_draft_list" not in response.url:
                return
            try:
                body = response.json()
            except Exception:
                return
            if body.get("errCode") != 0:
                self._log(
                    f"  [API] 错误码 {body.get('errCode')} "
                    f"{body.get('errMsg', '')}",
                    "WARNING",
                )
                return
            data = body.get("data", {})
            items = data.get("list", [])
            tc = data.get("totalCount", 0)
            all_drafts.extend(items)
            if tc > 0:
                total_count_holder[0] = tc
            self._log(
                f"  [API] +{len(items)} 条，累计 {len(all_drafts)}"
                + (f"/{tc}" if tc else "")
            )

        # 在 context 级别监听，覆盖主页面和所有 iframe
        self._context.on("response", _on_response)
        try:
            self._log("正在打开草稿箱页面...")
            self._page.goto(self.DRAFT_API_HOST_PAGE, timeout=60000)
            self._page.wait_for_load_state("domcontentloaded")
            time.sleep(4)

            cur = self._current_url()
            if "login" in cur:
                if not self._wait_for_login_done(timeout=login_timeout):
                    self._log("等待登录超时", "ERROR")
                    return ""
                # auth 完成后页面已自动导航回目标页，无需第二次 goto；
                # 等待 micro/content iframe 加载并发出首次 get_draft_list
                self._log("登录成功，等待草稿箱加载...")
                time.sleep(6)
                if "login" in self._current_url():
                    self._log("登录后仍为登录页", "ERROR")
                    return ""

            # 等待首次 API 数据（iframe 加载比主页面晚）
            for _ in range(15):
                if all_drafts:
                    break
                time.sleep(1)

            if not all_drafts:
                # 尝试刷新一次，有时 SPA 路由切换不会重发 API
                self._log("首次加载未拦截到 API，尝试刷新...")
                self._page.reload(timeout=60000)
                self._page.wait_for_load_state("domcontentloaded")
                time.sleep(5)
                for _ in range(15):
                    if all_drafts:
                        break
                    time.sleep(1)

            # 滚动触发分页（无限滚动，每页 20 条）
            # 微信草稿箱是 iframe 嵌套结构，直接用 Playwright frame API 在 iframe 内滚动
            def _scroll_draft_list():
                # 优先在 micro/content iframe 内滚动（用 Playwright frame API，避免跨框架脚本限制）
                for frame in self._page.frames:
                    if "micro/content" in frame.url and "draftListManager" in frame.url:
                        try:
                            frame.evaluate(
                                "window.scrollTo(0, document.body.scrollHeight)"
                            )
                            return
                        except Exception:
                            pass
                # fallback: 滚动主页面
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            prev_count = -1
            stable_rounds = 0
            for _ in range(40):
                tc = total_count_holder[0]
                cur_count = len(all_drafts)
                if tc > 0 and cur_count >= tc:
                    self._log(f"已加载全部 {cur_count}/{tc} 条草稿")
                    break
                _scroll_draft_list()
                time.sleep(2)
                # 重新读取（page.evaluate 中已派发 Playwright 事件）
                cur_count = len(all_drafts)
                if cur_count == prev_count:
                    stable_rounds += 1
                    if stable_rounds >= 4:
                        self._log(f"无新数据，停止滚动。已获取 {cur_count} 条草稿")
                        break
                else:
                    stable_rounds = 0
                prev_count = cur_count

        finally:
            self._context.remove_listener("response", _on_response)

        if not all_drafts:
            self._log("草稿列表为空（可能 API 未被拦截到）", "WARNING")
            return ""

        # 提取标题和描述文本用于匹配
        lines = []
        for d in all_drafts:
            desc_obj = d.get("desc", {})
            short_title_list = desc_obj.get("shortTitle", [])
            short_title = (
                short_title_list[0].get("shortTitle", "")
                if short_title_list else ""
            )
            description = desc_obj.get("description", "")
            if short_title:
                lines.append(short_title)
            if description:
                lines.append(description)

        full_text = "\n".join(lines)
        self._log(
            f"草稿箱共 {len(all_drafts)} 条草稿，"
            f"提取标题/描述文本 {len(full_text)} 字符"
        )
        return full_text

    def _wait_for_upload_complete(self, timeout: int = 600) -> bool:
        """
        等待视频上传完成。

        最可靠的完成信号：微信视频号页面在视频上传完成后才会显示
        描述编辑区（div.input-editor）——用它作为主要判断依据。
        辅助检测进度百分比和其他完成标志。

        Args:
            timeout: 最大等待时间（秒，默认 10 分钟）

        Returns:
            True 表示上传已完成，False 表示超时
        """
        self._log("等待视频上传完成（最长等待 10 分钟）...")
        start = time.time()
        last_logged_pct = ""

        while time.time() - start < timeout:
            elapsed = int(time.time() - start)

            # ── 主要信号：描述编辑框出现 ──────────────────────────────
            # 这是最可靠的信号：微信视频号只有在视频处理完成后才展示编辑区
            try:
                editor = self._page.locator(
                    'div.input-editor, div[data-placeholder="添加描述"]'
                ).first
                if editor.is_visible(timeout=1000):
                    self._log(f"视频上传完成（{elapsed}s）")
                    time.sleep(1)
                    return True
            except Exception:
                pass

            # ── 辅助信号：进度百分比 ──────────────────────────────────
            try:
                # 取所有可能带百分比文字的元素
                all_els = self._page.locator(
                    '.upload-progress, .progress-text, '
                    '.weui-desktop-upload__progress, '
                    '[class*="progress"]'
                ).all()
                for el in all_els:
                    try:
                        text = el.text_content() or ""
                    except Exception:
                        continue
                    pct_match = re.search(r'(\d+)%', text)
                    if not pct_match:
                        continue
                    pct_str = pct_match.group(0)
                    pct_val = int(pct_match.group(1))
                    if pct_str != last_logged_pct:
                        self._log(f"上传进度: {pct_str}（{elapsed}s）")
                        last_logged_pct = pct_str
                    if pct_val >= 100:
                        # 100% 后再额外等 3s 让页面渲染编辑区
                        time.sleep(3)
                        self._log(f"视频上传完成（{elapsed}s）")
                        return True
            except Exception:
                pass

            # ── 辅助信号：其他完成标志 ───────────────────────────────
            try:
                done_indicators = [
                    'text=重新上传',
                    '.finder-tag-wrap',
                    '.video-thumb',
                    '.upload-success',
                    '.media-cover',
                ]
                for selector in done_indicators:
                    try:
                        if self._page.locator(selector).first.is_visible(timeout=300):
                            self._log(f"视频上传完成（检测到 {selector}，{elapsed}s）")
                            time.sleep(2)
                            return True
                    except Exception:
                        pass
            except Exception:
                pass

            # 每 30 秒汇报一次等待进度
            if elapsed > 0 and elapsed % 30 == 0 and last_logged_pct == "":
                self._log(f"仍在等待上传... 已等待 {elapsed}s")

            time.sleep(3)

        self._log(
            f"上传等待超时（{timeout}s），为避免保存空草稿，本任务标记为失败",
            "WARNING",
        )
        return False

    def _save_draft(self) -> Tuple[bool, Optional[str]]:
        """点击存草稿按钮"""
        self._log("正在保存草稿...")
        
        draft_selectors = [
            'button:has-text("存草稿")',
            'text=存草稿',
            '.weui-desktop-btn:has-text("存草稿")',
            '.btn-draft',
        ]
        
        for selector in draft_selectors:
            try:
                btn = self._page.locator(selector).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    time.sleep(3)
                    
                    # 检查是否保存成功（页面跳转或出现成功提示）
                    try:
                        success_indicators = [
                            'text=草稿保存成功',
                            'text=保存成功',
                            '.weui-desktop-toast',
                        ]
                        for ind in success_indicators:
                            if self._page.locator(ind).first.is_visible(timeout=3000):
                                self._log("草稿保存成功")
                                return True, "草稿保存成功"
                    except Exception:
                        pass
                    
                    # 如果页面 URL 变了（跳转到草稿列表），也视为成功
                    if self._page.url != self.CREATOR_URL:
                        self._log("草稿保存成功")
                        return True, "草稿保存成功"
                    
                    self._log("草稿已保存（未检测到明确的成功提示）")
                    return True, "草稿已保存"
            except Exception:
                continue
        
        self._log("未找到存草稿按钮，请手动保存", "WARNING")
        return False, "未找到存草稿按钮"

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
        """勾选原创并确认弹窗"""
        self._log("正在勾选原创...")
        try:
            # 第一步：点击"原创"入口
            original_selectors = [
                'text=原创',
                'label:has-text("原创") input[type="checkbox"]',
                '.weui-desktop-checkbox:has-text("原创")',
            ]
            
            clicked = False
            for selector in original_selectors:
                try:
                    checkbox = self._page.locator(selector).first
                    if checkbox.is_visible(timeout=2000):
                        checkbox.click()
                        clicked = True
                        break
                except Exception:
                    continue
            
            if not clicked:
                self._log("未能自动勾选原创，请手动勾选", "WARNING")
                return
            
            time.sleep(1)
            
            # 第二步：处理"原创权益"确认弹窗
            # 勾选"我已阅读并同意"checkbox
            agree_selectors = [
                'text=我已阅读并同意',
                'label:has-text("我已阅读并同意")',
                '.weui-desktop-dialog input[type="checkbox"]',
                '.dialog-wrp input[type="checkbox"]',
            ]
            for selector in agree_selectors:
                try:
                    agree = self._page.locator(selector).first
                    if agree.is_visible(timeout=2000):
                        agree.click()
                        self._log("已勾选同意原创声明")
                        break
                except Exception:
                    continue
            
            time.sleep(0.5)
            
            # 点击"声明原创"按钮
            confirm_selectors = [
                'button:has-text("声明原创")',
                'text=声明原创',
                '.weui-desktop-btn_primary:has-text("声明原创")',
            ]
            for selector in confirm_selectors:
                try:
                    btn = self._page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        self._log("已确认声明原创")
                        time.sleep(1)
                        return
                except Exception:
                    continue
            
            self._log("已勾选原创（未检测到确认弹窗）")
        except Exception as e:
            self._log(f"勾选原创失败: {e}", "WARNING")

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
