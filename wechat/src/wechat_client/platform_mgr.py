from __future__ import annotations

import logging
import platform
import sys
import time

import pyautogui
import pyperclip

logger = logging.getLogger("wechat-bot")

class PlatformManager:
    """
    封装操作系统差异（Mac vs Windows）。
    处理屏幕缩放、快捷键映射、剪贴板操作。
    """

    def __init__(self) -> None:
        self.os_name = platform.system()  # 'Darwin' or 'Windows'
        self.is_mac = self.os_name == "Darwin"
        self.is_win = self.os_name == "Windows"
        
        # 屏幕缩放因子 (Retina 屏通常截图是 2x，但 pyautogui 点击坐标是 1x)
        # 默认 1.0，需要根据实际截图和屏幕表现调整。
        # 如果使用 pyautogui.locateOnScreen，通常不需要手动换算，因为 pyscreeze 会处理。
        # 但如果是 Mac Retina 下截图分辨率很高，而点击坐标系较小，可能需要 /2。
        # 暂定策略：自动计算缩放因子
        # pyautogui.size() 返回逻辑分辨率 (1x)
        # pyautogui.screenshot().size 返回物理分辨率 (1x or 2x)
        try:
            screen_width_logic, _ = pyautogui.size()
            screen_width_phys, _ = pyautogui.screenshot().size
            self.scale_factor = screen_width_phys / screen_width_logic
            logger.info(f"Screen Scale Factor Detected: {self.scale_factor}")
        except Exception as e:
            logger.warning(f"Failed to detect screen scale factor: {e}, using 1.0")
            self.scale_factor = 1.0
        
    
    def copy_text(self, text: str) -> None:
        """写入剪贴板"""
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error(f"Copy to clipboard failed: {e}")

    def paste(self) -> None:
        """模拟粘贴快捷键"""
        # Mac 下 pyautogui 有时不稳定，多尝试几种方式
        if self.is_mac:
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)

    def select_all(self) -> None:
        """模拟全选快捷键"""
        if self.is_mac:
            pyautogui.hotkey("command", "a")
        else:
            pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)

    def enter(self) -> None:
        """模拟回车键"""
        pyautogui.press("enter")
        time.sleep(0.1)

    def get_asset_dir_name(self) -> str:
        """返回当前系统的资源子目录名"""
        return "mac" if self.is_mac else "win"

