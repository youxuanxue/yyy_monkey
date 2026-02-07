"""
校准配置管理模块 - 保存和加载校准数据
"""

import json
import os
import platform
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class NavigatorCalibration:
    """导航器校准数据"""
    account_list_x: int = 400
    account_list_y_start: int = 150
    account_item_height: int = 70
    article_area_x: int = 900
    article_area_y: int = 300


@dataclass
class OCRCalibration:
    """OCR 校准数据"""
    account_name_x: int = 340
    account_name_y: int = 10
    account_name_width: int = 200
    account_name_height: int = 40
    article_title_x: int = 700
    article_title_y: int = 200
    article_title_width: int = 400
    article_title_height: int = 60
    searched_gongzhonghao_x: int = 800
    searched_gongzhonghao_y: int = 150
    searched_gongzhonghao_width: int = 1500
    searched_gongzhonghao_height: int = 100


@dataclass
class CalibrationData:
    """完整的校准数据"""
    navigator: NavigatorCalibration = field(default_factory=NavigatorCalibration)
    ocr: OCRCalibration = field(default_factory=OCRCalibration)
    calibrated: bool = False  # 是否已校准


class CalibrationManager:
    """校准配置管理器"""
    
    DEFAULT_FILE = "calibration.json"
    WIN_FILE = "calibration-win.json"
    
    def __init__(self, config_dir: str):
        """
        初始化校准管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir
        
        filename = self.WIN_FILE if platform.system() == "Windows" else self.DEFAULT_FILE
        self.config_file = os.path.join(config_dir, filename)
        
        self._data: Optional[CalibrationData] = None
    
    @property
    def data(self) -> CalibrationData:
        """获取校准数据（懒加载）"""
        if self._data is None:
            self._data = self.load()
        return self._data
    
    def load(self) -> CalibrationData:
        """
        从文件加载校准数据
        
        Returns:
            校准数据对象，如果文件不存在则返回默认值
        """
        if not os.path.exists(self.config_file):
            return CalibrationData()
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            # 过滤掉注释字段（以 _ 开头的键）
            def filter_comments(d: dict) -> dict:
                return {k: v for k, v in d.items() if not k.startswith("_")}
            
            # 解析嵌套结构（忽略注释字段）
            nav_data = filter_comments(raw_data.get("navigator", {}))
            ocr_data = filter_comments(raw_data.get("ocr", {}))
            
            navigator = NavigatorCalibration(**nav_data)
            ocr = OCRCalibration(**ocr_data)
            calibrated = raw_data.get("calibrated", False)
            
            return CalibrationData(
                navigator=navigator,
                ocr=ocr,
                calibrated=calibrated
            )
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"⚠ 加载校准配置失败: {e}，将使用默认值")
            return CalibrationData()
    
    def save(self, data: Optional[CalibrationData] = None) -> None:
        """
        保存校准数据到文件
        
        Args:
            data: 要保存的数据，如果为 None 则保存当前数据
        """
        if data is not None:
            self._data = data
        
        if self._data is None:
            return
        
        # 确保目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 转换为字典（带注释）
        is_win = platform.system() == "Windows"
        filename = self.WIN_FILE if is_win else self.DEFAULT_FILE
        
        save_data = {
            "_说明": f"校准配置文件 ({'Windows' if is_win else 'Mac/Linux'}) - 所有坐标为逻辑坐标（与 pyautogui.position() 一致，Retina 下非物理像素）",
            "_用法": f"可手动编辑此文件，然后用 -v 参数验证: uv run python -m wechat_gzh.auto_comment -v",
            
            "navigator": {
                "_说明": "导航器配置 - 控制点击公众号和文章的位置（逻辑坐标）",
                "account_list_x": self._data.navigator.account_list_x,
                "_account_list_x": "公众号列表项的 X 屏幕坐标",
                "account_list_y_start": self._data.navigator.account_list_y_start,
                "_account_list_y_start": "第一个公众号的 Y 屏幕坐标",
                "account_item_height": self._data.navigator.account_item_height,
                "_account_item_height": "每个公众号项的高度（用于计算第N个公众号的位置）",
                "article_area_x": self._data.navigator.article_area_x,
                "_article_area_x": "文章/消息区域的 X 屏幕坐标",
                "article_area_y": self._data.navigator.article_area_y,
                "_article_area_y": "第一篇文章的 Y 屏幕坐标",
            },
            
            "ocr": {
                "_说明": "OCR 识别区域配置 - 控制文字识别的截图区域（逻辑坐标）",
                "account_name_x": self._data.ocr.account_name_x,
                "account_name_y": self._data.ocr.account_name_y,
                "account_name_width": self._data.ocr.account_name_width,
                "account_name_height": self._data.ocr.account_name_height,
                "_account_name": "公众号名称区域：(x, y) 是屏幕左上角坐标，width/height 是宽高",
                "article_title_x": self._data.ocr.article_title_x,
                "article_title_y": self._data.ocr.article_title_y,
                "article_title_width": self._data.ocr.article_title_width,
                "article_title_height": self._data.ocr.article_title_height,
                "_article_title": "文章标题区域：(x, y) 是屏幕左上角坐标，width/height 是宽高",
                "searched_gongzhonghao_x": self._data.ocr.searched_gongzhonghao_x,
                "searched_gongzhonghao_y": self._data.ocr.searched_gongzhonghao_y,
                "searched_gongzhonghao_width": self._data.ocr.searched_gongzhonghao_width,
                "searched_gongzhonghao_height": self._data.ocr.searched_gongzhonghao_height,
                "_searched_gongzhonghao": "搜一搜下面的第一张公众号卡片的位置：(x, y) 是屏幕左上角坐标，width/height 是宽高",
            },
            
            "calibrated": self._data.calibrated,
        }
        
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 校准配置已保存到: {self.config_file}")
    
    def has_calibration(self) -> bool:
        """检查是否存在已保存的校准数据"""
        return os.path.exists(self.config_file) and self.data.calibrated
    
    def clear(self) -> None:
        """清除已保存的校准数据"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
            self._data = None
            print("✓ 已清除校准配置")
