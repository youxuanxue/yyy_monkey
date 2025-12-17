from __future__ import annotations

import logging
import platform
import time
import pyperclip
import pyautogui
from typing import Optional

# macOS 下 Retina 屏幕通常需要缩放因子 /2，Windows 下根据缩放比例可能需要调整
# 这里做一个简单的系统检测，后续可能需要根据实际截图分辨率自动校准
IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

class PlatformAdapter:
    """
    封装跨平台的操作差异（如快捷键、屏幕缩放等）
    """
    def __init__(self, scale_factor: float = 1.0):
        self.scale_factor = scale_factor
        self.logger = logging.getLogger("wechat-client")

        # macOS Retina 屏幕通常截图是 2x 大小，但 pyautogui 点击坐标是 1x
        # 如果用户手动截图是 1x 大小，则 scale_factor = 1.0
        # 如果截图是 Retina 2x 分辨率，而 pyautogui 需要逻辑像素，则可能需要 /2
        # 具体取决于截图来源。这里默认假设截图与屏幕逻辑像素 1:1，或由上层传入修正因子。
        if IS_MAC:
             # PyAutoGUI 在 mac 上处理 Retina 比较特殊，通常截图匹配返回的坐标已经是逻辑坐标
             # 但如果使用 opencv 匹配原始高分图，可能需要换算
             pass

    def copy(self, text: str) -> None:
        """写入剪贴板"""
        try:
            pyperclip.copy(text)
        except Exception as e:
            self.logger.error(f"Copy failed: {e}")

    def paste(self) -> None:
        """模拟粘贴快捷键"""
        if IS_MAC:
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1) # 等待粘贴动作完成

    def enter(self) -> None:
        """模拟回车发送"""
        pyautogui.press("enter")

    def select_all(self) -> None:
        """模拟全选"""
        if IS_MAC:
            pyautogui.hotkey("command", "a")
        else:
            pyautogui.hotkey("ctrl", "a")

    def scroll_down(self, amount: int = 100) -> None:
        """
        向下滚动
        pyautogui.scroll 参数含义在不同平台不同：
        - Windows: 正数向上，负数向下
        - Linux: 正数向上，负数向下
        - macOS: scroll 的单位与 Win 不同，且方向可能受系统设置（自然滚动）影响
        """
        # 统一尝试向下滚动
        # 很多 mac 用户开启了自然滚动（手指向上推页面向下），pyautogui 模拟的是滚轮信号
        # 通常：负数是向下
        clicks = -abs(amount)
        pyautogui.scroll(clicks)

