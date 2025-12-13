from __future__ import annotations

import argparse
import time
from pathlib import Path

from douyin_auto_like.browser import ChromeConfig, build_chrome_driver, safe_quit
from douyin_auto_like.danmaku import DanmakuConfig, DanmakuSender


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="抖音网页端自动发弹幕（Selenium + Chrome，支持复用登录态）")
    p.add_argument("--video-url", default="", help="视频链接（必填）")
    p.add_argument("--text", default="哇塞，赞赞赞", help="弹幕内容（默认：哇塞，赞赞赞）")
    p.add_argument("--timeout", type=float, default=30.0, help="显式等待超时秒数（默认 30）")
    p.add_argument("--interval", type=float, default=0.6, help="发送后等待秒数（默认 0.6）")
    p.add_argument(
        "--profile-dir",
        # local_service/src/douyin_auto_like/danmaku_cli.py -> parents[2] == local_service/
        default=str(Path(__file__).resolve().parents[2] / ".chrome_profile"),
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


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not args.video_url:
        raise SystemExit("必须提供 --video-url")

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    chrome_cfg = ChromeConfig(profile_dir=profile_dir, headless=bool(args.headless))
    dan_cfg = DanmakuConfig(wait_timeout_sec=float(args.timeout), interval_sec=float(args.interval))

    driver = None
    try:
        _log(f"douyin-danmaku 启动：headless={bool(args.headless)}, timeout={args.timeout}, interval={args.interval}")
        _log(f"使用 profile_dir={profile_dir}")
        _log(f"打开视频链接：{args.video_url}")
        driver = build_chrome_driver(chrome_cfg)
        driver.get(args.video_url)

        sender = DanmakuSender(driver, dan_cfg, verbose=bool(args.verbose))
        try:
            sender.wait_dom_ready()
        except Exception:
            pass
        time.sleep(1.0)

        if args.manual_login:
            cur = ""
            try:
                cur = driver.current_url
            except Exception:
                pass
            print(f"请在打开的浏览器里手动扫码登录完成后，回到终端按回车继续...\n(当前页面：{cur})", flush=True)
            input()
            _log("已继续执行（收到回车）。")

        ok = sender.send(str(args.text))
        print("完成：已尝试发送弹幕" if ok else "失败：未找到弹幕输入框（未发送）")
    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()


