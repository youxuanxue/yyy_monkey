from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import Image

from wechat_client.adapter import PlatformAdapter

class UIController:
    """
    负责图像识别、点击、输入等高层逻辑
    """
    def __init__(self, resource_dir: Path):
        self.logger = logging.getLogger("wechat-client")
        self.res_dir = resource_dir
        self.adapter = PlatformAdapter()
        
        # 默认置信度
        self.confidence = 0.85
        
        # 检查资源目录
        if not self.res_dir.exists():
            self.logger.warning(f"Resource directory not found: {self.res_dir}")

    def _load_image(self, name: str) -> Optional[str]:
        """返回图片绝对路径字符串，供 pyautogui 使用"""
        p = self.res_dir / name
        if not p.exists():
            # 尝试找 png
            p = self.res_dir / f"{name}.png"
        
        if p.exists():
            return str(p)
        return None

    def find_and_click(self, image_name: str, retry: int = 3, interval: float = 1.0) -> bool:
        """
        寻找图片并点击中心
        """
        path = self._load_image(image_name)
        if not path:
            self.logger.error(f"Image not found: {image_name}")
            return False

        self.logger.info(f"Looking for {image_name} ...")
        
        for i in range(retry):
            try:
                # 使用 opencv 引擎（需要安装 opencv-python）
                # grayscale=True 可以加快速度，但可能降低准确度，视情况而定
                location = pyautogui.locateCenterOnScreen(path, confidence=self.confidence, grayscale=False)
                
                if location:
                    x, y = location
                    # Mac Retina 修正：pyautogui.locateOnScreen 返回的是坐标，
                    # 但在 Retina 屏上截图通常是 2x 大小。
                    # pyautogui 内部已经处理了 scaling 吗？通常是的。
                    # 只要截图也是在同等缩放比例下截取的即可。
                    
                    self.logger.info(f"Found {image_name} at ({x}, {y}), clicking...")
                    pyautogui.click(x, y)
                    return True
            except pyautogui.ImageNotFoundException:
                pass
            except Exception as e:
                self.logger.warning(f"Error finding image: {e}")
            
            time.sleep(interval)
        
        self.logger.warning(f"Failed to find {image_name} after {retry} retries.")
        return False

    def exists(self, image_name: str) -> bool:
        """检查屏幕上是否存在某图片"""
        path = self._load_image(image_name)
        if not path:
            return False
        try:
            return pyautogui.locateOnScreen(path, confidence=self.confidence) is not None
        except:
            return False

    def paste_text(self, text: str) -> None:
        """使用剪贴板输入文本"""
        self.adapter.copy(text)
        time.sleep(0.1)
        self.adapter.paste()
        time.sleep(0.1)

    def send_enter(self) -> None:
        self.adapter.enter()

    def scroll(self) -> None:
        self.adapter.scroll_down(5)

    def input_comment(self, text: str) -> bool:
        """
        完整的评论流程：
        1. 确保已点击输入框（通常在上一步完成，或这里再找一次输入框）
        2. 粘贴文本
        3. 回车发送
        """
        # 假设光标已经在输入框里了
        self.logger.info(f"Pasting comment: {text}")
        self.paste_text(text)
        time.sleep(0.5)
        self.send_enter()
        return True

