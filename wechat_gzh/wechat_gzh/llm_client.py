"""
LLM 评论生成模块 - 使用大模型生成智能评论
"""

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

logger = logging.getLogger("wechat-gzh")


class OllamaServiceManager:
    """Ollama 服务管理器"""
    
    _cleanup_registered = False
    
    def __init__(self, host: str = "localhost", port: int = 11434):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
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
        """确保 Ollama 服务正在运行"""
        if self.is_running():
            logger.info("Ollama 服务已运行")
            return True
        
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning("Ollama 未安装，请访问 https://ollama.ai 安装")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Ollama 未安装，请访问 https://ollama.ai 安装")
            return False
        
        logger.info("正在启动 Ollama 服务...")
        try:
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            max_wait = 10
            wait_interval = 0.5
            waited = 0
            while waited < max_wait:
                if self.is_running():
                    logger.info(f"Ollama 服务启动成功 (等待 {waited:.1f}s)")
                    return True
                time.sleep(wait_interval)
                waited += wait_interval
            
            if self.process.poll() is not None:
                logger.error("Ollama 服务启动失败")
                self.process = None
                return False
            else:
                logger.warning(f"Ollama 服务可能未就绪 (等待 {max_wait}s)")
                return True
        except Exception as e:
            logger.error(f"启动 Ollama 服务失败: {e}")
            self.process = None
            return False
    
    def cleanup(self) -> None:
        """清理 Ollama 服务进程"""
        if self.process is not None:
            try:
                logger.info("正在停止 Ollama 服务...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    logger.info("Ollama 服务已停止")
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.warning(f"停止 Ollama 服务出错: {e}")
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
            logger.warning("OpenAI 包未安装，LLM 评论生成将被禁用")
            logger.warning("请运行: uv add openai")
            return
        
        try:
            api_key = os.environ.get("OPENAI_API_KEY", "ollama")
            base_url = os.environ.get("OPENAI_BASE_URL")
            
            if not base_url:
                base_url = "http://localhost:11434/v1"
                self.ollama_manager = OllamaServiceManager()
                if not self.ollama_manager.ensure_running():
                    logger.warning("Ollama 服务不可用，LLM 评论生成将被禁用")
                    return
            
            if not api_key or api_key == "ollama":
                api_key = "ollama"
            
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"LLM 客户端初始化成功: {base_url}")
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")
    
    def is_available(self) -> bool:
        """检查 LLM 客户端是否可用"""
        return self.client is not None
    
    def _get_default_model(self) -> str:
        """获取默认模型名称"""
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        
        if "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
            return os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        else:
            return "gpt-3.5-turbo"
    
    def _load_task_config(self) -> None:
        """加载 task_prompt.json 配置文件"""
        if self.config_path is None:
            self.config_path = Path.cwd() / "config" / "task_prompt.json"
        
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.task_config = json.load(f)
            logger.info(f"已加载配置: {self.config_path}")
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.task_config = None
    
    def generate_comment(
        self,
        article_content: str,
        suffix: str = "已关盼回。"
    ) -> Optional[str]:
        """
        根据文章内容生成评论
        
        Args:
            article_content: 文章内容
            suffix: 评论后缀
            
        Returns:
            生成的评论，失败返回 None
        """
        if not self.is_available():
            logger.warning("LLM 客户端不可用")
            return None
        
        if not self.task_config:
            logger.warning("配置未加载")
            return None
        
        if not article_content or not article_content.strip():
            logger.warning("文章内容为空")
            return None
        
        try:
            # 获取任务配置
            task_config = self.task_config.get("task_comment_generation", {})
            persona_config = task_config.get("default")
            
            if not persona_config:
                logger.warning("未找到默认 persona 配置")
                return None
            
            system_prompt = persona_config.get("system_prompt", "")
            user_prompt_template = persona_config.get("user_prompt", "")
            
            if not system_prompt or not user_prompt_template:
                logger.warning("系统提示词或用户提示词为空")
                return None
            
            # 格式化 user_prompt
            user_prompt = user_prompt_template.format(
                article_content=article_content[:2000]  # 限制长度
            )
            
            # 获取模型
            model_name = os.environ.get("OPENAI_MODEL", self._get_default_model())
            
            # 调用 LLM API
            logger.info(f"正在调用 LLM 生成评论 (模型: {model_name})...")
            
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150,
            )
            
            comment = response.choices[0].message.content.strip()
            
            # 清理评论（移除引号等）
            comment = comment.strip('"\'')
            
            # 不再强制添加固定的 suffix
            # 让 AI 自己在评论中自然融入回关意图（已在 prompt 中要求）
            # 如果生成的评论完全没有回关意图，可以适当补充，但不应每次都添加
            # 检查评论中是否已经包含回关相关的关键词
            follow_back_keywords = ["关", "互关", "回关", "关注", "交流", "互粉"]
            has_follow_back_intent = any(keyword in comment for keyword in follow_back_keywords)
            
            # 如果评论完全没有回关意图，且 suffix 非空，才考虑添加
            # 但优先相信 AI 的生成结果，只在明显缺失时补充
            if not has_follow_back_intent and suffix and len(comment) < 15:
                # 只对过短的评论补充，避免破坏 AI 的自然表达
                logger.info("评论中缺少回关意图，但已包含在 prompt 中，相信 AI 生成结果")
            
            logger.info(f"LLM 生成评论: {comment}")
            return comment
            
        except Exception as e:
            logger.error(f"生成评论失败: {e}")
            return None
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.ollama_manager:
            self.ollama_manager.cleanup()
