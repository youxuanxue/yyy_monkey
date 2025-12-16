from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import Image

from wechat_client.platform_mgr import PlatformManager

# 配置 pyautogui 安全设置
pyautogui.FAILSAFE = True  # 鼠标移动到角落触发异常
pyautogui.PAUSE = 0.5      # 默认操作间隔

logger = logging.getLogger("wechat-bot")

class BotCore:
    def __init__(self, asset_dir: Path, pm: PlatformManager) -> None:
        self.asset_dir = asset_dir
        self.pm = pm
        self.confidence = 0.85  # 图像匹配置信度

    def _locate(self, image_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int]]:
        """
        在屏幕上查找图片，返回中心坐标 (x, y)。
        image_name 不带路径，自动从 asset_dir/platform_name/ 下查找。
        """
        img_path = self.asset_dir / self.pm.get_asset_dir_name() / image_name
        if not img_path.exists():
            # 兼容：如果 specific 目录没有，试着找 assets 根目录
            img_path = self.asset_dir / image_name
        
        if not img_path.exists():
            logger.warning(f"Image asset not found: {img_path}")
            return None

        try:
            # grayscale=True 加快速度，但可能降低准确度（颜色敏感的图标不要开）
            box = pyautogui.locateOnScreen(str(img_path), confidence=self.confidence, region=region, grayscale=False)
            if box:
                # 修复 Mac Retina 坐标问题：
                # box 是在物理截图上找到的坐标，需要除以 scale_factor 转换回逻辑坐标
                center_x, center_y = pyautogui.center(box)
                return (int(center_x / self.pm.scale_factor), int(center_y / self.pm.scale_factor))
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            logger.error(f"Locate error: {e}")
        return None

    def _click_at(self, x: int, y: int, double: bool = False) -> None:
        """移动并点击"""
        # 增加随机偏移，模拟真人
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        if double:
            pyautogui.doubleClick(x + offset_x, y + offset_y)
        else:
            pyautogui.click(x + offset_x, y + offset_y)

    def find_and_click(self, image_name: str, retry: int = 3, wait: float = 1.0) -> bool:
        """
        查找并点击图标。
        retry: 重试次数
        wait: 每次重试间隔
        """
        for i in range(retry):
            pos = self._locate(image_name)
            if pos:
                logger.info(f"Found {image_name} at {pos}, clicking...")
                self._click_at(pos[0], pos[1])
                return True
            time.sleep(wait)
        logger.info(f"Not found: {image_name}")
        return False

    def send_comment(self, text: str) -> bool:
        """
        发送评论流程：
        1. 查找“评论输入框”图标 (comment_input.png) 或 “发送”按钮旁的空白区
        2. 点击激活焦点
        3. 粘贴文本
        4. 发送 (点击发送按钮 或 回车)
        """
        # 1. 寻找评论输入框特征
        # 建议截取“写评论...”那个灰色的框
        pos = self._locate("comment_input.png")
        if not pos:
            # 尝试寻找“评论图标”点击展开侧边栏（如果未展开）
            if self.find_and_click("comment_icon.png"):
                time.sleep(1.0)
                pos = self._locate("comment_input.png")
        
        if not pos:
            logger.warning("无法找到评论输入框")
            return False

        # 2. 点击激活
        self._click_at(pos[0], pos[1])
        time.sleep(0.5)

        # 3. 粘贴文本
        # 先全选删除旧的（如果有）
        self.pm.select_all()
        pyautogui.press("backspace")
        
        logger.info(f"Pasting comment: {text}")
        self.pm.copy_text(text)
        time.sleep(0.2)
        self.pm.paste()
        time.sleep(0.5)

        # 4. 发送
        # 优先尝试点击“发送”按钮 (send_btn.png)
        if self.find_and_click("send_btn.png"):
            logger.info("Clicked send button.")
            return True
        else:
            # 兜底：回车
            logger.info("Pressing Enter to send.")
            self.pm.enter()
            return True

    def like_current(self) -> bool:
        """
        点赞流程：
        寻找“未点赞的爱心” (like_empty.png)。
        如果找到“已点赞的爱心” (like_filled.png)，则跳过。
        """
        if self._locate("like_filled.png"):
            logger.info("Already liked. Skipping.")
            return True # 视为成功
        
        if self.find_and_click("like_empty.png"):
            logger.info("Liked video.")
            return True
        
        logger.warning("Like button not found.")
        return False

    def scroll_next(self) -> None:
        """
        切换到下一个视频。
        简单粗暴：鼠标滚轮向下，或者键盘 Down 键。
        为保证焦点在视频区域，先点击一下中心（或视频区域特征）。
        """
        # 假设屏幕中心是视频区
        w, h = pyautogui.size()
        pyautogui.moveTo(w // 2, h // 2)
        # pyautogui.click() # 慎点，可能会暂停视频
        
        logger.info("Scrolling to next video...")
        if self.pm.is_mac:
            # Mac 滚轮
            pyautogui.scroll(-5) 
        else:
            pyautogui.scroll(-300) 
        
        # 或者使用键盘
        # pyautogui.press("down") 
        time.sleep(1.5)
