"""
微信公众号自动留言主程序

使用方法：
    uv run python -m wechat_gzh.auto_comment           # 正常运行（需要校准）
    uv run python -m wechat_gzh.auto_comment -s        # 跳过校准，使用上次保存的配置
    uv run python -m wechat_gzh.auto_comment -r        # 强制重新校准

注意事项：
- 移动鼠标到屏幕左上角可以紧急中断程序
- 按 Ctrl+C 可以随时停止
- 处理记录会保存到 logs/comment_history.json
- 校准配置会保存到 config/calibration.json
"""

import argparse
import json
import os
import platform
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pyautogui
from PIL import Image

from .config import COMMENT_TEXT, CONFIG_DIR, HISTORY_FILE, LOG_DIR, TIMING
from .automation.navigator import Navigator, SCREEN_SCALE
from .automation.commenter import Commenter
from .automation.ocr import OCRReader
from .automation.calibration import CalibrationManager, CalibrationData
from .automation.visualizer import CalibrationVisualizer
from .automation.utils import HistoryManager, setup_logger, random_sleep, interrupt_handler, calculate_similarity
from .llm_client import LLMCommentGenerator


def signal_handler(signum, frame):
    """信号处理函数 - 处理 Ctrl+C（在主循环中使用，支持优雅退出）"""
    interrupt_handler.set_interrupted()


def install_graceful_handler():
    """安装优雅退出的信号处理器（用于主循环）"""
    signal.signal(signal.SIGINT, signal_handler)


def restore_default_handler():
    """恢复默认的信号处理器（用于校准阶段，支持直接退出）"""
    signal.signal(signal.SIGINT, signal.default_int_handler)


