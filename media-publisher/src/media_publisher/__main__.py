"""
媒体发布工具 - 入口文件

支持命令行参数启动 GUI 或直接发布到多个平台。
支持三种模式:
  - 传统模式: --video + --script (微信/YouTube)
  - Episode 模式: --episode ep*.json --platform medium,twitter (多平台)
  - 批量模式: --batch-dir <series_dir> --platform wechat (批量发布系列视频)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from media_publisher.shared.io import atomic_write_text
from media_publisher.shared.security import sanitize_identifier


# 所有支持的平台
ALL_PLATFORMS = ["wechat", "youtube", "medium", "twitter", "devto", "tiktok", "instagram"]
ARTICLE_PLATFORMS = ["medium", "twitter", "devto"]
VIDEO_PLATFORMS = ["wechat", "youtube", "tiktok", "instagram"]


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="火箭发射 - 多平台内容一键发布工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动 GUI 界面
  media-publisher

  # 批量模式: 将系列目录下所有视频批量保存到微信视频号草稿箱
  media-publisher --batch-dir /path/to/series/yingxiongernv --platform wechat --account 奶奶讲故事

  # Episode 模式: 从 ep*.json 发布到 Medium + Twitter
  media-publisher --episode ep01.json --platform medium,twitter

  # Episode 模式: 发布到所有文章平台 (Medium + Twitter + Dev.to)
  media-publisher --episode ep01.json --platform all-articles

  # Episode 模式: 发布到 TikTok (需要视频文件)
  media-publisher --episode ep01.json --platform tiktok --video /path/to/video.mp4

  # 传统模式: 发布到微信视频号
  media-publisher --video /path/to/video.mp4 --platform wechat --script /path/to/script.json

  # 传统模式: 发布到 YouTube Shorts
  media-publisher --video /path/to/video.mp4 --platform youtube --script /path/to/script.json
        """
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=7860,
        help="GUI 服务端口 (默认: 7860)"
    )
    
    parser.add_argument(
        "--share",
        action="store_true",
        help="生成公开分享链接"
    )
    
    parser.add_argument(
        "--batch-dir",
        type=str,
        help="系列目录路径（批量模式），自动匹配 output/*-Clip.mp4 和 config/*-Strategy.json"
    )
    
    parser.add_argument(
        "--episode",
        type=str,
        help="ep*.json 素材文件路径（Episode 模式）"
    )
    
    parser.add_argument(
        "--video",
        type=str,
        help="视频文件路径（视频平台必需）"
    )
    
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help=(
            "发布平台，逗号分隔。可选: "
            "medium, twitter, devto, tiktok, instagram, wechat, youtube, "
            "all-articles, all-videos, both (传统兼容)"
        )
    )
    
    parser.add_argument(
        "--script",
        type=str,
        help="JSON 脚本文件路径（传统模式）"
    )
    
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default="private",
        help="视频隐私设置 (默认: private)"
    )
    
    parser.add_argument(
        "--account",
        type=str,
        default=None,
        help="微信视频号账号名称，用于区分多账号登录状态（如 '奶奶讲故事'）"
    )
    
    parser.add_argument(
        "--list-drafts",
        action="store_true",
        help="与 --batch-dir 同用：打开草稿箱列表，与预期列表对比，输出可能未保存成功的视频"
    )
    
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="批量模式仅发布指定集数，逗号分隔，如 04,09,10,12,17,20（匹配文件名中含该编号的视频）"
    )
    parser.add_argument(
        "--job-file",
        type=str,
        default=None,
        help="结构化任务文件路径（job 模式）"
    )
    parser.add_argument(
        "--result-file",
        type=str,
        default=None,
        help="结构化结果输出路径（job 模式）"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出结构化 JSON 结果（用于调度系统）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅校验任务，不执行实际发布（job 模式）"
    )
    
    args = parser.parse_args()
    
    if args.job_file:
        result = run_job_cli(args)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        if args.result_file:
            atomic_write_text(
                args.result_file,
                json.dumps(result, ensure_ascii=False, indent=2),
            )
        if result.get("status") == "success":
            return
        sys.exit(1)

    # 查看草稿箱并对比（找出未成功保存的）
    if args.list_drafts and args.batch_dir:
        run_list_drafts(args)
    # 批量模式
    elif args.batch_dir:
        run_batch_cli(args)
    # Episode 模式
    elif args.episode:
        run_episode_cli(args)
    # 传统命令行模式
    elif args.video:
        run_legacy_cli(args)
    else:
        # GUI 模式
        run_gui(args)


