"""
校准可视化模块 - 在截图上标注校准位置
"""

import os
from datetime import datetime
from typing import Optional, Tuple, TYPE_CHECKING

import pyautogui
from PIL import Image, ImageDraw, ImageFont

from .navigator import SCREEN_SCALE

if TYPE_CHECKING:
    from .calibration import CalibrationData


# 颜色定义（RGB）
COLORS = {
    "navigator_account": (255, 0, 0),      # 红色 - 公众号列表位置
    "navigator_article": (0, 255, 0),      # 绿色 - 文章位置
    "ocr_name": (0, 0, 255),               # 蓝色 - 公众号名称 OCR 区域
    "ocr_title": (255, 165, 0),            # 橙色 - 文章标题 OCR 区域
}

# 标签文字
LABELS = {
    "navigator_account": "公众号列表 (1-3)",
    "navigator_article": "文章位置",
    "ocr_name": "公众号名称 OCR",
    "ocr_title": "文章标题 OCR",
}


class CalibrationVisualizer:
    """校准可视化器"""
    
    def __init__(self, output_dir: str):
        """
        初始化可视化器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def capture_and_annotate(
        self,
        calibration: "CalibrationData",
        output_filename: Optional[str] = None
    ) -> str:
        """
        截取整个屏幕并标注校准位置
        
        Args:
            calibration: 校准数据
            output_filename: 输出文件名（不含路径），默认自动生成
            
        Returns:
            保存的文件路径
        """
        # 截取整个屏幕
        screenshot = pyautogui.screenshot()
        screen_width, screen_height = screenshot.size
        
        # 窗口坐标 (使用全屏)
        window_x = 0
        window_y = 0
        
        # 在截图上绘制屏幕边框
        annotated = self._draw_window_border(
            screenshot, 
            window_x, 
            window_y, 
            screen_width, 
            screen_height
        )
        
        # 在截图上绘制标注
        annotated = self._draw_annotations(
            annotated, 
            calibration, 
            window_x, 
            window_y
        )
        
        # 添加图例
        annotated = self._draw_legend(annotated)
        
        # 添加信息
        annotated = self._draw_info(annotated, screen_width, screen_height)
        
        # 生成文件名
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"calibration_check_{timestamp}.png"
        
        # 保存
        output_path = os.path.join(self.output_dir, output_filename)
        annotated.save(output_path)
        
        return output_path
    
    def _draw_window_border(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Image.Image:
        """
        绘制微信窗口边框
        
        Args:
            image: 原始截图
            x, y: 窗口左上角坐标
            width, height: 窗口尺寸
            
        Returns:
            添加边框后的图像
        """
        draw = ImageDraw.Draw(image, "RGBA")
        
        # 绘制窗口边框（白色）
        border_color = (255, 255, 255)
        draw.rectangle(
            [x, y, x + width, y + height],
            outline=border_color,
            width=3
        )
        
        # 在窗口四角添加角标（白色小圆点）
        corners = [
            (x + width, y),  # 右上
            (x, y + height),  # 左下
            (x + width, y + height),  # 右下
        ]
        
        for cx, cy in corners:
            draw.ellipse(
                [cx - 5, cy - 5, cx + 5, cy + 5],
                fill=(255, 255, 255, 200),
                outline=border_color
            )
        
        # 🔴 在窗口左上角（坐标原点）绘制红色大圆点
        origin_color = (255, 0, 0)  # 红色
        origin_radius = 15
        draw.ellipse(
            [x - origin_radius, y - origin_radius, x + origin_radius, y + origin_radius],
            fill=(*origin_color, 200),
            outline=origin_color,
            width=3
        )
        # 绘制十字准星
        draw.line([x - origin_radius - 10, y, x + origin_radius + 10, y], fill=origin_color, width=3)
        draw.line([x, y - origin_radius - 10, x, y + origin_radius + 10], fill=origin_color, width=3)
        # 原点标签
        self._draw_label(draw, x + origin_radius + 5, y - 25, "原点 (0,0)", origin_color)
        
        # 在窗口顶部绘制标签
        self._draw_label(draw, x + 50, y + 10, "微信窗口", (255, 255, 255))
        
        return image
    
    def _draw_info(
        self,
        image: Image.Image,
        width: int,
        height: int
    ) -> Image.Image:
        """
        在图像左上角绘制信息
        
        Args:
            image: 原始图像
            width: 屏幕宽度
            height: 屏幕高度
            
        Returns:
            添加信息后的图像
        """
        draw = ImageDraw.Draw(image, "RGBA")
        
        # 信息文字
        info_lines = [
            f"屏幕大小: {width} x {height}",
        ]
        
        # 绘制背景
        padding = 10
        line_height = 20
        box_width = 200
        box_height = len(info_lines) * line_height + padding * 2
        
        draw.rectangle(
            [10, 10, 10 + box_width, 10 + box_height],
            fill=(0, 0, 0, 200),
            outline=(255, 255, 255),
            width=1
        )
        
        # 绘制文字
        y = 10 + padding
        for line in info_lines:
            draw.text((20, y), line, fill=(255, 255, 255))
            y += line_height
        
        return image
    
    def _draw_annotations(
        self,
        image: Image.Image,
        calibration: "CalibrationData",
        offset_x: int,
        offset_y: int
    ) -> Image.Image:
        """
        在图像上绘制校准位置标注
        
        Args:
            image: 原始截图
            calibration: 校准数据
            offset_x: 窗口 X 偏移
            offset_y: 窗口 Y 偏移
            
        Returns:
            标注后的图像
        """
        # 创建可绘制对象
        draw = ImageDraw.Draw(image, "RGBA")
        
        nav = calibration.navigator
        ocr = calibration.ocr
        # 截图为物理像素（Retina 2x），校准为逻辑坐标，需乘以 SCREEN_SCALE 再绘制
        s = SCREEN_SCALE
        
        # 1. 绘制公众号列表位置（前3个位置）
        color = COLORS["navigator_account"]
        for i in range(3):
            x = offset_x + int(nav.account_list_x * s)
            y = offset_y + int((nav.account_list_y_start + (i * nav.account_item_height)) * s)
            self._draw_point(draw, x, y, color, str(i + 1))
        
        # 2. 绘制文章位置
        color = COLORS["navigator_article"]
        x = offset_x + int(nav.article_area_x * s)
        y = offset_y + int(nav.article_area_y * s)
        self._draw_point(draw, x, y, color, "文章")
        
        # 3. 绘制公众号名称 OCR 区域
        color = COLORS["ocr_name"]
        x1 = offset_x + int(ocr.account_name_x * s)
        y1 = offset_y + int(ocr.account_name_y * s)
        x2 = offset_x + int((ocr.account_name_x + ocr.account_name_width) * s)
        y2 = offset_y + int((ocr.account_name_y + ocr.account_name_height) * s)
        self._draw_rect(draw, x1, y1, x2, y2, color, "名称")
        
        # 4. 绘制文章标题 OCR 区域
        color = COLORS["ocr_title"]
        x1 = offset_x + int(ocr.article_title_x * s)
        y1 = offset_y + int(ocr.article_title_y * s)
        x2 = offset_x + int((ocr.article_title_x + ocr.article_title_width) * s)
        y2 = offset_y + int((ocr.article_title_y + ocr.article_title_height) * s)
        self._draw_rect(draw, x1, y1, x2, y2, color, "标题")
        
        return image
    
    def _draw_point(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        color: Tuple[int, int, int],
        label: str,
        radius: int = 10
    ) -> None:
        """绘制标注点"""
        # 绘制填充圆
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(*color, 180),
            outline=color,
            width=2
        )
        # 绘制十字准星
        draw.line([x - radius - 5, y, x + radius + 5, y], fill=color, width=2)
        draw.line([x, y - radius - 5, x, y + radius + 5], fill=color, width=2)
        # 绘制标签
        self._draw_label(draw, x + radius + 5, y - 10, label, color)
    
    def _draw_rect(
        self,
        draw: ImageDraw.ImageDraw,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        label: str
    ) -> None:
        """绘制标注矩形"""
        # 绘制半透明填充
        draw.rectangle([x1, y1, x2, y2], fill=(*color, 50), outline=color, width=2)
        # 绘制标签
        self._draw_label(draw, x1, y1 - 20, label, color)
    
    def _draw_label(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        text: str,
        color: Tuple[int, int, int]
    ) -> None:
        """绘制文字标签"""
        # 绘制背景
        bbox = draw.textbbox((x, y), text)
        padding = 2
        draw.rectangle(
            [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
            fill=(0, 0, 0, 200)
        )
        # 绘制文字
        draw.text((x, y), text, fill=color)
    
    def _draw_legend(self, image: Image.Image) -> Image.Image:
        """
        在图像右上角绘制图例
        
        Args:
            image: 原始图像
            
        Returns:
            添加图例后的图像
        """
        draw = ImageDraw.Draw(image, "RGBA")
        
        # 图例位置和尺寸
        legend_x = image.width - 220
        legend_y = 10
        line_height = 22
        box_size = 15
        
        # 绘制图例背景
        legend_items = list(LABELS.items())
        legend_height = len(legend_items) * line_height + 30
        draw.rectangle(
            [legend_x - 10, legend_y - 5, image.width - 10, legend_y + legend_height],
            fill=(0, 0, 0, 200),
            outline=(255, 255, 255),
            width=1
        )
        
        # 绘制标题
        draw.text((legend_x, legend_y), "校准位置图例", fill=(255, 255, 255))
        
        # 绘制各项
        current_y = legend_y + 25
        for key, label in legend_items:
            color = COLORS[key]
            # 颜色方块
            draw.rectangle(
                [legend_x, current_y, legend_x + box_size, current_y + box_size],
                fill=color
            )
            # 文字
            draw.text((legend_x + box_size + 5, current_y), label, fill=(255, 255, 255))
            current_y += line_height
        
        return image


def verify_calibration(
    calibration: "CalibrationData",
    output_dir: str
) -> str:
    """
    验证校准配置的便捷函数
    
    Args:
        calibration: 校准数据
        output_dir: 输出目录
        
    Returns:
        保存的截图路径
    """
    visualizer = CalibrationVisualizer(output_dir)
    return visualizer.capture_and_annotate(calibration)
