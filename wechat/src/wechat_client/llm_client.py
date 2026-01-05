from __future__ import annotations

import json
import logging
import time
import os
import subprocess
import atexit
import socket
from pathlib import Path
from typing import Optional, Dict, List, Any

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
    
    def __init__(self, config_path: Optional[Path] = None):
        self.client: Optional["OpenAI"] = None  # type: ignore
        self.ollama_manager: Optional[OllamaServiceManager] = None
        self.config_path = config_path
        self.task_config: Optional[Dict[str, Any]] = None
        self._initialize()
        self._load_task_config()
    
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
    
    def _load_task_config(self) -> None:
        """加载 task_prompt.json 配置文件"""
        if self.config_path is None:
            # 尝试自动查找配置文件
            # 优先查找当前工作目录下的 config/task_prompt.json
            possible_paths = [
                Path.cwd() / "config" / "task_prompt.json",
                Path.cwd() / "wechat" / "config" / "task_prompt.json",
                Path(__file__).resolve().parent.parent.parent / "config" / "task_prompt.json",
            ]
            
            for path in possible_paths:
                if path.exists():
                    self.config_path = path
                    break
        
        if self.config_path is None or not self.config_path.exists():
            logger.warning(f"Task prompt config file not found. Path: {self.config_path}")
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.task_config = json.load(f)
            logger.info(f"Loaded task prompt config from: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load task prompt config: {e}")
            self.task_config = None
    
    def generate_comment_from_task(
        self,
        video_description: str,
        comments: List[str],
        persona: str = "yi_ba",
        task_name: str = "task_comment_generation"
    ) -> Optional[Dict[str, Any]]:
        """
        根据 task_prompt.json 配置生成评论
        
        Args:
            video_description: 视频描述文本
            comments: 他人评论列表（最多取前3条）
            persona: 角色名称，默认为 "yi_ba"，可选 "yi_ma"
            task_name: 任务名称，默认为 "task_comment_generation"
            
        Returns:
            包含 comment、real_human_score、follow_back_score、persona_consistency_score 的字典
            如果生成失败或不符合条件，返回 None
        """
        if not self.is_available():
            logger.warning("LLM client not available. Cannot generate comment.")
            return None
        
        if not self.task_config:
            logger.warning("Task config not loaded. Cannot generate comment from task.")
            return None
        
        if not video_description or not video_description.strip():
            logger.warning("Video description is empty. Cannot generate comment.")
            return None
        
        try:
            # 获取任务配置
            task_config = self.task_config.get(task_name, {})
            persona_config = task_config.get(persona)
            
            if not persona_config:
                logger.warning(f"Persona '{persona}' not found in task config.")
                return None
            
            system_prompt = persona_config.get("system_prompt", "")
            user_prompt_template = persona_config.get("user_prompt", "")
            
            if not system_prompt or not user_prompt_template:
                logger.warning(f"System prompt or user prompt template is empty for persona '{persona}'.")
                return None
            
            # 格式化 user_prompt
            # 取前3条评论，如果不足3条则用空字符串填充
            comment_1 = comments[0] if len(comments) > 0 else ""
            comment_2 = comments[1] if len(comments) > 1 else ""
            comment_3 = comments[2] if len(comments) > 2 else ""
            
            user_prompt = user_prompt_template.format(
                video_description=video_description,
                comment_1=comment_1,
                comment_2=comment_2,
                comment_3=comment_3
            )
            
            # 获取模型名称
            default_model = self._get_default_model()
            model_name = os.environ.get("OPENAI_MODEL", default_model)
            
            # 调用 LLM API
            # 尝试使用 response_format（如果模型支持），否则回退到普通调用
            api_params = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 300,  # JSON 输出可能需要更多 tokens
            }
            
            # 尝试添加 response_format（某些模型可能不支持，需要捕获异常）
            try:
                api_params["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**api_params)
            except Exception as e:
                # 如果 response_format 不支持，回退到不使用它
                logger.debug(f"Response format not supported, falling back: {e}")
                api_params.pop("response_format", None)
                response = self.client.chat.completions.create(**api_params)
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析 JSON 输出
            try:
                # 尝试提取 JSON（可能包含其他文本）
                # 先尝试直接解析
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取 JSON 部分
                # 查找第一个 { 和最后一个 }
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}")
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx + 1]
                    result = json.loads(json_str)
                else:
                    logger.error(f"Failed to parse JSON from response: {response_text}")
                    return None
            
            # 验证返回的字段
            required_fields = ["comment", "real_human_score", "follow_back_score", "persona_consistency_score"]
            for field in required_fields:
                if field not in result:
                    logger.warning(f"Missing required field '{field}' in LLM response.")
            
            # 如果 comment 为 None 或空，返回 None
            comment = result.get("comment")
            if not comment or comment == "None" or (isinstance(comment, str) and comment.strip() == ""):
                logger.info("❌❌LLM decided not to generate comment (comment=None).")
                return None
            
            # 记录评分信息
            logger.info(
                f"Generated comment from task (persona={persona}): {comment}\n"
                f"Scores - real_human: {result.get('real_human_score')}, "
                f"follow_back: {result.get('follow_back_score')}, "
                f"consistency: {result.get('persona_consistency_score')}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate comment from task: {e}")
            return None
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.ollama_manager:
            self.ollama_manager.cleanup()

