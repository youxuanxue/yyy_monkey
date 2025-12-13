from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True)
class DanmakuConfig:
    wait_timeout_sec: float = 30.0
    interval_sec: float = 0.6


class DanmakuSender:
    """
    抖音网页端“发弹幕”自动化：
    - 通过 placeholder（如“发一条弹幕吧”）等特征定位输入框
    - 自动输入文本并尝试发送（Enter / 点击“发送”按钮）
    """

    def __init__(self, driver: WebDriver, cfg: DanmakuConfig, *, verbose: bool = False) -> None:
        self.driver = driver
        self.cfg = cfg
        self.wait = WebDriverWait(driver, cfg.wait_timeout_sec)
        self.verbose = verbose

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def wait_dom_ready(self) -> None:
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    def maybe_close_popups(self) -> None:
        """
        尝试关闭一些常见弹窗（不保证覆盖所有情况）。
        这里做得很轻量，避免影响其他交互。
        """
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
        尽量找到弹幕输入框。抖音页面 class 名通常是 hash（会变），因此优先用 placeholder/通用语义。
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

        # 兜底：用 XPath 找“placeholder 包含 弹幕”的 input/textarea
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

    def send(self, text: str = "哇塞，赞赞赞") -> bool:
        """
        发送一条弹幕。返回 True 表示已执行“输入+提交”动作；False 表示未找到输入框。
        """
        self.maybe_close_popups()

        try:
            self.wait_dom_ready()
        except Exception:
            # dom ready 只是加速定位，不是硬依赖
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

        # 清空并输入
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

        try:
            box.send_keys(text)
        except Exception:
            # contenteditable 等情况用 ActionChains
            ActionChains(self.driver).send_keys(text).perform()

        time.sleep(0.05)

        # 优先 Enter 提交
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

        # 若页面需要按钮，则再尝试点“发送”
        try:
            btn = self._find_send_button()
            if btn is not None and btn.is_displayed() and btn.is_enabled():
                btn.click()
                submitted = True
        except Exception:
            pass

        time.sleep(self.cfg.interval_sec)
        return submitted


