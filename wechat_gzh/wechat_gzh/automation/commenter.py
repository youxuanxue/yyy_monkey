"""
留言操作模块 - 使用图像识别定位按钮
"""

import os
import time
import random
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

import pyautogui
import pyperclip

from .navigator import Navigator, SCREEN_SCALE
from .utils import random_sleep, interrupt_handler

if TYPE_CHECKING:
    from .calibration import CommenterCalibration

# 获取 assets 目录路径
MODULE_DIR = Path(__file__).parent
PROJECT_DIR = MODULE_DIR.parent.parent
ASSETS_DIR = PROJECT_DIR / "assets"


class Commenter:
    """留言操作类（支持图像识别）"""
    
    # 图片资源文件名（支持多个备选图片）
    COMMENT_BUTTON_IMAGES = [
        "comment_button.png",    # 写留言按钮（气泡图标）
        "comment_button_2.png",  # 写留言按钮（加号图标）
    ]
    COMMENT_INPUT_IMAGES = [
        "comment_input.png",     # 留言输入框（样式1）
        "comment_input_2.png",   # 留言输入框（样式2）
    ]
    SEND_BUTTON_IMAGE = "send_button.png"        # 发送按钮
    
    def __init__(self, navigator: Navigator, confidence: float = 0.8):
        """
        初始化留言器
        
        Args:
            navigator: Navigator 实例
            confidence: 图像识别置信度 (0-1)
        """
        self.navigator = navigator
        self.confidence = confidence
        
        # 获取平台对应的资源目录
        import platform
        self.platform = "mac" if platform.system() == "Darwin" else "win"
        self.asset_dir = ASSETS_DIR / self.platform
        
        # 备用：固定坐标（当图像识别失败时使用）
        self.comment_button_x = 900
        self.comment_button_y = 700
        self.comment_input_x = 900
        self.comment_input_y = 600
        self.send_button_x = 1100
        self.send_button_y = 600
        
        # 是否使用图像识别
        self._use_image_recognition = True
        self._check_assets()
        
        self._positions_calibrated = False
    
    def _check_assets(self) -> None:
        """检查图片资源是否存在"""
        # 检查写留言按钮（至少需要一个）
        comment_btn_exists = any(
            (self.asset_dir / img).exists() for img in self.COMMENT_BUTTON_IMAGES
        )
        
        # 检查其他必需图片
        input_exists = any(
            (self.asset_dir / img).exists() for img in self.COMMENT_INPUT_IMAGES
        )
        send_exists = (self.asset_dir / self.SEND_BUTTON_IMAGE).exists()
        
        missing = []
        if not comment_btn_exists:
            missing.append("comment_button*.png")
        if not input_exists:
            missing.append("comment_input*.png")
        if not send_exists:
            missing.append(self.SEND_BUTTON_IMAGE)
        
        if missing:
            print(f"    ⚠ 缺少图片资源: {missing}")
            print(f"    请将图片放到: {self.asset_dir}")
            print(f"    将使用备用固定坐标")
            self._use_image_recognition = False
        else:
            # 显示找到的写留言按钮图片
            found_btns = [img for img in self.COMMENT_BUTTON_IMAGES if (self.asset_dir / img).exists()]
            print(f"    ✓ 图片资源已就绪: {self.asset_dir}")
            print(f"    ✓ 写留言按钮图片: {found_btns}")
    
    def _locate(self, image_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int]]:
        """
        在屏幕上查找图片，返回中心坐标
        
        Args:
            image_name: 图片文件名
            region: 搜索区域 (x, y, width, height)
            
        Returns:
            (x, y) 中心坐标，未找到返回 None
        """
        img_path = self.asset_dir / image_name
        if not img_path.exists():
            print(f"    ⚠ 图片不存在: {img_path}")
            return None
        
        try:
            box = pyautogui.locateOnScreen(
                str(img_path), 
                confidence=self.confidence,
                region=region,
                grayscale=False
            )
            if box:
                # box is (left, top, width, height) in physical pixels
                # convert to logical coordinates
                x = int((box.left + box.width / 2) / SCREEN_SCALE)
                y = int((box.top + box.height / 2) / SCREEN_SCALE)
                return (x, y)
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            print(f"    图像识别出错: {e}")
        
        return None
    
    def _find_and_click(self, image_name: str, desc: str, retry: int = 3, wait: float = 1.0) -> bool:
        """
        查找并点击图片
        
        Args:
            image_name: 图片文件名
            desc: 描述（用于日志）
            retry: 重试次数
            wait: 每次重试间隔
            
        Returns:
            是否成功点击
        """
        for i in range(retry):
            pos = self._locate(image_name)
            if pos:
                print(f"    ✓ 找到 {desc} 位置: {pos}")
                # 添加随机偏移，模拟真人
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                pyautogui.moveTo(pos[0] + offset_x, pos[1] + offset_y, duration=0.3)
                time.sleep(0.2)
                pyautogui.click(pos[0] + offset_x, pos[1] + offset_y)
                return True
            if i < retry - 1:
                print(f"    未找到 {desc}，重试 ({i + 1}/{retry})...")
                time.sleep(wait)
        
        print(f"    ✗ 未找到 {desc}")
        return False
    
    def load_calibration(self, calibration: "CommenterCalibration") -> None:
        """加载校准数据（备用坐标）"""
        self.comment_button_x = calibration.comment_button_x
        self.comment_button_y = calibration.comment_button_y
        self.comment_input_x = calibration.comment_input_x
        self.comment_input_y = calibration.comment_input_y
        self.send_button_x = calibration.send_button_x
        self.send_button_y = calibration.send_button_y
    
    def get_calibration(self) -> "CommenterCalibration":
        """获取当前校准数据"""
        from .calibration import CommenterCalibration
        return CommenterCalibration(
            comment_button_x=self.comment_button_x,
            comment_button_y=self.comment_button_y,
            comment_input_x=self.comment_input_x,
            comment_input_y=self.comment_input_y,
            send_button_x=self.send_button_x,
            send_button_y=self.send_button_y,
        )
    
    def open_article(self, wait_time: float = 3.0) -> None:
        """打开文章"""
        self.navigator.click_first_article()
        time.sleep(wait_time)
    
    def scroll_to_comment_area(self) -> str:
        """
        滚动到文章底部的留言区域
        
        Returns:
            识别到的文章内容
        """
        scroll_count, article_content = self.navigator.scroll_to_article_bottom()
        time.sleep(0.5)
        return article_content
    
    def click_comment_button(self) -> bool:
        """
        点击写留言按钮（尝试多个图片）
        
        Returns:
            是否成功
        """
        if self._use_image_recognition:
            # 尝试所有写留言按钮图片
            for img in self.COMMENT_BUTTON_IMAGES:
                if (self.asset_dir / img).exists():
                    if self._find_and_click(img, f"写留言按钮({img})"):
                        return True
            print(f"    → 所有图片都未找到，尝试使用备用坐标")
        
        # 备用：使用固定坐标
        click_x = int(self.comment_button_x / SCREEN_SCALE)
        click_y = int(self.comment_button_y / SCREEN_SCALE)
        print(f"    → 备用坐标: ({self.comment_button_x}, {self.comment_button_y})")
        print(f"    → 实际点击: ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click(click_x, click_y)
        return True
    
    def click_input_box(self) -> bool:
        """
        点击留言输入框
        
        Returns:
            是否成功
        """
        if self._use_image_recognition:
            # 尝试所有留言输入框图片
            for img in self.COMMENT_INPUT_IMAGES:
                if (self.asset_dir / img).exists():
                    if self._find_and_click(img, f"留言输入框({img})"):
                        return True
            print(f"    → 所有图片都未找到，尝试使用备用坐标")
        
        # 备用：使用固定坐标
        click_x = int(self.comment_input_x / SCREEN_SCALE)
        click_y = int(self.comment_input_y / SCREEN_SCALE)
        print(f"    → 备用坐标: ({self.comment_input_x}, {self.comment_input_y})")
        print(f"    → 实际点击: ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click(click_x, click_y)
        return True
    
    def input_comment(self, text: str) -> None:
        """
        输入留言内容
        
        Args:
            text: 留言文本
        """
        # 点击输入框
        self.click_input_box()
        time.sleep(0.3)
        
        # 使用剪贴板输入中文
        pyperclip.copy(text)
        modifier = "command" if self.platform == "mac" else "ctrl"
        pyautogui.hotkey(modifier, "v")
        time.sleep(0.3)
    
    def click_send(self) -> bool:
        """
        点击发送按钮
        
        Returns:
            是否成功
        """
        if self._use_image_recognition:
            if self._find_and_click(self.SEND_BUTTON_IMAGE, "发送按钮"):
                return True
            print(f"    → 图像识别失败，尝试使用备用坐标")
        
        # 备用：使用固定坐标
        click_x = int(self.send_button_x / SCREEN_SCALE)
        click_y = int(self.send_button_y / SCREEN_SCALE)
        print(f"    → 备用坐标: ({self.send_button_x}, {self.send_button_y})")
        print(f"    → 实际点击: ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click(click_x, click_y)
        return True
    
    def leave_comment(
        self, 
        text: str, 
        wait_before_send_min: float = 3.0,
        wait_before_send_max: float = 10.0,
        skip_scroll: bool = False
    ) -> bool:
        """
        完整的留言流程
        
        Args:
            text: 留言内容
            wait_before_send_min: 发送前最小等待时间
            wait_before_send_max: 发送前最大等待时间
            skip_scroll: 是否跳过滚动
            
            
        Returns:
            是否成功
        """
        try:
            interrupt_handler.check()
            
            # 滚动到留言区域
            if not skip_scroll:
                self.scroll_to_comment_area()
            
            # 点击写留言按钮
            if not self.click_comment_button():
                return False
            time.sleep(0.5)
            
            interrupt_handler.check()
            
            # 输入留言内容
            self.input_comment(text)
            
            # 随机等待
            print(f"    输入完成，随机等待后发送...")
            wait_time = random_sleep(wait_before_send_min, wait_before_send_max)
            print(f"    等待了 {wait_time:.1f} 秒，正在发送...")
            
            # 点击发送
            if not self.click_send():
                return False
            time.sleep(1.0)
            
            return True
            
        except KeyboardInterrupt:
            print(f"    留言过程被中断")
            raise
        except Exception as e:
            print(f"    留言过程出错: {e}")
            return False
    
    def go_back_to_list(self) -> None:
        """返回公众号列表"""
        self.navigator.go_back()
        time.sleep(0.5)