def run_gui(args):
    """启动 GUI 界面"""
    try:
        from .gui import launch_app
        print("🚀 正在启动火箭发射...")
        print(f"📍 访问地址: http://localhost:{args.port}")
        launch_app(share=args.share, server_port=args.port)
    except ImportError as e:
        print(f"❌ 启动失败: {e}")
        print("请确保已安装依赖: uv pip install -e .")
        sys.exit(1)


def scan_batch_dir(batch_dir: Path) -> list:
    """
    扫描系列目录，匹配视频和配置文件对。
    
    目录结构：
      batch_dir/
        output/*-Clip.mp4
        config/*-Strategy.json
    
    Returns:
        [(video_path, config_path), ...] 按文件名排序
    """
    output_dir = batch_dir / "output"
    config_dir = batch_dir / "config"
    
    if not output_dir.exists():
        print(f"❌ 未找到 output 目录: {output_dir}")
        sys.exit(1)
    if not config_dir.exists():
        print(f"❌ 未找到 config 目录: {config_dir}")
        sys.exit(1)
    
    videos = sorted(output_dir.glob("*-Clip.mp4"))
    if not videos:
        print(f"❌ 未找到视频文件 (*-Clip.mp4): {output_dir}")
        sys.exit(1)
    
    pairs = []
    for video in videos:
        # yingxiongernv01-Clip.mp4 -> yingxiongernv01-Strategy.json
        stem = video.stem.replace("-Clip", "-Strategy")
        config = config_dir / f"{stem}.json"
        if not config.exists():
            print(f"⚠️  跳过 {video.name}：未找到配置 {config.name}")
            continue
        pairs.append((video, config))
    
    return pairs


def run_list_drafts(args):
    """打开草稿箱列表，与 batch_dir 预期列表对比，输出可能未保存成功的视频"""
    from .core import WeChatPublisher, WeChatPublishTask

    # 支持逗号分隔的多个系列目录
    batch_dir_str = args.batch_dir.strip()
    batch_dirs = [Path(p.strip()) for p in batch_dir_str.split(",") if p.strip()]
    if not batch_dirs:
        print("❌ 请指定 --batch-dir（可逗号分隔多个目录）")
        sys.exit(1)
    for d in batch_dirs:
        if not d.exists():
            print(f"❌ 目录不存在: {d}")
            sys.exit(1)

    # 构建预期列表：(系列名, 视频文件名, 标题, 描述前50字)，不调用 scan_batch_dir 以免缺目录时 exit
    expected = []
    for batch_dir in batch_dirs:
        output_dir = batch_dir / "output"
        config_dir = batch_dir / "config"
        if not output_dir.exists() or not config_dir.exists():
            print(f"⚠️ 跳过（缺 output/config）: {batch_dir}")
            continue
        videos = sorted(output_dir.glob("*-Clip.mp4"))
        pairs = []
        for video in videos:
            stem = video.stem.replace("-Clip", "-Strategy")
            config = config_dir / f"{stem}.json"
            if config.exists():
                pairs.append((video, config))
        if not pairs:
            print(f"⚠️ 未找到视频-配置对: {batch_dir}")
            continue
        series_name = batch_dir.name
        for video, config in pairs:
            with open(config, "r", encoding="utf-8") as f:
                script_data = json.load(f)
            task = WeChatPublishTask.from_json(video, script_data)
            desc = (task.get_full_description() or "").strip()[:50]
            title = (task.title or "").strip()
            expected.append((series_name, video.name, title, desc))
    if not expected:
        print("❌ 未找到任何预期视频配置")
        sys.exit(1)
    print(f"\n📂 预期草稿数: {len(expected)}（来自 {len(batch_dirs)} 个系列）\n")

    account = getattr(args, "account", None)
    try:
        with WeChatPublisher(headless=False, log_callback=_print_log, account=account) as publisher:
            publisher.authenticate()
            draft_full_text = publisher.get_draft_page_text()
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 获取草稿列表失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not draft_full_text:
        print("❌ 未能获取草稿箱页面内容，请检查登录状态后重试")
        sys.exit(1)

    # 将草稿全文保存到 batch_dir（第一个）供人工核查
    dump_path = Path(args.batch_dir.split(",")[0].strip()) / "draft_page_dump.txt"
    try:
        atomic_write_text(dump_path, draft_full_text, encoding="utf-8")
        print(f"📄 草稿箱全文已保存至: {dump_path}（可人工核查）")
    except Exception:
        pass

    # 匹配：用标题或描述前50字在整页文本中做包含搜索（不依赖 CSS 结构）
    def matched(title: str, desc: str) -> bool:
        title = (title or "").strip()
        desc = (desc or "").strip()[:50]
        if title and len(title) >= 4 and title in draft_full_text:
            return True
        if desc and len(desc) >= 10 and desc in draft_full_text:
            return True
        return False

    missing = []
    for series_name, video_name, title, desc in expected:
        if not matched(title, desc):
            missing.append((series_name, video_name, title or desc[:30]))

    print("📊 草稿箱对比结果")
    print("=" * 50)
    if not missing:
        print("✅ 预期草稿均在草稿箱中，无缺失。")
        return
    print(f"❌ 以下 {len(missing)} 条未在草稿箱中找到（可能上传/保存失败）：\n")
    for series_name, video_name, label in missing:
        print(f"  [{series_name}] {video_name}  — {label}")
    print(f"\n可针对上述视频重新执行批量发布以重试。")


