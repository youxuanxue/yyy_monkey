"""
LLM 评论生成模块 - 使用大模型生成智能评论
"""

from __future__ import annotations

import json
import logging
import time
import os
import sys
import subprocess
import atexit
import socket
import platform
from pathlib import Path
from typing import Optional, Dict, List, Any

from .config import OLLAMA_CONFIG, PROJECT_DIR

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None  # type: ignore

logger = logging.getLogger("wechat-gzh")


class OllamaServiceManager:
    """Ollama 服务管理器（使用系统安装的 Ollama）"""
    
    _cleanup_registered = False
    
    def __init__(self, host: str = OLLAMA_CONFIG["host"], port: int = OLLAMA_CONFIG["port"]):
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
            logger.info(f"Ollama 服务已在运行 ({self.host}:{self.port})")
            return True
  
        # 检查系统是否安装了 ollama
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning("系统未安装 Ollama，请先安装: https://ollama.ai")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("系统未安装 Ollama，请先安装: https://ollama.ai")
            return False

        logger.info("正在启动 Ollama 服务...")
        try:
            # Windows 下隐藏窗口
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"{self.host}:{self.port}"
            
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=env,
                startupinfo=startupinfo
            )
            
            max_wait = 15
            wait_interval = 0.5
            waited = 0
            while waited < max_wait:
                if self.is_running():
                    logger.info(f"Ollama 服务启动成功 (等待 {waited:.1f}s)")
                    return True
                time.sleep(wait_interval)
                waited += wait_interval
            
            if self.process.poll() is not None:
                _, stderr = self.process.communicate()
                logger.error(f"Ollama 服务启动失败: {stderr.decode('utf-8', errors='ignore')}")
                self.process = None
                return False
            else:
                logger.warning(f"Ollama 服务可能未就绪 (等待 {max_wait}s)")
                return True
        except Exception as e:
            logger.error(f"启动 Ollama 服务失败: {e}")
            self.process = None
            return False
    
    def pull_model(self, model_name: str) -> bool:
        """拉取模型"""
        logger.info(f"正在尝试拉取模型 {model_name} (这可能需要几分钟)...")
        try:
            # Windows 下隐藏窗口
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            # 设置环境变量（主要针对内置 Ollama 需要 OLLAMA_MODELS）
            env = os.environ.copy()
            if self.is_embedded:
                models_path = os.path.join(PROJECT_DIR, OLLAMA_CONFIG["models_path"])
                env["OLLAMA_MODELS"] = models_path
                env["OLLAMA_HOST"] = f"{self.host}:{self.port}"

            subprocess.run(
                [self.cmd, "pull", model_name],
                check=True,
                env=env,
                startupinfo=startupinfo
            )
            logger.info(f"模型 {model_name} 拉取成功")
            return True
        except subprocess.CalledProcessError:
            logger.error(f"模型 {model_name} 拉取失败")
            return False
        except Exception as e:
            logger.error(f"拉取模型出错: {e}")
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
                # 默认连接本地 Ollama
                host = OLLAMA_CONFIG["host"]
                port = OLLAMA_CONFIG["port"]
                base_url = f"http://{host}:{port}/v1"
                
                self.ollama_manager = OllamaServiceManager(host, port)
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
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        
        # 如果是本地服务
        if not base_url or "localhost" in base_url or "127.0.0.1" in base_url:
            # 优先使用环境变量
            model = os.environ.get("OLLAMA_MODEL")
            if model:
                return model
            
            # 默认模型策略
            if platform.system() == "Windows":
                # Windows 下使用 1.5b 模型以提高速度
                return "qwen2.5:1.5b"
            else:
                # 其他系统使用 3b 模型
                return "qwen2.5:3b"
        else:
            return "gpt-3.5-turbo"
    
    def _load_task_config(self) -> None:
        """加载 task_prompt.json 配置文件"""
        if self.config_path is None:
            self.config_path = Path(PROJECT_DIR) / "config" / "task_prompt.json"
        
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
            # 优化：限制文章内容长度，提高生成速度
            # 对于评论生成任务，通常前 800 个字符已足够理解大意
            # 进一步缩短以应对低配置机器
            user_prompt = user_prompt_template.format(
                article_content=article_content[:800]
            )
            
            # 获取模型
            model_name = os.environ.get("OPENAI_MODEL", self._get_default_model())
            
            # 调用 LLM API
            start_time = time.time()
            logger.info(f"正在调用 LLM 生成评论 (模型: {model_name}, 输入长度: {len(article_content[:800])})...")
            
            # 设置较短的超时时间，避免长时间卡死
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=60,  # 评论通常很短，减少生成token数
                    timeout=30.0,   # 30秒超时
                )
            except Exception as e:
                logger.warning(f"LLM 请求超时或出错 ({e})，将使用默认评论")
                return None
            
            elapsed = time.time() - start_time
            logger.info(f"LLM 生成耗时: {elapsed:.2f}s")
            
            comment = response.choices[0].message.content.strip()
            
            # 清理评论（移除引号等）
            comment = comment.strip('"\'')
            
            # 检查评论中是否已经包含回关相关的关键词
            follow_back_keywords = ["关", "互关", "回关", "关注", "交流", "互粉"]
            has_follow_back_intent = any(keyword in comment for keyword in follow_back_keywords)
            
            # 如果评论完全没有回关意图，且 suffix 非空，才考虑添加
            if not has_follow_back_intent and suffix and len(comment) < 15:
                logger.info("评论中缺少回关意图，但已包含在 prompt 中，相信 AI 生成结果")
            
            logger.info(f"LLM 生成评论: {comment}")
            return comment
            
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower() or "404" in error_msg:
                logger.warning(f"模型 {model_name} 未找到，尝试自动拉取...")
                if self.ollama_manager and self.ollama_manager.pull_model(model_name):
                    # 拉取成功后重试一次
                    logger.info("模型拉取成功，正在重试生成评论...")
                    return self.generate_comment(article_content, suffix)
            
            logger.error(f"生成评论失败: {e}")
            return None
    
    def warmup(self, timeout: float = 180.0) -> bool:
        """
        预热模型（触发加载到内存）
        
        Args:
            timeout: 超时时间（秒）
        """
        if not self.is_available():
            return False
            
        try:
            logger.info("正在预热 LLM 模型...")
            
            # 使用 threading 来实现超时控制
            import threading
            result = {"success": False, "error": None}
            
            def _warmup_task():
                try:
                    start_time = time.time()
                    # 发送一个极简请求
                    self.client.chat.completions.create(
                        model=os.environ.get("OPENAI_MODEL", self._get_default_model()),
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=1
                    )
                    logger.info(f"模型预热完成 (耗时: {time.time() - start_time:.2f}s)")
                    result["success"] = True
                except Exception as e:
                    result["error"] = e
            
            t = threading.Thread(target=_warmup_task)
            t.daemon = True
            t.start()
            t.join(timeout)
            
            if t.is_alive():
                logger.warning(f"模型预热超时 ({timeout}s)，将跳过等待，后续可能会较慢")
                return False
                
            if result["error"]:
                logger.warning(f"模型预热失败: {result['error']}")
                return False
                
            return result["success"]
        except Exception as e:
            logger.warning(f"模型预热过程出错: {e}")
            return False

    def cleanup(self) -> None:
        """清理资源"""
        if self.ollama_manager:
            self.ollama_manager.cleanup()
