from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from douyin_auto_like.browser import ChromeConfig, build_chrome_driver, safe_quit
from douyin_auto_like.douyin import DouyinBot, RunConfig


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="抖音网页端自动点赞（Selenium + Chrome，支持复用登录态）")
    p.add_argument("--video-url", default="", help="视频链接（必填）")
    p.add_argument("--interval", type=float, default=2.0, help="每次操作间隔秒数（默认 2.0）")
    p.add_argument("--timeout", type=float, default=30.0, help="显式等待超时秒数（默认 30）")
    p.add_argument("--like-prob", type=float, default=0.67, help="对每个视频执行点赞动作的概率（0~1，默认 0.67）")
    p.add_argument("--seed", type=int, default=None, help="随机种子（可选，用于复现概率选择）")
    p.add_argument(
        "--follow",
        action="store_true",
        help="点赞后持续监控：每隔一段时间打印 URL；URL 变化则对新视频继续点赞（遇到 live 跳过）",
    )
    p.add_argument("--check-interval", type=float, default=10.0, help="follow 模式 URL 检测间隔秒数（默认 10）")
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

    if args.seed is not None:
        random.seed(int(args.seed))
    like_prob = float(args.like_prob)
    if not (0.0 <= like_prob <= 1.0):
        raise SystemExit("--like-prob 必须在 0~1 之间")

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    chrome_cfg = ChromeConfig(profile_dir=profile_dir, headless=bool(args.headless))
    run_cfg = RunConfig(wait_timeout_sec=float(args.timeout), interval_sec=float(args.interval))

    driver = None
    try:
        _log(f"douyin-like 启动：headless={bool(args.headless)}, timeout={args.timeout}, interval={args.interval}")
        _log(f"使用 profile_dir={profile_dir}")
        _log("正在启动 Chrome WebDriver（如首次需要下载/查找 driver，可能会等待一段时间）...")
        driver = build_chrome_driver(chrome_cfg)
        _log("WebDriver 启动成功。")
        bot = DouyinBot(driver, run_cfg, verbose=bool(args.verbose))

        if not args.video_url:
            raise SystemExit("必须提供 --video-url")
        _log(f"打开视频链接：{args.video_url}")
        bot.open(args.video_url)
        bot.wait_dom_ready()
        _log(f"页面已加载：title={bot.safe_title()}")
        if args.manual_login:
            bot.pause_for_manual_login()
            _log("已继续执行（收到回车）。")
        like_this = random.random() < like_prob
        # 播放速率策略：命中点赞=1.5x；未命中=2.0x
        target_rate = 1.5 if like_this else 2.0
        bot.set_playback_rate(target_rate)

        if like_this:
            _log(f"命中点赞概率（p={like_prob:.2f}）：开始尝试点赞当前视频...")
            did_click = bot.like_current_video()
            print("完成：已执行双击点赞动作" if did_click else "未找到可操作的视频元素或 live（未执行双击）")
        else:
            _log(f"未命中点赞概率（p={like_prob:.2f}）：跳过当前视频点赞")

        if args.follow:
            last_url = bot.safe_current_url()
            _log(f"进入 follow 模式：每 {float(args.check_interval)}s 检测 URL 变化（Ctrl+C 结束）")
            while True:
                time.sleep(float(args.check_interval))
                cur_url = bot.safe_current_url()
                print(f"URL {cur_url}", flush=True)

                # 可选：打印播放状态（仅 verbose 时）
                if args.verbose:
                    st = bot.get_video_state()
                    if st.get("has_video"):
                        bot.log(
                            f"video_state current={st.get('current_time'):.1f}s duration={st.get('duration'):.1f}s paused={st.get('paused')} ended={st.get('ended')}"
                        )

                if cur_url and cur_url != last_url:
                    _log(f"检测到 URL 变化：{last_url} -> {cur_url}")
                    last_url = cur_url
                    if bot.is_live_url(cur_url):
                        _log("检测到 live URL：跳过点赞")
                        continue
                    try:
                        bot.wait_dom_ready()
                    except Exception:
                        pass
                    time.sleep(0.8)
                    like_this = random.random() < like_prob
                    target_rate = 1.5 if like_this else 2.0
                    bot.set_playback_rate(target_rate)
                    if like_this:
                        _log(f"命中点赞概率（p={like_prob:.2f}）：对新视频继续点赞...")
                        bot.like_current_video()
                    else:
                        _log(f"未命中点赞概率（p={like_prob:.2f}）：跳过新视频点赞")

        if args.dump_cookies:
            bot.dump_cookies(Path(args.dump_cookies).expanduser().resolve())
    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()