def run_batch_cli(args):
    """批量模式：扫描系列目录，批量保存到草稿箱"""
    from .core import WeChatPublisher, WeChatPublishTask
    
    batch_dir = Path(args.batch_dir)
    if not batch_dir.exists():
        print(f"❌ 目录不存在: {batch_dir}")
        sys.exit(1)
    
    platform = args.platform or "wechat"
    if platform != "wechat":
        print(f"❌ 批量模式目前仅支持 wechat 平台，收到: {platform}")
        sys.exit(1)
    
    pairs = scan_batch_dir(batch_dir)
    if not pairs:
        print("❌ 未找到可发布的视频-配置对")
        sys.exit(1)
    
    # 仅发布指定集数（--only 04,09,10 等）
    only_arg = getattr(args, "only", None)
    if only_arg:
        only_tokens = [t.strip() for t in only_arg.split(",") if t.strip()]
        if only_tokens:
            original_count = len(pairs)
            pairs = [(v, c) for v, c in pairs if any(t in v.stem for t in only_tokens)]
            if not pairs:
                print(f"❌ --only {only_arg} 未匹配到任何视频")
                sys.exit(1)
            print(f"📌 仅发布指定集数: {only_tokens}（共 {len(pairs)} 条，已过滤 {original_count - len(pairs)} 条）")
    
    # 构建任务列表
    tasks = []
    print(f"\n📂 系列目录: {batch_dir}")
    print(f"📊 共发现 {len(pairs)} 个视频\n")
    
    for i, (video, config) in enumerate(pairs, 1):
        with open(config, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        task = WeChatPublishTask.from_json(video, script_data)
        tasks.append(task)
        print(f"  {i:2d}. {video.name}  ->  {task.title}")
    
    print()
    
    # 批量发布（共享浏览器会话）
    account = getattr(args, 'account', None)
    if account:
        print(f"📌 账号: {account}")
    try:
        with WeChatPublisher(headless=False, log_callback=_print_log, account=account) as publisher:
            publisher.authenticate()
            results = publisher.publish_batch(tasks)
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 批量发布失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 汇总
    print(f"\n{'='*50}")
    print("📊 批量发布结果汇总")
    print(f"{'='*50}")
    
    success_count = 0
    failed_list = []
    for (video, _), (success, msg) in zip(pairs, results):
        status = "✅" if success else "❌"
        if success:
            success_count += 1
        else:
            failed_list.append((video.name, msg))
        print(f"  {status} {video.name}: {msg}")
    
    print(f"\n  成功: {success_count}/{len(pairs)}")
    
    # 将结果写入报告文件，便于后续查看或重试失败项
    report_name = f"wechat_batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = batch_dir / report_name
    lines = [
        "# 微信视频号批量发布报告",
        f"# 时间: {datetime.now().isoformat(timespec='seconds')}",
        f"# 目录: {batch_dir}",
        f"# 成功: {success_count}  失败: {len(pairs) - success_count}",
        "",
    ]
    for (video, _), (success, msg) in zip(pairs, results):
        line = "OK\t" if success else "FAIL\t"
        line += f"{video.name}\t{msg}"
        lines.append(line)
    if failed_list:
        lines.append("")
        lines.append("# 失败列表（可据此重试）")
        for name, msg in failed_list:
            lines.append(f"{name}\t{msg}")
    atomic_write_text(report_path, "\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n📄 结果已写入: {report_path}")
    if failed_list:
        print(f"   失败 {len(failed_list)} 个: {', '.join(f[0] for f in failed_list)}")


def parse_platform_arg(platform_str: str) -> list:
    """解析 --platform 参数为平台列表"""
    if not platform_str:
        return []
    
    # 快捷别名
    if platform_str == "all-articles":
        return ARTICLE_PLATFORMS
    elif platform_str == "all-videos":
        return VIDEO_PLATFORMS
    elif platform_str == "all":
        return ALL_PLATFORMS
    elif platform_str == "both":
        return ["wechat", "youtube"]  # 传统兼容
    
    platforms = [p.strip().lower() for p in platform_str.split(',')]
    invalid = [p for p in platforms if p not in ALL_PLATFORMS]
    if invalid:
        print(f"❌ 未知平台: {', '.join(invalid)}")
        print(f"   支持的平台: {', '.join(ALL_PLATFORMS)}")
        sys.exit(1)
    
    return platforms


def run_episode_cli(args):
    """Episode 模式: 从 ep*.json 发布到指定平台"""
    from .core import (
        EpisodeAdapter,
        MediumPublisher,
        TwitterPublisher,
        DevToPublisher,
        TikTokPublisher,
        InstagramPublisher,
        WeChatPublisher,
        YouTubePublisher,
    )
    
    ep_path = Path(args.episode)
    if not ep_path.exists():
        print(f"❌ ep*.json 文件不存在: {ep_path}")
        sys.exit(1)
    
    # 解析平台
    if not args.platform:
        print("❌ Episode 模式需要 --platform 参数")
        print("   例: --platform medium,twitter")
        sys.exit(1)
    
    platforms = parse_platform_arg(args.platform)
    
    # 加载 Episode
    try:
        adapter = EpisodeAdapter(ep_path)
        print(f"\n📄 {adapter.summary()}\n")
    except Exception as e:
        print(f"❌ 加载 ep*.json 失败: {e}")
        sys.exit(1)
    
    # 检查视频平台是否提供了视频文件
    video_platforms_requested = [p for p in platforms if p in VIDEO_PLATFORMS]
    video_path = Path(args.video) if args.video else None
    
    if video_platforms_requested and not video_path:
        print(f"❌ 平台 {', '.join(video_platforms_requested)} 需要 --video 参数")
        sys.exit(1)
    
    if video_path and not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)
    
    # 逐平台发布
    results = {}
    
    for platform in platforms:
        print(f"\n{'='*50}")
        print(f"📤 发布到 {platform.upper()}")
        print(f"{'='*50}")
        
        try:
            if platform == "medium":
                task = adapter.to_medium_task()
                with MediumPublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
            elif platform == "twitter":
                task = adapter.to_twitter_task()
                with TwitterPublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
            elif platform == "devto":
                task = adapter.to_devto_task()
                with DevToPublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
            elif platform == "tiktok":
                task = adapter.to_tiktok_task(video_path)
                with TikTokPublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
            elif platform == "instagram":
                task = adapter.to_instagram_task(video_path)
                with InstagramPublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
            elif platform == "wechat":
                task = adapter.to_wechat_task(video_path)
                account = getattr(args, 'account', None)
                with WeChatPublisher(headless=False, log_callback=_print_log, account=account) as publisher:
                    publisher.authenticate()
                    success, msg = publisher.publish(task)
                results[platform] = (success, msg)
                
            elif platform == "youtube":
                task = adapter.to_youtube_task(video_path)
                task.privacy_status = args.privacy
                with YouTubePublisher(log_callback=_print_log) as publisher:
                    success, url = publisher.publish(task)
                results[platform] = (success, url)
                
        except FileNotFoundError as e:
            print(f"\n❌ {platform}: 凭据文件未找到")
            print(f"   {e}")
            results[platform] = (False, str(e))
        except Exception as e:
            print(f"\n❌ {platform}: 发布失败 - {e}")
            import traceback
            traceback.print_exc()
            results[platform] = (False, str(e))
    
    # 汇总结果
    print(f"\n{'='*50}")
    print("📊 发布结果汇总")
    print(f"{'='*50}")
    
    for platform, (success, detail) in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {platform}: {detail or '(无详情)'}")


