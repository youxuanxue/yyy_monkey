"""
工具函数模块
"""

import json
import logging
import os
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import pyautogui

# 配置 pyautogui
pyautogui.FAILSAFE = True  # 移动鼠标到左上角可以中断程序
pyautogui.PAUSE = 0.1  # 每个操作后暂停 0.1 秒


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        
    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器
    logger.handlers.clear()
    
    # 文件处理器
    log_file = os.path.join(
        log_dir, 
        f"auto_comment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


class InterruptHandler:
    """中断处理器 - 用于优雅地处理 Ctrl+C"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._interrupted = False
        return cls._instance
    
    @property
    def interrupted(self) -> bool:
        return self._interrupted
    
    def set_interrupted(self) -> None:
        self._interrupted = True
        print("\n\n⚠️  收到中断信号，正在安全停止...")
    
    def reset(self) -> None:
        self._interrupted = False
    
    def check(self) -> None:
        """检查是否被中断，如果是则抛出 KeyboardInterrupt"""
        if self._interrupted:
            raise KeyboardInterrupt("用户中断")


# 全局中断处理器实例
interrupt_handler = InterruptHandler()


def interruptible_sleep(seconds: float, check_interval: float = 0.5) -> float:
    """
    可中断的睡眠函数
    
    Args:
        seconds: 睡眠时间（秒）
        check_interval: 检查中断的间隔（秒）
        
    Returns:
        实际睡眠的时间
        
    Raises:
        KeyboardInterrupt: 如果收到中断信号
    """
    elapsed = 0.0
    while elapsed < seconds:
        interrupt_handler.check()
        sleep_time = min(check_interval, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
    return elapsed


def random_sleep(min_seconds: float, max_seconds: float) -> float:
    """
    随机等待一段时间（可中断）
    
    Args:
        min_seconds: 最小等待时间（秒）
        max_seconds: 最大等待时间（秒）
        
    Returns:
        实际等待的时间
        
    Raises:
        KeyboardInterrupt: 如果收到中断信号
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    interruptible_sleep(sleep_time)
    return sleep_time


def normalize_title(title: str) -> str:
    """
    标准化标题：去除所有标点符号和空格，用于模糊匹配
    
    Args:
        title: 原始标题
        
    Returns:
        去除标点符号和空格后的标题
    """
    if not title:
        return ""
    # 去除所有标点符号（中英文）和空格
    # 保留中文、英文、数字
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', title)


class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, history_file: str = "comment_history.json"):
        """
        初始化历史记录管理器
        
        Args:
            history_file: 历史记录文件路径
        """
        self.history_file = history_file
        # 确保目录存在
        os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
        self.history: Dict[str, Dict] = self._load_history()
    
    def _load_history(self) -> Dict[str, Dict]:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_history(self) -> None:
        """保存历史记录到文件"""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def is_processed(self, account_name: str, article_title: str) -> bool:
        """
        检查是否已经处理过该公众号的该文章
        
        使用标准化后的标题（去除标点符号）进行模糊匹配，
        避免因 OCR 识别标点不准确导致重复处理。
        
        Args:
            account_name: 公众号名称
            article_title: 文章标题
            
        Returns:
            如果已处理返回 True，否则返回 False
        """
        if account_name in self.history:
            saved_title = self.history[account_name].get("article_title", "")
            # 使用标准化后的标题进行比较（去除标点符号）
            return normalize_title(saved_title) == normalize_title(article_title)
        return False
    
    def is_account_processed(self, account_name: str) -> bool:
        """
        检查公众号是否已经处理过（不检查具体文章）
        
        Args:
            account_name: 公众号名称
            
        Returns:
            如果公众号已在历史记录中返回 True，否则返回 False
        """
        return account_name in self.history
    
    def get_processed_accounts(self) -> set:
        """
        获取所有已处理的公众号名称集合
        
        Returns:
            已处理公众号名称的集合
        """
        return set(self.history.keys())
    
    def add_record(
        self, 
        account_name: str, 
        article_title: str
    ) -> None:
        """
        添加处理记录
        
        如果公众号名称或文章标题为空，则跳过不记录。
        
        Args:
            account_name: 公众号名称
            article_title: 文章标题
        """
        # 公众号名称或文章标题为空时，不记录
        if not account_name or not account_name.strip():
            return
        if not article_title or not article_title.strip():
            return
        
        self.history[account_name] = {
            "article_title": article_title,
            "processed_time": datetime.now().isoformat(),
        }
        self.save_history()
    
    def get_summary(self) -> Dict:
        """
        获取处理汇总信息
        
        Returns:
            汇总信息字典
        """
        total = len(self.history)
        
        return {
            "total": total,
        }


def calibrate():
    """
    校准模式：帮助用户获取屏幕坐标
    
    运行此函数后，移动鼠标到目标位置，按下 Ctrl+C 停止，
    程序会打印当前鼠标位置。
    """
    print("=" * 60)
    print("校准模式")
    print("=" * 60)
    print("将鼠标移动到目标位置，按 Ctrl+C 停止")
    print("程序会每秒打印一次当前鼠标位置")
    print("=" * 60)
    
    try:
        while True:
            x, y = pyautogui.position()
            print(f"当前鼠标位置: x={x}, y={y}")
            time.sleep(1)
    except KeyboardInterrupt:
        x, y = pyautogui.position()
        print(f"\n最终位置: x={x}, y={y}")
        print("校准完成！")


def get_screen_info():
    """获取屏幕信息"""
    screen_width, screen_height = pyautogui.size()
    print(f"屏幕分辨率: {screen_width} x {screen_height}")
    return screen_width, screen_height


if __name__ == "__main__":
    calibrate()
