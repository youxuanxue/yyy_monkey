"""
微信公众号视频素材独立上传模块

通过直接访问视频素材管理页面，上传视频并填写元数据。
与文章发布流程解耦，可独立运行。
"""

import logging
import random
import re
import time
from pathlib import Path
from typing import Optional, Callable

from playwright.sync_api import Page

from .browser import PlaywrightBrowser
from .gzh import authenticate_gzh

logger = logging.getLogger(__name__)


class GzhVideoUploader:
    """
    微信公众号视频素材独立上传器

    直接操作视频素材管理页面完成上传，不依赖文章编辑器。
    浏览器管理委托给 PlaywrightBrowser。
    """

    BASE_URL = "https://mp.weixin.qq.com"

    def __init__(
        self,
        user_name: Optional[str] = None,
        headless: bool = False,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化上传器

        Args:
            user_name: 用户名，用于隔离认证状态
            headless: 是否使用无头模式
            log_callback: 日志回调函数
        """
        self.log_callback = log_callback
        self._session = PlaywrightBrowser(
            "gzh", user_name, headless, self._log
        )

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _log(self, message: str, level: str = "INFO"):
        """记录日志"""
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message)
        if self.log_callback:
            self.log_callback(f"[{level}] {message}")

    # ------------------------------------------------------------------
    # 浏览器管理委托
    # ------------------------------------------------------------------

    @property
    def _page(self) -> Optional[Page]:
        return self._session.page

    @_page.setter
    def _page(self, value: Optional[Page]):
        self._session.page = value

    @property
    def _context(self):
        return self._session.context

    def start(self):
        """启动浏览器"""
        self._session.start()

    def close(self):
        """关闭浏览器"""
        self._session.close()

    def _save_auth_state(self):
        """保存认证状态"""
        self._session.save_auth_state()

    # ------------------------------------------------------------------
    # 认证（复用 GZH 认证逻辑）
    # ------------------------------------------------------------------

    def authenticate(self, timeout: int = 120):
        """
        检查登录状态，未登录则等待扫码

        Args:
            timeout: 等待扫码超时（秒）
        """
        if not self._page:
            self.start()

        authenticate_gzh(
            page=self._page,
            base_url=self.BASE_URL,
            log_fn=self._log,
            save_fn=self._save_auth_state,
            timeout=timeout,
            has_stored_auth=self._session.has_stored_auth,
        )

    # ------------------------------------------------------------------
    # Token 提取
    # ------------------------------------------------------------------

    def _extract_token(self) -> str:
        """
        从当前页面提取 session token

        认证完成后，页面 URL 或页面内链接中包含 token=xxx 参数。

        Returns:
            token 字符串

        Raises:
            RuntimeError: 无法提取 token
        """
        # 方式 1：从当前 URL 提取
        url = self._page.url
        match = re.search(r'token=(\d+)', url)
        if match:
            return match.group(1)

        # 方式 2：从页面中的链接提取
        token = self._page.evaluate(
            """() => {
                // 尝试从页面链接中提取 token
                const links = document.querySelectorAll('a[href*="token="]');
                for (const link of links) {
                    const match = link.href.match(/token=(\\d+)/);
                    if (match) return match[1];
                }
                // 尝试从 window.wx.commonData.token 提取
                try {
                    if (window.wx && window.wx.commonData && window.wx.commonData.token) {
                        return String(window.wx.commonData.token);
                    }
                } catch(e) {}
                return null;
            }"""
        )
        if token:
            return token

        raise RuntimeError(
            "无法提取 session token，请确认已成功登录"
        )

    # ------------------------------------------------------------------
    # 视频上传
    # ------------------------------------------------------------------

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str = "",
        cover_dir: Optional[Path] = None,
    ):
        """
        上传视频到公众号视频素材库

        流程：
        1. 提取 token，导航到视频素材列表页
        2. 点击「添加」按钮（打开新 tab）
        3. 在新 tab 中上传视频文件
        4. 填写标题和描述
        5. 勾选服务协议、选择封面
        6. 保存并关闭 tab

        Args:
            video_path: 本地视频文件路径
            title: 视频标题
            description: 视频描述（可选）
            cover_dir: 封面图片目录（可选），从中随机选取一张 PNG 作为封面
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        self._log(f"准备上传视频: {video_path.name}")
        self._log(f"视频标题: {title}")

        # 1. 提取 token 并导航到视频素材列表页
        try:
            token = self._extract_token()
        except RuntimeError:
            self._log(
                "token 提取失败，尝试重新认证...", "WARNING"
            )
            self.authenticate()
            token = self._extract_token()
        self._log(f"已提取 token: {token}")

        video_list_url = (
            f"{self.BASE_URL}/cgi-bin/appmsg?"
            f"begin=0&count=10&action=list_video&type=15"
            f"&token={token}&lang=zh_CN"
        )
        self._page.goto(video_list_url, timeout=60000)
        self._page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        self._log("已打开视频素材列表页")

        # 2. 点击「添加」按钮（打开新 tab）
        with self._context.expect_page(timeout=15000) as new_page_info:
            add_btn = self._page.locator(
                'button.weui-desktop-btn_primary:has-text("添加")'
            )
            add_btn.click()

        video_page = new_page_info.value
        video_page.wait_for_load_state("domcontentloaded")
        self._log("已打开视频编辑页面")
        time.sleep(2)

        try:
            # 3. 上传视频文件
            self._upload_file(video_page, video_path)

            # 4. 填写标题和描述
            self._fill_video_info(video_page, title, description)

            # 5. 勾选服务协议
            self._check_agreement(video_page)

            # 6. 选择封面（含封面处理等待）
            self._select_cover(video_page, cover_dir=cover_dir)

            # 7. 勾选原创声明
            self._enable_original_declaration(video_page)

            # 8. 点击保存并等待保存完成
            self._click_save_and_wait(video_page)

            # 9. 保存成功后关闭视频编辑 tab
            if not video_page.is_closed():
                video_page.close()
                self._log("已关闭视频编辑页面")

        except Exception as e:
            self._log(f"视频上传过程中出错: {e}", "ERROR")
            # 出错时不自动关闭 tab，方便用户查看问题
            raise

        self._log(f"视频上传完成: {title}")

    def _upload_file(self, video_page: Page, video_path: Path):
        """上传视频文件并等待上传真正完成（通过进度元素检测）"""
        file_input = video_page.locator(
            'input[name="vid"][type="file"]'
        )
        file_input.set_input_files(str(video_path))
        self._log("视频文件已选择，等待上传...")

        # ----------------------------------------------------------
        # 轮询检测上传进度，最多等待 10 分钟
        # 页面上传时会显示 "已上传:XX%" 文本；上传完成后该文本消失
        # ----------------------------------------------------------
        max_wait = 600  # 秒
        poll_interval = 3  # 秒
        waited = 0
        last_pct = -1

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            # 尝试从页面中读取上传进度
            pct = video_page.evaluate(
                """() => {
                    // 查找包含 "已上传" 的文本节点
                    const el = document.querySelector('.upload_progress_tips')
                        || document.querySelector('.upload_file_info')
                        || document.body;
                    const text = el.innerText || '';
                    const m = text.match(/已上传[：:]\\s*(\\d+)[\\d.]*%/);
                    if (m) return parseInt(m[1], 10);
                    // 如果完全找不到"已上传"文本，说明上传已完成或还未开始
                    if (text.includes('已上传')) return 0;
                    return -1;  // 无进度信息
                }"""
            )

            if pct == -1:
                # 页面上没有 "已上传" 文本
                # 可能上传已完成（进度条消失）或还未开始
                has_progress = video_page.evaluate(
                    """() => {
                        const text = document.body.innerText || '';
                        return text.includes('剩余时间') || text.includes('上传中');
                    }"""
                )
                if not has_progress:
                    self._log("上传进度元素已消失，视频上传完成")
                    break
                # 还有进度信息但没匹配到百分比，继续等
            elif pct >= 100:
                self._log("已上传:100%，视频上传完成")
                break
            else:
                if pct != last_pct:
                    self._log(f"上传进度: 已上传:{pct}%")
                    last_pct = pct

            if waited % 30 == 0 and pct >= 0:
                self._log(
                    f"等待上传中... {pct}% ({waited}s/{max_wait}s)"
                )
        else:
            self._log(
                f"视频上传等待超时（{max_wait}秒），尝试继续...",
                "WARNING",
            )

        time.sleep(2)

    @staticmethod
    def _clean_title(title: str) -> str:
        """
        清理视频标题，去除公众号平台不允许的特殊字符

        公众号视频素材标题不允许 emoji 和特殊符号，
        只保留中文、英文、数字、常规标点。
        """
        # 去除 emoji 和其他特殊 Unicode 字符
        cleaned = re.sub(
            r'[\U00010000-\U0010ffff]'   # Supplementary planes (emoji等)
            r'|[\u2600-\u27BF]'           # Misc symbols
            r'|[\uFE00-\uFE0F]'           # Variation selectors
            r'|[\u200D]'                   # Zero width joiner
            r'|[\u20E3]'                   # Combining enclosing keycap
            r'|[\uD83C-\uDBFF\uDC00-\uDFFF]',  # Surrogate pairs
            '',
            title,
        )
        # 去除首尾空白
        cleaned = cleaned.strip()
        return cleaned if cleaned else title.strip()

    def _fill_video_info(
        self, video_page: Page, title: str, description: str
    ):
        """
        填写视频标题和描述

        注意：
        - 公众号视频标题不允许 emoji 等特殊字符，填写前自动清理
        - 上传完成后页面会用文件名自动填充标题，需要先全选再覆盖
        """
        # 清理标题中的特殊字符
        clean = self._clean_title(title)
        if clean != title:
            self._log(f"标题已清理特殊字符: {title} → {clean}")
        title = clean

        # 填写标题
        title_selectors = [
            'input[name="title"]',
            'input.weui-desktop-form__input[placeholder*="标题"]',
            '.video-setting__title input',
        ]
        title_filled = False
        for sel in title_selectors:
            try:
                inp = video_page.locator(sel).first
                if inp.is_visible(timeout=3000):
                    # 全选后覆盖（处理页面自动填充了文件名的情况）
                    inp.click()
                    inp.press("Meta+a")  # macOS 全选
                    inp.fill(title)
                    # 验证填写是否成功
                    actual = inp.input_value()
                    if actual == title:
                        self._log(f"已填写标题: {title}")
                    else:
                        self._log(
                            f"标题验证不一致: 期望={title}, 实际={actual}",
                            "WARNING",
                        )
                    title_filled = True
                    break
            except Exception:
                continue

        if not title_filled:
            self._log("填写标题失败：未找到标题输入框", "WARNING")

        # 填写描述
        if description:
            try:
                desc_input = video_page.locator(
                    'textarea[placeholder*="介绍"], '
                    'textarea[placeholder*="描述"]'
                )
                if desc_input.is_visible(timeout=3000):
                    desc_input.fill(description)
                    self._log("已填写描述")
            except Exception as e:
                self._log(f"填写描述失败: {e}", "WARNING")

    def _check_agreement(self, video_page: Page):
        """勾选服务协议"""
        # 微信的自定义 checkbox 隐藏了原生 <input>，需要点击旁边的 <i> 图标
        try:
            # 方式 1：点击 <i> 图标
            agreement_icon = video_page.locator(
                '.video-setting__footer-link i.weui-desktop-icon-checkbox'
            )
            if agreement_icon.is_visible(timeout=3000):
                agreement_icon.click()
                self._log("已勾选服务协议")
                time.sleep(0.5)
                return
        except Exception:
            pass

        try:
            # 方式 2：强制点击隐藏的 <input>
            agreement_input = video_page.locator(
                '.video-setting__footer-link input[type="checkbox"]'
            )
            agreement_input.check(force=True)
            self._log("已勾选服务协议（force）")
            time.sleep(0.5)
            return
        except Exception:
            pass

        try:
            # 方式 3：点击整个 <label> 元素
            agreement_label = video_page.locator(
                'label.video-setting__footer-link'
            )
            if agreement_label.is_visible(timeout=2000):
                agreement_label.click()
                self._log("已勾选服务协议（label）")
                time.sleep(0.5)
                return
        except Exception:
            pass

        self._log("未能勾选服务协议，继续尝试保存...", "WARNING")

    def _enable_original_declaration(self, video_page: Page):
        """
        勾选「原创声明」开关

        页面上是一个 weui-desktop-switch 切换控件，
        点击后会变为开启状态（aria-checked="true"）。
        如果已经是开启状态则跳过。
        """
        try:
            # 定位「原创声明」文本旁边的开关（页面可能有多个 switch）
            switch_box = video_page.locator(
                ':text("原创声明") >> .. >> .weui-desktop-switch__box'
            )
            if not switch_box.is_visible(timeout=3000):
                # 兜底：取第一个 switch
                switch_box = video_page.locator(
                    '.weui-desktop-switch__box'
                ).first
                if not switch_box.is_visible(timeout=2000):
                    self._log("未找到原创声明开关，跳过", "WARNING")
                    return

            # 检查是否已经开启
            is_checked = switch_box.get_attribute("aria-checked")
            if is_checked == "true":
                self._log("原创声明已开启，无需重复操作")
                return

            switch_box.click()
            time.sleep(1)

            # 点击后会弹出「原创声明」对话框，协议默认已勾选，直接点击「确定」
            try:
                dialog = video_page.locator(
                    '.weui-desktop-dialog:has-text("原创声明")'
                ).first
                dialog.wait_for(state="visible", timeout=5000)

                confirm_btn = dialog.locator(
                    'button:has-text("确定")'
                ).first
                confirm_btn.wait_for(state="visible", timeout=3000)
                confirm_btn.click()
                self._log("已确认原创声明")
                time.sleep(1)
            except Exception as e:
                self._log(
                    f"处理原创声明对话框失败: {e}", "WARNING"
                )

            self._log("已勾选原创声明")
        except Exception as e:
            self._log(f"勾选原创声明失败: {e}", "WARNING")

    def _select_cover(
        self, video_page: Page, cover_dir: Optional[Path] = None
    ):
        """
        选择封面图片（必填项）

        如果提供了 cover_dir，则从该目录随机选取一张 PNG 上传；
        否则从页面推荐封面中随机选一张。

        上传/选择后统一处理「编辑封面」对话框。
        """
        if cover_dir:
            self._select_cover_from_local(video_page, cover_dir)
        else:
            self._select_cover_from_recommended(video_page)

    def _select_cover_from_local(
        self, video_page: Page, cover_dir: Path
    ):
        """从本地目录随机选取一张 PNG 上传为封面"""
        cover_dir = Path(cover_dir)
        png_files = sorted(cover_dir.glob("*.png"))
        if not png_files:
            self._log(
                f"封面目录中没有 PNG 文件: {cover_dir}", "WARNING"
            )
            # 回退到推荐封面
            self._select_cover_from_recommended(video_page)
            return

        chosen = random.choice(png_files)
        self._log(
            f"已随机选择封面: {chosen.name}（共 {len(png_files)} 张）"
        )

        # Step 1: 点击空封面项，打开"选择视频封面"对话框
        try:
            empty_item = video_page.locator(
                ".cover__options__item_empty"
            ).first
            empty_item.click()
            self._log("已点击空封面项，等待对话框打开...")
            time.sleep(2)
        except Exception as e:
            self._log(f"点击空封面项失败: {e}", "WARNING")
            self._select_cover_from_recommended(video_page)
            return

        # Step 2: 在"选择视频封面"对话框内上传图片
        try:
            cover_dialog = video_page.locator(
                '.weui-desktop-dialog__wrp:not([style*="display: none"])'
            ).filter(
                has=video_page.locator(
                    '.weui-desktop-dialog__title:text("选择视频封面")'
                )
            )
            cover_dialog.wait_for(state="visible", timeout=5000)
            self._log("「选择视频封面」对话框已打开")

            # 通过对话框内 file input 上传图片到素材库
            dialog_file_input = cover_dialog.locator(
                'input[type="file"]'
            )
            if dialog_file_input.count() == 0:
                raise RuntimeError("对话框内未找到 file input")

            dialog_file_input.first.set_input_files(str(chosen))
            self._log("已通过 file input 上传封面图片到素材库")
            time.sleep(3)

            # Step 3: 点击「下一步」进入编辑封面
            # 上传后图片会自动被选中，"下一步"按钮变为可用
            next_btn = cover_dialog.locator(
                'button:has-text("下一步"):not(.weui-desktop-btn_disabled)'
            )

            # 等待"下一步"按钮变为可用（最多 10 秒）
            for _w in range(10):
                if next_btn.count() > 0 and next_btn.is_visible():
                    break
                time.sleep(1)
                self._log(
                    f"等待「下一步」按钮变为可用... ({_w+1}s)"
                )
            else:
                self._log("「下一步」按钮未变为可用", "WARNING")

            if next_btn.count() > 0 and next_btn.is_visible():
                next_btn.click()
                self._log("已点击「下一步」")
                time.sleep(2)

            # Step 4: 处理「编辑封面」步骤（同一个对话框的第二步）
            # 使用 dispatchEvent 发送完整鼠标事件序列点击「完成」
            # （微信平台框架不响应普通 click/keyboard 事件，
            #  需要 pointerdown→mousedown→pointerup→mouseup→click）
            finish_btn = cover_dialog.locator(
                'button.weui-desktop-btn_primary:has-text("完成")'
            )
            try:
                finish_btn.wait_for(state="visible", timeout=10000)
                self._log("编辑封面步骤已就绪，点击「完成」...")

                video_page.evaluate("""() => {
                    const dialogs = document.querySelectorAll(
                        '.weui-desktop-dialog__wrp'
                    );
                    for (const d of dialogs) {
                        const title = d.querySelector(
                            '.weui-desktop-dialog__title'
                        );
                        if (title && title.textContent.includes(
                            '选择视频封面'
                        )) {
                            const btns = d.querySelectorAll(
                                'button.weui-desktop-btn_primary'
                            );
                            for (const b of btns) {
                                if (b.textContent.trim() === '完成'
                                    && b.offsetParent !== null) {
                                    b.scrollIntoView({block: 'center'});
                                    for (const t of [
                                        'pointerdown', 'mousedown'
                                    ]) {
                                        b.dispatchEvent(new PointerEvent(
                                            t, {bubbles:true,
                                                cancelable:true}));
                                    }
                                    for (const t of [
                                        'pointerup', 'mouseup'
                                    ]) {
                                        b.dispatchEvent(new PointerEvent(
                                            t, {bubbles:true,
                                                cancelable:true}));
                                    }
                                    b.dispatchEvent(new MouseEvent(
                                        'click',
                                        {bubbles:true,
                                         cancelable:true}));
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                }""")
                self._log("已点击「完成」，等待封面对话框关闭...")
                time.sleep(2)

                # 等待封面对话框关闭（最多 60 秒）
                for _w in range(60):
                    try:
                        dialog_visible = video_page.evaluate(
                            """() => {
                                const dialogs = document.querySelectorAll(
                                    '.weui-desktop-dialog__wrp'
                                );
                                for (const d of dialogs) {
                                    const title = d.querySelector(
                                        '.weui-desktop-dialog__title'
                                    );
                                    if (title
                                        && title.textContent.includes(
                                            '选择视频封面')) {
                                        const s = window
                                            .getComputedStyle(d);
                                        return s.display !== 'none'
                                            && s.visibility !== 'hidden';
                                    }
                                }
                                return false;
                            }"""
                        )
                        if not dialog_visible:
                            self._log(
                                "封面对话框已关闭，封面设置完成"
                            )
                            break
                        if _w % 5 == 0:
                            self._log(
                                f"等待封面对话框关闭中... ({_w}s)"
                            )
                    except Exception:
                        self._log("封面对话框检测异常，继续")
                        break
                    time.sleep(1)
                else:
                    self._log(
                        "封面对话框关闭等待超时", "WARNING"
                    )
                    try:
                        video_page.keyboard.press("Escape")
                        time.sleep(1)
                    except Exception:
                        pass

                # 额外等待，确保页面状态稳定
                time.sleep(2)

            except Exception as e:
                self._log(
                    f"封面编辑完成步骤失败: {e}", "WARNING"
                )

        except Exception as e:
            self._log(f"封面上传失败: {e}", "WARNING")
            try:
                video_page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass
            self._select_cover_from_recommended(video_page)

    def _select_cover_from_recommended(self, video_page: Page):
        """从页面推荐封面中随机选一张"""
        # 1. 点击推荐封面缩略图（跳过 _empty 的）
        try:
            real_covers = video_page.locator(
                ".cover__options__item:not(.cover__options__item_empty)"
            )
            if real_covers.count() == 0:
                self._log("未找到推荐封面缩略图", "WARNING")
                return
            count = real_covers.count()
            idx = random.randint(0, count - 1)
            real_covers.nth(idx).click()
            self._log(f"已随机选择第 {idx + 1}/{count} 张推荐封面")
            time.sleep(2)
        except Exception as e:
            self._log(f"点击封面缩略图失败: {e}", "WARNING")
            return

        # 2. 处理编辑封面对话框
        self._handle_cover_edit_dialog(video_page)

    def _handle_cover_edit_dialog(self, video_page: Page):
        """
        处理「编辑封面」对话框：点击「完成」并等待封面处理完成。

        上传或选择封面后统一调用此方法。
        """
        try:
            # 定位「编辑封面」对话框
            edit_dialog = video_page.locator(
                '.weui-desktop-dialog__wrp:not([style*="display: none"])'
            ).filter(
                has=video_page.locator(
                    '.weui-desktop-dialog__title:text("编辑封面")'
                )
            )
            edit_dialog.wait_for(state="visible", timeout=10000)
            self._log("编辑封面对话框已打开")

            # 在对话框内点击「完成」
            finish_btn = edit_dialog.locator(
                'button.weui-desktop-btn_primary:has-text("完成")'
            )
            finish_btn.click()
            self._log("已点击「完成」，等待封面处理完成...")
            time.sleep(2)

            # 等待封面上传/处理完成
            for _w in range(60):  # 最多等 60 秒
                try:
                    has_pending = video_page.evaluate(
                        """() => {
                            const t = document.body.innerText || '';
                            return t.includes('请等待推荐封面上传完成')
                                || t.includes('封面上传中')
                                || t.includes('正在载入');
                        }"""
                    )
                    if not has_pending:
                        self._log("封面处理完成")
                        break
                    if _w % 5 == 0:
                        self._log(
                            f"等待封面处理中... ({_w}s)"
                        )
                except Exception:
                    break
                time.sleep(1)
            else:
                self._log("封面处理等待超时", "WARNING")

        except Exception as e:
            self._log(f"编辑封面对话框操作失败: {e}", "WARNING")
            # 尝试关闭对话框
            try:
                video_page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception:
                pass

    def _click_save_and_wait(self, video_page: Page):
        """
        点击保存按钮并等待保存完成

        保存完成的判断依据（任一满足即可）：
        - 页面自动关闭
        - 页面 URL 发生跳转（navigation）
        - 出现成功提示（"保存成功"文本）
        """
        save_clicked = False
        url_before = video_page.url

        save_selectors = [
            '.weui-desktop-btn_wrp.mr-16 button.weui-desktop-btn_primary',
            'button.weui-desktop-btn_primary:has-text("保存")',
        ]
        for sel in save_selectors:
            try:
                save_btn = video_page.locator(sel)
                if save_btn.is_visible(timeout=3000):
                    save_btn.click()
                    save_clicked = True
                    self._log("已点击保存，等待保存完成...")
                    break
            except Exception:
                continue

        if not save_clicked:
            self._log("保存按钮点击失败", "WARNING")
            return

        # 点击后短暂等待，检测是否立即跳转（保存成功）
        time.sleep(1)
        try:
            if video_page.is_closed():
                self._log("保存后页面已关闭，保存成功")
                return
            # 尝试访问页面，如果跳转了会抛异常
            video_page.evaluate("() => null")
        except Exception:
            self._log("保存后页面已跳转（navigation），保存成功")
            return

        # 等待保存完成（最多 120 秒，封面处理可能较久）
        max_wait = 120  # 秒
        poll_interval = 2  # 秒
        waited = 0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            # 1. 页面已被自动关闭
            if video_page.is_closed():
                self._log("视频编辑页已自动关闭，保存完成")
                return

            # 2. URL 发生变化或页面跳转（navigation）
            try:
                if video_page.url != url_before:
                    self._log("页面已跳转，保存完成")
                    time.sleep(1)
                    return
            except Exception:
                self._log("保存后页面已跳转（navigation），保存成功")
                return

            # 3. 检测「提交视频」确认弹窗（如"视频未声明原创"）
            try:
                confirm_btn = video_page.locator(
                    'button.weui-desktop-btn_primary:has-text("继续提交")'
                )
                if confirm_btn.is_visible(timeout=500):
                    confirm_btn.click()
                    self._log("检测到「提交视频」确认弹窗，已点击「继续提交」")
                    time.sleep(2)
                    continue
            except Exception:
                pass

            # 4. 通过 JS 检测保存成功信号 / 封面处理中
            try:
                page_state = video_page.evaluate(
                    """() => {
                        const body = document.body.innerText || '';
                        // 明确的成功信号
                        if (body.includes('保存成功')) return 'save_success';
                        if (body.includes('发布成功')) return 'publish_success';
                        // toast 成功（排除 upload tips）
                        const toasts = document.querySelectorAll('.weui-desktop-toast');
                        for (const toast of toasts) {
                            const t = toast.innerText || '';
                            if (t.includes('保存成功') || t.includes('提交成功'))
                                return 'toast_success:' + t.trim().substring(0, 100);
                        }
                        // 封面仍在处理中
                        if (body.includes('请等待推荐封面上传完成'))
                            return 'cover_pending';
                        return null;
                    }"""
                )
                if page_state and page_state.startswith(
                    ('save_', 'publish_', 'toast_')
                ):
                    self._log(f"检测到保存成功信号: {page_state}")
                    time.sleep(1)
                    return
                if page_state == 'cover_pending':
                    # 封面还在处理，等待后重试保存
                    if waited % 10 == 0:
                        self._log("封面仍在处理中，等待后重试保存...")
                    if waited % 5 == 0:
                        try:
                            cover_done = video_page.evaluate(
                                "() => !(document.body.innerText || '')"
                                ".includes('请等待推荐封面上传完成')"
                            )
                            if cover_done:
                                self._log("封面处理完成，重新点击保存")
                                for sel in save_selectors:
                                    try:
                                        btn = video_page.locator(sel)
                                        if btn.is_visible(timeout=2000):
                                            btn.click()
                                            self._log("已重新点击保存")
                                            break
                                    except Exception:
                                        continue
                        except Exception:
                            pass
            except Exception as _eval_err:
                err_msg = str(_eval_err).lower()
                if "navigation" in err_msg or "destroyed" in err_msg:
                    self._log(
                        "保存后页面已跳转（navigation），保存成功"
                    )
                    return

            if waited % 10 == 0:
                self._log(f"等待保存完成... ({waited}s/{max_wait}s)")

        self._log(
            f"等待保存完成超时（{max_wait}秒），请手动确认保存状态",
            "WARNING",
        )

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
