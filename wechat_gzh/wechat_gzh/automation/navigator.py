"""
导航操作模块
"""

import time
import platform
from typing import Tuple, Optional, TYPE_CHECKING

import pyautogui

from .utils import random_sleep

if TYPE_CHECKING:
    from .calibration import NavigatorCalibration


def get_screen_scale() -> float:
    """
    获取屏幕缩放比例（Retina 屏幕为 2.0）
    
    Returns:
        缩放比例，普通屏幕为 1.0，Retina 为 2.0
    """
    # 尝试通过截图和 pyautogui 尺寸比较来检测
    try:
        screenshot = pyautogui.screenshot()
        screen_size = pyautogui.size()
        # 避免除零错误
        if screen_size[0] > 0:
            scale = screenshot.width / screen_size[0]
            # 如果比例接近 1.0 (0.9-1.1)，直接返回 1.0
            if 0.9 < scale < 1.1:
                return 1.0
            return scale
    except Exception:
        pass
        
    return 1.0


# 全局缩放比例（启动时检测一次）
SCREEN_SCALE = get_screen_scale()
print(f"📺 屏幕缩放比例: {SCREEN_SCALE}x")


class Navigator:
    """微信导航操作类"""
    
    def __init__(self):
        """
        初始化导航器
        """
        
        # 公众号列表相关位置配置
        # 这些值可能需要根据实际屏幕调整
        self.account_list_x = 400  # 公众号列表中心 X 偏移
        self.account_list_y_start = 150  # 公众号列表 Y 起始偏移
        self.account_item_height = 70  # 每个公众号项的高度
        
        # 文章列表位置
        self.article_area_x = 900  # 文章区域 X 偏移
        self.article_area_y = 300  # 第一篇文章 Y 偏移
        
        # 返回按钮位置（文章页面左上角的返回按钮）
        self.back_button_x = 550  # 返回按钮 X 偏移
        self.back_button_y = 60   # 返回按钮 Y 偏移
        
        self._positions_calibrated = False
    
    def load_calibration(self, calibration: "NavigatorCalibration") -> None:
        """
        加载校准数据
        
        Args:
            calibration: 导航器校准数据
        """
        self.account_list_x = calibration.account_list_x
        self.account_list_y_start = calibration.account_list_y_start
        self.account_item_height = calibration.account_item_height
        self.article_area_x = calibration.article_area_x
        self.article_area_y = calibration.article_area_y
    
    def get_calibration(self) -> "NavigatorCalibration":
        """
        获取当前校准数据
        
        Returns:
            导航器校准数据
        """
        from .calibration import NavigatorCalibration
        return NavigatorCalibration(
            account_list_x=self.account_list_x,
            account_list_y_start=self.account_list_y_start,
            account_item_height=self.account_item_height,
            article_area_x=self.article_area_x,
            article_area_y=self.article_area_y,
        )
    
    def click_account_at_index(self, index: int) -> None:
        """
        点击公众号列表中指定索引的公众号
        
        Args:
            index: 公众号在可见列表中的索引（从 0 开始）
        """
        # 配置中的坐标是物理像素（截图坐标），需要转换为逻辑坐标
        click_x = int(self.account_list_x / SCREEN_SCALE)
        click_y = int((self.account_list_y_start + (index * self.account_item_height)) / SCREEN_SCALE)
        # 先移动鼠标到目标位置（让用户看到鼠标移动）
        pyautogui.moveTo(click_x, click_y, duration=0.3)
        time.sleep(0.2)
        # 点击
        pyautogui.click()
        print(f"    → 配置坐标: ({self.account_list_x}, {self.account_list_y_start + (index * self.account_item_height)})")
        print(f"    → 实际点击: ({click_x}, {click_y}) [缩放 {SCREEN_SCALE}x]")
    
    def click_first_article(self) -> None:
        """点击当前公众号的第一篇（最新）文章"""
        # 配置中的坐标是物理像素（截图坐标），需要转换为逻辑坐标
        click_x = int(self.article_area_x / SCREEN_SCALE)
        click_y = int(self.article_area_y / SCREEN_SCALE)
        # 先移动鼠标到目标位置
        pyautogui.moveTo(click_x, click_y, duration=0.3)
        time.sleep(0.2)
        # 点击
        pyautogui.click()
        print(f"    → 配置坐标: ({self.article_area_x}, {self.article_area_y})")
        print(f"    → 实际点击: ({click_x}, {click_y}) [缩放 {SCREEN_SCALE}x]")
    
    def scroll_account_list(self, direction: str = "down", amount: int = 3) -> None:
        """
        滚动公众号列表
        
        Args:
            direction: 滚动方向，"up" 或 "down"
            amount: 滚动量
        """
        # 使用屏幕绝对坐标（配置值除以缩放比例）
        scroll_x = int(self.account_list_x / SCREEN_SCALE)
        scroll_y = int((self.account_list_y_start + 100) / SCREEN_SCALE)
        
        pyautogui.moveTo(scroll_x, scroll_y)
        time.sleep(0.2)
        
        # 滚动
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount)
    
    def scroll_account_list_by_one(self, direction: str = "down") -> None:
        """
        滚动公众号列表一个项目的高度
        
        通过多次小幅滚动来实现更精确的滚动控制
        
        Args:
            direction: 滚动方向，"up" 或 "down"
        """
        # 使用屏幕绝对坐标
        scroll_x = int(self.account_list_x / SCREEN_SCALE)
        scroll_y = int((self.account_list_y_start + 100) / SCREEN_SCALE)
        
        pyautogui.moveTo(scroll_x, scroll_y)
        time.sleep(0.1)
        
        # 根据 account_item_height 计算需要滚动的次数
        # pyautogui.scroll 的单位不是像素，经验值：约 3-4 个单位 ≈ 一个公众号高度
        # 这里使用小步滚动来提高精度
        target_pixels = self.account_item_height / SCREEN_SCALE  # 转换为逻辑像素
        
        # 经验值：每次 scroll(1) 约滚动 30-40 像素（取决于系统设置）
        # 为了更精确，我们使用多次小滚动
        scroll_units = max(1, int(target_pixels / 35))  # 约 35 像素一个单位
        
        scroll_amount = scroll_units if direction == "up" else -scroll_units
        pyautogui.scroll(scroll_amount)
        
        print(f"    📜 滚动列表: {scroll_units} 单位 (目标 {target_pixels:.0f} 逻辑像素)")
    
    def scroll_article(self, direction: str = "down", amount: int = 5) -> None:
        """
        滚动文章内容（文章详情页打开后）
        
        Args:
            direction: 滚动方向，"up" 或 "down"
            amount: 滚动量
        """
        # 文章详情页通常全屏显示，使用屏幕中心位置滚动
        screen_width, screen_height = pyautogui.size()
        scroll_x = screen_width // 2
        scroll_y = screen_height // 2
        
        pyautogui.moveTo(scroll_x, scroll_y)
        time.sleep(0.1)
        
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount)
    
    def scroll_to_article_top(self, max_scrolls: int = 200, similarity_threshold: float = 0.99) -> int:
        """
        滚动到文章顶部（通过鼠标滚动，与滚动到底部类似，方向相反）
        
        Args:
            max_scrolls: 最大滚动次数
            similarity_threshold: 相似度阈值，超过此值认为已到顶部
            
        Returns:
            实际滚动次数
        """
        import numpy as np
        
        def capture_screen_region() -> np.ndarray:
            """截取屏幕中间区域用于对比"""
            screenshot = pyautogui.screenshot()
            img_array = np.array(screenshot)
            h, w = img_array.shape[:2]
            return img_array[h//3:2*h//3, w//3:2*w//3]
        
        def calculate_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
            """计算两张图片的相似度（0-1）"""
            if img1.shape != img2.shape:
                return 0.0
            diff = np.abs(img1.astype(float) - img2.astype(float))
            normalized_diff = diff / 255.0
            return 1.0 - np.mean(normalized_diff)
        
        scroll_count = 0
        prev_screenshot = None
        consecutive_same = 0
        
        print(f"    📜 滚动到文章顶部...")
        
        from .utils import interrupt_handler
        
        for i in range(max_scrolls):
            # 检查中断
            interrupt_handler.check()
            
            # 向上滚动
            self.scroll_article("up", 10)
            time.sleep(0.2)
            scroll_count += 1
            
            # 截图对比检测是否到顶
            current_screenshot = capture_screen_region()
            
            if prev_screenshot is not None:
                similarity = calculate_similarity(prev_screenshot, current_screenshot)
                
                if similarity >= similarity_threshold:
                    consecutive_same += 1
                    if consecutive_same >= 3:
                        print(f"    ✓ 已滚动到顶部（第 {scroll_count} 次滚动）")
                        break
                else:
                    consecutive_same = 0
            
            prev_screenshot = current_screenshot
        
        time.sleep(0.3)
        return scroll_count
    
    def scroll_to_article_bottom(
        self, 
        similarity_threshold: float = 0.95,
        ocr_screens: int = 2,
        max_scrolls: int = 200
    ) -> Tuple[int, str]:
        """
        滚动到文章底部（通过截图对比检测是否到底），同时 OCR 识别前几屏内容
        
        Args:
            similarity_threshold: 相似度阈值（0-1），超过此值认为已到底部
            ocr_screens: OCR 识别前几屏的内容（默认2屏）
            max_scrolls: 最大滚动次数，防止无限循环
            
        Returns:
            (实际滚动次数, 识别到的文章内容)
        """
        import numpy as np
        
        # 尝试导入 CnOcr
        try:
            from cnocr import CnOcr
            ocr = CnOcr(det_model_name='ch_PP-OCRv3_det')
            has_ocr = True
        except ImportError:
            has_ocr = False
            ocr = None
        
        def capture_screen_region() -> np.ndarray:
            """截取屏幕中间区域用于对比"""
            screenshot = pyautogui.screenshot()
            img_array = np.array(screenshot)
            h, w = img_array.shape[:2]
            return img_array[h//3:2*h//3, w//3:2*w//3]
        
        def capture_full_screen():
            """截取全屏用于 OCR"""
            return pyautogui.screenshot()
        
        def calculate_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
            """计算两张图片的相似度（0-1）"""
            if img1.shape != img2.shape:
                return 0.0
            diff = np.abs(img1.astype(float) - img2.astype(float))
            normalized_diff = diff / 255.0
            similarity = 1.0 - np.mean(normalized_diff)
            return similarity
        
        scroll_count = 0
        prev_screenshot = None
        consecutive_same = 0
        article_content_parts = []
        
        print(f"    📜 开始模拟阅读文章...")
        
        from .utils import interrupt_handler
        
        # 识别第一屏内容（滚动前）
        if has_ocr and ocr_screens > 0:
            try:
                interrupt_handler.check()  # 检查中断
                first_screen = capture_full_screen()
                results = ocr.ocr(first_screen)
                texts = [item['text'] for item in results if item.get('text')]
                if texts:
                    article_content_parts.append("\n".join(texts))
                    print(f"    📖 已识别第 1 屏内容 ({len(texts)} 行)")
            except Exception as e:
                print(f"    ⚠ OCR 识别出错: {e}")
        
        while scroll_count < max_scrolls:
            # 检查中断
            interrupt_handler.check()
            
            # 滚动
            self.scroll_article("down", 5)
            time.sleep(0.4)
            scroll_count += 1
            
            # 识别更多屏内容（第 2 屏开始，每滚动几次识别一次）
            if has_ocr and scroll_count <= ocr_screens * 3 and scroll_count % 3 == 0:
                screen_num = len(article_content_parts) + 1
                if screen_num <= ocr_screens:
                    try:
                        interrupt_handler.check()  # 检查中断
                        screen = capture_full_screen()
                        results = ocr.ocr(screen)
                        texts = [item['text'] for item in results if item.get('text')]
                        if texts:
                            article_content_parts.append("\n".join(texts))
                            print(f"    📖 已识别第 {screen_num} 屏内容 ({len(texts)} 行)")
                    except Exception as e:
                        print(f"    ⚠ OCR 识别出错: {e}")
            
            # 截图对比检测是否到底
            current_screenshot = capture_screen_region()
            
            if prev_screenshot is not None:
                similarity = calculate_similarity(prev_screenshot, current_screenshot)
                
                if similarity >= similarity_threshold:
                    consecutive_same += 1
                    if consecutive_same >= 3:
                        print(f"    ✓ 已滚动到底部（第 {scroll_count} 次滚动，相似度 {similarity:.2%}）")
                        break
                else:
                    consecutive_same = 0
            
            prev_screenshot = current_screenshot
            
            # 每10次滚动打印进度
            if scroll_count % 10 == 0:
                print(f"    📜 已滚动 {scroll_count} 次...")
        
        # 检查是否达到最大滚动次数
        if scroll_count >= max_scrolls:
            print(f"    ⚠ 已达到最大滚动次数 {max_scrolls}，停止滚动")
        
        # 合并识别到的内容
        article_content = "\n\n".join(article_content_parts)
        if article_content:
            print(f"    📝 共识别文章内容 {len(article_content)} 字")
        
        return scroll_count, article_content
    
    def go_back(self) -> None:
        """返回上一页（使用快捷键关闭当前窗口）"""
        # macOS 使用 command+w，Windows 使用 ctrl+w
        modifier = "command" if platform.system() == "Darwin" else "ctrl"
        pyautogui.hotkey(modifier, "w")
        time.sleep(0.5)
    
    def click_at_position(self, x: int, y: int) -> None:
        """
        在指定屏幕坐标位置点击
        
        Args:
            x: 屏幕 X 坐标
            y: 屏幕 Y 坐标
        """
        pyautogui.click(x, y)
    
    def move_to_position(self, x: int, y: int) -> None:
        """
        移动鼠标到指定位置
        
        Args:
            x: 屏幕 X 坐标
            y: 屏幕 Y 坐标
        """
        pyautogui.moveTo(x, y)
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """获取当前鼠标位置"""
        return pyautogui.position()
    
    def wait_for_page_load(self, seconds: float = 2.0) -> None:
        """
        等待页面加载
        
        Args:
            seconds: 等待秒数
        """
        time.sleep(seconds)
