"""
媒体发布工具 - 入口文件

支持命令行参数启动 GUI 或直接发布到多个平台。
支持两种模式:
  - 传统模式: --video + --script (微信/YouTube)
  - Episode 模式: --episode ep*.json --platform medium,twitter (多平台)
"""

import argparse
import json
import sys
from pathlib import Path


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
    
    args = parser.parse_args()
    
    # Episode 模式
    if args.episode:
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
                with WeChatPublisher(headless=False, log_callback=_print_log) as publisher:
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
    
    # 发布到微信
    if platform in ["wechat", "both"]:
        publish_to_wechat(video_path, script_data)
    
    # 发布到YouTube
    if platform in ["youtube", "both"]:
        publish_to_youtube(video_path, script_data, args.privacy)


def publish_to_wechat(video_path: Path, script_data: dict):
    """发布到微信视频号"""
    from .core import WeChatPublisher, WeChatPublishTask
    
    print("\n" + "="*50)
    print("📱 发布到微信视频号")
    print("="*50)
    
    try:
        task = WeChatPublishTask.from_json(video_path, script_data)
        
        print(f"📹 视频: {video_path.name}")
        print(f"📝 标题: {task.title or '(未设置)'}")
        print(f"📦 合集: {task.heji or '(未设置)'}")
        print(f"🎯 活动: {task.huodong or '(未设置)'}")
        print()
        
        with WeChatPublisher(headless=False) as publisher:
            publisher.authenticate()
            success, message = publisher.publish(task)
            
            if success:
                print("\n✅ 微信视频号发布准备完成！")
                print("请在浏览器中确认信息并点击发布按钮。")
                try:
                    input("按回车键关闭浏览器...")
                except EOFError:
                    import time
                    print("检测到非交互式环境，保持浏览器打开 5 分钟...")
                    time.sleep(300)
            else:
                print(f"\n❌ 微信视频号发布失败: {message}")
                
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消操作")
    except Exception as e:
        print(f"\n❌ 微信视频号发布失败: {e}")
        import traceback
        traceback.print_exc()


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
            else:
                print(f"\n❌ YouTube 上传失败")
                
    except FileNotFoundError as e:
        print(f"\n❌ YouTube 认证文件未找到")
        print("\n请按照以下步骤设置 YouTube API：")
        print("1. 访问 https://console.cloud.google.com/")
        print("2. 创建或选择项目")
        print("3. 启用 YouTube Data API v3")
        print("4. 创建 OAuth 2.0 凭据（桌面应用）")
        print("5. ⚠️  重要：添加授权重定向 URI: http://localhost:8080/")
        print("6. 下载并保存为: config/youtube_credentials.json")
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
        else:
            print(f"\n❌ YouTube 发布失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
