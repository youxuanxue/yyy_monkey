from __future__ import annotations

import logging
import time
import os
import subprocess
import atexit
import socket
from typing import Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None  # type: ignore

logger = logging.getLogger("wechat-bot")


class OllamaServiceManager:
    """Ollama 服务管理器，负责启动、检查和关闭 Ollama 服务"""
    
    _cleanup_registered = False  # 类级别的标志，避免重复注册
    
    def __init__(self, host: str = "localhost", port: int = 11434):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        # 注册退出时清理函数（只注册一次，使用类级别标志）
        if not OllamaServiceManager._cleanup_registered:
            atexit.register(self.cleanup)
            OllamaServiceManager._cleanup_registered = True
    
    def is_running(self) -> bool:
        """检查 Ollama 服务是否正在运行"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def ensure_running(self) -> bool:
        """
        确保 Ollama 服务正在运行，如果没有则启动
        
        Returns:
            bool: 如果服务可用则返回 True，否则返回 False
        """
        # 检查服务是否已运行
        if self.is_running():
            logger.info("Ollama service is already running.")
            return True
        
        # 检查 ollama 命令是否可用
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning("Ollama command not found or not working. Please install Ollama first.")
                logger.warning("Visit https://ollama.ai to install Ollama.")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Ollama command not found. Please install Ollama first.")
            logger.warning("Visit https://ollama.ai to install Ollama.")
            return False
        
        # 启动 Ollama 服务
        logger.info("Starting Ollama service...")
        try:
            # 使用 subprocess.Popen 启动服务（后台运行）
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # 创建新会话，避免主进程退出时子进程被终止
            )
            
            # 等待服务启动（最多等待 10 秒）
            max_wait = 10
            wait_interval = 0.5
            waited = 0
            while waited < max_wait:
                if self.is_running():
                    logger.info(f"Ollama service started successfully (waited {waited:.1f}s).")
                    return True
                time.sleep(wait_interval)
                waited += wait_interval
            
            # 如果超时仍未启动，检查进程状态
            if self.process.poll() is not None:
                logger.error("Ollama service failed to start. Please check if Ollama is installed correctly.")
                self.process = None
                return False
            else:
                logger.warning(f"Ollama service may not be ready yet (waited {max_wait}s). Continuing anyway...")
                return True
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")
            self.process = None
            return False
    
    def cleanup(self) -> None:
        """清理 Ollama 服务进程（程序退出时调用）"""
        if self.process is not None:
            try:
                logger.info("Stopping Ollama service...")
                self.process.terminate()
                # 等待最多 5 秒让进程正常退出
                try:
                    self.process.wait(timeout=5)
                    logger.info("Ollama service stopped successfully.")
                except subprocess.TimeoutExpired:
                    # 如果 5 秒后仍未退出，强制终止
                    logger.warning("Ollama service did not stop gracefully, forcing termination...")
                    self.process.kill()
                    self.process.wait()
                    logger.info("Ollama service force stopped.")
            except Exception as e:
                logger.warning(f"Error while stopping Ollama service: {e}")
            finally:
                self.process = None


class LLMCommentGenerator:
    """大模型评论生成器"""
    
    def __init__(self):
        self.client: Optional["OpenAI"] = None  # type: ignore
        self.ollama_manager: Optional[OllamaServiceManager] = None
        self._initialize()
    
    def _initialize(self) -> None:
        """初始化 LLM 客户端"""
        if not HAS_OPENAI:
            logger.warning("OpenAI package not installed. LLM comment generation will be disabled.")
            return
        
        try:
            # 从环境变量获取配置
            api_key = os.environ.get("OPENAI_API_KEY", "ollama")
            base_url = os.environ.get("OPENAI_BASE_URL")
            
            # 如果没有设置 base_url，使用 Ollama（本地模型）
            if not base_url:
                base_url = "http://localhost:11434/v1"
                # 自动启动和管理 Ollama 服务
                self.ollama_manager = OllamaServiceManager()
                if not self.ollama_manager.ensure_running():
                    logger.warning("Failed to start Ollama service. LLM comment generation will be disabled.")
                    return
            
            # 如果设置了 base_url 但没有 api_key，使用默认值
            if not api_key or api_key == "ollama":
                api_key = "ollama"  # Ollama 使用占位符
            
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"LLM client initialized successfully. Base URL: {base_url}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")
            logger.warning("LLM comment generation will be disabled. Falling back to default comments.")
    
    def is_available(self) -> bool:
        """检查 LLM 客户端是否可用"""
        return self.client is not None
    
    def generate_comment(
        self, 
        topic_text: str, 
        activity_tag: str = "#小小谋略家"
    ) -> Optional[str]:
        """
        使用大模型根据视频描述生成适合的评论。
        大模型会根据视频内容自动判断是否需要插入活动邀请。
        
        Args:
            topic_text: 视频号的视频描述文本
            activity_tag: 活动标签（默认 "#小小谋略家"）
            
        Returns:
            生成的评论文本，如果生成失败则返回 None
        """
        if not self.is_available():
            logger.warning("LLM client not available. Cannot generate comment.")
            return None
        
        if not topic_text or not topic_text.strip():
            logger.warning("Topic text is empty. Cannot generate comment.")
            return None
        
        try:
            # 构建提示词，针对 qwen2.5:3b 模型优化，确保生成与视频内容相关的优质评论
            system_prompt = (
                "你是一位35岁、育有一双儿女（儿女双全）的平凡家长。你性格善良、真诚，热爱生活，看视频时总能发现生活中的闪光点。\n\n"
                "**你的评论风格：**\n"
                "1. **真实感：** 说话要有生活气息，多用‘咱们’、‘孩子’、‘受教了’、‘共勉’等接地气的词汇。\n"
                "2. **情绪价值：** 作为一个成熟的中年人，你的评论要温暖、包容，带有一点点人生阅历感，像是老朋友间的闲聊。\n"
                "3. **字数约束：** 保持在15-40字，不啰嗦，一语破的。\n"
                "4. **禁止：** 禁止使用‘祝你视频大火’、‘点赞分享’等营销号用语，禁止使用过于死板的成语堆砌。\n\n"
                "**活动邀请逻辑（非常重要）：**\n"
                f"1. **判定标准：** 只有视频内容深度涉及《孙子兵法》、古代谋略、思维局限破除、职场策略时，才在结尾顺带提一句活动。\n"
                f"2. **融合方式：** 话锋要自然。例如：‘...这种智慧，带孩子参加{activity_tag}挺合适的。’\n"
                f"3. **无关内容：** 如果是纯育儿、风景、美食、搞笑或生活琐事，**绝对不要**提活动，只发自内心地夸赞视频内容。"
            )
            
            user_prompt = (
                f"【视频内容】: {topic_text}\n\n"
                "请以这位35岁家长的身份，看完视频后写下一条发自肺腑的短评。记住：要像真人写的，要有温度。"
            )            
            # 获取模型名称，默认根据 base_url 判断
            default_model = self._get_default_model()
            model_name = os.environ.get("OPENAI_MODEL", default_model)
            
            # 调用 LLM API
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,        # 适度的随机性
                top_p=0.9,              # 保证逻辑合理性
                presence_penalty=0.6,   # 减少套话，鼓励新鲜表达
                frequency_penalty=0.3,  # 减少词汇重复
                max_tokens=150,          # 限制长度，节省资源
                stop=["\n", "评论："]     # 强制停止符，防止模型自言自语
            )            
            
            comment = response.choices[0].message.content.strip()
            
            # 记录是否包含活动标签（由模型决定）
            includes_activity = activity_tag in comment
            
            logger.info(f"Generated comment with LLM (activity_invite={includes_activity}): {comment}")
            return comment
            
        except Exception as e:
            logger.error(f"Failed to generate comment with LLM: {e}")
            return None
    
    def _get_default_model(self) -> str:
        """
        获取默认模型名称
        
        Returns:
            默认模型名称
        """
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        
        # 推荐模型优先级：
        # 1. qwen2.5:3b - 默认模型（推荐）：3B参数，中文能力强，质量好，速度适中
        # 2. qwen2.5:1.5b - 最小配置：1.5B参数，适合资源受限环境，速度快
        # 3. qwen2.5:7b - 高质量：7B参数，质量最好但需要更多资源
        
        if "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
            # 使用 Ollama，默认使用 qwen2.5:3b（最佳平衡）
            return os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        else:
            # 使用其他服务，默认使用 gpt-3.5-turbo
            return "gpt-3.5-turbo"
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.ollama_manager:
            self.ollama_manager.cleanup()