def run_job_cli(args) -> dict[str, Any]:
    """
    结构化 job 入口，面向调度系统。

    最小契约:
      {
        "status": "success|failed",
        "retryable": bool,
        "error": {"code": str, "message": str} | null,
        "artifacts": [str],
        "metrics": {"mode": str}
      }
    """
    try:
        job_path = Path(args.job_file)
        if not job_path.exists():
            return {
                "status": "failed",
                "retryable": False,
                "error": {
                    "code": "MP_INPUT_INVALID",
                    "message": f"job 文件不存在: {job_path}",
                },
                "artifacts": [],
                "metrics": {"mode": "job"},
            }

        with open(job_path, "r", encoding="utf-8") as f:
            job = json.load(f)

        mode = (job.get("mode") or "legacy").strip().lower()
        if mode != "legacy":
            return {
                "status": "failed",
                "retryable": False,
                "error": {
                    "code": "MP_INPUT_INVALID",
                    "message": f"不支持的 job mode: {mode}",
                },
                "artifacts": [],
                "metrics": {"mode": mode},
            }

        platform = (job.get("platform") or "wechat").strip().lower()
        if platform not in {"wechat", "youtube", "both"}:
            return {
                "status": "failed",
                "retryable": False,
                "error": {
                    "code": "MP_INPUT_INVALID",
                    "message": f"不支持的平台: {platform}",
                },
                "artifacts": [],
                "metrics": {"mode": mode},
            }

        account = sanitize_identifier(job.get("account"), field_name="account")
        video = Path(job.get("video", ""))
        script = Path(job.get("script", ""))

        if not video.exists() or not script.exists():
            return {
                "status": "failed",
                "retryable": False,
                "error": {
                    "code": "MP_INPUT_INVALID",
                    "message": "video 或 script 文件不存在",
                },
                "artifacts": [],
                "metrics": {"mode": mode},
            }

        if args.dry_run or bool(job.get("dry_run", False)):
            return {
                "status": "success",
                "retryable": False,
                "error": None,
                "artifacts": [],
                "metrics": {"mode": mode, "dry_run": True, "platform": platform},
            }

        publish_results = run_legacy_cli(
            argparse.Namespace(
                video=str(video),
                script=str(script),
                platform=platform,
                privacy=job.get("privacy", "private"),
                account=account,
            )
        )
        success = all(item.get("success") for item in publish_results.values())
        return {
            "status": "success" if success else "failed",
            "retryable": not success,
            "error": None
            if success
            else {
                "code": "MP_PLATFORM_ERROR",
                "message": "部分平台发布失败",
            },
            "artifacts": [],
            "metrics": {
                "mode": mode,
                "platform": platform,
                "results": publish_results,
            },
        }
    except ValueError as e:
        return {
            "status": "failed",
            "retryable": False,
            "error": {"code": "MP_INPUT_INVALID", "message": str(e)},
            "artifacts": [],
            "metrics": {"mode": "job"},
        }
    except Exception as e:
        return {
            "status": "failed",
            "retryable": True,
            "error": {"code": "MP_INTERNAL_ERROR", "message": str(e)},
            "artifacts": [],
            "metrics": {"mode": "job"},
        }


