"""
火箭发射 - Gradio GUI

提供简洁的 Web 界面，用于选择视频和脚本文件并发布到多个平台。
"""

import json
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List

import gradio as gr

from ..core import (
    Platform,
    WeChatPublisher,
    YouTubePublisher,
    WeChatPublishTask,
    YouTubePublishTask,
)


class PublisherApp:
    """发布工具应用"""
    
    def __init__(self):
        self.logs = []
        self.is_publishing = False
        self.wechat_publisher = None  # 保存微信发布器实例
        self.youtube_publisher = None  # 保存YouTube发布器实例
    
    def add_log(self, message: str):
        """添加日志"""
        self.logs.append(message)
        # 保留最近 200 条日志
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]
    
    def get_logs(self) -> str:
        """获取所有日志"""
        return "\n".join(self.logs)
    
    def clear_logs(self):
        """清空日志"""
        self.logs = []
    
    def close_browser(self) -> str:
        """关闭微信浏览器"""
        if self.wechat_publisher:
            try:
                self.wechat_publisher.close()
                self.add_log("[INFO] 微信浏览器已关闭")
                self.wechat_publisher = None
            except Exception as e:
                self.add_log(f"[ERROR] 关闭浏览器失败: {e}")
        else:
            self.add_log("[WARNING] 没有打开的微信浏览器")
        return self.get_logs()
    
    def parse_script_json(self, script_text: Optional[str], platform: str) -> tuple:
        """
        解析 JSON 脚本文本
        
        Args:
            script_text: JSON 脚本文本
            platform: 平台选择 (wechat/youtube/both) - 不再影响解析，总是解析所有平台数据
            
        Returns:
            总是返回 9 个值 (5个微信 + 4个YouTube)
        """
        # 总是返回 9 个值，确保与输出组件数量一致
        empty_result = ("", "", "", "", "", "", "", "", "")
        
        if not script_text or not script_text.strip():
            return empty_result
        
        try:
            data = json.loads(script_text)
            
            # 总是解析微信数据（不管当前选择的平台）
            wechat_title = ""
            wechat_description = ""
            wechat_hashtags = ""
            wechat_heji = ""
            wechat_huodong = ""
            
            wechat_data = data.get('wechat', {})
            if wechat_data:
                wechat_title = wechat_data.get('title', '')
                wechat_description = wechat_data.get('description', '')
                hashtags_list = wechat_data.get('hashtags', [])
                wechat_hashtags = ' '.join(hashtags_list)
                wechat_heji = wechat_data.get('heji', '')
                wechat_huodong = wechat_data.get('huodong', '')
            
            # 总是解析 YouTube 数据（不管当前选择的平台）
            youtube_title = ""
            youtube_description = ""
            youtube_tags = ""
            youtube_playlist = ""
            
            youtube_data = data.get('youtube', {})
            # 如果没有 youtube 字段，使用 wechat 作为后备
            if not youtube_data and wechat_data:
                youtube_title = wechat_data.get('title', '')
                youtube_description = wechat_data.get('description', '')
                hashtags = wechat_data.get('hashtags', [])
                tags = [tag.replace('#', '') for tag in hashtags if tag.startswith('#')]
                youtube_tags = ', '.join(tags)
            elif youtube_data:
                youtube_title = youtube_data.get('title', '')
                youtube_description = youtube_data.get('description', '')
                # 支持 hashtags 或 tags 字段
                tags_list = youtube_data.get('tags', youtube_data.get('hashtags', []))
                # 去掉标签中的 # 符号（如果有）
                tags_list = [tag.replace('#', '').strip() for tag in tags_list]
                youtube_tags = ', '.join(tags_list)
                youtube_playlist = youtube_data.get('playlists', '')
            
            self.add_log("[INFO] ✅ JSON 格式正确，已解析脚本")
            
            # 总是返回 9 个值
            return (wechat_title, wechat_description, wechat_hashtags, wechat_heji, wechat_huodong,
                    youtube_title, youtube_description, youtube_tags, youtube_playlist)
            
        except json.JSONDecodeError as e:
            self.add_log(f"[ERROR] JSON 格式错误: {e}")
            return empty_result
        except Exception as e:
            self.add_log(f"[ERROR] 解析脚本失败: {e}")
            return empty_result
    
    def publish(
        self, 
        video_file,
        platform: str,
        # 微信字段
        wechat_title: str,
        wechat_description: str,
        wechat_hashtags: str,
        wechat_heji: str,
        wechat_huodong: str,
        # YouTube字段
        youtube_title: str,
        youtube_description: str,
        youtube_tags: str,
        youtube_playlist: str,
        youtube_privacy: str,
    ):
        """
        执行发布（流式输出日志）
        
        Args:
            video_file: 视频文件
            platform: 发布平台 (wechat/youtube/both)
            其他参数: 各平台的发布参数
            
        Yields:
            实时日志输出
        """
        if self.is_publishing:
            yield self.get_logs() + "\n[WARNING] 正在发布中，请等待..."
            return
        
        if video_file is None:
            self.add_log("[ERROR] 请选择视频文件")
            yield self.get_logs()
            return
        
        self.is_publishing = True
        self.clear_logs()
        self.add_log(f"[INFO] 开始发布流程... 平台: {platform}")
        yield self.get_logs()
        
        try:
            video_path = Path(video_file.name if hasattr(video_file, 'name') else video_file)
            
            # 发布到微信
            if platform in ["wechat", "both"]:
                self.add_log("\n" + "="*50)
                self.add_log("[INFO] 发布到微信视频号")
                self.add_log("="*50)
                yield self.get_logs()
                
                # 使用生成器方式发布微信
                for _ in self._publish_to_wechat_stream(
                    video_path, wechat_title, wechat_description, 
                    wechat_hashtags, wechat_heji, wechat_huodong
                ):
                    yield self.get_logs()
            
            # 发布到YouTube
            if platform in ["youtube", "both"]:
                self.add_log("\n" + "="*50)
                self.add_log("[INFO] 发布到 YouTube Shorts")
                self.add_log("="*50)
                yield self.get_logs()
                
                # 使用生成器方式发布YouTube
                for _ in self._publish_to_youtube_stream(
                    video_path, youtube_title, youtube_description,
                    youtube_tags, youtube_playlist, youtube_privacy
                ):
                    yield self.get_logs()
            
        except Exception as e:
            self.add_log(f"[ERROR] 发布失败: {e}")
            import traceback
            self.add_log(f"[ERROR] 详细错误: {traceback.format_exc()}")
            yield self.get_logs()
        finally:
            self.is_publishing = False
        
        yield self.get_logs()
    
    def _publish_to_wechat_stream(
        self, video_path: Path, title: str, description: str,
        hashtags: str, heji: str, huodong: str
    ):
        """发布到微信视频号（流式版本）"""
        import time
        
        # 保存原始回调
        original_callback = self.add_log
        
        # 创建带 yield 的回调
        def yielding_callback(message: str):
            original_callback(message)
            # 不能在这里 yield，所以我们使用标志
            self._need_yield = True
        
        try:
            # 解析 hashtags
            hashtag_list = []
            if hashtags.strip():
                hashtag_list = [tag.strip() for tag in hashtags.split() if tag.strip()]
            
            # 创建发布任务
            task = WeChatPublishTask(
                video_path=video_path,
                title=title.strip(),
                description=description.strip(),
                hashtags=hashtag_list,
                heji=heji.strip(),
                huodong=huodong.strip(),
            )
            
            self.add_log(f"[INFO] 视频文件: {video_path.name}")
            self.add_log(f"[INFO] 标题: {task.title or '(未设置)'}")
            self.add_log(f"[INFO] 合集: {task.heji or '(未设置)'}")
            self.add_log(f"[INFO] 活动: {task.huodong or '(未设置)'}")
            yield
            
            # 执行发布
            self.wechat_publisher = WeChatPublisher(
                headless=False, 
                debug=False,
                log_callback=self.add_log
            )
            self.wechat_publisher.start()
            yield
            
            self.wechat_publisher.authenticate()
            yield
            
            success, message = self.wechat_publisher.publish(task)
            yield
            
            if success:
                self.add_log("[INFO] ✅ 微信视频号发布流程完成！请在浏览器中确认发布。")
                self.add_log("[INFO] 💡 确认发布后，请手动关闭浏览器窗口。或者点击「已完成发布」按钮。")
            else:
                self.add_log(f"[ERROR] 微信视频号发布失败: {message}")
            yield
            
        except Exception as e:
            self.add_log(f"[ERROR] 微信视频号发布失败: {e}")
            if self.wechat_publisher:
                self.add_log("[INFO] 💡 如浏览器已打开，请手动关闭浏览器窗口。")
            yield
    
    def _publish_to_wechat(
        self, video_path: Path, title: str, description: str,
        hashtags: str, heji: str, huodong: str
    ):
        """发布到微信视频号"""
        try:
            # 解析 hashtags
            hashtag_list = []
            if hashtags.strip():
                hashtag_list = [tag.strip() for tag in hashtags.split() if tag.strip()]
            
            # 创建发布任务
            task = WeChatPublishTask(
                video_path=video_path,
                title=title.strip(),
                description=description.strip(),
                hashtags=hashtag_list,
                heji=heji.strip(),
                huodong=huodong.strip(),
            )
            
            self.add_log(f"[INFO] 视频文件: {video_path.name}")
            self.add_log(f"[INFO] 标题: {task.title or '(未设置)'}")
            self.add_log(f"[INFO] 合集: {task.heji or '(未设置)'}")
            self.add_log(f"[INFO] 活动: {task.huodong or '(未设置)'}")
            
            # 执行发布
            self.wechat_publisher = WeChatPublisher(
                headless=False, 
                debug=False,
                log_callback=self.add_log
            )
            self.wechat_publisher.start()
            self.wechat_publisher.authenticate()
            success, message = self.wechat_publisher.publish(task)
            
            if success:
                self.add_log("[INFO] ✅ 微信视频号发布流程完成！请在浏览器中确认发布。")
                self.add_log("[INFO] 💡 确认发布后，请手动关闭浏览器窗口。或者点击「已完成发布」按钮。")
            else:
                self.add_log(f"[ERROR] 微信视频号发布失败: {message}")
            
        except Exception as e:
            self.add_log(f"[ERROR] 微信视频号发布失败: {e}")
            if self.wechat_publisher:
                self.add_log("[INFO] 💡 如浏览器已打开，请手动关闭浏览器窗口。")
    
    def _publish_to_youtube_stream(
        self, video_path: Path, title: str, description: str,
        tags: str, playlist: str, privacy: str
    ):
        """发布到 YouTube（流式版本，实时显示日志）"""
        # 用于标记操作是否完成
        operation_done = threading.Event()
        
        def run_publish():
            """在后台线程中执行发布"""
            try:
                self._publish_to_youtube(video_path, title, description, tags, playlist, privacy)
            except Exception as e:
                self.add_log(f"[ERROR] YouTube 发布异常: {e}")
            finally:
                operation_done.set()
        
        # 在后台线程中执行发布
        thread = threading.Thread(target=run_publish, daemon=True)
        thread.start()
        
        # 每 0.3 秒 yield 一次，让 Gradio 更新 UI
        # 这样 add_log 添加的日志会及时显示
        while not operation_done.is_set():
            yield  # 触发 UI 刷新
            time.sleep(0.3)
        
        # 等待线程完全结束
        thread.join(timeout=1.0)
        
        # 最后 yield 一次确保所有日志都显示
        yield
    
    def _publish_to_youtube(
        self, video_path: Path, title: str, description: str,
        tags: str, playlist: str, privacy: str
    ):
        """发布到YouTube"""
        try:
            # 调试：打印原始参数
            self.add_log(f"[DEBUG] 原始 title 参数: '{title}' (类型: {type(title).__name__}, 长度: {len(title) if title else 0})")
            
            # 解析 tags
            tags_list = []
            if tags and tags.strip():
                tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            # 确保参数不为 None
            title = title or ""
            description = description or ""
            playlist = playlist or ""
            
            # 创建发布任务
            task = YouTubePublishTask(
                video_path=video_path,
                title=title.strip(),
                description=description.strip(),
                tags=tags_list,
                privacy_status=privacy,
                made_for_kids=False,
                playlist_title=playlist.strip() if playlist.strip() else None
            )
            
            self.add_log(f"[INFO] 视频文件: {video_path.name}")
            self.add_log(f"[INFO] 标题: {task.title}")
            self.add_log(f"[INFO] 隐私设置: {task.privacy_status}")
            if task.playlist_title:
                self.add_log(f"[INFO] 播放列表: {task.playlist_title}")
            
            # 执行发布
            self.youtube_publisher = YouTubePublisher(
                log_callback=self.add_log
            )
            
            with self.youtube_publisher:
                success, video_url = self.youtube_publisher.publish(task)
                
                if success:
                    self.add_log(f"[INFO] ✅ YouTube Shorts 上传成功！")
                    self.add_log(f"[INFO] 视频链接: {video_url}")
                    self.add_log(f"[INFO] 请在 YouTube Studio 中查看和管理视频: https://studio.youtube.com/")
                else:
                    self.add_log(f"[ERROR] YouTube 上传失败")
            
        except FileNotFoundError as e:
            self.add_log(f"[ERROR] YouTube 认证文件未找到: {e}")
            self.add_log("\n请按照以下步骤设置 YouTube API：")
            self.add_log("1. 访问 https://console.cloud.google.com/")
            self.add_log("2. 创建或选择项目")
            self.add_log("3. 启用 YouTube Data API v3")
            self.add_log("4. 创建 OAuth 2.0 凭据（桌面应用）")
            self.add_log("5. ⚠️  重要：添加授权重定向 URI: http://localhost:8080/")
            self.add_log("6. 下载并保存为: config/youtube_credentials.json")
        except Exception as e:
            error_msg = str(e)
            if "redirect_uri_mismatch" in error_msg.lower() or "400" in error_msg:
                self.add_log("[ERROR] OAuth 重定向 URI 不匹配错误")
                self.add_log("\n解决方法：")
                self.add_log("1. 访问 Google Cloud Console: https://console.cloud.google.com/")
                self.add_log("2. 进入 APIs & Services > Credentials")
                self.add_log("3. 点击你的 OAuth 2.0 客户端 ID")
                self.add_log("4. 在 '已授权的重定向 URI' 中添加: http://localhost:8080/")
                self.add_log("5. 保存更改后重新运行")
            else:
                self.add_log(f"[ERROR] YouTube 发布失败: {e}")


