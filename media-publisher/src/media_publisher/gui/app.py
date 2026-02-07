"""
火箭发射 - Gradio GUI

提供简洁的 Web 界面，支持两种发布模式:
1. 传统模式: 选择视频 + 粘贴 JSON 脚本 (微信/YouTube)
2. Episode 模式: 加载 ep*.json + 选择平台 + 一键发布 (全平台)
"""

import json
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List

import gradio as gr

from ..core import (
    Platform,
    EpisodeAdapter,
    WeChatPublisher,
    YouTubePublisher,
    MediumPublisher,
    TwitterPublisher,
    DevToPublisher,
    TikTokPublisher,
    InstagramPublisher,
    WeChatPublishTask,
    YouTubePublishTask,
)


class PublisherApp:
    """发布工具应用"""
    
    def __init__(self):
        self.logs = []
        self.is_publishing = False
        self.wechat_publisher = None
        self.youtube_publisher = None
        self.current_adapter: Optional[EpisodeAdapter] = None
    
    def add_log(self, message: str):
        """添加日志"""
        self.logs.append(message)
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
    
    # ============================================================
    # Episode 模式
    # ============================================================
    
    def load_episode(self, ep_file) -> Tuple[str, str]:
        """
        加载 ep*.json 文件
        
        Returns:
            (summary, preview) - 摘要信息和文章预览
        """
        if ep_file is None:
            return "请选择 ep*.json 文件", ""
        
        try:
            ep_path = Path(ep_file.name if hasattr(ep_file, 'name') else ep_file)
            self.current_adapter = EpisodeAdapter(ep_path)
            
            # 构建摘要
            adapter = self.current_adapter
            platforms = adapter.get_available_platforms()
            ready = [
                p for p, info in platforms.items()
                if info['has_content'] and info['has_config']
            ]
            
            summary = (
                f"系列: {adapter.series_info.get('series_name', '未知')}\n"
                f"集数: 第 {adapter.episode_number} 集\n"
                f"标题: {adapter.meta.get('title', '未知')}\n"
                f"可发布平台: {', '.join(ready)}"
            )
            
            # 文章预览 (overseas_blog 前 500 字符)
            blog_text = adapter.content.get('overseas_blog', {}).get('text', '')
            preview = blog_text[:500] + "..." if len(blog_text) > 500 else blog_text
            
            self.add_log(f"[INFO] 已加载: {ep_path.name}")
            
            return summary, preview
            
        except Exception as e:
            self.current_adapter = None
            return f"加载失败: {e}", ""
    
    def publish_episode(
        self,
        ep_file,
        selected_platforms: List[str],
        video_file,
    ):
        """
        Episode 模式发布（流式日志）
        
        Args:
            ep_file: ep*.json 文件
            selected_platforms: 选中的平台列表
            video_file: 视频文件（视频平台需要）
        """
        if self.is_publishing:
            yield self.get_logs() + "\n[WARNING] 正在发布中，请等待..."
            return
        
        if not self.current_adapter:
            if ep_file is None:
                self.add_log("[ERROR] 请先加载 ep*.json 文件")
                yield self.get_logs()
                return
            # 尝试重新加载
            try:
                ep_path = Path(ep_file.name if hasattr(ep_file, 'name') else ep_file)
                self.current_adapter = EpisodeAdapter(ep_path)
            except Exception as e:
                self.add_log(f"[ERROR] 加载 ep*.json 失败: {e}")
                yield self.get_logs()
                return
        
        if not selected_platforms:
            self.add_log("[ERROR] 请至少选择一个发布平台")
            yield self.get_logs()
            return
        
        # 检查视频平台是否有视频文件
        video_platforms = ["wechat", "youtube", "tiktok", "instagram"]
        need_video = [p for p in selected_platforms if p in video_platforms]
        video_path = None
        if need_video:
            if video_file is None:
                self.add_log(
                    f"[ERROR] 平台 {', '.join(need_video)} 需要视频文件"
                )
                yield self.get_logs()
                return
            video_path = Path(
                video_file.name if hasattr(video_file, 'name') else video_file
            )
        
        self.is_publishing = True
        self.clear_logs()
        adapter = self.current_adapter
        self.add_log(
            f"[INFO] 开始发布 EP{adapter.episode_number:02d} "
            f"到 {', '.join(selected_platforms)}"
        )
        yield self.get_logs()
        
        # 在后台线程发布
        operation_done = threading.Event()
        
        def run_publish():
            try:
                self._do_episode_publish(adapter, selected_platforms, video_path)
            except Exception as e:
                self.add_log(f"[ERROR] 发布异常: {e}")
                import traceback
                self.add_log(f"[ERROR] {traceback.format_exc()}")
            finally:
                operation_done.set()
        
        thread = threading.Thread(target=run_publish, daemon=True)
        thread.start()
        
        while not operation_done.is_set():
            yield self.get_logs()
            time.sleep(0.5)
        
        thread.join(timeout=1.0)
        self.is_publishing = False
        yield self.get_logs()
    
    def _do_episode_publish(
        self,
        adapter: EpisodeAdapter,
        platforms: List[str],
        video_path: Optional[Path],
    ):
        """实际执行 Episode 发布逻辑"""
        results = {}
        
        for platform in platforms:
            self.add_log(f"\n{'='*50}")
            self.add_log(f"[INFO] 发布到 {platform.upper()}")
            self.add_log(f"{'='*50}")
            
            try:
                if platform == "medium":
                    task = adapter.to_medium_task()
                    self.add_log(f"[INFO] 标题: {task.title}")
                    self.add_log(f"[INFO] 标签: {', '.join(task.tags)}")
                    with MediumPublisher(log_callback=self.add_log) as pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "twitter":
                    task = adapter.to_twitter_task()
                    self.add_log(f"[INFO] Thread: {len(task.tweets)} 条推文")
                    with TwitterPublisher(log_callback=self.add_log) as pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "devto":
                    task = adapter.to_devto_task()
                    self.add_log(f"[INFO] 标题: {task.title}")
                    self.add_log(f"[INFO] 标签: {', '.join(task.tags)}")
                    with DevToPublisher(log_callback=self.add_log) as pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "tiktok":
                    task = adapter.to_tiktok_task(video_path)
                    with TikTokPublisher(log_callback=self.add_log) as pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "instagram":
                    task = adapter.to_instagram_task(video_path)
                    with InstagramPublisher(log_callback=self.add_log) as pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "youtube":
                    task = adapter.to_youtube_task(video_path)
                    pub = YouTubePublisher(log_callback=self.add_log)
                    with pub:
                        success, url = pub.publish(task)
                    results[platform] = (success, url)
                    
                elif platform == "wechat":
                    task = adapter.to_wechat_task(video_path)
                    self.wechat_publisher = WeChatPublisher(
                        headless=False,
                        log_callback=self.add_log,
                    )
                    self.wechat_publisher.start()
                    self.wechat_publisher.authenticate()
                    success, msg = self.wechat_publisher.publish(task)
                    results[platform] = (success, msg)
                    if success:
                        self.add_log(
                            "[INFO] 请在浏览器中确认发布，"
                            "然后点击「已完成发布」按钮"
                        )
                        
            except FileNotFoundError as e:
                self.add_log(f"[ERROR] {platform}: 凭据文件未找到 - {e}")
                results[platform] = (False, str(e))
            except Exception as e:
                self.add_log(f"[ERROR] {platform}: {e}")
                results[platform] = (False, str(e))
        
        # 汇总
        self.add_log(f"\n{'='*50}")
        self.add_log("[INFO] 发布结果汇总")
        self.add_log(f"{'='*50}")
        for platform, (success, detail) in results.items():
            status = "✅" if success else "❌"
            self.add_log(f"  {status} {platform}: {detail or '(无详情)'}")
    
    # ============================================================
    # 传统模式（保留）
    # ============================================================
    
    def parse_script_json(self, script_text: Optional[str], platform: str) -> tuple:
        """解析 JSON 脚本文本"""
        empty_result = ("", "", "", "", "", "", "", "", "")
        
        if not script_text or not script_text.strip():
            return empty_result
        
        try:
            data = json.loads(script_text)
            
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
            
            youtube_title = ""
            youtube_description = ""
            youtube_tags = ""
            youtube_playlist = ""
            
            youtube_data = data.get('youtube', {})
            if not youtube_data and wechat_data:
                youtube_title = wechat_data.get('title', '')
                youtube_description = wechat_data.get('description', '')
                hashtags = wechat_data.get('hashtags', [])
                tags = [tag.replace('#', '') for tag in hashtags if tag.startswith('#')]
                youtube_tags = ', '.join(tags)
            elif youtube_data:
                youtube_title = youtube_data.get('title', '')
                youtube_description = youtube_data.get('description', '')
                tags_list = youtube_data.get('tags', youtube_data.get('hashtags', []))
                tags_list = [tag.replace('#', '').strip() for tag in tags_list]
                youtube_tags = ', '.join(tags_list)
                youtube_playlist = youtube_data.get('playlists', '')
            
            self.add_log("[INFO] ✅ JSON 格式正确，已解析脚本")
            
            return (wechat_title, wechat_description, wechat_hashtags,
                    wechat_heji, wechat_huodong,
                    youtube_title, youtube_description, youtube_tags,
                    youtube_playlist)
            
        except json.JSONDecodeError as e:
            self.add_log(f"[ERROR] JSON 格式错误: {e}")
            return empty_result
        except Exception as e:
            self.add_log(f"[ERROR] 解析脚本失败: {e}")
            return empty_result
    
    def publish_legacy(
        self, 
        video_file,
        platform: str,
        wechat_title: str,
        wechat_description: str,
        wechat_hashtags: str,
        wechat_heji: str,
        wechat_huodong: str,
        youtube_title: str,
        youtube_description: str,
        youtube_tags: str,
        youtube_playlist: str,
        youtube_privacy: str,
    ):
        """传统模式发布（流式日志）"""
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
            video_path = Path(
                video_file.name if hasattr(video_file, 'name') else video_file
            )
            
            if platform in ["wechat", "both"]:
                self.add_log("\n" + "="*50)
                self.add_log("[INFO] 发布到微信视频号")
                self.add_log("="*50)
                yield self.get_logs()
                
                for _ in self._publish_to_wechat_stream(
                    video_path, wechat_title, wechat_description,
                    wechat_hashtags, wechat_heji, wechat_huodong
                ):
                    yield self.get_logs()
            
            if platform in ["youtube", "both"]:
                self.add_log("\n" + "="*50)
                self.add_log("[INFO] 发布到 YouTube Shorts")
                self.add_log("="*50)
                yield self.get_logs()
                
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
        try:
            hashtag_list = []
            if hashtags.strip():
                hashtag_list = [
                    tag.strip() for tag in hashtags.split() if tag.strip()
                ]
            
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
            yield
            
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
                self.add_log(
                    "[INFO] ✅ 微信视频号发布流程完成！"
                    "请在浏览器中确认发布。"
                )
                self.add_log(
                    "[INFO] 💡 确认发布后，点击「已完成发布」按钮。"
                )
            else:
                self.add_log(f"[ERROR] 微信视频号发布失败: {message}")
            yield
            
        except Exception as e:
            self.add_log(f"[ERROR] 微信视频号发布失败: {e}")
            yield
    
    def _publish_to_youtube_stream(
        self, video_path: Path, title: str, description: str,
        tags: str, playlist: str, privacy: str
    ):
        """发布到 YouTube（流式版本）"""
        operation_done = threading.Event()
        
        def run_publish():
            try:
                self._publish_to_youtube(
                    video_path, title, description, tags, playlist, privacy
                )
            except Exception as e:
                self.add_log(f"[ERROR] YouTube 发布异常: {e}")
            finally:
                operation_done.set()
        
        thread = threading.Thread(target=run_publish, daemon=True)
        thread.start()
        
        while not operation_done.is_set():
            yield
            time.sleep(0.3)
        
        thread.join(timeout=1.0)
        yield
    
    def _publish_to_youtube(
        self, video_path: Path, title: str, description: str,
        tags: str, playlist: str, privacy: str
    ):
        """发布到YouTube"""
        try:
            tags_list = []
            if tags and tags.strip():
                tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            title = title or ""
            description = description or ""
            playlist = playlist or ""
            
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
            
            self.youtube_publisher = YouTubePublisher(
                log_callback=self.add_log
            )
            
            with self.youtube_publisher:
                success, video_url = self.youtube_publisher.publish(task)
                
                if success:
                    self.add_log(f"[INFO] ✅ YouTube Shorts 上传成功！")
                    self.add_log(f"[INFO] 视频链接: {video_url}")
                else:
                    self.add_log(f"[ERROR] YouTube 上传失败")
            
        except FileNotFoundError as e:
            self.add_log(f"[ERROR] YouTube 认证文件未找到: {e}")
        except Exception as e:
            self.add_log(f"[ERROR] YouTube 发布失败: {e}")


