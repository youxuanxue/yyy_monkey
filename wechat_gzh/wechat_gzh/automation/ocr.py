"""
OCR 模块 - 使用 CnOcr 进行中文文字识别
"""

from typing import TYPE_CHECKING, Optional, List

from PIL import Image
import pyautogui

try:
    from cnocr import CnOcr
    HAS_CNOCR = True
except ImportError:
    HAS_CNOCR = False
    CnOcr = None  # type: ignore

from .navigator import SCREEN_SCALE

if TYPE_CHECKING:
    from .calibration import OCRCalibration


class OCRReader:
    """OCR 文字识别器（使用 CnOcr）"""
    
    def __init__(self):
        """初始化 OCR 识别器"""
        # 初始化 CnOcr（使用 PP-OCRv3 检测模型）
        if HAS_CNOCR:
            self._ocr = CnOcr(det_model_name='ch_PP-OCRv3_det')
            print("    ✓ CnOcr 初始化成功")
        else:
            self._ocr = None
            print("    ⚠ CnOcr 未安装，OCR 功能不可用")
        
        # 公众号名称区域（逻辑坐标，与 pyautogui.position() 一致）
        self.account_name_x = 340
        self.account_name_y = 10
        self.account_name_width = 200
        self.account_name_height = 40
        
        # 文章标题区域（逻辑坐标）
        self.article_title_x = 700
        self.article_title_y = 200
        self.article_title_width = 400
        self.article_title_height = 60
        
        self._name_calibrated = False
        self._title_calibrated = False
    
    def load_calibration(self, calibration: "OCRCalibration") -> None:
        """加载校准数据"""
        self.account_name_x = calibration.account_name_x
        self.account_name_y = calibration.account_name_y
        self.account_name_width = calibration.account_name_width
        self.account_name_height = calibration.account_name_height
        self.article_title_x = calibration.article_title_x
        self.article_title_y = calibration.article_title_y
        self.article_title_width = calibration.article_title_width
        self.article_title_height = calibration.article_title_height
        self._name_calibrated = True
        self._title_calibrated = True
    
    def get_calibration(self) -> "OCRCalibration":
        """获取当前校准数据"""
        from .calibration import OCRCalibration
        return OCRCalibration(
            account_name_x=self.account_name_x,
            account_name_y=self.account_name_y,
            account_name_width=self.account_name_width,
            account_name_height=self.account_name_height,
            article_title_x=self.article_title_x,
            article_title_y=self.article_title_y,
            article_title_width=self.article_title_width,
            article_title_height=self.article_title_height,
        )
    
    def capture_region(
        self, 
        x: int, 
        y: int, 
        width: int, 
        height: int
    ) -> Image.Image:
        """
        截取屏幕指定区域。配置为逻辑坐标。
        Mac Retina 下全屏截图为物理像素，screenshot(region=) 的 region 与截图同坐标系，故用物理坐标。
        
        Args:
            x, y: 左上角逻辑坐标（与 pyautogui.position() 一致）
            width, height: 宽高（逻辑）
            
        Returns:
            PIL Image 对象
        """
        physical_x = int(x * SCREEN_SCALE)
        physical_y = int(y * SCREEN_SCALE)
        physical_width = int(width * SCREEN_SCALE)
        physical_height = int(height * SCREEN_SCALE)
        return pyautogui.screenshot(region=(physical_x, physical_y, physical_width, physical_height))
    
    def recognize_text(self, image: Image.Image) -> str:
        """
        使用 CnOcr 识别图像中的文字
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文字
        """
        if not self._ocr:
            print("    ⚠ CnOcr 未初始化")
            return ""
        
        try:
            # CnOcr 直接识别 PIL Image
            results = self._ocr.ocr(image)
            
            # 提取文本
            text_lines = [item['text'] for item in results if item.get('text')]
            full_text = "\n".join(text_lines)
            
            return full_text.strip()
            
        except Exception as e:
            print(f"    OCR 识别出错: {e}")
            return ""
    
    def get_account_name(self, save_crop_path: Optional[str] = None) -> str:
        """
        获取公众号名称（使用屏幕绝对坐标）
        
        Args:
            save_crop_path: 可选，保存本次 OCR 裁剪图到此路径，便于核对识别区域与结果
        
        Returns:
            公众号名称，如果识别失败返回空字符串
        """
        try:
            # 截取区域
            image = self.capture_region(
                self.account_name_x, 
                self.account_name_y, 
                self.account_name_width, 
                self.account_name_height
            )
            
            # 调试：保存实际送入 OCR 的裁剪图
            if save_crop_path:
                image.save(save_crop_path)
            
            # 识别文字
            text = self.recognize_text(image)
            
            # 清理：取第一行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            name = lines[0] if lines else ""
            
            return name
            
        except Exception as e:
            print(f"    OCR 识别公众号名称出错: {e}")
            return ""
    
    def get_account_name_in_list_row(
        self,
        row_index: int,
        list_x: int,
        list_y_start: int,
        item_height: int,
    ) -> str:
        """
        在公众号列表页获取指定行（第 row_index 行）的公众号名称。
        列表页每行名称区域：在列表项左侧，使用与 account_name 相同的宽高。
        
        Args:
            row_index: 行索引（从 0 开始）
            list_x: 列表点击 X（navigator.account_list_x）
            list_y_start: 列表起始 Y（navigator.account_list_y_start）
            item_height: 每行高度（navigator.account_item_height）
            
        Returns:
            该行公众号名称，识别失败返回空字符串
        """
        try:
            # 列表页名称在每行左侧，使用与公众号名称相同的宽高
            x = list_x - self.account_name_width - 20
            y = list_y_start + row_index * item_height + 15
            image = self.capture_region(
                x, y,
                self.account_name_width,
                self.account_name_height,
            )
            text = self.recognize_text(image)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return lines[0] if lines else ""
        except Exception as e:
            print(f"    OCR 列表行 {row_index} 识别出错: {e}")
            return ""
    
    def get_article_title(self, save_debug: bool = True) -> str:
        """
        获取文章标题（使用屏幕绝对坐标）
        
        Args:
            save_debug: 是否保存调试截图
            
        Returns:
            文章标题，如果识别失败返回空字符串
        """
        try:
            # 截取区域
            image = self.capture_region(
                self.article_title_x, 
                self.article_title_y, 
                self.article_title_width, 
                self.article_title_height
            )
            
            # 保存调试截图
            if save_debug:
                import os
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                logs_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "logs"
                )
                debug_path = os.path.join(logs_dir, f"ocr_article_title_{timestamp}.png")
                image.save(debug_path)
                print(f"    📸 OCR 区域截图: {os.path.basename(debug_path)}")
            
            # 识别文字
            text = self.recognize_text(image)
            
            # 清理：取第一行作为标题
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            title = lines[0] if lines else ""
            
            # 打印识别结果
            print(f"    🔍 OCR 识别结果: {repr(text[:100] if len(text) > 100 else text)}")
            
            return title
            
        except Exception as e:
            print(f"    OCR 识别文章标题出错: {e}")
            return ""
    
    def _countdown_capture(self, prompt: str, seconds: int = 5) -> tuple:
        """倒计时后捕获鼠标位置"""
        import time
        
        print(f"\n{prompt}")
        print(f"请在 {seconds} 秒内将鼠标移动到目标位置...")
        print()
        
        for i in range(seconds, 0, -1):
            print(f"  {i}...", end=" ", flush=True)
            time.sleep(1)
        
        x, y = pyautogui.position()
        print(f"\n  ✓ 已捕获位置: ({x}, {y})")
        return x, y
    
    def calibrate_account_name(self) -> None:
        """校准公众号名称区域位置"""
        print("\n" + "=" * 60)
        print("【1/2】公众号名称区域校准（使用屏幕绝对坐标）")
        print("=" * 60)
        print("请先点击一个公众号，确保右侧顶部显示公众号名称")
        print("=" * 60)
        
        input("\n准备好后按 Enter 开始校准...")
        
        x1, y1 = self._countdown_capture("【公众号名称左上角】")
        
        input("\n按 Enter 继续校准右下角...")
        
        x2, y2 = self._countdown_capture("【公众号名称右下角】")
        
        # 直接使用屏幕绝对坐标
        self.account_name_x = x1
        self.account_name_y = y1
        self.account_name_width = x2 - x1
        self.account_name_height = y2 - y1
        
        print(f"\n  → 名称区域: 屏幕坐标({self.account_name_x}, {self.account_name_y}), "
              f"宽={self.account_name_width}, 高={self.account_name_height}")
        
        # 测试识别
        print("\n正在测试 OCR 识别...")
        name = self.get_account_name()
        if name:
            print(f"  ✓ 识别成功: 【{name}】")
        else:
            print("  ⚠ 识别结果为空，可能需要调整区域")
        
        self._name_calibrated = True
    
    def calibrate_article_title(self) -> None:
        """校准文章标题区域位置"""
        print("\n" + "=" * 60)
        print("【2/2】文章标题区域校准（使用屏幕绝对坐标）")
        print("=" * 60)
        print("请确保当前显示文章消息卡片（标题预览）")
        print("=" * 60)
        
        input("\n准备好后按 Enter 开始校准...")
        
        x1, y1 = self._countdown_capture("【文章标题左上角】- 框选文章卡片上的标题文字")
        
        input("\n按 Enter 继续校准右下角...")
        
        x2, y2 = self._countdown_capture("【文章标题右下角】")
        
        # 直接使用屏幕绝对坐标
        self.article_title_x = x1
        self.article_title_y = y1
        self.article_title_width = x2 - x1
        self.article_title_height = y2 - y1
        
        print(f"\n  → 标题区域: 屏幕坐标({self.article_title_x}, {self.article_title_y}), "
              f"宽={self.article_title_width}, 高={self.article_title_height}")
        
        # 测试识别
        print("\n正在测试 OCR 识别...")
        title = self.get_article_title()
        if title:
            print(f"  ✓ 识别成功: 【{title}】")
        else:
            print("  ⚠ 识别结果为空，可能需要调整区域")
        
        self._title_calibrated = True
    
    def calibrate(self) -> None:
        """校准所有 OCR 区域"""
        print("\n" + "=" * 60)
        print("OCR 识别区域校准（使用 CnOcr）")
        print("=" * 60)
        print("将校准以下区域：")
        print("  1. 公众号名称（顶部标题栏）")
        print("  2. 文章标题（消息卡片上的标题）")
        print("=" * 60)
        
        self.calibrate_account_name()
        self.calibrate_article_title()
        
        print("\n" + "=" * 60)
        print("✓ OCR 区域校准完成！")
        print("=" * 60)