def create_app() -> gr.Blocks:
    """创建 Gradio 应用"""
    
    app_instance = PublisherApp()
    
    with gr.Blocks(
        title="火箭发射",
        theme=gr.themes.Soft(),
        css="""
        .main-container { max-width: 900px; margin: 0 auto; }
        .publish-btn { height: 50px !important; font-size: 18px !important; }
        """
    ) as app:
        
        with gr.Row():
            with gr.Column(scale=1, min_width=120):
                gr.Markdown("# 🚀 火箭发射\n多平台视频发布工具")
            with gr.Column(scale=4):
                gr.Markdown("💡 **使用说明**: 【1】选择平台和视频\t【2】粘贴JSON脚本自动填充\t【3】点击「发布」")
        
        with gr.Row(equal_height=True):
            # 平台选择
            platform_radio = gr.Radio(
                choices=["wechat", "youtube", "both"],
                value="wechat",
                label="🎯 发布平台",
                info="选择要发布到的平台",
                scale=1
            )
            
            # 视频文件选择
            video_input = gr.File(
                label="📹 视频文件 (必需)",
                file_types=[".mp4", ".mov", ".avi"],
                type="filepath",
                file_count="single",
                scale=1,
                height=200
            )
            
            # 脚本 JSON 输入
            with gr.Column(scale=2):
                script_input = gr.Textbox(
                    label="📄 脚本 (JSON 格式)",
                    placeholder='''{
  "wechat": {
    "title": "标题(最多16字)",
    "description": "描述",
    "hashtags": ["#标签1", "#标签2"],
    "heji": "合集名称",
    "huodong": "活动名称"
  },
  "youtube": {
    "title": "YouTube标题",
    "description": "YouTube描述",
    "tags": ["标签1", "标签2"],
    "playlists": "播放列表"
  }
}''',
                    lines=7,
                    max_lines=10
                )
                parse_script_btn = gr.Button("✅ 确认脚本", variant="secondary", size="sm")
        
        # 微信字段
        with gr.Group(visible=True) as wechat_group:
            gr.Markdown("### 📱 微信视频号")
            with gr.Row():
                with gr.Column(scale=1):
                    wechat_title_input = gr.Textbox(
                        label="标题 (最多16字)",
                        placeholder="输入视频标题...",
                        max_lines=1
                    )
                    wechat_hashtags_input = gr.Textbox(
                        label="话题标签 (空格分隔)",
                        placeholder="#标签1 #标签2 #标签3",
                        max_lines=1
                    )
                with gr.Column(scale=1):
                    wechat_description_input = gr.Textbox(
                        label="描述",
                        placeholder="输入视频描述...",
                        lines=4
                    )
            with gr.Row():
                wechat_heji_input = gr.Textbox(
                    label="合集名称 (可选)",
                    placeholder="输入要添加到的合集名称...",
                    max_lines=1
                )
                wechat_huodong_input = gr.Textbox(
                    label="活动名称 (可选)",
                    placeholder="输入要参加的活动名称...",
                    max_lines=1
                )
        
        # YouTube字段
        with gr.Group(visible=False) as youtube_group:
            gr.Markdown("### 📺 YouTube Shorts")
            with gr.Row():
                with gr.Column(scale=1):
                    youtube_title_input = gr.Textbox(
                        label="标题 (必需)",
                        placeholder="输入 YouTube 视频标题...",
                        max_lines=1
                    )
                    youtube_tags_input = gr.Textbox(
                        label="标签 (逗号分隔)",
                        placeholder="标签1, 标签2, 标签3",
                        max_lines=1
                    )
                with gr.Column(scale=1):
                    youtube_description_input = gr.Textbox(
                        label="描述 (必需)",
                        placeholder="输入 YouTube 视频描述...",
                        lines=4
                    )
            with gr.Row():
                youtube_playlist_input = gr.Textbox(
                    label="播放列表 (可选)",
                    placeholder="输入播放列表名称（不存在会自动创建）...",
                    max_lines=1,
                    scale=2
                )
                youtube_privacy_dropdown = gr.Dropdown(
                    choices=["private", "unlisted", "public"],
                    value="private",
                    label="隐私设置",
                    scale=1
                )
        
        # 发布按钮
        with gr.Row():
            publish_btn = gr.Button(
                "🚀 发布", 
                variant="primary",
                elem_classes=["publish-btn"],
                scale=3
            )
            close_browser_btn = gr.Button(
                "✅ 已完成发布(微信)",
                variant="secondary",
                elem_classes=["publish-btn"],
                scale=1
            )
        
        # 平台切换逻辑
        def update_platform_visibility(platform):
            wechat_visible = gr.update(visible=platform in ["wechat", "both"])
            youtube_visible = gr.update(visible=platform in ["youtube", "both"])
            # 微信需要手动关闭浏览器，YouTube 不需要
            close_btn_visible = gr.update(visible=platform in ["wechat", "both"])
            return wechat_visible, youtube_visible, close_btn_visible
        
        platform_radio.change(
            fn=update_platform_visibility,
            inputs=[platform_radio],
            outputs=[wechat_group, youtube_group, close_browser_btn],
            api_name=False  # 禁用 API 生成，避免 gr.update() 类型解析错误
        )
        
        gr.Markdown("### 📋 日志")
        
        log_output = gr.Textbox(
            label="",
            lines=15,
            max_lines=15,  # 固定高度，启用内部滚动
            interactive=False,
            show_label=False,
            autoscroll=True  # 自动滚动到底部
        )
        
        # 脚本解析事件（点击确认按钮后解析）
        def parse_and_update(script_text, platform):
            # parse_script_json 现在总是返回 9 个值
            return app_instance.parse_script_json(script_text, platform)
        
        parse_script_btn.click(
            fn=parse_and_update,
            inputs=[script_input, platform_radio],
            outputs=[
                wechat_title_input, wechat_description_input, wechat_hashtags_input,
                wechat_heji_input, wechat_huodong_input,
                youtube_title_input, youtube_description_input, youtube_tags_input,
                youtube_playlist_input
            ],
            api_name=False  # 禁用 API 生成
        )
        
        publish_btn.click(
            fn=app_instance.publish,
            inputs=[
                video_input, platform_radio,
                wechat_title_input, wechat_description_input, wechat_hashtags_input,
                wechat_heji_input, wechat_huodong_input,
                youtube_title_input, youtube_description_input, youtube_tags_input,
                youtube_playlist_input, youtube_privacy_dropdown
            ],
            outputs=[log_output],
            api_name=False  # 禁用 API 生成
        )
        
        close_browser_btn.click(
            fn=app_instance.close_browser,
            inputs=[],
            outputs=[log_output],
            api_name=False  # 禁用 API 生成
        )
    
    return app


def launch_app(share: bool = False, server_port: int = 7860):
    """
    启动应用
    
    Args:
        share: 是否生成公开链接
        server_port: 服务端口
    """
    app = create_app()
    app.launch(
        share=share,
        server_port=server_port,
        inbrowser=True
    )
