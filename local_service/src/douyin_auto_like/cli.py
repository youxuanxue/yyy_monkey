from __future__ import annotations

import argparse
import json
import logging
import math
import random
import time
import re
from pathlib import Path

from douyin_auto_like.browser import ChromeConfig, build_chrome_driver, safe_quit
from douyin_auto_like.douyin import DouyinBot, RunConfig


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


def _decide_like_prob(duration_sec: float) -> float:
    # 根据视频时长决定点赞概率：
    # - 10秒以下的短视频：不点赞（可能是广告或低质量内容）
    # - 10秒~3分钟：67% 概率点赞（正常短视频）
    # - 3分钟以上：34% 概率点赞（长视频降低点赞频率）
    if duration_sec < 10:
        return 0.0
    if duration_sec < 180.0:
        return 0.67
    return 0.34


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="抖音网页端自动点赞（Selenium + Chrome，支持复用登录态）")
    p.add_argument("--video-url", default="", help="视频链接（必填）")
    p.add_argument("--interval", type=float, default=2.0, help="每次操作间隔秒数（默认 2.0）")
    p.add_argument("--timeout", type=float, default=30.0, help="显式等待超时秒数（默认 30）")
    p.add_argument("--seed", type=int, default=None, help="随机种子（可选，用于复现概率选择）")
    p.add_argument("--max-likes", type=int, default=0, help="点赞动作总数上限（>0 生效；达到后退出）")
    p.add_argument(
        "--follow",
        action="store_true",
        help="点赞后持续监控：每隔一段时间输出 TICK(JSON)；URL 稳定变化后对新视频继续决策/点赞（遇到 live 跳过）",
    )
    p.add_argument("--check-interval", type=float, default=5.0, help="follow 模式 URL 检测间隔秒数（默认 5）")
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
        # local_service/src/douyin_auto_like/cli.py -> parents[2] == local_service/
        default=str(Path(__file__).resolve().parents[2] / ".chrome_profile"),
        help="Chrome Profile 目录（用于复用登录态）",
    )
    p.add_argument("--headless", action="store_true", help="无头模式（首次扫码登录不建议）")
    p.add_argument(
        "--manual-login",
        action="store_true",
        help="打开页面后暂停，等待你手动扫码/登录完成后再继续（推荐首次使用开启）",
    )
    p.add_argument(
        "--dump-cookies",
        default="",
        help="把 cookies 导出为 JSON 文件路径（可选，用于排查登录态）",
    )
    p.add_argument("--verbose", action="store_true", help="输出更详细的执行日志（定位/兜底过程）")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    # 日志：按启动时间创建文件，并同步输出到终端
    base_dir = Path(__file__).resolve().parents[2]
    logger = _setup_logger(base_dir / "logs")

    if args.seed is not None:
        random.seed(int(args.seed))

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    chrome_cfg = ChromeConfig(profile_dir=profile_dir, headless=bool(args.headless))
    run_cfg = RunConfig(wait_timeout_sec=float(args.timeout), interval_sec=float(args.interval))

    driver = None
    try:
        logger.info("douyin-like 启动：headless=%s timeout=%s interval=%s follow=%s check_interval=%s max_likes=%s",
                    bool(args.headless), args.timeout, args.interval, bool(args.follow), args.check_interval, args.max_likes)
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

        liked_count = 0

        # 播放速率固定 1.5（并尽量确保生效）
        bot.ensure_playback_rate(1.5, wait_sec=2.0)

        # 概率：按时长分档
        dur = _get_duration_sec(bot, wait_sec=5.0)
        p = _decide_like_prob(dur)
        roll = random.random()
        like_this = roll < p
        logger.info("决策：duration=%.2fs prob=%.2f roll=%.4f like=%s", dur, p, roll, like_this)

        if like_this:
            logger.info("开始尝试点赞当前视频...")
            did_click = bot.like_current_video()
            if did_click:
                liked_count += 1
                logger.info("点赞动作完成（累计=%d）", liked_count)
            else:
                logger.info("未执行点赞（可能无 video 或 live）")
            # 点赞/双击后，抖音有时会暂停播放器；这里主动恢复播放
            bot.ensure_playing(wait_sec=2.0)
        else:
            logger.info("未命中概率：不点赞，模拟滑走到下一条")
            bot.swipe_next()

        if int(args.max_likes) > 0 and liked_count >= int(args.max_likes):
            logger.info("达到 max_likes=%s，退出。", args.max_likes)
            return

        if args.follow:
            last_processed_url = bot.safe_current_url()
            stable_url = last_processed_url
            stable_count = 0
            # 超过 3 分钟自动划走（避免长视频卡住不切换）
            max_watch_sec = 180.0
            last_force_swipe_ts = 0.0
            seen_modal_ids: set[str] = set()
            modal_re = re.compile(r"[?&]modal_id=([0-9]+)")

            def _modal_id(url: str) -> str:
                m = modal_re.search(url or "")
                return m.group(1) if m else ""

            # 把启动时的 modal_id 也加入已见集合（如果有）
            mid0 = _modal_id(last_processed_url)
            if mid0:
                seen_modal_ids.add(mid0)
            logger.info("进入 follow 模式：每 %.1fs 检测 URL 变化（Ctrl+C 结束）", float(args.check_interval))

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
                new_bot.ensure_playback_rate(1.5, wait_sec=2.0)
                return new_bot
            while True:
                time.sleep(float(args.check_interval))
                cur_url = bot.safe_current_url()
                # 同时输出页面与视频信息（方便按 URL 回溯检查）
                pi = bot.get_page_info()
                title = pi.get("og_title") or pi.get("h1") or pi.get("doc_title") or ""
                st = bot.get_video_state()
                # 若被页面重置了倍速，自动校准回 1.5
                if st.get("has_video") and abs(float(st.get("playback_rate", 0.0) or 0.0) - 1.5) > 0.05:
                    bot.ensure_playback_rate(1.5, wait_sec=1.2)
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

                # current_time 超过 3 分钟后自动划走（非 live 场景）
                if st.get("has_video") and not bot.is_live_url(cur_url):
                    try:
                        ct = float(st.get("current_time", 0.0) or 0.0)
                    except Exception:
                        ct = 0.0
                    now = time.time()
                    cooldown = max(2.0, float(args.check_interval))
                    if ct >= max_watch_sec and (now - last_force_swipe_ts) >= cooldown:
                        logger.info("current_time=%.1fs 超过 %.0fs，自动划走到下一条", ct, max_watch_sec)
                        bot.swipe_next()
                        last_force_swipe_ts = now
                        # 划走后让下一轮重新观察 URL 稳定变化
                        stable_url = bot.safe_current_url()
                        stable_count = 0
                        continue

                # URL 去抖：必须连续出现 2 次才认为已“稳定切换”
                if cur_url == stable_url:
                    stable_count += 1
                else:
                    stable_url = cur_url
                    stable_count = 1

                # 只有稳定 2 次，且与上次已处理 URL 不同，才进入处理逻辑
                if stable_count < 2 or not stable_url or stable_url == last_processed_url:
                    continue

                logger.info("URL 变化已稳定：%s -> %s", last_processed_url, stable_url)
                last_processed_url = stable_url

                # 回跳/震荡保护：如果 modal_id 已经见过，认为发生回跳，直接滑走
                mid = _modal_id(stable_url)
                if mid:
                    if mid in seen_modal_ids:
                        logger.info("检测到 modal_id 回跳（%s），跳过处理并继续滑走", mid)
                        bot.swipe_next()
                        continue
                    seen_modal_ids.add(mid)

                if bot.is_live_url(stable_url):
                    logger.info("检测到 live URL：跳过点赞；尝试滑走离开")
                    bot.swipe_next()
                    continue

                if args.restart_driver_on_change:
                    bot = _restart_driver_and_open(stable_url)
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
                bot.ensure_playback_rate(1.5, wait_sec=2.0)

                dur = _get_duration_sec(bot, wait_sec=5.0)
                p = _decide_like_prob(dur)
                roll = random.random()
                like_this = roll < p
                logger.info("决策：duration=%.2fs prob=%.2f roll=%.4f like=%s", dur, p, roll, like_this)

                if like_this:
                    logger.info("对新视频尝试点赞...")
                    did_click = bot.like_current_video()
                    if did_click:
                        liked_count += 1
                        logger.info("点赞动作完成（累计=%d）", liked_count)
                    else:
                        logger.info("未执行点赞（可能无 video 或 live）")
                    bot.ensure_playing(wait_sec=2.0)
                    if int(args.max_likes) > 0 and liked_count >= int(args.max_likes):
                        logger.info("达到 max_likes=%s，退出。", args.max_likes)
                        return
                else:
                    logger.info("未命中概率：不点赞，模拟滑走到下一条")
                    bot.swipe_next()

        if args.dump_cookies:
            bot.dump_cookies(Path(args.dump_cookies).expanduser().resolve())
    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()