def create_app() -> gr.Blocks:
    """创建 Gradio 应用"""
    
    app_instance = PublisherApp()
    
    with gr.Blocks(
        title="火箭发射",
        theme=gr.themes.Soft(),
        css="""
        .main-container { max-width: 1000px; margin: 0 auto; }
        .publish-btn { height: 50px !important; font-size: 18px !important; }
        """
    ) as app:
        
        with gr.Row():
            with gr.Column(scale=1, min_width=120):
                gr.Markdown("# 🚀 火箭发射\n多平台发布工具")
            with gr.Column(scale=4):
                gr.Markdown(
                    "💡 **使用说明**: "
                    "选择 **Episode 模式** 从 ep*.json 发布，"
                    "或 **传统模式** 手动填写参数发布"
                )
        
        with gr.Tabs():
            # ============================================================
            # Tab 1: Episode 模式
            # ============================================================
            with gr.TabItem("📄 Episode 模式 (推荐)"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        ep_file_input = gr.File(
                            label="📄 ep*.json 文件",
                            file_types=[".json"],
                            type="filepath",
                            file_count="single",
                            height=120,
                        )
                        load_ep_btn = gr.Button(
                            "📖 加载素材", variant="secondary"
                        )
                        
                        ep_summary = gr.Textbox(
                            label="📋 素材信息",
                            lines=5,
                            interactive=False,
                        )
                    
                    with gr.Column(scale=1):
                        ep_platform_checkboxes = gr.CheckboxGroup(
                            choices=[
                                "medium", "twitter", "devto",
                                "tiktok", "instagram",
                                "wechat", "youtube",
                            ],
                            value=["medium", "twitter"],
                            label="🎯 发布平台",
                            info="文章类无需视频，视频类需上传视频文件",
                        )
                        
                        ep_video_input = gr.File(
                            label="📹 视频文件 (视频平台需要)",
                            file_types=[".mp4", ".mov", ".avi"],
                            type="filepath",
                            file_count="single",
                            height=100,
                        )
                
                ep_preview = gr.Textbox(
                    label="📝 文章预览 (overseas_blog)",
                    lines=6,
                    max_lines=8,
                    interactive=False,
                )
                
                with gr.Row():
                    ep_publish_btn = gr.Button(
                        "🚀 发布",
                        variant="primary",
                        elem_classes=["publish-btn"],
                        scale=3,
                    )
                    ep_close_btn = gr.Button(
                        "✅ 已完成发布(微信)",
                        variant="secondary",
                        elem_classes=["publish-btn"],
                        scale=1,
                    )
                
                # 绑定事件
                load_ep_btn.click(
                    fn=app_instance.load_episode,
                    inputs=[ep_file_input],
                    outputs=[ep_summary, ep_preview],
                    api_name=False,
                )
                
                ep_publish_btn.click(
                    fn=app_instance.publish_episode,
                    inputs=[
                        ep_file_input, ep_platform_checkboxes, ep_video_input,
                    ],
                    outputs=[gr.Textbox(
                        label="",
                        lines=15,
                        max_lines=15,
                        interactive=False,
                        show_label=False,
                        autoscroll=True,
                        elem_id="ep_log_output",
                    )],
                    api_name=False,
                )
                
                ep_close_btn.click(
                    fn=app_instance.close_browser,
                    inputs=[],
                    outputs=[],
                    api_name=False,
                )
            
            # ============================================================
            # Tab 2: 传统模式
            # ============================================================
            with gr.TabItem("📹 传统模式 (微信/YouTube)"):
                with gr.Row(equal_height=True):
                    platform_radio = gr.Radio(
                        choices=["wechat", "youtube", "both"],
                        value="wechat",
                        label="🎯 发布平台",
                        info="选择要发布到的平台",
                        scale=1,
                    )
                    
                    video_input = gr.File(
                        label="📹 视频文件 (必需)",
                        file_types=[".mp4", ".mov", ".avi"],
                        type="filepath",
                        file_count="single",
                        scale=1,
                        height=200,
                    )
                    
                    with gr.Column(scale=2):
                        script_input = gr.Textbox(
                            label="📄 脚本 (JSON 格式)",
                            placeholder='{\n  "wechat": {...},\n  "youtube": {...}\n}',
                            lines=7,
                            max_lines=10,
                        )
                        parse_script_btn = gr.Button(
                            "✅ 确认脚本", variant="secondary", size="sm"
                        )
                
                with gr.Group(visible=True) as wechat_group:
                    gr.Markdown("### 📱 微信视频号")
                    with gr.Row():
                        with gr.Column(scale=1):
                            wechat_title_input = gr.Textbox(
                                label="标题 (最多16字)",
                                placeholder="输入视频标题...",
                                max_lines=1,
                            )
                            wechat_hashtags_input = gr.Textbox(
                                label="话题标签 (空格分隔)",
                                placeholder="#标签1 #标签2",
                                max_lines=1,
                            )
                        with gr.Column(scale=1):
                            wechat_description_input = gr.Textbox(
                                label="描述",
                                placeholder="输入视频描述...",
                                lines=4,
                            )
                    with gr.Row():
                        wechat_heji_input = gr.Textbox(
                            label="合集名称 (可选)",
                            placeholder="合集名称...",
                            max_lines=1,
                        )
                        wechat_huodong_input = gr.Textbox(
                            label="活动名称 (可选)",
                            placeholder="活动名称...",
                            max_lines=1,
                        )
                
                with gr.Group(visible=False) as youtube_group:
                    gr.Markdown("### 📺 YouTube Shorts")
                    with gr.Row():
                        with gr.Column(scale=1):
                            youtube_title_input = gr.Textbox(
                                label="标题 (必需)",
                                placeholder="YouTube 视频标题...",
                                max_lines=1,
                            )
                            youtube_tags_input = gr.Textbox(
                                label="标签 (逗号分隔)",
                                placeholder="标签1, 标签2",
                                max_lines=1,
                            )
                        with gr.Column(scale=1):
                            youtube_description_input = gr.Textbox(
                                label="描述 (必需)",
                                placeholder="YouTube 视频描述...",
                                lines=4,
                            )
                    with gr.Row():
                        youtube_playlist_input = gr.Textbox(
                            label="播放列表 (可选)",
                            placeholder="播放列表名称...",
                            max_lines=1,
                            scale=2,
                        )
                        youtube_privacy_dropdown = gr.Dropdown(
                            choices=["private", "unlisted", "public"],
                            value="private",
                            label="隐私设置",
                            scale=1,
                        )
                
                with gr.Row():
                    legacy_publish_btn = gr.Button(
                        "🚀 发布",
                        variant="primary",
                        elem_classes=["publish-btn"],
                        scale=3,
                    )
                    legacy_close_btn = gr.Button(
                        "✅ 已完成发布(微信)",
                        variant="secondary",
                        elem_classes=["publish-btn"],
                        scale=1,
                    )
                
                # 平台切换
                def update_platform_visibility(platform):
                    wechat_visible = gr.update(
                        visible=platform in ["wechat", "both"]
                    )
                    youtube_visible = gr.update(
                        visible=platform in ["youtube", "both"]
                    )
                    close_btn_visible = gr.update(
                        visible=platform in ["wechat", "both"]
                    )
                    return wechat_visible, youtube_visible, close_btn_visible
                
                platform_radio.change(
                    fn=update_platform_visibility,
                    inputs=[platform_radio],
                    outputs=[wechat_group, youtube_group, legacy_close_btn],
                    api_name=False,
                )
                
                parse_script_btn.click(
                    fn=lambda s, p: app_instance.parse_script_json(s, p),
                    inputs=[script_input, platform_radio],
                    outputs=[
                        wechat_title_input, wechat_description_input,
                        wechat_hashtags_input, wechat_heji_input,
                        wechat_huodong_input,
                        youtube_title_input, youtube_description_input,
                        youtube_tags_input, youtube_playlist_input,
                    ],
                    api_name=False,
                )
                
                legacy_publish_btn.click(
                    fn=app_instance.publish_legacy,
                    inputs=[
                        video_input, platform_radio,
                        wechat_title_input, wechat_description_input,
                        wechat_hashtags_input, wechat_heji_input,
                        wechat_huodong_input,
                        youtube_title_input, youtube_description_input,
                        youtube_tags_input, youtube_playlist_input,
                        youtube_privacy_dropdown,
                    ],
                    outputs=[gr.Textbox(
                        label="",
                        lines=15,
                        max_lines=15,
                        interactive=False,
                        show_label=False,
                        autoscroll=True,
                        elem_id="legacy_log_output",
                    )],
                    api_name=False,
                )
                
                legacy_close_btn.click(
                    fn=app_instance.close_browser,
                    inputs=[],
                    outputs=[],
                    api_name=False,
                )
        
        # 共用日志区域
        gr.Markdown("### 📋 日志")
        
        log_output = gr.Textbox(
            label="",
            lines=15,
            max_lines=15,
            interactive=False,
            show_label=False,
            autoscroll=True,
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
