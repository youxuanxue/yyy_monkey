"""
微信公众号自动化操作模块
"""

from .window import WeChatWindow
from .navigator import Navigator, InteractiveNavigator
from .commenter import Commenter, InteractiveCommenter
from .ocr import OCRReader
from .calibration import (
    CalibrationManager,
    CalibrationData,
    NavigatorCalibration,
    OCRCalibration,
    CommenterCalibration,
)
from .visualizer import CalibrationVisualizer, verify_calibration
from .utils import (
    HistoryManager, 
    setup_logger, 
    random_sleep, 
    interrupt_handler,
    interruptible_sleep,
    calibrate,
)

__all__ = [
    "WeChatWindow",
    "Navigator",
    "InteractiveNavigator",
    "Commenter",
    "InteractiveCommenter",
    "OCRReader",
    "CalibrationManager",
    "CalibrationData",
    "NavigatorCalibration",
    "OCRCalibration",
    "CommenterCalibration",
    "CalibrationVisualizer",
    "verify_calibration",
    "HistoryManager",
    "setup_logger",
    "random_sleep",
    "interrupt_handler",
    "interruptible_sleep",
    "calibrate",
]
