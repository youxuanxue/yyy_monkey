"""
命令行入口
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import time
import re
import base64
from itertools import cycle
from pathlib import Path

from douyin_auto_like.browser import ChromeConfig, build_chrome_driver, safe_quit
from douyin_auto_like.douyin import DouyinBot, RunConfig

# ---------------------------------------------------------------------------
# 评论/弹幕文本库加载
# ---------------------------------------------------------------------------
_COMMENTS: list[str] = []
_DANMAKUS: list[str] = []
_ENC_KEY = "douyin-monkey-2025-secret"

def _xor_decrypt(data: bytes, key: str) -> str:
    """Base64 decode -> XOR decrypt -> utf-8 decode"""
    try:
        raw_bytes = base64.b64decode(data)
        key_bytes = key.encode("utf-8")
        decrypted_bytes = bytes(a ^ b for a, b in zip(raw_bytes, cycle(key_bytes)))
        return decrypted_bytes.decode("utf-8")
    except Exception:
        return ""

import sys

def _load_text_files() -> None:
    """启动时加载 data/comments.enc 和 data/danmaku.enc (支持回退到 txt)"""
    global _COMMENTS, _DANMAKUS
    
    # 兼容 PyInstaller 打包后的路径
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        # 策略1：优先读取 exe 同级目录下的 data 文件夹（方便用户替换）
        # 策略2：如果同级没有，读取打包在内部的资源 (sys._MEIPASS)
        exe_dir = Path(sys.executable).parent
        external_data = exe_dir / "data"
        if external_data.exists():
            base_dir = external_data
        else:
            base_dir = Path(getattr(sys, "_MEIPASS", exe_dir)) / "data"
    else:
        # 开发模式
        base_dir = Path(__file__).resolve().parent.parent.parent / "data"

    # Load comments
    c_enc = base_dir / "comments.enc"
    c_txt = base_dir / "comments.txt"
    raw_text = ""
    if c_enc.exists():
        raw_text = _xor_decrypt(c_enc.read_bytes(), _ENC_KEY)
    elif c_txt.exists():
        raw_text = c_txt.read_text(encoding="utf-8")
    
    if raw_text:
        _COMMENTS = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Load danmaku
    d_enc = base_dir / "danmaku.enc"
    d_txt = base_dir / "danmaku.txt"
    raw_text = ""
    if d_enc.exists():
        raw_text = _xor_decrypt(d_enc.read_bytes(), _ENC_KEY)
    elif d_txt.exists():
        raw_text = d_txt.read_text(encoding="utf-8")

    if raw_text:
        _DANMAKUS = [line.strip() for line in raw_text.splitlines() if line.strip()]


# 模块加载时执行
_load_text_files()


def _setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"douyin-like_{ts}.log"

    logger = logging.getLogger("douyin-like")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 防止重复添加 handler（例如在交互环境重复调用）
    if logger.handlers:
        return logger

    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)

    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.info("日志文件：%s", log_path)
    return logger

def _maybe_send_like(bot: DouyinBot, max_wait:float, logger: logging.Logger) -> int:
    """
    根据视频时长和随机概率决定是否点赞。
    - 短于 10s：不点赞。
    - 长于 10s：49% 概率点赞。
    
    如果决定点赞，会先调用 _simulate_watch 观看一段时间，然后执行点赞动作。
    返回 1 表示尝试了点赞，0 表示未点赞。
    """
    dur = _get_duration_sec(bot, wait_sec=2.0)
    # 根据视频时长决定点赞概率：
    # - 10秒以下的短视频：不点赞（可能是广告或低质量内容）
    # - 其余时长：49% 概率点赞
    if dur < 10:
        p = 0.0
        return 0
    else:
        p = 0.49
    
    roll = random.random()
    if roll >= p:
        logger.info("点赞：未命中概率：prob=%.2f roll=%.4f（跳过）", p, roll)
        return 0
    
    try:
        logger.info("点赞：命中概率：prob=%.2f roll=%.4f(模拟观看)", p, roll)
        _simulate_watch(bot, max_wait, logger)
        logger.info("点赞：命中概率：prob=%.2f roll=%.4f（尝试发送）", p, roll)
        ok = bot.like_current_video()
        logger.info("点赞%s", "已尝试发送" if ok else "未发送")
        if ok: 
            return 1
        else:
            return 0
    except Exception as e:
        logger.info("点赞：发送异常（%s: %s）", type(e).__name__, e)
        return 0


def _maybe_send_danmaku(bot: DouyinBot, text: str, *, prob: float, logger: logging.Logger) -> int:
    """
    在“命中点赞决策”的视频中，再以 prob 的概率尝试发送弹幕。
    失败（未找到输入框/页面限制等）只记录日志，不影响主流程。
    """
    try:
        p = float(prob)
    except Exception:
        p = 0.0
    if p <= 0:
        return 0

    roll = random.random()
    if roll >= p:
        logger.info("弹幕：未命中概率：prob=%.2f roll=%.4f（跳过）", p, roll)
        return 0

    try:
        logger.info("弹幕：命中概率：prob=%.2f roll=%.4f（尝试发送）", p, roll)
        ok = bot.send_danmaku(str(text))
        logger.info("弹幕：%s", "已尝试发送" if ok else "未找到输入框/未发送")
        if ok: 
            return 1
        else:
            return 0
    except Exception as e:
        logger.info("弹幕：发送异常（%s: %s）", type(e).__name__, e)
        return 0


def _maybe_send_comment(bot: DouyinBot, text: str, *, prob: float, logger: logging.Logger) -> int:
    """
    在“命中点赞决策”的视频中，再以 prob 的概率尝试发送评论。
    """
    try:
        p = float(prob)
    except Exception:
        p = 0.0
    if p <= 0:
        return 0

    roll = random.random()
    if roll >= p:
        logger.info("评论：未命中概率：prob=%.2f roll=%.4f（跳过）", p, roll)
        return 0

    try:
        logger.info("评论：命中概率：prob=%.2f roll=%.4f（尝试发送）", p, roll)
        ok = bot.send_comment(str(text))
        logger.info("评论：%s", "已成功发送并验证" if ok else "发送失败或未验证")
        if ok: 
            return 1
        else:
            return 0
    except Exception as e:
        logger.info("评论：发送异常（%s: %s）", type(e).__name__, e)
        return 0


def _get_duration_sec(bot: DouyinBot, *, wait_sec: float = 5.0) -> float:
    """
    尽量等待 video metadata 可用，拿到 duration（秒）。
    返回 0 表示未拿到。
    """
    deadline = time.time() + max(0.0, float(wait_sec))
    while time.time() < deadline:
        st = bot.get_video_state()
        if st.get("has_video"):
            dur = float(st.get("duration", 0.0) or 0.0)
            if not math.isnan(dur) and dur > 0.1:
                return dur
        time.sleep(0.2)
    return 0.0

def build_parser() -> argparse.ArgumentParser:
    # 确定默认 profile 目录
    if getattr(sys, 'frozen', False):
        # exe 模式：在 exe 同级目录下的 .chrome_profile
        base = Path(sys.executable).parent
    else:
        # 开发模式：local_service/
        base = Path(__file__).resolve().parents[2]
        
    p = argparse.ArgumentParser(description="抖音网页端自动点赞（Selenium + Chrome，支持复用登录态）")
    p.add_argument(
        "--mode",
        choices=["danmaku", "comment", "follow", "open"],
        default="follow",
        help="follow=follow模式下全自动(点赞+弹幕+评论); danmaku/comment=单次发送; open=调试",
    )
    p.add_argument("--video-url", default="https://www.douyin.com/jingxuan?modal_id=7577987307542720243", help="视频链接")
    p.add_argument("--max-likes", type=int, default=10, help="点赞动作总数上限（>0 生效；达到后退出）")
    p.add_argument(
        "--restart-driver-on-change",
        action="store_true",
        help="follow 模式下 URL 变化时重启 WebDriver（复用 profile），用于强制刷新页面信息（更慢但更稳）",
    )
    p.add_argument(
        "--refresh-on-change",
        action="store_true",
        help="follow 模式下 URL 变化时先 driver.refresh() 再抓信息（比重启更轻量）",
    )
    p.add_argument(
        "--profile-dir",
        default=str(base / ".chrome_profile"),
        help="Chrome Profile 目录（用于复用登录态）",
    )
    p.add_argument("--headless", action="store_true", help="无头模式（首次扫码登录不建议）")
    p.add_argument(
        "--manual-login",
        action="store_true",
        help="打开页面后暂停，等待你手动扫码/登录完成后再继续（推荐首次使用开启）",
    )
    p.add_argument("--verbose", action="store_true", help="输出更详细的执行日志（定位/兜底过程）")
    return p


def _simulate_watch(bot: DouyinBot, max_wait: float, logger: logging.Logger) -> None:
    """
    模拟人类观看：在进行互动（点赞/评论/弹幕）之前，随机等待一段时间。
    策略：
    - 视频时长 < 5s：观看大部分时长（50%~90%）
    - 视频时长 >= 5s：随机观看 5s ~ max_wait（但不超过视频剩余时长）
    """
    dur = _get_duration_sec(bot, wait_sec=5.0)
    
    # 默认等待区间 [5.0, max_wait]
    min_wait = 5.0
    
    if dur > 0.1:
        if dur < 5.0:
            # 极短视频：观看 50% ~ 90% (按实际播放时长算)
            wait_time = dur * random.uniform(0.5, 0.9)
        else:
            # 正常/长视频：观看 5s ~ 2min，且不超过 real_duration * 0.9
            upper = min(max_wait, dur * 0.9)
            if upper < min_wait:
                upper = min_wait
            wait_time = random.uniform(min_wait, upper)
    else:
        # 获取不到 duration，保守等待 5~10s
        wait_time = random.uniform(5.0, 10.0)
    
    logger.info("模拟观看：计划等待 %.2fs, duration=%.1fs...", wait_time, dur)
    
    # 分段 sleep，期间检查播放状态与验证码
    start_ts = time.time()
    deadline = start_ts + wait_time
    
    while time.time() < deadline:
        # 1. 验证码检测
        if hasattr(bot, "_handle_verification_if_present"):
            bot._handle_verification_if_present()
            
        # 2. 检查是否已播完 (提前结束)
        st = bot.get_video_state()
        if st.get("has_video"):
            is_ended = bool(st.get("ended", False))
            cur_t = float(st.get("current_time", 0.0) or 0.0)
            total_t = float(st.get("duration", 0.0) or 0.0)
            
            # 如果已结束，或进度已超过 90% (且等待已超过 5s，避免刚开始就误判)
            if (is_ended or (total_t > 0 and cur_t > total_t * 0.9)) and (time.time() - start_ts > 5.0):
                logger.info("视频已播完 (%.1fs / %.1fs)，提前结束等待", cur_t, total_t)
                break

        left = deadline - time.time()
        if left <= 0:
            break
            
        # 3. 确保播放中
        step = min(left, 2.0)
        time.sleep(step)
        bot.ensure_playing(wait_sec=0.1)

def get_text(for_what: str) -> str:
    """从预加载的文本库中随机返回一条评论或弹幕"""
    if for_what == "comment":
        return random.choice(_COMMENTS) if _COMMENTS else "好开心看到你的视频"
    elif for_what == "danmaku":
        return random.choice(_DANMAKUS) if _DANMAKUS else "哇塞，赞赞赞"
    else:
        return ""

def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    # 日志：按启动时间创建文件，并同步输出到终端
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).resolve().parents[2]

    logger = _setup_logger(base_dir / "logs")

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    chrome_cfg = ChromeConfig(profile_dir=profile_dir, headless=bool(args.headless))
    run_cfg = RunConfig()

    driver = None
    try:
        logger.info("douyin-like 启动：headless=%s mode=%s max_likes=%s",
                    bool(args.headless), args.mode, args.max_likes)
        logger.info("使用 profile_dir=%s", profile_dir)
        logger.info("正在启动 Chrome WebDriver（如首次需要下载/查找 driver，可能会等待一段时间）...")
        driver = build_chrome_driver(chrome_cfg)
        logger.info("WebDriver 启动成功。")
        bot = DouyinBot(driver, run_cfg, verbose=bool(args.verbose))

        if not args.video_url:
            raise SystemExit("必须提供 --video-url")
        logger.info("打开视频链接：%s", args.video_url)
        bot.open(args.video_url)
        bot.wait_dom_ready()
        pi0 = bot.get_page_info()
        logger.info("页面已加载：doc_title=%s og_title=%s", pi0.get("doc_title", ""), pi0.get("og_title", ""))
        if args.manual_login:
            bot.pause_for_manual_login()
            logger.info("已继续执行（收到回车）。")

        # mode=open：仅打开页面并暂停，方便你手工走流程/调试 DOM（不做任何自动化动作）
        if str(args.mode) == "open":
            logger.info("mode=open：已打开页面。你可以在浏览器里手动操作/调试（完成后回车退出并关闭浏览器）")
            bot.pause_for_manual_login(prompt="浏览器已打开，请手工操作/调试完成后回到终端按回车退出...")
            return

        # mode=danmaku/comment：发送后退出（不走后续点赞/follow 流程）
        if str(args.mode) == "danmaku":
            _simulate_watch(bot, 10.0, logger)
            txt = get_text("danmaku")
            logger.info("mode=danmaku：准备发送弹幕：%s", txt)
            ok = bot.send_danmaku(txt)
            if ok:
                logger.info("完成：已尝试发送弹幕")
            else:
                logger.info("失败：未找到弹幕输入框（未发送）")
            return
        if str(args.mode) == "comment":
            _simulate_watch(bot, 10.0, logger)
            txt = get_text("comment")
            logger.info("mode=comment：准备发送评论：%s", txt)
            ok = bot.send_comment(txt)
            if ok:
                logger.info("完成：已确认评论发送成功（评论列表已出现该文本）")
            else:
                logger.info("失败：未确认评论发送成功（可能触发验证/风控/页面未刷新/未找到输入框）")
            return
        
        if str(args.mode) == "follow":
            liked_count = 0
            commented_count = 0
            danmakued_count = 0
            last_url = bot.safe_current_url()
            seen_modal_ids: set[str] = set()
            modal_re = re.compile(r"[?&]modal_id=([0-9]+)")

            def _modal_id(url: str) -> str:
                m = modal_re.search(url or "")
                return m.group(1) if m else ""

            def _restart_driver_and_open(url: str) -> DouyinBot:
                nonlocal driver
                logger.info("重启 WebDriver（用于强制刷新页面信息）...")
                safe_quit(driver)
                driver = build_chrome_driver(chrome_cfg)
                logger.info("WebDriver 重启成功。打开：%s", url)
                new_bot = DouyinBot(driver, run_cfg, verbose=bool(args.verbose))
                new_bot.open(url)
                try:
                    new_bot.wait_dom_ready()
                except Exception:
                    pass
                time.sleep(0.6)
                return new_bot
            while liked_count < int(args.max_likes):
                cur_url = bot.safe_current_url()
                # 同时输出页面与视频信息（方便按 URL 回溯检查）
                pi = bot.get_page_info()
                title = pi.get("og_title") or pi.get("h1") or pi.get("doc_title") or ""
                st = bot.get_video_state()
                # 若播放器被暂停，主动恢复播放（避免一直停在同一帧）
                if st.get("has_video") and bool(st.get("paused", False)) and not bool(st.get("ended", False)):
                    bot.ensure_playing(wait_sec=1.2)
                    st = bot.get_video_state()
                tick_payload = {
                    "url": cur_url,
                    "title": title,
                    "has_video": bool(st.get("has_video", False)),
                }
                if st.get("has_video"):
                    def _f(v, default: float = 0.0) -> float:
                        try:
                            x = float(v if v is not None else default)
                            if math.isnan(x):
                                return float(default)
                            return x
                        except Exception:
                            return float(default)

                    tick_payload.update(
                        {
                            "current_time": _f(st.get("current_time", 0.0), 0.0),
                            "duration": _f(st.get("duration", 0.0), 0.0),
                            "playback_rate": _f(st.get("playback_rate", 1.0), 1.0),
                            "paused": bool(st.get("paused", False)),
                            "ended": bool(st.get("ended", False)),
                            "ready_state": int(st.get("ready_state", 0) or 0),
                        }
                    )
                logger.info("TICK %s", json.dumps(tick_payload, ensure_ascii=False))

                # 回跳/震荡保护：如果 modal_id 已经见过，认为发生回跳，直接滑走
                mid = _modal_id(cur_url)
                if mid:
                    if mid in seen_modal_ids:
                        logger.info("检测到 modal_id 回跳（%s），跳过处理并继续滑走", mid)
                        bot.swipe_next()
                        continue
                    seen_modal_ids.add(mid)

                if bot.is_live_url(cur_url):
                    logger.info("检测到 live URL：跳过点赞；尝试滑走离开")
                    bot.swipe_next()
                    continue

                # 仅当 URL 发生变化（切换到了新视频）时，才尝试重启/刷新机制
                if cur_url != last_url:
                    if args.restart_driver_on_change:
                        bot = _restart_driver_and_open(cur_url)
                    elif args.refresh_on_change:
                        try:
                            logger.info("refresh-on-change：driver.refresh()")
                            bot.driver.refresh()
                        except Exception:
                            pass

                try:
                    bot.wait_dom_ready()
                except Exception:
                    pass
                time.sleep(0.8)

                # 1. 点赞决策
                # 注意：_maybe_send_like 内部会根据时长进行 _simulate_watch，如果决定点赞
                if _maybe_send_like(bot, 30.0, logger) > 0:
                    liked_count += 1
                    logger.info("点赞动作完成（累计=%d）", liked_count)
                    
                    # 2. 评论 
                    commented_count += _maybe_send_comment(bot, get_text("comment"), prob=0.67, logger=logger)
                    logger.info("评论动作完成（累计=%d）", commented_count)
                    
                    # 3. 弹幕 
                    danmakued_count += _maybe_send_danmaku(bot, get_text("danmaku"), prob=0.46, logger=logger)
                    logger.info("弹幕动作完成（累计=%d）", danmakued_count)

                    # 4. 点赞/双击后，抖音有时会暂停播放器；这里主动恢复播放
                    bot.ensure_playing(wait_sec=2.0)
                    
                    # 5. 模拟观看剩余部分（或一段时间）并滑走
                    _simulate_watch(bot, 60.0, logger)
                    bot.swipe_next()
                else:
                    logger.info("未命中概率：不点赞")
                    # 即使不点赞，也稍微看一会再走，避免秒滑被判定机器人
                    _simulate_watch(bot, random.uniform(3.0, 8.0), logger)
                    logger.info("模拟滑走到下一条")
                    bot.swipe_next()
                
                # prepare next
                last_url = cur_url
                time.sleep(2.0)

    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()
