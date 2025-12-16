from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait


DOUYIN_HOME = "https://www.douyin.com/"


@dataclass(frozen=True)
class RunConfig:
    wait_timeout_sec: float = 30.0
    interval_sec: float = 2.0


class DouyinBot:
    """
    Douyin 网页端自动化：
    - 支持打开首页/视频链接
    - 支持人工扫码登录后复用 Profile（由 browser.py 负责）
    - 支持对当前视频执行双击点赞、滑走切换到下一条、以及播放状态/倍速控制
    """

    def __init__(self, driver: WebDriver, cfg: RunConfig, *, verbose: bool = False) -> None:
        self.driver = driver
        self.cfg = cfg
        self.wait = WebDriverWait(driver, cfg.wait_timeout_sec)
        self.verbose = verbose

    def _ts(self) -> str:
        return time.strftime("%H:%M:%S")

    def log(self, msg: str) -> None:
        if self.verbose:
            logging.getLogger("douyin-like").info("%s", msg)

    # -------------------------
    # 基础能力
    # -------------------------
    def open(self, url: str) -> None:
        try:
            # 智能打开：如果当前 URL 已经包含了目标 URL 的关键特征（如 modal_id），则跳过刷新
            # 避免频繁 refresh 触发风控
            cur = self.driver.current_url
            if url and cur and url in cur:
                self.log(f"当前已在目标 URL，跳过刷新: {url}")
                return
            # 对于 jingxuan?modal_id=... 这种结构，进一步检查参数
            if "modal_id=" in url and "modal_id=" in cur:
                # 简单提取 modal_id 对比
                import re
                m1 = re.search(r"modal_id=([0-9]+)", url)
                m2 = re.search(r"modal_id=([0-9]+)", cur)
                if m1 and m2 and m1.group(1) == m2.group(1):
                    self.log(f"当前已在目标 modal_id ({m1.group(1)})，跳过刷新")
                    return
        except Exception:
            pass
        self.driver.get(url)

    def _human_type(self, element: WebElement, text: str) -> None:
        """
        模拟人类打字：逐字输入，字符之间随机停顿，遇到标点停顿稍长。
        """
        import random
        for char in text:
            try:
                element.send_keys(char)
            except Exception:
                # 兜底：如果 send_keys 失败（例如 element 突然不可交互），尝试 ActionChains
                try:
                    ActionChains(self.driver).send_keys(char).perform()
                except Exception:
                    pass
            
            # 基础输入间隔 0.05 ~ 0.25s
            delay = random.uniform(0.05, 0.25)
            # 标点符号停顿稍长（模拟思考/选词）
            if char in ",.，。!?！？ ":
                delay += random.uniform(0.1, 0.3)
            time.sleep(delay)

    def open_home(self) -> None:
        self.open(DOUYIN_HOME)

    def wait_dom_ready(self) -> None:
        # 等待 document.readyState === "complete"
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    def safe_title(self) -> str:
        try:
            return self.driver.title
        except Exception:
            return ""

    def safe_current_url(self) -> str:
        try:
            return self.driver.current_url
        except Exception:
            return ""

    def is_live_url(self, url: str) -> bool:
        u = (url or "").lower()
        return "/live/" in u or "root/live" in u or "live" in u

    def _detect_verification(self) -> Optional[dict]:
        """
        检测页面是否弹出了“安全验证/验证码/滑块”等人机验证。
        只做检测与提示，不做绕过。
        返回 None 表示未检测到；否则返回包含 reason 的 dict（尽量小，便于写日志）。
        """
        try:
            payload = self.driver.execute_script(
                """
                function isVisible(el) {
                  if (!el) return false;
                  const r = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                  if (!r || r.width < 10 || r.height < 10) return false;
                  if (r.bottom <= 0 || r.right <= 0) return false;
                  if (r.top >= (window.innerHeight||0) || r.left >= (window.innerWidth||0)) return false;
                  const st = window.getComputedStyle ? window.getComputedStyle(el) : null;
                  if (st && (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity||'1') <= 0)) return false;
                  return true;
                }
                const keywords = [
                  '安全验证','验证码','滑动验证','拖动滑块','请完成验证','完成验证','验证','人机','机器人',
                  'captcha','verify','geetest'
                ];
                function hasKeyword(txt) {
                  const t = String(txt||'').toLowerCase();
                  for (const k of keywords) {
                    if (t.includes(String(k).toLowerCase())) return k;
                  }
                  return '';
                }
                // 1) iframe 线索
                const iframes = Array.from(document.querySelectorAll('iframe'));
                for (const f of iframes) {
                  if (!isVisible(f)) continue;
                  const src = (f.getAttribute('src')||'') + ' ' + (f.getAttribute('data-src')||'');
                  const hit = hasKeyword(src);
                  if (hit) return {hit:true, reason:'iframe_src', keyword:hit, sample:src.slice(0,200)};
                }
                // 2) dialog/overlay 文本线索
                const candidates = Array.from(document.querySelectorAll("[role='dialog'],[class*='captcha'],[id*='captcha'],[class*='verify'],[id*='verify'],[class*='geetest'],[id*='geetest']"));
                for (const el of candidates) {
                  if (!isVisible(el)) continue;
                  const txt = (el.innerText || el.textContent || '').trim();
                  const hit = hasKeyword(txt);
                  if (hit) return {hit:true, reason:'overlay_text', keyword:hit, sample:txt.slice(0,200)};
                }
                // 3) body 片段兜底（截断，避免太大）
                const bodyTxt = (document.body && (document.body.innerText || document.body.textContent)) || '';
                if (bodyTxt.length < 500 && hasKeyword(bodyTxt)) {
                     // 仅当 body 内容很少且包含关键字时才认为是全屏验证，避免误判正常页面的文字
                     return {hit:true, reason:'body_text_short', keyword:hasKeyword(bodyTxt), sample:String(bodyTxt).trim().slice(0,200)};
                }
                return {hit:false};
                """
            )
            if isinstance(payload, dict) and payload.get("hit"):
                return payload
        except Exception:
            return None
        return None

    def _handle_verification_if_present(self) -> None:
        """
        如果检测到验证码，暂停并等待用户手动处理。
        """
        ver = self._detect_verification()
        if ver is not None:
            self.log(f"[verify] !!! 检测到验证码 ({ver.get('reason')}) !!!")
            self.log(f"详情: {ver.get('keyword')} - {ver.get('sample')}")
            print("\n" + "="*60)
            print(f"⚠️  检测到安全验证！脚本已暂停。")
            print(f"请在浏览器中手动完成验证（滑块/点选等）。")
            print(f"完成后，请回到终端按 【回车】 继续...")
            print("="*60 + "\n")
            input()
            self.log("[verify] 用户已确认完成验证，继续执行...")
            time.sleep(1.0) # 留点时间让页面恢复

    def maybe_close_popups(self) -> None:
        """
        尝试关闭一些常见弹窗（不保证覆盖所有情况）。
        """
        # 先检查是不是验证码，如果是，转交手动处理
        self._handle_verification_if_present()
        
        candidates = [
            (By.CSS_SELECTOR, "button[aria-label='关闭']"),
            (By.CSS_SELECTOR, "button[aria-label='Close']"),
            (By.XPATH, "//button[contains(., '关闭')]"),
            (By.XPATH, "//button[contains(., '我知道了')]"),
        ]
        for by, sel in candidates:
            try:
                els = self.driver.find_elements(by, sel)
                for el in els[:2]:
                    if el.is_displayed() and el.is_enabled():
                        try:
                            el.click()
                            time.sleep(0.2)
                            return
                        except Exception:
                            continue
            except Exception:
                continue

    # -------------------------
    # 弹幕相关（自动发送）
    # -------------------------
    def _pick_best_visible(self, elements: list[WebElement]) -> Optional[WebElement]:
        best: Optional[WebElement] = None
        best_area = 0
        for el in elements:
            try:
                if not el.is_displayed() or not el.is_enabled():
                    continue
                rect = el.rect or {}
                area = int(rect.get("width", 0)) * int(rect.get("height", 0))
                if area > best_area:
                    best_area = area
                    best = el
            except Exception:
                continue
        return best

    def _find_danmaku_input(self) -> Optional[WebElement]:
        """
        尽量找到弹幕输入框。抖音页面 class 名经常是 hash（会变），因此优先用 placeholder/语义特征。
        """
        selectors = [
            "input[placeholder='发一条弹幕吧']",
            "input[placeholder*='弹幕']",
            "textarea[placeholder*='弹幕']",
            "[contenteditable='true'][placeholder*='弹幕']",
            "[contenteditable='true'][aria-label*='弹幕']",
        ]
        for sel in selectors:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                best = self._pick_best_visible(list(els))
                if best is not None:
                    self.log(f"[danmaku] 找到疑似输入框：selector={sel}")
                    return best
            except Exception:
                continue

        xpaths = [
            "//input[contains(@placeholder,'弹幕')]",
            "//textarea[contains(@placeholder,'弹幕')]",
        ]
        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                best = self._pick_best_visible(list(els))
                if best is not None:
                    self.log(f"[danmaku] 找到疑似输入框：xpath={xp}")
                    return best
            except Exception:
                continue
        return None

    def _find_send_button(self) -> Optional[WebElement]:
        """
        尝试定位“发送”按钮（有些页面 Enter 就能发；有些需要点击按钮）。
        """
        xpaths = [
            "//button[normalize-space()='发送' or contains(., '发送')]",
            "//*[@role='button' and (normalize-space()='发送' or contains(., '发送'))]",
            "//button[normalize-space()='发布' or contains(., '发布')]",
            "//*[@role='button' and (normalize-space()='发布' or contains(., '发布'))]",
            # 新增：红色 SVG 发送按钮 (class 含 WFB7wUOX 或 svg fill 含 FE2C55)
            "//div[contains(@class,'commentInput-right-ct')]//span[contains(@class,'WFB7wUOX')]",
            "//div[contains(@class,'commentInput-right-ct')]//*[local-name()='svg' and @fill='#FE2C55']/ancestor::*[1]",
        ]
        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                best = self._pick_best_visible(list(els))
                if best is not None:
                    self.log(f"[danmaku] 找到疑似发送按钮：xpath={xp}")
                    return best
            except Exception:
                continue
        return None

    def send_danmaku(self, text: str = "哇塞，赞赞赞") -> bool:
        """
        自动发送一条弹幕：
        - 定位输入框（优先 placeholder='发一条弹幕吧' / 包含“弹幕”）
        - 填充文本
        - 优先 Enter 提交，必要时点击“发送”按钮兜底
        返回 True 表示已执行“输入+提交”动作；False 表示未找到输入框。
        """
        self.log("准备发送弹幕：尝试关闭可能的弹窗")
        self.maybe_close_popups()
        try:
            self.wait_dom_ready()
        except Exception:
            pass
        time.sleep(0.3)

        box = self._find_danmaku_input()
        if box is None:
            self.log("[danmaku] 未找到弹幕输入框")
            return False

        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'})", box)
        except Exception:
            pass

        try:
            box.click()
            time.sleep(0.1)
        except Exception:
            pass

        # 清空并输入（兼容 mac/win）
        try:
            ActionChains(self.driver).key_down(Keys.COMMAND).send_keys("a").key_up(Keys.COMMAND).perform()
        except Exception:
            try:
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            except Exception:
                pass
        try:
            box.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        
        # 模拟人类思考/停顿
        import random
        time.sleep(random.uniform(0.3, 0.8))

        try:
            self._human_type(box, text)
        except Exception:
            ActionChains(self.driver).send_keys(text).perform()
        
        # 输入后停顿，再提交
        time.sleep(random.uniform(0.5, 1.2))

        submitted = False
        try:
            box.send_keys(Keys.ENTER)
            submitted = True
        except Exception:
            try:
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                submitted = True
            except Exception:
                submitted = False

        # 若页面要求按钮提交，再兜底点“发送”
        try:
            btn = self._find_send_button()
            if btn is not None and btn.is_displayed() and btn.is_enabled():
                btn.click()
                submitted = True
        except Exception:
            pass

        time.sleep(self.cfg.interval_sec)
        return submitted

    # -------------------------
    # 评论相关（自动发送）
    # -------------------------
    def _maybe_expand_comment_panel(self) -> bool:
        """
        某些页面（如 jingxuan modal）需要点击“更多评论/展开”后才渲染输入框。
        """
        selectors = [
            "[data-e2e='video-comment-more']",
            "[data-e2e*='comment-more']",
            "[data-e2e*='comment_more']",
        ]
        for sel in selectors:
            try:
                el = self._pick_best_visible(list(self.driver.find_elements(By.CSS_SELECTOR, sel)))
                if el is None:
                    continue
                self.log(f"[comment] 尝试展开评论：selector={sel}")
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click()", el)
                time.sleep(0.35)
                return True
            except Exception:
                continue
        return False

    def _find_comment_icon(self) -> Optional[WebElement]:
        """
        尝试定位“评论”按钮（右侧气泡图标）。
        说明：抖音 class 名常变，优先使用 data-e2e 语义属性（截图中为 data-e2e="feed-comment-icon"）。
        """
        selectors = [
            "[data-e2e='feed-comment-icon']",
            "[data-e2e='comment-icon']",
            "[data-e2e='comment']",
            "[data-e2e*='comment-icon']",
            "[data-e2e*='comment']",
            "[aria-label*='评论']",
            "[title*='评论']",
            "[aria-label*='comment']",
            "[aria-label*='Comment']",
        ]
        for sel in selectors:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                best = self._pick_best_visible(list(els))
                if best is not None:
                    self.log(f"[comment] 找到疑似评论按钮：selector={sel}")
                    return best
            except Exception:
                continue
        # 兜底：找包含“评论”的可点击按钮/元素
        xpaths = [
            "//*[@role='button' and (contains(@aria-label,'评论') or contains(., '评论'))]",
            "//button[contains(@aria-label,'评论') or contains(., '评论')]",
            "//*[(@role='button' or self::button) and (contains(translate(@aria-label,'COMMENT','comment'),'comment') or contains(translate(normalize-space(.),'COMMENT','comment'),'comment'))]",
        ]
        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                best = self._pick_best_visible(list(els))
                if best is not None:
                    self.log(f"[comment] 找到疑似评论按钮：xpath={xp}")
                    return best
            except Exception:
                continue
        return None

    def _find_comment_input(self) -> Optional[WebElement]:
        """
        定位评论输入框。
        策略：
        1. 先找 Draft.js 真身。
        2. 没找到，则找“留下你的精彩评论吧”占位符 -> 点击激活 -> 等待真身出现。
        3. 增加 iframe 穿透查找。
        """
        # 定义精准选择器 (Draft.js 真身)
        draft_sels = [
            "div.public-DraftEditor-content[role='combobox'][contenteditable='true']",
            ".public-DraftEditor-content[contenteditable='true']"
        ]

        def search_draft_in_context(ctx_driver):
            for ds in draft_sels:
                els = ctx_driver.find_elements(By.CSS_SELECTOR, ds)
                visible_els = [e for e in els if e.is_displayed()]
                if visible_els:
                    return self._pick_best_visible(visible_els), ds
            return None, None

        # --- 阶段 1: 直接查找真身 ---
        # 1.1 主文档查找
        best, selector = search_draft_in_context(self.driver)
        if best:
            self.log(f"[comment] 直接命中 Draft.js 编辑器 (Main)：{selector}")
            return best

        # 1.2 iframe 查找
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i, frm in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frm)
                best, selector = search_draft_in_context(self.driver)
                if best:
                    self.log(f"[comment] 直接命中 Draft.js 编辑器 (Iframe #{i})：{selector}")
                    return best
                self.driver.switch_to.default_content()
            except:
                self.driver.switch_to.default_content()

        # --- 阶段 2: 查找并激活占位符 ---
        self.log("[comment] 未找到激活的输入框，尝试寻找并点击占位符...")
        
        # 占位符特征：包含 "留下你的精彩评论吧" 的元素，或者 .comment-input-inner-container
        placeholder_xpaths = [
            "//span[contains(text(), '留下你的精彩评论吧')]",
            "//div[contains(@class, 'comment-input-inner-container')]",
            "//div[contains(@class, 'comment-input-container')]"
        ]

        placeholder_found = False
        for xpath in placeholder_xpaths:
            try:
                # 显式等待占位符出现 (快速检查)
                els = self.driver.find_elements(By.XPATH, xpath)
                visible_placeholders = [e for e in els if e.is_displayed()]
                if visible_placeholders:
                    target = visible_placeholders[0]
                    self.log(f"[comment] 发现评论占位符 ({xpath})，正在点击激活...")
                    
                    # 尝试多种点击方式
                    try:
                        target.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", target)
                    
                    placeholder_found = True
                    time.sleep(1.5) # 等待 JS 渲染真身
                    break
            except Exception as e:
                pass
        
        if not placeholder_found:
            self.log("[comment] 未找到任何评论框占位符。")

        # --- 阶段 3: 激活后再次查找真身 ---
        # 3.1 主文档重试
        best, selector = search_draft_in_context(self.driver)
        if best:
            self.log(f"[comment] 激活后命中 Draft.js 编辑器 (Main)：{selector}")
            return best

        # 3.2 iframe 重试
        for i, frm in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frm)
                best, selector = search_draft_in_context(self.driver)
                if best:
                    self.log(f"[comment] 激活后命中 Draft.js 编辑器 (Iframe #{i})：{selector}")
                    return best
                self.driver.switch_to.default_content()
            except:
                self.driver.switch_to.default_content()

        # --- 阶段 4: 最后的兜底 (通用 contenteditable) ---
        try:
            els = self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
            candidates = []
            for el in els:
                if not el.is_displayed(): continue
                # 排除搜索框
                if "search" in str(el.getAttribute("data-e2e") or ""): continue
                if "搜索" in str(el.getAttribute("placeholder") or ""): continue
                candidates.append(el)
            
            if candidates:
                best = self._pick_best_visible(candidates)
                if best:
                    self.log("[comment] 兜底：找到通用 contenteditable 输入框")
                    return best
        except:
            pass

        return None

    def _open_comment_panel(self) -> bool:
        """
        点击评论按钮打开评论面板。返回 True 表示已执行点击（不保证面板必开）。
        """
        self.log("准备打开评论面板：尝试关闭可能的弹窗")
        self.maybe_close_popups()
        try:
            self.wait_dom_ready()
        except Exception:
            pass
        time.sleep(0.2)

        icon = self._find_comment_icon()
        if icon is None:
            self.log("[comment] 未找到评论按钮")
            return False
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'})", icon)
        except Exception:
            pass

        try:
            icon.click()
            time.sleep(0.25)
            return True
        except Exception:
            # 兜底：用 JS 触发 click
            try:
                self.driver.execute_script("arguments[0].click()", icon)
                time.sleep(0.25)
                return True
            except Exception:
                return False

    def send_comment(self, text: str = "好开心看到你的视频") -> bool:
        """
        自动发评论（对应截图 1/2/3）：
        1) 点击评论按钮（data-e2e='feed-comment-icon'）
        2) 定位评论输入框（placeholder 含“评论/精彩评论”或 contenteditable）
        3) 输入 text 并提交（Enter；必要时再点“发送”按钮兜底）
        
        增加：全程验证码检测 + 暂停
        """
        # 阶段0: 检查验证码
        self._handle_verification_if_present()

        # 先尝试直接找输入框：有些页面（例如 modal 结构）默认已渲染输入框
        try:
            self.maybe_close_popups()
        except Exception:
            pass
        try:
            self.wait_dom_ready()
        except Exception:
            pass
        time.sleep(0.2)
        
        # 阶段1: 找/开输入框
        box = self._find_comment_input()
        if box is None:
            opened = self._open_comment_panel()
            self._handle_verification_if_present() # 点击后检查
            if not opened:
                return False
            self._maybe_expand_comment_panel()
            self._handle_verification_if_present()

        # 等评论输入框出现
        deadline = time.time() + max(1.0, float(self.cfg.wait_timeout_sec))
        box = None if box is None else box
        while time.time() < deadline:
            if box is None:
                box = self._find_comment_input()
            if box is not None:
                break
            self._maybe_expand_comment_panel()
            time.sleep(0.2)
            self._handle_verification_if_present() # 等待期间检查

        if box is None:
            self.log("[comment] 未找到评论输入框")
            return False

        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'})", box)
        except Exception:
            pass
        
        # 阶段2: 点击输入框
        try:
            box.click()
            time.sleep(0.05)
        except Exception:
            pass
        
        self._handle_verification_if_present()
        
        # 清空
        try:
            ActionChains(self.driver).key_down(Keys.COMMAND).send_keys("a").key_up(Keys.COMMAND).perform()
        except Exception:
            try:
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            except Exception:
                pass
        try:
            box.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        
        # 模拟人类思考/停顿
        import random
        time.sleep(random.uniform(0.3, 0.8))

        # 阶段3: 输入文字
        try:
            self._human_type(box, text)
        except Exception:
            ActionChains(self.driver).send_keys(text).perform()
        
        # 输入后停顿
        self._handle_verification_if_present()
        time.sleep(random.uniform(0.5, 1.2))

        # 阶段4: 提交
        submitted = False
        # 1) send_keys Enter
        for key in (Keys.ENTER, Keys.RETURN):
            try:
                box.send_keys(key)
                submitted = True
                break
            except Exception:
                continue
        
        if not submitted:
            # 2) ActionChains Enter
            for key in (Keys.ENTER, Keys.RETURN):
                try:
                    ActionChains(self.driver).send_keys(key).perform()
                    submitted = True
                    break
                except Exception:
                    continue
        
        if not submitted:
             # 3) JS keydown
            try:
                ok = bool(
                    self.driver.execute_script(
                        """
                        const el = arguments[0] || document.activeElement || document.body;
                        try { if (el && el.focus) el.focus(); } catch (e) {}
                        const evtInit = {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true};
                        const down = new KeyboardEvent('keydown', evtInit);
                        const press = new KeyboardEvent('keypress', evtInit);
                        const up = new KeyboardEvent('keyup', evtInit);
                        const t = el || document;
                        t.dispatchEvent(down);
                        t.dispatchEvent(press);
                        t.dispatchEvent(up);
                        return true;
                        """,
                        box,
                    )
                )
                submitted = bool(ok)
            except Exception:
                submitted = False

        # 阶段5: 提交后检查验证与结果
        time.sleep(0.5)
        self._handle_verification_if_present()

        # 确认式成功：轮询评论列表
        def _comment_appeared(wait_sec: float = 8.0) -> bool:
            deadline = time.time() + max(0.0, float(wait_sec))
            while time.time() < deadline:
                # 期间持续检查验证码
                self._handle_verification_if_present()
                try:
                    ok = bool(
                        self.driver.execute_script(
                            """
                            const target = String(arguments[0]||'').trim();
                            if (!target) return false;
                            const list = document.querySelector("[data-e2e='comment-list']") || document;
                            const items = Array.from(list.querySelectorAll("[data-e2e='comment-item'],[data-e2e*='comment-item']"));
                            for (const it of items) {
                              const txt = (it.innerText || it.textContent || '').trim();
                              if (txt && txt.includes(target)) return true;
                            }
                            return false;
                            """,
                            text,
                        )
                    )
                    if ok:
                        return True
                except Exception:
                    pass
                time.sleep(0.4)
            return False

        # 适当延长等待时间 (max 12s -> 15s)，给验证码处理留余量
        confirmed = _comment_appeared(wait_sec=min(15.0, float(self.cfg.wait_timeout_sec)))
        if not confirmed:
            self.log("[comment] 未能在评论列表中确认到发送内容")
            return False

        time.sleep(self.cfg.interval_sec)
        return True

    def pause_for_manual_login(self, prompt: str = "请在打开的浏览器里手动扫码登录完成后，回到终端按回车继续...") -> None:
        cur = ""
        try:
            cur = self.driver.current_url
        except Exception:
            pass
        logging.getLogger("douyin-like").info("%s (当前页面：%s)", prompt, cur)
        input()

    # -------------------------
    # 点赞相关
    # -------------------------
    def _find_visible_video(self) -> Optional[WebElement]:
        """
        兜底：很多场景下“双击视频区域”也能触发点赞。
        尽量找到一个可见且面积最大的 <video> 元素。
        """
        try:
            videos = self.driver.find_elements(By.CSS_SELECTOR, "video")
        except Exception:
            return None
        if not videos:
            return None

        best: Optional[WebElement] = None
        best_area = 0
        for v in videos:
            try:
                if not v.is_displayed():
                    continue
                rect = v.rect or {}
                area = int(rect.get("width", 0)) * int(rect.get("height", 0))
                if area > best_area:
                    best_area = area
                    best = v
            except Exception:
                continue
        return best

    def _dispatch_dblclick_at(self, x: int, y: int) -> bool:
        """
        在视口坐标 (clientX, clientY) 派发双击事件（JS），避免 ActionChains 坐标系问题。
        """
        try:
            return bool(
                self.driver.execute_script(
                    """
                    let x = arguments[0], y = arguments[1];
                    const vw = Math.max(0, window.innerWidth || 0);
                    const vh = Math.max(0, window.innerHeight || 0);
                    x = Math.min(Math.max(x, 1), Math.max(vw - 2, 1));
                    y = Math.min(Math.max(y, 1), Math.max(vh - 2, 1));
                    const el = document.elementFromPoint(x, y);
                    if (!el) return false;
                    const opts = {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y};
                    el.dispatchEvent(new MouseEvent('mousemove', opts));
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.dispatchEvent(new MouseEvent('click', opts));
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new MouseEvent('mouseup', opts));
                    el.dispatchEvent(new MouseEvent('click', opts));
                    el.dispatchEvent(new MouseEvent('dblclick', opts));
                    return true;
                    """,
                    int(x),
                    int(y),
                )
            )
        except Exception:
            return False

    def double_click_video_to_like(self) -> bool:
        v = self._find_visible_video()
        if v is None:
            # videos 为空：改用“左上角 1/3 处”的视口区域作为兜底点击点
            try:
                vw = int(self.driver.execute_script("return Math.max(0, window.innerWidth || 0)"))
                vh = int(self.driver.execute_script("return Math.max(0, window.innerHeight || 0)"))
            except Exception:
                vw, vh = 0, 0
            x = max(1, vw // 3) if vw else 100
            y = max(1, vh // 3) if vh else 100
            try:
                tag = self.driver.execute_script(
                    "const el=document.elementFromPoint(arguments[0],arguments[1]); return el?el.tagName:'';",
                    x,
                    y,
                )
            except Exception:
                tag = ""
            self.log(f"未找到 <video>：改用视口左上 1/3 处双击（x={x}, y={y}, vw={vw}, vh={vh}, tag={tag}）")
            ok = self._dispatch_dblclick_at(x, y)
            time.sleep(1.0)
            return ok
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'})", v)
        except Exception:
            pass

        # 关键：不要直接对 <video> 元素点（单击往往是播放/暂停），而是对视频画面中心点的“覆盖层元素”双击。
        # 优先用 JS 派发 dblclick（避免 Selenium 鼠标移动坐标系/滚动导致的 MoveTargetOutOfBounds）。
        try:
            info = self.driver.execute_script(
                """
                const v = arguments[0];
                const r = v.getBoundingClientRect();
                let cx = Math.floor(r.left + r.width / 2);
                let cy = Math.floor(r.top + r.height / 2);
                // clamp to viewport
                const vw = Math.max(0, window.innerWidth || 0);
                const vh = Math.max(0, window.innerHeight || 0);
                cx = Math.min(Math.max(cx, 1), Math.max(vw - 2, 1));
                cy = Math.min(Math.max(cy, 1), Math.max(vh - 2, 1));
                const el = document.elementFromPoint(cx, cy);
                const tag = el ? el.tagName : null;
                let cls = "";
                try { cls = el ? (el.className || "") : ""; } catch (e) { cls = ""; }
                const aria = el ? (el.getAttribute("aria-label") || "") : "";
                return {cx, cy, tag, cls, aria, vw, vh};
                """,
                v,
            )
        except Exception:
            info = None

        try:
            if isinstance(info, dict):
                self.log(
                    "使用兜底方案：对视频中心点双击触发点赞"
                    f"（x={info.get('cx')}, y={info.get('cy')}, vw={info.get('vw')}, vh={info.get('vh')}, tag={info.get('tag')}, aria={info.get('aria')}, class={info.get('cls')}）"
                )
                x = int(info.get("cx", 0))
                y = int(info.get("cy", 0))
                ok = self._dispatch_dblclick_at(x, y)
                if not ok:
                    self.log("JS 双击派发失败，退化为 Selenium ActionChains 双击")
                    ActionChains(self.driver).move_to_element(v).double_click().perform()
            else:
                self.log("使用兜底方案：未取到中心点信息，退化为对 <video> 元素双击")
                ActionChains(self.driver).move_to_element(v).double_click().perform()

            time.sleep(1.0)
            return True
        except Exception as e:
            self.log(f"兜底失败：双击视频区域执行异常（{type(e).__name__}: {e}）")
            return False

    def like_current_video(self) -> bool:
        """
        对当前视频执行“点赞”。
        说明：此实现**仅使用双击视频区域**触发点赞，不做“是否已点赞”的判断。
        返回 True 表示已执行双击动作；False 表示未找到可操作的视频元素。
        """
        self.log("准备点赞：尝试关闭可能的弹窗")
        self.maybe_close_popups()
        cur = self.safe_current_url()
        if self.is_live_url(cur):
            self.log(f"检测到 live URL，跳过点赞：{cur}")
            return False
        return self.double_click_video_to_like()
    
    def get_video_state(self) -> dict:
        """
        返回播放状态（用于“等待播放完成”）。字段：
        - has_video: bool
        - current_time: float
        - duration: float
        - playback_rate: float
        - paused: bool
        - ended: bool
        - ready_state: int
        """
        try:
            return dict(
                self.driver.execute_script(
                    """
                    // 选取当前“最可见/最大”的 video，避免拿到后台/预加载 video
                    const vids = Array.from(document.querySelectorAll('video'));
                    if (!vids.length) return {has_video:false};
                    let best = null, bestArea = 0;
                    for (const v of vids) {
                      const r = v.getBoundingClientRect();
                      const area = Math.max(0, r.width) * Math.max(0, r.height);
                      const inView = r.bottom > 0 && r.right > 0 &&
                        r.left < (window.innerWidth||0) && r.top < (window.innerHeight||0);
                      if (inView && area > bestArea) { best = v; bestArea = area; }
                    }
                    const v = best || vids[0];
                    return {
                      has_video: true,
                      current_time: v.currentTime || 0,
                      duration: v.duration || 0,
                      playback_rate: v.playbackRate || 1,
                      paused: !!v.paused,
                      ended: !!v.ended,
                      ready_state: v.readyState || 0
                    };
                    """
                )
                or {}
            )
        except Exception:
            return {"has_video": False}

    def set_playback_rate(self, rate: float) -> bool:
        """
        设置当前视频播放速率（playbackRate）。
        返回 True 表示已尝试设置到某个 video 元素；False 表示未找到可用 video。
        """
        try:
            r = float(rate)
        except Exception:
            return False
        if r <= 0:
            return False

        try:
            ok = bool(
                self.driver.execute_script(
                    """
                    const r = arguments[0];
                    const vids = Array.from(document.querySelectorAll('video'));
                    if (!vids.length) return false;
                    let best = null, bestArea = 0;
                    for (const v of vids) {
                      const rect = v.getBoundingClientRect();
                      const area = Math.max(0, rect.width) * Math.max(0, rect.height);
                      const inView = rect.bottom > 0 && rect.right > 0 &&
                        rect.left < (window.innerWidth||0) && rect.top < (window.innerHeight||0);
                      if (inView && area > bestArea) { best = v; bestArea = area; }
                    }
                    const v = best || vids[0];
                    v.playbackRate = r;
                    return true;
                    """,
                    r,
                )
            )
            if ok:
                self.log(f"已设置 playbackRate={r}")
            return ok
        except Exception:
            return False

    def ensure_playback_rate(self, rate: float, *, wait_sec: float = 2.0) -> bool:
        """
        确保 playbackRate 生效：重复设置并读取验证（某些页面会重置 playbackRate）。
        """
        deadline = time.time() + max(0.0, float(wait_sec))
        target = float(rate)
        last = None
        while time.time() < deadline:
            self.set_playback_rate(target)
            st = self.get_video_state()
            if st.get("has_video"):
                last = float(st.get("playback_rate", 0.0) or 0.0)
                if abs(last - target) < 0.05:
                    return True
            time.sleep(0.2)
        if last is not None:
            self.log(f"playbackRate 未完全生效：target={target} actual={last}")
        return False

    def ensure_playing(self, *, wait_sec: float = 2.0) -> bool:
        """
        尽量确保视频处于播放状态：
        - 若 paused 且未 ended，则尝试 v.play()
        - 为了绕过某些自动播放限制，会先设置 muted=true
        返回 True 表示最终检测到处于播放（paused=False）或 ended=True；False 表示没做到。
        """
        deadline = time.time() + max(0.0, float(wait_sec))
        while time.time() < deadline:
            st = self.get_video_state()
            if not st.get("has_video"):
                return False
            if bool(st.get("ended", False)):
                return True
            if not bool(st.get("paused", False)):
                return True
            try:
                self.driver.execute_script(
                    """
                    const vids = Array.from(document.querySelectorAll('video'));
                    if (!vids.length) return false;
                    let best = null, bestArea = 0;
                    for (const v of vids) {
                      const r = v.getBoundingClientRect();
                      const area = Math.max(0, r.width) * Math.max(0, r.height);
                      const inView = r.bottom > 0 && r.right > 0 &&
                        r.left < (window.innerWidth||0) && r.top < (window.innerHeight||0);
                      if (inView && area > bestArea) { best = v; bestArea = area; }
                    }
                    const v = best || vids[0];
                    v.muted = true;
                    const p = v.play();
                    if (p && typeof p.catch === 'function') { p.catch(()=>{}); }
                    return true;
                    """
                )
            except Exception:
                pass
            time.sleep(0.25)
        return False

    def get_page_info(self) -> dict:
        """
        获取页面信息（SPA 场景下 document.title 可能不更新，补充 og:title 等）。
        """
        try:
            return dict(
                self.driver.execute_script(
                    """
                    const docTitle = document.title || "";
                    const og = document.querySelector("meta[property='og:title']")?.getAttribute("content") || "";
                    const desc = document.querySelector("meta[name='description']")?.getAttribute("content") || "";
                    const h1 = document.querySelector("h1")?.textContent?.trim() || "";
                    const h2 = document.querySelector("h2")?.textContent?.trim() || "";
                    return {doc_title: docTitle, og_title: og, description: desc, h1, h2};
                    """
                )
                or {}
            )
        except Exception:
            return {}

    def swipe_next(self) -> bool:
        """
        模拟“滑走/切到下一条视频”。
        返回 True 表示检测到“已切换到下一条”（URL 或视频特征发生变化）；False 表示多次尝试后仍未检测到切换。
        """
        def _sig() -> tuple[str, float, float]:
            # 用 URL + duration + current_time 作为“是否切换”的粗特征
            st = self.get_video_state()
            return (
                self.safe_current_url(),
                float(st.get("duration", 0.0) or 0.0),
                float(st.get("current_time", 0.0) or 0.0),
            )

        def _changed(before: tuple[str, float, float], after: tuple[str, float, float]) -> bool:
            if after[0] and before[0] and after[0] != before[0]:
                return True
            # duration 改变通常表示换片
            if abs(after[1] - before[1]) > 0.5 and after[1] > 0 and before[1] > 0:
                return True
            # current_time 回到较小值也可能表示换片（避免误判：要求差值足够大）
            if before[2] > 3.0 and after[2] < 1.0:
                return True
            return False

        def _wait_change(before: tuple[str, float, float], wait_sec: float = 1.6) -> bool:
            deadline = time.time() + max(0.0, wait_sec)
            while time.time() < deadline:
                if _changed(before, _sig()):
                    return True
                time.sleep(0.2)
            return False

        before = _sig()
        self.log(f"模拟滑走：before url={before[0]} dur={before[1]:.1f} cur={before[2]:.1f}")

        # 确保焦点在页面上
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
        except Exception:
            pass

        # 尝试序列（从轻到重）
        attempts: list[tuple[str, callable]] = []

        def _keys_arrow_down() -> None:
            ActionChains(self.driver).send_keys(Keys.ARROW_DOWN).perform()

        def _keys_page_down() -> None:
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()

        def _scroll_by_amount() -> None:
            # Selenium 4: scroll_by_amount（部分环境可用）
            try:
                ActionChains(self.driver).scroll_by_amount(0, 900).perform()
            except Exception:
                self.driver.execute_script("window.scrollBy(0, Math.floor((window.innerHeight||800)*0.9));")

        def _wheel_event_at_center() -> None:
            self.driver.execute_script(
                """
                const dy = Math.floor((window.innerHeight||800)*0.9);
                const x = Math.floor((window.innerWidth||1200)/2);
                const y = Math.floor((window.innerHeight||800)/2);
                const el = document.elementFromPoint(x, y) || document.body;
                const ev = new WheelEvent('wheel', {deltaY: dy, clientX: x, clientY: y, bubbles: true, cancelable: true});
                el.dispatchEvent(ev);
                window.scrollBy(0, dy);
                """,
            )

        def _drag_swipe() -> None:
            # 触控式“上滑”（等价于向下滚动到下一条）
            w = int(self.driver.execute_script("return Math.max(0, window.innerWidth||0)")) or 1200
            h = int(self.driver.execute_script("return Math.max(0, window.innerHeight||0)")) or 800
            x = w // 2
            y1 = int(h * 0.75)
            y2 = int(h * 0.25)
            root = self.driver.find_element(By.TAG_NAME, "html")
            ActionChains(self.driver).move_to_element_with_offset(root, x, y1).click_and_hold().pause(0.05).move_by_offset(0, y2 - y1).pause(0.05).release().perform()

        attempts.extend(
            [
                ("ArrowDown", _keys_arrow_down),
                ("PageDown", _keys_page_down),
                ("scrollByAmount", _scroll_by_amount),
                ("wheelEvent", _wheel_event_at_center),
                ("dragSwipe", _drag_swipe),
            ]
        )

        for name, fn in attempts:
            try:
                self.log(f"模拟滑走：尝试 {name}")
                fn()
            except Exception as e:
                self.log(f"模拟滑走：{name} 异常（{type(e).__name__}: {e}）")
                continue
            if _wait_change(before, wait_sec=1.8):
                after = _sig()
                self.log(f"模拟滑走：成功 {name} after url={after[0]} dur={after[1]:.1f} cur={after[2]:.1f}")
                return True

        after = _sig()
        self.log(f"模拟滑走：失败 after url={after[0]} dur={after[1]:.1f} cur={after[2]:.1f}")
        return False

    # -------------------------
    # 指定视频链接模式
    # -------------------------
    def like_video_url(self, url: str) -> bool:
        self.open(url)
        self.wait_dom_ready()
        time.sleep(1.0)
        return self.like_current_video()

    # -------------------------
    # 调试辅助
    # -------------------------
    def dump_cookies(self, path: Path) -> None:
        try:
            cookies = self.driver.get_cookies()
            path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


