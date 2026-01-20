"""
媒体发布工具 - 入口文件

支持命令行参数启动 GUI 或直接发布到多个平台。
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="火箭发射 - 一键发布视频到微信视频号和YouTube Shorts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动 GUI 界面
  media-publisher
  
  # 指定端口启动
  media-publisher --port 8080
  
  # 命令行模式发布到微信视频号
  media-publisher --video /path/to/video.mp4 --platform wechat --script /path/to/script.json
  
  # 命令行模式发布到 YouTube Shorts
  media-publisher --video /path/to/video.mp4 --platform youtube --script /path/to/script.json
  
  # 同时发布到两个平台
  media-publisher --video /path/to/video.mp4 --platform both --script /path/to/script.json
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
        "--video",
        type=str,
        help="视频文件路径（命令行模式）"
    )
    
    parser.add_argument(
        "--platform",
        choices=["wechat", "youtube", "both"],
        default="wechat",
        help="发布平台 (默认: wechat)"
    )
    
    parser.add_argument(
        "--script",
        type=str,
        help="JSON 脚本文件路径（命令行模式，推荐）"
    )
    
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default="private",
        help="YouTube 隐私设置 (默认: private)"
    )
    
    args = parser.parse_args()
    
    # 命令行模式
    if args.video:
        run_cli(args)
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


def run_cli(args):
    """命令行模式发布"""
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
    
    # 发布到微信
    if args.platform in ["wechat", "both"]:
        publish_to_wechat(video_path, script_data)
    
    # 发布到YouTube
    if args.platform in ["youtube", "both"]:
        publish_to_youtube(video_path, script_data, args.privacy)


def publish_to_wechat(video_path: Path, script_data: dict):
    """发布到微信视频号"""
    from .core import WeChatPublisher, WeChatPublishTask
    
    print("\n" + "="*50)
    print("📱 发布到微信视频号")
    print("="*50)
    
    try:
        # 创建发布任务
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
        # 创建发布任务
        task = YouTubePublishTask.from_json(video_path, script_data)
        task.privacy_status = privacy  # 使用命令行指定的隐私设置
        
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