def _print_log(message: str):
    """CLI 日志回调"""
    print(message)


# ============================================================
# 传统模式（兼容已有的 --video + --script 用法）
# ============================================================

def run_legacy_cli(args):
    """传统命令行模式发布"""
    from .core import (
        WeChatPublisher,
        YouTubePublisher,
        WeChatPublishTask,
        YouTubePublishTask,
    )
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)
    
    # 读取脚本文件
    script_data = {}
    if args.script:
        script_path = Path(args.script)
        if not script_path.exists():
            print(f"❌ 脚本文件不存在: {script_path}")
            sys.exit(1)
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 格式错误: {e}")
            sys.exit(1)
    else:
        print("⚠️  未指定脚本文件，请使用 --script 参数指定")
        sys.exit(1)
    
    # 解析平台
    platform = args.platform or "wechat"
    
    results: dict[str, dict[str, Any]] = {}

    # 发布到微信
    if platform in ["wechat", "both"]:
        success, message = publish_to_wechat(video_path, script_data, account=args.account)
        results["wechat"] = {"success": success, "message": message}
    
    # 发布到YouTube
    if platform in ["youtube", "both"]:
        success, message = publish_to_youtube(video_path, script_data, args.privacy)
        results["youtube"] = {"success": success, "message": message}

    return results


