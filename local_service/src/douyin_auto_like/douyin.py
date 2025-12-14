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
        self.driver.get(url)

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

    def maybe_close_popups(self) -> None:
        """
        尝试关闭一些常见弹窗（不保证覆盖所有情况）。
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