class AutoCommentBot:
    """自动留言机器人"""
    
    def __init__(self, verify_only: bool = False, enable_debug_screenshot: bool = False):
        """
        初始化机器人
        
        Args:
            verify_only: 仅验证校准配置（生成标注截图后退出）
            enable_debug_screenshot: 是否启用调试截图（默认 False，需要显式传入 True 才保存）
        """
        self.logger = setup_logger("auto_comment", LOG_DIR)
        self.history = HistoryManager(HISTORY_FILE)
        self.calibration_mgr = CalibrationManager(CONFIG_DIR)
        self.visualizer = CalibrationVisualizer(LOG_DIR)
        
        self.verify_only = verify_only
        self.enable_debug_screenshot = enable_debug_screenshot
        
        # 初始化窗口和导航器
        self.navigator = Navigator()
        self.commenter = Commenter(self.navigator)
        self.ocr = OCRReader()
        
        # 初始化 LLM 评论生成器
        config_path = Path(CONFIG_DIR) / "task_prompt.json"
        self.llm = LLMCommentGenerator(config_path=config_path)
        
        # 统计信息
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "no_comment": 0,  # 不支持留言的文章
        }
        
        # 失败记录
        self.failed_accounts = []
        self.no_comment_accounts = []
    
    def check_prerequisites(self) -> bool:
        """
        检查前置条件（由用户手动确保微信已打开）
        
        Returns:
            总是返回 True（信任用户已准备好）
        """
        self.logger.info("请确保微信已打开并显示公众号列表")
        return True
    
    def calibrate(self) -> bool:
        """
        加载校准配置
        
        Returns:
            总是返回 True
        """
        if self.calibration_mgr.has_calibration():
            print("\n正在加载已保存的校准配置...")
            self._load_saved_calibration(show_visual=False)
        else:
            print("\n未找到校准配置，初始化默认配置...")
            print(f"配置文件将保存到: {self.calibration_mgr.config_file}")
            print("请运行 'uv run python -m wechat_gzh.auto_comment -v' 验证并根据需要手动修改配置。")
            
            # 标记为已校准
            self.navigator._positions_calibrated = True
            
            # 保存默认配置
            self._save_calibration()
            
        return True
    
    def _load_saved_calibration(self, show_visual: bool = True) -> bool:
        """
        加载已保存的校准配置
        
        Args:
            show_visual: 是否生成验证截图
        """
        data = self.calibration_mgr.data
        
        self.navigator.load_calibration(data.navigator)
        self.navigator._positions_calibrated = True
        
        self.ocr.load_calibration(data.ocr)
        
        print("✓ 已加载校准配置")
        print(f"  导航器: 公众号列表位置 ({data.navigator.account_list_x}, {data.navigator.account_list_y_start})")
        print(f"  OCR: 名称区域 ({data.ocr.account_name_x}, {data.ocr.account_name_y})")
        
        # 生成验证截图
        if show_visual:
            self.verify_calibration_visual()
        
        return True
    
    def _save_calibration(self) -> None:
        """保存校准配置"""
        data = CalibrationData(
            navigator=self.navigator.get_calibration(),
            ocr=self.ocr.get_calibration(),
            calibrated=True,
        )
        self.calibration_mgr.save(data)
    
    def verify_calibration_visual(self, countdown: int = 0) -> str:
        """
        生成校准验证截图
        
        Args:
            countdown: 倒计时秒数，0 表示立即截图
        
        Returns:
            截图保存路径
        """
        # 倒计时
        if countdown > 0:
            self.logger.info(f"{countdown} 秒后截图，请确保微信窗口可见...")
            for i in range(countdown, 0, -1):
                self.logger.info(f"  {i}...")
                time.sleep(1)
        
        print("\n正在生成校准验证截图...")
        
        # 获取当前校准数据
        data = CalibrationData(
            navigator=self.navigator.get_calibration(),
            ocr=self.ocr.get_calibration(),
            calibrated=True,
        )
        
        # 生成标注截图
        output_path = self.visualizer.capture_and_annotate(data)
        

        self.logger.info(f"✓ 校准验证截图已保存: {output_path}")
        self.logger.info("请检查截图中的标注位置是否正确：")
        self.logger.info("  - 红色点 (1-3): 公众号列表中的前3个位置")
        self.logger.info("  - 绿色点: 文章点击位置")
        self.logger.info("  - 蓝色框: 公众号名称 OCR 识别区域")
        self.logger.info("  - 橙色框: 文章标题 OCR 识别区域")
        
        return output_path
    
    def run_verify_only(self) -> bool:
        """
        仅验证模式：加载配置并生成验证截图（5秒后截图）
        
        Returns:
            是否成功
        """
        self.logger.info("运行校准验证模式...")
        
        # 检查是否有已保存的配置
        if not self.calibration_mgr.has_calibration():
            print("⚠ 未找到已保存的校准配置")
            print("请先运行一次校准: uv run python -m wechat_gzh.auto_comment")
            return False
        
        # 加载配置（不生成截图）
        self._load_saved_calibration(show_visual=False)
        
        # 5秒倒计时后截图
        self.verify_calibration_visual(countdown=5)
        
        return True
    
    def _save_debug_screenshot(
        self, 
        step_name: str, 
        index: int, 
        mark_position: tuple = None,
        mark_regions: list = None,
        enable_debug_screenshot: bool = False,
        base_image: Image.Image = None
    ) -> Optional[str]:
        """
        保存调试截图，可选在截图上标注点击位置和区域
        
        Args:
            step_name: 步骤名称（用于文件名）
            index: 当前公众号索引
            mark_position: 可选，要标注的点击位置 (x, y) 逻辑坐标
            mark_regions: 可选，要标注的区域列表 [(x, y, w, h, color, label), ...] 逻辑坐标
            enable_debug_screenshot: 是否启用调试截图（默认 False，需要显式传入 True 才保存）
            base_image: 可选，基础图片（如果不传则重新截图）
            
        Returns:
            截图保存路径，如果未启用则返回 None
        """
        # 只有显式传入 enable_debug_screenshot=True 才保存截图
        if not enable_debug_screenshot:
            return None
        from PIL import ImageDraw, ImageFont
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"debug_{index+1:02d}_{step_name}_{timestamp}.png"
        filepath = os.path.join(LOG_DIR, filename)
        
        # 使用传入的基础图片或截取整个屏幕
        if base_image:
            screenshot = base_image.copy()
        else:
            screenshot = pyautogui.screenshot()
            
        draw = ImageDraw.Draw(screenshot)
        line_width = 3
        # 截图为物理像素（Retina 2x），传入坐标为逻辑，需乘以 SCREEN_SCALE 再绘制
        s = SCREEN_SCALE
        
        # 标注点击位置（红色十字）
        if mark_position:
            x, y = mark_position
            px, py = int(x * s), int(y * s)
            cross_size = 30
            draw.line([(px - cross_size, py), (px + cross_size, py)], fill='red', width=line_width)
            draw.line([(px, py - cross_size), (px, py + cross_size)], fill='red', width=line_width)
            circle_radius = 20
            draw.ellipse(
                [(px - circle_radius, py - circle_radius), (px + circle_radius, py + circle_radius)],
                outline='red', width=line_width
            )
            draw.text((px + 25, py - 25), f"点击({x}, {y})", fill='red')
            self.logger.info(f"  📍 标注点击位置: ({x}, {y})")
        
        # 标注区域（矩形框）
        if mark_regions:
            for region in mark_regions:
                x, y, w, h, color, label = region
                px, py = int(x * s), int(y * s)
                pw, ph = int(w * s), int(h * s)
                draw.rectangle([(px, py), (px + pw, py + ph)], outline=color, width=line_width)
                draw.text((px, py - 20), label, fill=color)
                self.logger.info(f"  📐 标注区域: {label}")
        
        screenshot.save(filepath)
        self.logger.info(f"  📸 截图已保存: {filename}")
        return filepath
    
    def process_single_account(self, index: int) -> dict:
        """
        处理单个公众号
        
        Args:
            index: 公众号在列表中的索引（从 0 开始）
            
        Returns:
            处理结果字典
        """
        result = {
            "success": False,
            "account_name": f"公众号_{index + 1}",  # 默认名称
            "article_title": "",
            "error": None,
            "skipped": False,
            "no_comment": False,
        }
        
        try:
            # 计算点击公众号的屏幕绝对坐标
            account_click_x = self.navigator.account_list_x
            account_click_y = self.navigator.account_list_y_start + (index * self.navigator.account_item_height)
            
            # OCR 公众号名称区域（标签包含配置坐标）
            ocr_account_region = (
                self.ocr.account_name_x,
                self.ocr.account_name_y,
                self.ocr.account_name_width,
                self.ocr.account_name_height,
                'cyan',  # 青色
                f'OCR公众号({self.ocr.account_name_x},{self.ocr.account_name_y} {self.ocr.account_name_width}x{self.ocr.account_name_height})'
            )
            
            # OCR 文章标题区域（标签包含配置坐标）
            ocr_title_region = (
                self.ocr.article_title_x,
                self.ocr.article_title_y,
                self.ocr.article_title_width,
                self.ocr.article_title_height,
                'orange',  # 橙色
                f'OCR文章标题({self.ocr.article_title_x},{self.ocr.article_title_y} {self.ocr.article_title_width}x{self.ocr.article_title_height})'
            )
            
            # 截图：点击公众号前（标注点击位置 + OCR区域）
            self._save_debug_screenshot(
                "1_before_click_account", index, 
                mark_position=(account_click_x, account_click_y),
                mark_regions=[ocr_account_region],
                enable_debug_screenshot=self.enable_debug_screenshot
            )
            self.logger.info(f"  公众号点击屏幕坐标: ({account_click_x}, {account_click_y})")
            
            # 点击公众号
            self.logger.info(f"正在点击第 {index + 1} 个公众号...")
            self.navigator.click_account_at_index(index)
            time.sleep(TIMING["page_load_wait"])
            
            # 截图：点击公众号后（标注 OCR 公众号名称区域）
            self._save_debug_screenshot(
                "2_after_click_account", index,
                mark_regions=[ocr_account_region],
                enable_debug_screenshot=self.enable_debug_screenshot
            )
            
            # 使用 OCR 识别公众号名称
            account_name = self.ocr.get_account_name()
            if account_name:
                result["account_name"] = account_name
                self.logger.info(f"  识别到公众号: 【{account_name}】")
            else:
                # 如果识别失败，退出程序以便排查问题
                self.logger.error("  ✗ 无法识别公众号名称，请检查截图和校准配置")
                print("\n" + "=" * 60)
                print("❌ 错误：无法识别公众号名称")
                print("=" * 60)
                print("请检查以下内容：")
                print(f"  1. 调试截图: {LOG_DIR}/debug_*.png")
                config_file = "calibration-win.json" if platform.system() == "Windows" else "calibration.json"
                print(f"  2. 校准配置: {CONFIG_DIR}/{config_file}")
                print("  3. 确认 OCR 的 account_name_* 区域是否正确")
                print("=" * 60)
                sys.exit(1)
            
            # 文章点击的屏幕绝对坐标
            article_click_x = self.navigator.article_area_x
            article_click_y = self.navigator.article_area_y
            
            # 截图：点击文章前（标注点击位置）
            before_click_img = pyautogui.screenshot()
            self._save_debug_screenshot(
                "3_before_click_article", index, 
                mark_position=(article_click_x, article_click_y),
                enable_debug_screenshot=self.enable_debug_screenshot,
                base_image=before_click_img
            )
            self.logger.info(f"  文章点击屏幕坐标: ({article_click_x}, {article_click_y})")
            
            # 点击最新文章
            self.logger.info("点击最新文章...")
            self.navigator.click_first_article()
            time.sleep(TIMING["article_load_wait"])
            
            # 截图：点击文章后（标注 OCR 文章标题区域）
            # 同时用于比较点击是否生效
            after_click_img = pyautogui.screenshot()
            
            # 检查点击是否生效（对比点击前后的截图）
            similarity = calculate_similarity(before_click_img, after_click_img)
            self.logger.info(f"  文章点击前后相似度: {similarity:.4f}")
            
            similarity_threshold = 0.98

            if similarity > similarity_threshold:
                self.logger.warning(f"  ⚠ 文章点击失败（相似度 {similarity:.4f} >= {similarity_threshold:.2f}），跳过")
                result["skipped"] = True
                result["error"] = "点击文章失败(画面无变化)"
                return result
            
            # 截图：点击文章后（标注 OCR 文章标题区域）
            self._save_debug_screenshot(
                "4_after_click_article", index,
                mark_regions=[ocr_title_region],
                enable_debug_screenshot=self.enable_debug_screenshot,
                base_image=after_click_img
            )
            
            # 先滚动到文章顶部，确保能看到标题
            interrupt_handler.check()  # 检查中断
            self.navigator.scroll_to_article_top()
            
            # 使用 OCR 识别文章标题（在文章页面识别标题）
            interrupt_handler.check()  # 检查中断
            article_title = self.ocr.get_article_title(save_debug=self.enable_debug_screenshot)
            if article_title:
                result["article_title"] = article_title
                self.logger.info(f"  识别到文章: 【{article_title}】")
            else:
                # 如果识别失败，关闭文章窗口返回列表
                self.logger.warning("  ⚠ 无法识别文章标题，跳过此文章")
                result["skipped"] = True
                result["error"] = "无法识别文章标题"    
                self.navigator.go_back()
                time.sleep(0.5)
                return result
            
            # 检查是否已处理过此公众号的此文章
            if self.history.is_processed(result["account_name"], result["article_title"]):
                self.logger.info(f"  已处理过此文章【{result['article_title']}】，跳过")
                result["skipped"] = True
                self.logger.info("  关闭文章窗口...")
                self.commenter.go_back_to_list()
                time.sleep(0.5)
                return result
            
            # 尝试留言
            self.logger.info("正在留言...")
            
            # 先滚动到文章底部（同时识别文章内容）
            interrupt_handler.check()  # 检查中断
            article_content = self.commenter.scroll_to_comment_area()
            
            # 使用 LLM 生成评论
            interrupt_handler.check()  # 检查中断
            comment_text = None
            if article_content and self.llm.is_available():
                self.logger.info("正在使用 LLM 生成评论...")
                if self.commenter.platform == "win":
                    comment_text = self.llm.generate_comment(
                        article_content=article_title,
                        suffix=None
                    )
                else:
                    comment_text = self.llm.generate_comment(
                        article_content=article_content,
                        suffix=None
                    )
            
            # 如果 LLM 生成失败，使用默认评论
            if not comment_text:
                comment_text = COMMENT_TEXT
                self.logger.info(f"使用默认评论: {comment_text}")
            else:
                self.logger.info(f"LLM 生成评论: {comment_text}")
            
            # 滚动结束后再截图（标注留言按钮、输入框、发送按钮位置）
            # 截图：滚动到底部后，留言前
            self._save_debug_screenshot(
                "5_after_scroll_before_comment", index,
                enable_debug_screenshot=self.enable_debug_screenshot
            )
            
            # 继续留言流程（跳过滚动，因为已经滚动过了）
            success = self.commenter.leave_comment(
                comment_text,
                TIMING["comment_wait_min"],
                TIMING["comment_wait_max"],
                skip_scroll=True
            )
            
            # 截图：留言后
            self._save_debug_screenshot(
                "6_after_comment", index,
                enable_debug_screenshot=self.enable_debug_screenshot
            )
            
            if success:
                result["success"] = True
                self.logger.info("  ✓ 留言成功")
            else:
                result["error"] = "留言失败"
                self.logger.warning("  ✗ 留言失败")
            
            self.commenter.go_back_to_list()
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"  处理出错: {e}")
            # 尝试返回列表
            try:
                self.navigator.go_back()
            except:
                pass
        
        return result
    
    def run(self, max_accounts: int = 0) -> None:
        """
        运行自动留言流程（优化版：滚动策略）
        
        策略：
        1. 每次只处理第一个位置（index=0）的公众号
        2. 处理后滚动列表，让下一个公众号出现在第一个位置
        3. 当连续两次检测到相同的公众号名称时，说明到达底部
        4. 到达底部后，切换到逐项处理模式处理剩余可见的公众号
        
        Args:
            max_accounts: 最大处理公众号数量，0 表示不限制
        """
        self.logger.info("=" * 60)
        self.logger.info("微信公众号自动留言程序启动（优化版滚动策略）")
        self.logger.info("=" * 60)
        
        # 检查前置条件
        if not self.check_prerequisites():
            return
        
        # 预热 LLM (在后台加载模型)
        if self.llm.is_available():
            print("正在预热 AI 模型，请稍候...")
            self.llm.warmup()
        
        # 校准位置
        self.calibrate()
        
        print("\n" + "=" * 60)
        print("开始自动处理（优化版滚动策略）")
        print("=" * 60)
        print("策略说明：")
        print("  1. 每次处理第一个位置的公众号")
        print("  2. 滚动后继续处理新的第一个位置")
        print("  3. 检测到底部后，逐项处理剩余公众号")
        print("-" * 60)
        print("提示：将鼠标移动到屏幕左上角可以紧急中断")
        print("      按 Ctrl+C 可以随时停止")
        print("=" * 60)
        
        # input("\n确认微信显示公众号列表后，按 Enter 开始...")
        
        # 等待 5 秒，让用户切回到微信主界面
        self.logger.info("5 秒后开始，请切换到微信窗口...")
        for i in range(5, 0, -1):
            self.logger.info(f"  {i}...")
            time.sleep(1)
        
        # 安装优雅退出的信号处理器（主循环中 Ctrl+C 会等待当前操作完成）
        # 只在主线程中设置信号处理器
        if threading.current_thread() is threading.main_thread():
            install_graceful_handler()
            print("提示：主循环已启动，Ctrl+C 将在当前操作完成后安全退出")
        else:
            self.logger.info("在后台线程中运行，信号处理器已禁用（使用 UI 停止按钮来停止）")
        
        # 状态变量
        prev_account_name = None  # 上一次处理的公众号名称
        consecutive_same_count = 0  # 连续相同名称计数
        at_bottom = False  # 是否已到达底部
        scroll_count = 0
        max_scrolls = 200  # 最大滚动次数，防止无限循环
        
        try:
            # ========== 阶段1：滚动策略，每次处理第一个位置 ==========
            self.logger.info("\n" + "=" * 40)
            self.logger.info("阶段1：滚动策略处理")
            self.logger.info("=" * 40)
            
            while not at_bottom:
                # 检查中断信号
                interrupt_handler.check()
                
                # 检查是否达到最大处理数量
                if max_accounts > 0 and self.stats["total"] >= max_accounts:
                    self.logger.info(f"已达到最大处理数量 {max_accounts}，停止处理")
                    break
                
                # 检查是否达到最大滚动次数
                if scroll_count >= max_scrolls:
                    self.logger.info("已达到最大滚动次数，停止处理")
                    break
                
                self.stats["total"] += 1
                self.logger.info(f"\n{'=' * 40}")
                self.logger.info(f"处理第 {self.stats['total']} 个公众号（位置: 第1个）")
                self.logger.info(f"{'=' * 40}")
                
                # 处理第一个位置的公众号（index=0）
                result = self.process_single_account(0)
                current_name = result.get("account_name", "")
                
                # 更新统计
                self._update_stats(result)
                
                # 检测是否到达底部：连续三次处理相同的公众号
                if current_name and current_name == prev_account_name:
                    consecutive_same_count += 1
                    self.logger.info(f"  ⚠ 检测到相同公众号【{current_name}】（连续 {consecutive_same_count} 次）")
                    
                    if consecutive_same_count >= 3:
                        self.logger.info("\n" + "=" * 40)
                        self.logger.info("📍 已到达列表底部，切换到逐项处理模式")
                        self.logger.info("=" * 40)
                        at_bottom = True
                        # 撤销最后一次重复统计
                        self.stats["total"] -= 1
                        if result["skipped"]:
                            self.stats["skipped"] -= 1
                        break
                else:
                    consecutive_same_count = 0
                    prev_account_name = current_name
                
                # 随机等待（可中断）
                self.logger.info(f"随机等待中...")
                wait_time = random_sleep(
                    TIMING["account_interval_min"],
                    TIMING["account_interval_max"]
                )
                self.logger.info(f"等待了 {wait_time:.1f} 秒")
                
                # 滚动列表一个公众号的高度
                scroll_count += 1
                self.logger.info(f"\n📜 滚动列表（第 {scroll_count} 次）...")
                self.navigator.scroll_account_list_by_one("down")
                time.sleep(0.8)  # 等待滚动完成
            
            # ========== 阶段2：到达底部后，逐项处理剩余公众号 ==========
            if at_bottom:
                self.logger.info("\n" + "=" * 40)
                self.logger.info("阶段2：逐项处理剩余公众号")
                self.logger.info("=" * 40)
                
                # 假设最后一屏还有几个未处理的公众号（从 index=1 开始）
                # 因为 index=0 的公众号刚刚被检测为重复
                visible_remaining = 7  # 最多处理7个剩余的
                
                for i in range(1, visible_remaining + 1):
                    # 检查中断信号
                    interrupt_handler.check()
                    
                    # 检查是否达到最大处理数量
                    if max_accounts > 0 and self.stats["total"] >= max_accounts:
                        self.logger.info(f"已达到最大处理数量 {max_accounts}，停止处理")
                        break
                    
                    self.stats["total"] += 1
                    self.logger.info(f"\n{'=' * 40}")
                    self.logger.info(f"处理第 {self.stats['total']} 个公众号（位置: 第{i+1}个）")
                    self.logger.info(f"{'=' * 40}")
                    
                    # 处理指定位置的公众号
                    result = self.process_single_account(i)
                    
                    # 如果识别到的是已处理过的公众号，说明已经处理完所有的了
                    if result.get("account_name") and self.history.is_account_processed(result["account_name"]):
                        self.logger.info(f"  公众号【{result['account_name']}】已处理过，可能已无更多新公众号")
                        self.stats["total"] -= 1  # 撤销计数
                        # 继续处理，因为可能中间有间隔
                    
                    # 更新统计
                    self._update_stats(result)
                    
                    # 随机等待
                    self.logger.info(f"随机等待中...")
                    wait_time = random_sleep(
                        TIMING["account_interval_min"],
                        TIMING["account_interval_max"]
                    )
                    self.logger.info(f"等待了 {wait_time:.1f} 秒")
        
        except KeyboardInterrupt:
            self.logger.info("\n用户中断，停止处理")
        
        # 打印汇总
        self.print_summary()
    
    def run_list_mode(self, output_path: str) -> None:
        """
        列表模式：通过点击公众号列表位置进入公众号，用 OCR 公众号名称区域识别名称，滚动到底部后保存到 JSON。
        
        策略：每次点击列表第一项 -> 进入公众号 -> 识别 OCR 公众号名称区域作为名字 -> 返回列表 -> 滚动一行；
        当连续 3 次识别到相同名称时认为到底，保存结果。（与 process_single_account 中识别公众号名称的方式一致）
        
        Args:
            output_path: 保存路径，如 config/followeds_20260207_mia.json
        """
        self.logger.info("=" * 60)
        self.logger.info("公众号列表页 - 识别所有公众号名称（list 模式）")
        self.logger.info("=" * 60)
        
        if not self.check_prerequisites():
            return
        self.calibrate()
        
        print("\n请确保微信已打开并显示公众号列表（订阅号/服务号列表）。")
        print("5 秒后开始识别，请切换到微信窗口...")
        for i in range(5, 0, -1):
            self.logger.info(f"  {i}...")
            time.sleep(1)
        
        if threading.current_thread() is threading.main_thread():
            install_graceful_handler()
        
        names_seen = set()
        all_names_ordered = []
        prev_first_name = None
        consecutive_same = 0
        scroll_count = 0
        max_scrolls = 200
        at_bottom = False
        
        def _list_mode_recognize_one(list_index: int, debug_index: int) -> str:
            """点击列表指定项 -> 进入公众号 -> 截图裁 OCR 区域 -> 识别名称 -> 返回列表。返回识别到的公众号名。"""
            self.navigator.click_account_at_index(list_index)
            time.sleep(TIMING["page_load_wait"])
            base_image = pyautogui.screenshot()
            px = int(self.ocr.account_name_x * SCREEN_SCALE)
            py = int(self.ocr.account_name_y * SCREEN_SCALE)
            pw = int(self.ocr.account_name_width * SCREEN_SCALE)
            ph = int(self.ocr.account_name_height * SCREEN_SCALE)
            crop_image = base_image.crop((px, py, px + pw, py + ph))
            if self.enable_debug_screenshot:
                ocr_account_region = (
                    self.ocr.account_name_x,
                    self.ocr.account_name_y,
                    self.ocr.account_name_width,
                    self.ocr.account_name_height,
                    'cyan',
                    f'OCR公众号({self.ocr.account_name_x},{self.ocr.account_name_y} {self.ocr.account_name_width}x{self.ocr.account_name_height})'
                )
                self._save_debug_screenshot(
                    "list_ocr_region",
                    debug_index,
                    mark_regions=[ocr_account_region],
                    enable_debug_screenshot=True,
                    base_image=base_image,
                )
                crop_filename = f"list_ocr_crop_{debug_index:02d}_{datetime.now().strftime('%H%M%S')}.png"
                crop_path = os.path.join(LOG_DIR, crop_filename)
                crop_image.save(crop_path)
                self.logger.info(f"  OCR 裁剪图已保存: {crop_filename}")
            text = self.ocr.recognize_text(crop_image)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            name = lines[0] if lines else ""
        
            return name
        
        try:
            while True:
                interrupt_handler.check()
                if scroll_count >= max_scrolls:
                    self.logger.info("已达到最大滚动次数，停止")
                    break
                
                self.logger.info(f"点击第 1 个公众号...")
                first_name = _list_mode_recognize_one(0, scroll_count)
                if first_name:
                    self.logger.info(f"  识别到公众号: 【{first_name}】")
                
                # 检测是否到达底部：连续 3 次第一项为同一公众号
                if first_name and first_name == prev_first_name:
                    consecutive_same += 1
                    self.logger.info(f"  第一项重复【{first_name}】（连续 {consecutive_same} 次）")
                    if consecutive_same >= 3:
                        self.logger.info("已到达列表底部，停止滚动")
                        at_bottom = True
                        break
                else:
                    consecutive_same = 0
                prev_first_name = first_name
                
                if first_name and first_name not in names_seen:
                    names_seen.add(first_name)
                    all_names_ordered.append(first_name)
                
                scroll_count += 1
                self.logger.info(f"滚动列表（第 {scroll_count} 次）...")
                self.navigator.scroll_account_list_by_one("down")
                time.sleep(0.8)
            
            # 阶段2：到达底部后，逐项处理剩余可见公众号（index 1, 2, ...）
            if at_bottom:
                self.logger.info("\n" + "=" * 40)
                self.logger.info("阶段2：逐项处理剩余可见公众号（位置 2、3、4...）")
                self.logger.info("=" * 40)
                visible_remaining = 7
                for i in range(1, visible_remaining + 1):
                    interrupt_handler.check()
                    self.logger.info(f"点击第 {i + 1} 个公众号...")
                    name = _list_mode_recognize_one(i, scroll_count + i)
                    if name:
                        self.logger.info(f"  识别到公众号: 【{name}】")
                        if name not in names_seen:
                            names_seen.add(name)
                            all_names_ordered.append(name)
                    time.sleep(0.3)
        
        except KeyboardInterrupt:
            self.logger.info("\n用户中断，停止识别")
        
        # 保存为与 followees 兼容的格式：[{"user_name": "xxx"}, ...]
        out_data = [{"user_name": n} for n in all_names_ordered]
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        # 先读取旧数据，合并、去重，然后写回文件
        old_data = []
        if out_file.exists():
            with open(out_file, "r", encoding="utf-8") as f:
                try:
                    old_data = json.load(f)
                except Exception:
                    old_data = []
        # 合并已有和新数据
        merged_names = {}
        for entry in old_data + out_data:
            user_name = entry.get("user_name")
            if user_name:
                merged_names[user_name] = {"user_name": user_name}
        merged_data = list(merged_names.values())
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print("\n" + "=" * 60)
        print(f"列表模式完成，共识别 {len(all_names_ordered)} 个公众号")
        print(f"已保存到: {out_file.resolve()}")
        print("=" * 60)
        self.logger.info(f"列表模式完成，已保存到 {out_file}")
    
    def _update_stats(self, result: dict) -> None:
        """
        更新统计信息
        
        Args:
            result: process_single_account 返回的结果字典
        """
        if result["skipped"]:
            self.stats["skipped"] += 1
        elif result["no_comment"]:
            self.stats["no_comment"] += 1
            self.no_comment_accounts.append(result["account_name"])
        elif result["success"]:
            self.stats["success"] += 1
            # 记录到历史
            self.history.add_record(
                result["account_name"],
                result["article_title"]
            )
        else:
            self.stats["failed"] += 1
            self.failed_accounts.append({
                "name": result["account_name"],
                "error": result["error"]
            })
            # 记录到历史（无论成功失败都记录，避免重复处理）
            self.history.add_record(
                result["account_name"],
                result["article_title"]
            )
    
    def print_summary(self) -> None:
        """打印处理汇总"""
        print("\n")
        print("=" * 60)
        print("处理完成！汇总信息：")
        print("=" * 60)
        print(f"  总计处理: {self.stats['total']} 个公众号")
        print(f"  成功留言: {self.stats['success']} 个")
        print(f"  跳过(已处理): {self.stats['skipped']} 个")
        print(f"  留言失败: {self.stats['failed']} 个")
        print(f"  不支持留言: {self.stats['no_comment']} 个")
        
        if self.failed_accounts:
            print("\n失败的公众号：")
            for account in self.failed_accounts:
                print(f"  - {account['name']}: {account['error']}")
        
        if self.no_comment_accounts:
            print("\n不支持留言的公众号：")
            for name in self.no_comment_accounts:
                print(f"  - {name}")
        
        print("\n" + "=" * 60)
        print(f"详细记录已保存到: {HISTORY_FILE}")
        print(f"校准配置已保存到: {self.calibration_mgr.config_file}")
        print(f"运行日志保存在: {LOG_DIR}/ 目录")
        print("=" * 60)
        
        # 保存到日志
        self.logger.info("=" * 60)
        self.logger.info("处理汇总")
        self.logger.info("=" * 60)
        self.logger.info(f"总计: {self.stats['total']}, 成功: {self.stats['success']}, "
                        f"跳过: {self.stats['skipped']}, 失败: {self.stats['failed']}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="微信公众号自动留言工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  uv run python -m wechat_gzh.auto_comment           # 正常运行
  uv run python -m wechat_gzh.auto_comment -v        # 仅验证校准配置（生成标注截图）
  uv run python -m wechat_gzh.auto_comment -n 10     # 最多处理 10 个公众号
  uv run python -m wechat_gzh.auto_comment --mode list --list-output config/followeds_20260207_mia.json  # 列表模式
        """
    )
    
    parser.add_argument(
        "-v", "--verify",
        action="store_true",
        help="仅验证校准配置（生成标注截图后退出，不执行自动留言）"
    )
    
    parser.add_argument(
        "--mode",
        choices=["comment", "list"],
        default="comment",
        help="运行模式：comment=自动留言，list=识别公众号列表页所有公众号名称并保存（默认：comment）"
    )
    
    parser.add_argument(
        "--list-output",
        type=str,
        default="config/followeds_20260207_mia.json",
        help="list 模式下保存结果的 JSON 路径（默认：config/followeds_20260207_mia.json）"
    )
    
    parser.add_argument(
        "-n", "--max-accounts",
        type=int,
        default=0,
        help="最大处理公众号数量，0 表示不限制（默认：0）"
    )
    
    parser.add_argument(
        "--debug-screenshot",
        action="store_true",
        help="启用调试截图（保存调试截图和 OCR 区域截图）"
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 校准阶段使用默认信号处理器（Ctrl+C 直接退出）
    # 主循环阶段会安装优雅退出的处理器
    
    print("=" * 60)
    print("微信公众号自动留言工具")
    print("=" * 60)
    print()
    print("使用前请确保：")
    print("  1. 微信桌面客户端已打开")
    print("  2. 已进入公众号列表页面")
    print("  3. 已授予终端辅助功能权限（系统偏好设置 > 安全性与隐私 > 辅助功能）")
    print()
    
    if args.verify:
        print("模式：仅验证校准配置（生成标注截图）")
    elif args.mode == "list":
        print("模式：列表模式（识别公众号列表页所有公众号名称并保存）")
        print(f"输出：{args.list_output}")
    else:
        print("模式：正常运行（自动留言）")
    
    if args.max_accounts > 0 and not args.verify and args.mode != "list":
        print(f"限制：最多处理 {args.max_accounts} 个公众号")
    
    print()
    print("安全提示：")
    print("  - 将鼠标移动到屏幕左上角可以紧急中断程序")
    print("  - 按 Ctrl+C 可以随时停止")
    print("    （校准阶段直接退出，主循环阶段会等待当前操作完成）")
    print()
    
    # response = input("准备好后按 Enter 继续，输入 'q' 退出: ")
    # if response.lower() == 'q':
    #     print("已退出")
    #     return 0
    
    
    try:
        bot = AutoCommentBot(
            verify_only=args.verify,
            enable_debug_screenshot=args.debug_screenshot
        )
        
        # 仅验证模式
        if args.verify:
            bot.run_verify_only()
            return 0
        
        # 列表模式：识别公众号列表页所有公众号名称并保存
        if args.mode == "list":
            bot.run_list_mode(output_path=args.list_output)
            return 0
        
        # 正常运行模式
        bot.run(max_accounts=args.max_accounts)
    except KeyboardInterrupt:
        print("\n\n用户中断，程序已停止")
    except Exception as e:
        print(f"\n程序出错: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