def publish_to_wechat(video_path: Path, script_data: dict, account: str = None):
    """发布到微信视频号"""
    from .core import WeChatPublisher, WeChatPublishTask
    
    print("\n" + "="*50)
    print(f"📱 发布到微信视频号" + (f" [{account}]" if account else ""))
    print("="*50)
    
    try:
        task = WeChatPublishTask.from_json(video_path, script_data)
        
        print(f"📹 视频: {video_path.name}")
        print(f"📝 标题: {task.title or '(未设置)'}")
        print(f"📦 合集: {task.heji or '(未设置)'}")
        print(f"🎯 活动: {task.huodong or '(未设置)'}")
        print()
        
        with WeChatPublisher(headless=False, account=account) as publisher:
            publisher.authenticate()
            success, message = publisher.publish(task)
            
            if success:
                print(f"\n✅ {message}")
                return True, message
            else:
                print(f"\n❌ 微信视频号发布失败: {message}")
                return False, message
                
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消操作")
        return False, "用户取消操作"
    except Exception as e:
        print(f"\n❌ 微信视频号发布失败: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def publish_to_youtube(video_path: Path, script_data: dict, privacy: str):
    """发布到YouTube"""
    from .core import YouTubePublisher, YouTubePublishTask
    
    print("\n" + "="*50)
    print("📺 发布到 YouTube Shorts")
    print("="*50)
    
    try:
        task = YouTubePublishTask.from_json(video_path, script_data)
        task.privacy_status = privacy
        
        print(f"📹 视频: {video_path.name}")
        print(f"📝 标题: {task.title}")
        print(f"🔒 隐私: {task.privacy_status}")
        if task.playlist_title:
            print(f"📋 播放列表: {task.playlist_title}")
        print()
        
        publisher = YouTubePublisher()
        
        with publisher:
            success, video_url = publisher.publish(task)
            
            if success:
                print(f"\n✅ YouTube Shorts 上传成功！")
                print(f"🔗 视频链接: {video_url}")
                print(f"🎬 YouTube Studio: https://studio.youtube.com/")
                return True, video_url
            else:
                print(f"\n❌ YouTube 上传失败")
                return False, "YouTube 上传失败"
                
    except FileNotFoundError as e:
        print(f"\n❌ YouTube 认证文件未找到")
        print("\n请按照以下步骤设置 YouTube API：")
        print("1. 访问 https://console.cloud.google.com/")
        print("2. 创建或选择项目")
        print("3. 启用 YouTube Data API v3")
        print("4. 创建 OAuth 2.0 凭据（桌面应用）")
        print("5. ⚠️  重要：添加授权重定向 URI: http://localhost:8080/")
        print("6. 下载并保存为: config/youtube_credentials.json")
        return False, str(e)
    except Exception as e:
        error_msg = str(e)
        if "redirect_uri_mismatch" in error_msg.lower() or "400" in error_msg:
            print("\n❌ OAuth 重定向 URI 不匹配错误")
            print("\n解决方法：")
            print("1. 访问 Google Cloud Console: https://console.cloud.google.com/")
            print("2. 进入 APIs & Services > Credentials")
            print("3. 点击你的 OAuth 2.0 客户端 ID")
            print("4. 在 '已授权的重定向 URI' 中添加: http://localhost:8080/")
            print("5. 保存更改后重新运行脚本")
            return False, error_msg
        else:
            print(f"\n❌ YouTube 发布失败: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)


if __name__ == "__main__":
    main()
