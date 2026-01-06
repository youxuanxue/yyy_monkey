"""
抖音网页端自动互动助手 - 命令行入口

基于 LLM 评分的智能互动模式，支持自动点赞和评论。
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import re
import sys
import time
from pathlib import Path

from douyin_auto_like.browser import ChromeConfig, build_chrome_driver, safe_quit
from douyin_auto_like.douyin import DouyinBot, RunConfig
from douyin_auto_like.license import verify_license


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
    
    # 同时配置 wechat-bot logger，让 llm_client 的日志也能输出
    wechat_logger = logging.getLogger("wechat-bot")
    wechat_logger.setLevel(logging.INFO)
    wechat_logger.propagate = False
    if not wechat_logger.handlers:
        wechat_logger.addHandler(sh)
        wechat_logger.addHandler(fh)
    
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

def build_parser() -> argparse.ArgumentParser:
    # 确定默认 profile 目录
    if getattr(sys, 'frozen', False):
        # exe 模式：在 exe 同级目录下的 .chrome_profile
        base = Path(sys.executable).parent
    else:
        # 开发模式：local_service/
        base = Path(__file__).resolve().parents[2]
        
    p = argparse.ArgumentParser(description="抖音网页端智能互动助手（基于 LLM 评分，支持自动点赞和评论）")
    p.add_argument(
        "--mode",
        choices=["follow", "open"],
        default="follow",
        help="follow=智能互动模式(基于LLM评分); open=调试模式",
    )
    
    p.add_argument("--video-url", default="https://www.douyin.com/jingxuan/child?modal_id=7573246357294003791", help="视频链接")
    p.add_argument("--max-interactions", type=int, default=17, help="互动动作总数上限（>0 生效；达到后退出）")
    p.add_argument(
        "--profile-dir",
        default=str(base / ".chrome_profile"),
        help="Chrome Profile 目录（用于复用登录态）",
    )
    p.add_argument(
        "--manual-login",
        action="store_true",
        help="打开页面后暂停，等待你手动扫码/登录完成后再继续（推荐首次使用开启）",
    )
    p.add_argument("--verbose", action="store_true", help="输出更详细的执行日志（定位/兜底过程）")
    return p


def _simulate_watch(bot: DouyinBot, max_wait: float, logger: logging.Logger) -> None:
    """
    模拟人类观看：在进行互动（点赞/评论）之前，随机等待一段时间。
    策略：
    - 视频时长 < 5s：观看大部分时长（40%~80%）
    - 视频时长 >= 5s：随机观看 5s ~ max_wait（但不超过视频剩余时长）
    """
    dur = _get_duration_sec(bot, wait_sec=5.0)
    
    # 默认等待区间 [5.0, max_wait]
    min_wait = 5.0
    
    if dur > 0.1:
        if dur < 5.0:
            wait_time = dur * random.uniform(0.4, 0.8)
        else:
            upper = min(max_wait, dur * 0.8)
            if upper < min_wait:
                upper = min_wait
            wait_time = random.uniform(min_wait, upper)
    else:
        # 获取不到 duration，保守等待 3~5s
        wait_time = random.uniform(3.0, 5.0)
    
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

def main(argv: list[str] | None = None) -> None:
    """
    主函数：启动抖音智能互动助手
    
    Args:
        argv: 命令行参数列表（用于测试）
    """
    # 1. 校验 License
    verify_license()
    
    # 2. 解析命令行参数
    args = build_parser().parse_args(argv)

    # 3. 设置日志
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).resolve().parents[2]

    logger = _setup_logger(base_dir / "logs")

    # 4. 初始化配置
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    chrome_cfg = ChromeConfig(profile_dir=profile_dir, headless=False)
    run_cfg = RunConfig()

    # 5. 启动浏览器和 Bot
    driver = None
    try:
        logger.info("douyin-like 启动：mode=%s max_interactions=%s",
                    args.mode, args.max_interactions)
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

        # mode=follow：智能互动模式（基于 LLM 评分）
        if str(args.mode) == "follow":
            # 初始化统计变量
            liked_count = 0
            commented_count = 0
            interactived_count = 0
            last_url = bot.safe_current_url()
            seen_modal_ids: set[str] = set()
            modal_re = re.compile(r"[?&]modal_id=([0-9]+)")

            def _modal_id(url: str) -> str:
                """从 URL 中提取 modal_id"""
                m = modal_re.search(url or "")
                return m.group(1) if m else ""

            # 主循环：智能互动逻辑
            while interactived_count < int(args.max_interactions):
                cur_url = bot.safe_current_url()
                
                # 仅当 URL 发生变化（切换到了新视频）时，直接使用 driver.get() 强制刷新
                if cur_url != last_url:
                    bot.driver.get(cur_url)
                    try:
                        bot.wait_dom_ready()
                    except Exception:
                        pass
                    time.sleep(0.8)  # 等待页面内容稳定
                
                last_url = cur_url
                
                # 同时输出页面与视频信息（方便按 URL 回溯检查）
                pi = bot.get_page_info()
                title = pi.get("og_title") or pi.get("h1") or pi.get("doc_title") or ""
                if not title:
                    logger.warning("无法获取页面标题，跳过此视频")
                    bot.swipe_next()
                    continue

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

                # ========== 智能互动逻辑（基于 LLM 评分）==========
                # 1. 使用 LLM 生成评论结果（基于 task_prompt.json）
                result = bot.generate_comment_from_task(title)
                if not result:
                    bot.swipe_next()
                    continue
                
                # 2. 解析评分并决定互动策略
                interactived = False
                real_human_score = result.get("real_human_score", 0.0)
                persona_consistency_score = result.get("persona_consistency_score", 0.0)
                # 注意：follow_back_score 不再用于决定是否关注，仅作为 LLM 返回的评分之一
                
                # 互动策略：
                # - persona_consistency_score < 0.8 或 real_human_score < 0.8 → 跳过互动
                # - 其他情况 → 点赞 + 评论
                if persona_consistency_score < 0.8 or real_human_score < 0.8:
                    logger.info(
                        f"评分不达标 (consistency={persona_consistency_score:.2f}<0.8 或 "
                        f"real_human={real_human_score:.2f}<0.8)，跳过互动"
                    )
                    bot.swipe_next()
                    continue
                
                logger.info(f"评分正常，点赞+评论")
                
                # 4.1 评论（如果需要）
                if result and result.get("comment"):
                    comment = result.get("comment")        
                    if comment and bot.send_comment(comment):
                        commented_count += 1
                        interactived = True
                        logger.info(f"✅Commented this video, total: {commented_count}")
                    else:
                        logger.warning("评论发送失败")
                
                # 4.3 点赞（
                time.sleep(random.uniform(0.5, 2.0))
                if bot.like_current_video():
                    liked_count += 1
                    interactived = True
                    logger.info(f"✅Liked this video, total: {liked_count}")
                else:
                    logger.warning("点赞失败")

                # 5. 后处理
                # 点赞/双击后，抖音有时会暂停播放器；这里主动恢复播放
                bot.ensure_playing(wait_sec=2.0)
                
                # 6. 根据互动结果决定下一步
                if interactived:
                    interactived_count += 1
                    logger.info(f"✅Interactived this video, total: {interactived_count}")
                    # 模拟观看剩余部分（或一段时间）并滑走
                    _simulate_watch(bot, 20.0, logger)
                    bot.swipe_next()
                else:
                    logger.info("❌Not interacting with this video.")
                    # 即使不互动，也稍微看一会再走，避免秒滑被判定机器人
                    _simulate_watch(bot, random.uniform(3.0, 8.0), logger)
                    bot.swipe_next()
            
            logger.info("Task finished.")

    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()
