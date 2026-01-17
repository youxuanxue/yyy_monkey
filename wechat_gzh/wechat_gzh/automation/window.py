"""
微信窗口管理模块
"""

import subprocess
from typing import Optional, Tuple

import pyautogui

try:
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGNullWindowID,
        kCGWindowListOptionOnScreenOnly,
    )
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False


class WeChatWindow:
    """微信窗口管理类"""
    
    def __init__(self, window_title: str = "微信"):
        """
        初始化微信窗口管理器
        
        Args:
            window_title: 微信窗口标题关键字
        """
        self.window_title = window_title
        self.window_info: Optional[dict] = None
        self._bounds: Optional[Tuple[int, int, int, int]] = None
    
    def find_window(self) -> bool:
        """
        查找微信主窗口（找最大的窗口）
        
        Returns:
            如果找到返回 True，否则返回 False
        """
        if not HAS_QUARTZ:
            print("警告: 无法导入 Quartz，将使用默认窗口位置")
            return False
        
        # 获取所有窗口信息
        window_list = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, 
            kCGNullWindowID
        )
        
        # 收集所有微信窗口
        wechat_windows = []
        for window in window_list:
            owner_name = window.get("kCGWindowOwnerName", "")
            window_name = window.get("kCGWindowName", "")
            
            if self.window_title in owner_name or self.window_title in str(window_name):
                bounds = window.get("kCGWindowBounds", {})
                width = int(bounds.get("Width", 0))
                height = int(bounds.get("Height", 0))
                area = width * height
                wechat_windows.append({
                    "window": window,
                    "bounds": bounds,
                    "area": area,
                    "name": window_name,
                })
        
        if not wechat_windows:
            return False
        
        # 找最大的窗口（主窗口）
        largest = max(wechat_windows, key=lambda w: w["area"])
        self.window_info = largest["window"]
        bounds = largest["bounds"]
        self._bounds = (
            int(bounds.get("X", 0)),
            int(bounds.get("Y", 0)),
            int(bounds.get("Width", 800)),
            int(bounds.get("Height", 600)),
        )
        
        # 打印调试信息
        print(f"  找到 {len(wechat_windows)} 个微信窗口，选择最大的：")
        print(f"    位置: ({self._bounds[0]}, {self._bounds[1]})")
        print(f"    大小: {self._bounds[2]}x{self._bounds[3]}")
        
        return True
    
    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """
        获取窗口边界
        
        Returns:
            (x, y, width, height) 元组
        """
        if self._bounds is None:
            if not self.find_window():
                # 默认值
                self._bounds = (0, 0, 1200, 800)
        return self._bounds
    
    @property
    def x(self) -> int:
        """窗口左上角 X 坐标"""
        return self.bounds[0]
    
    @property
    def y(self) -> int:
        """窗口左上角 Y 坐标"""
        return self.bounds[1]
    
    @property
    def width(self) -> int:
        """窗口宽度"""
        return self.bounds[2]
    
    @property
    def height(self) -> int:
        """窗口高度"""
        return self.bounds[3]
    
    def activate(self) -> bool:
        """
        激活微信窗口（将其置于前台）
        
        Returns:
            如果成功返回 True
        """
        try:
            # 使用 AppleScript 激活微信窗口
            script = '''
            tell application "WeChat"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            # 尝试另一种方式
            try:
                script = '''
                tell application "System Events"
                    set frontmost of process "WeChat" to true
                end tell
                '''
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError:
                return False
    
    def get_absolute_position(self, x_offset: int, y_offset: int) -> Tuple[int, int]:
        """
        将相对于窗口的偏移转换为屏幕绝对坐标
        
        Args:
            x_offset: 相对于窗口左上角的 X 偏移
            y_offset: 相对于窗口左上角的 Y 偏移
            
        Returns:
            (绝对 X, 绝对 Y) 元组
        """
        return (self.x + x_offset, self.y + y_offset)
    
    def click_at_offset(self, x_offset: int, y_offset: int, clicks: int = 1) -> None:
        """
        在窗口内的指定偏移位置点击
        
        Args:
            x_offset: 相对于窗口左上角的 X 偏移
            y_offset: 相对于窗口左上角的 Y 偏移
            clicks: 点击次数
        """
        abs_x, abs_y = self.get_absolute_position(x_offset, y_offset)
        pyautogui.click(abs_x, abs_y, clicks=clicks)
    
    def is_wechat_running(self) -> bool:
        """
        检查微信是否正在运行
        
        Returns:
            如果微信正在运行返回 True
        """
        try:
            result = subprocess.run(
                ["pgrep", "-x", "WeChat"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False
    
    def take_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None):
        """
        截取窗口或指定区域的截图
        
        Args:
            region: 可选的截图区域 (x, y, width, height)，如果不指定则截取整个窗口
            
        Returns:
            PIL Image 对象
        """
        if region is None:
            region = self.bounds
        return pyautogui.screenshot(region=region)
