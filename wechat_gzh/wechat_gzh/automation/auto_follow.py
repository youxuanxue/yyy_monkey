"""
自动关注公众号模块

业务流程：
1. 读取 followees.json 得到用户列表
2. 倒计时5秒，等用户打开微信搜一搜页面
3. 每个用户执行：
   - 找到搜一搜输入框，输入 user_name，Enter 启动搜索
   - 点击账号
   - 点击公众号
   - 在公众号位置往下200px处，模拟点击卡片
   - 弹出卡片，点击关注（可能失败，跳过即可）
   - command+w 关闭卡片
   - 点击搜一搜 logo
4. 继续循环
"""

import json
import os
import platform
import random
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pyautogui
import pyperclip
from PIL import Image, ImageDraw

from .navigator import SCREEN_SCALE
from .utils import interrupt_handler, interruptible_sleep

# 尝试导入 CnOcr
try:
    from cnocr import CnOcr
    HAS_CNOCR = True
except ImportError:
    HAS_CNOCR = False
    CnOcr = None  # type: ignore

# 获取项目目录
MODULE_DIR = Path(__file__).parent
PROJECT_DIR = MODULE_DIR.parent.parent
ASSETS_DIR = PROJECT_DIR / "assets"
CONFIG_DIR = PROJECT_DIR / "config"


class AutoFollower:
    """自动关注公众号类"""
    
    # 搜一搜输入框图片（支持多个备选）
    SEARCH_INPUT_IMAGES = [
        "souyisou_input_2.png",
        "souyisou_input.png",
    ]
    
    # 账号标签图片
    ACCOUNT_TAB_IMAGES = [
        "zhanghao_2.png",
        "zhanghao.png",
    ]
    
    # 公众号标签图片
    GZH_TAB_IMAGES = [
        "gongzhonghao_2.png",
        "gongzhonghao.png",
    ]
    
    # 视频号标签图片
    SHIPINGHAO_TAB_IMAGES = [
        "shipinghao_2.png",
        "shipinghao.png",
    ]
    
    # 关注按钮图片
    FOLLOW_BUTTON_IMAGES = [
        "guanzhu.png",
        "guanzhu_2.png",
    ]
    
    # 搜一搜 logo 图片
    SEARCH_LOGO_IMAGE = "souyisou_logo.png"
    
    def __init__(self, confidence: float = 0.8):
        """
        初始化自动关注器
        
        Args:
            confidence: 图像识别置信度 (0-1)
        """
        self.confidence = confidence
        
        # 获取平台对应的资源目录
        self.platform = "mac" if platform.system() == "Darwin" else "win"
        self.asset_dir = ASSETS_DIR / self.platform
        
        # 记录上次点击公众号标签的位置（用于计算卡片位置）
        self._last_gzh_tab_pos: Optional[Tuple[int, int]] = None
        
        # OCR 相关
        self._ocr = None
        if HAS_CNOCR:
            self._ocr = CnOcr(det_model_name='ch_PP-OCRv3_det')
            print("✓ CnOcr 初始化成功")
        else:
            print("⚠ CnOcr 未安装，OCR 功能不可用")
        
        # 搜一搜公众号卡片 OCR 区域（物理像素）
        self.searched_gzh_x = 800
        self.searched_gzh_y = 150
        self.searched_gzh_width = 1500
        self.searched_gzh_height = 100
        
        # 加载校准配置
        self._load_calibration()
        
        self._check_assets()
    
    def _load_calibration(self) -> None:
        """加载校准配置文件，根据平台选择不同配置"""
        # 根据平台选择配置文件
        if platform.system() == "Windows":
            calibration_path = CONFIG_DIR / "calibration-win.json"
        else:
            calibration_path = CONFIG_DIR / "calibration.json"

        if not calibration_path.exists():
            print(f"⚠ 未找到校准配置: {calibration_path}")
            return

        try:
            with open(calibration_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            ocr_config = config.get("ocr", {})
            if "searched_gongzhonghao_x" in ocr_config:
                self.searched_gzh_x = ocr_config["searched_gongzhonghao_x"]
                self.searched_gzh_y = ocr_config["searched_gongzhonghao_y"]
                self.searched_gzh_width = ocr_config["searched_gongzhonghao_width"]
                self.searched_gzh_height = ocr_config["searched_gongzhonghao_height"]
                print(f"✓ 已加载 OCR 校准配置 ({calibration_path.name}): ({self.searched_gzh_x}, {self.searched_gzh_y}, {self.searched_gzh_width}x{self.searched_gzh_height})")
        except Exception as e:
            print(f"⚠ 加载校准配置出错: {e}")
    
    def _capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        截取屏幕指定区域（物理像素坐标）
        
        Args:
            x: 左上角 X 坐标（物理像素）
            y: 左上角 Y 坐标（物理像素）
            width: 宽度（物理像素）
            height: 高度（物理像素）
            
        Returns:
            PIL Image 对象
        """
        # 配置中的坐标是物理像素，需要转换为逻辑坐标
        logical_x = int(x / SCREEN_SCALE)
        logical_y = int(y / SCREEN_SCALE)
        logical_width = int(width / SCREEN_SCALE)
        logical_height = int(height / SCREEN_SCALE)
        return pyautogui.screenshot(region=(logical_x, logical_y, logical_width, logical_height))
    
    def _recognize_text(self, image: Image.Image) -> str:
        """
        使用 CnOcr 识别图像中的文字
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文字
        """
        if not self._ocr:
            return ""
        
        try:
            results = self._ocr.ocr(image)
            text_lines = [item['text'] for item in results if item.get('text')]
            return "\n".join(text_lines).strip()
        except Exception as e:
            print(f"  OCR 识别出错: {e}")
            return ""
    
    def recognize_searched_gzh_name(self) -> str:
        """
        识别搜索结果中第一个公众号卡片的名称
            
        Returns:
            识别出的公众号名称
        """
        if not self._ocr:
            print("  ⚠ OCR 未初始化，跳过名称验证")
            return ""
        
        try:
            # 截取区域
            image = self._capture_region(
                self.searched_gzh_x,
                self.searched_gzh_y,
                self.searched_gzh_width,
                self.searched_gzh_height
            )
            
            # 识别文字
            text = self._recognize_text(image)
            
            # 清理：取第一行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            name = lines[0] if lines else ""
            
            if name:
                print(f"  🔍 OCR 识别卡片名称: 【{name}】")
            
            return name
            
        except Exception as e:
            print(f"  OCR 识别公众号名称出错: {e}")
            return ""
    
    def _normalize_name(self, name: str) -> str:
        """
        标准化名称用于比较（去除空格和特殊字符）
        
        Args:
            name: 原始名称
            
        Returns:
            标准化后的名称
        """
        import re
        if not name:
            return ""
        # 去除空格、标点符号，只保留中文、英文、数字
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', name)
    
    def verify_gzh_card_name(self, expected_name: str) -> bool:
        """
        验证搜索结果中的公众号卡片名称是否匹配
        
        Args:
            expected_name: 期望的公众号名称
            
        Returns:
            是否匹配
        """
        if not self._ocr:
            # 没有 OCR 功能
            return False
        
        recognized_name = self.recognize_searched_gzh_name()
        
        if not recognized_name:
            print(f"  ⚠ OCR 识别为空，跳过验证")
            return False  # 识别失败
        
        # 标准化比较
        norm_expected = self._normalize_name(expected_name)
        norm_recognized = self._normalize_name(recognized_name)

        # 防止空字符串导致误匹配
        if not norm_expected or not norm_recognized:
            # 标准化后为空（如纯 emoji 名称），使用原始名称直接比较
            if expected_name.strip() == recognized_name.strip():
                print(f"  ✓ 名称匹配: 【{expected_name}】")
                return True
            else:
                print(f"  ✗ 名称不匹配: 期望【{expected_name}】, 识别【{recognized_name}】")
                return False

        # 检查是否包含（因为 OCR 可能识别到额外内容）
        if norm_expected in norm_recognized or norm_recognized in norm_expected:
            print(f"  ✓ 名称匹配: 【{expected_name}】")
            return True
        else:
            print(f"  ✗ 名称不匹配: 期望【{expected_name}】, 识别【{recognized_name}】")
            return False
    
    def _check_assets(self) -> None:
        """检查图片资源是否存在"""
        missing = []
        
        # 检查搜一搜输入框
        if not any((self.asset_dir / img).exists() for img in self.SEARCH_INPUT_IMAGES):
            missing.append("souyisou_input*.png")
        
        # 检查账号标签
        if not any((self.asset_dir / img).exists() for img in self.ACCOUNT_TAB_IMAGES):
            missing.append("zhanghao*.png")
        
        # 检查公众号标签
        if not any((self.asset_dir / img).exists() for img in self.GZH_TAB_IMAGES):
            missing.append("gongzhonghao*.png")
        
        # 检查关注按钮
        if not any((self.asset_dir / img).exists() for img in self.FOLLOW_BUTTON_IMAGES):
            missing.append("guanzhu*.png")
        
        # 检查搜一搜 logo
        if not (self.asset_dir / self.SEARCH_LOGO_IMAGE).exists():
            missing.append(self.SEARCH_LOGO_IMAGE)
        
        if missing:
            print(f"⚠ 缺少图片资源: {missing}")
            print(f"  请将图片放到: {self.asset_dir}")
        else:
            print(f"✓ 图片资源已就绪: {self.asset_dir}")
    
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
            print(f"  图像识别出错: {e}")
        
        return None
    
    def _locate_multiple(self, image_names: List[str]) -> Optional[Tuple[int, int]]:
        """
        尝试多个图片，返回第一个找到的
        
        Args:
            image_names: 图片文件名列表
            
        Returns:
            (x, y) 中心坐标，未找到返回 None
        """
        for img in image_names:
            if (self.asset_dir / img).exists():
                pos = self._locate(img)
                if pos:
                    return pos
        return None
    
    def _find_and_click(
        self, 
        image_names: List[str], 
        desc: str, 
        retry: int = 3, 
        wait: float = 1.0
    ) -> Optional[Tuple[int, int]]:
        """
        查找并点击图片
        
        Args:
            image_names: 图片文件名列表（按优先级）
            desc: 描述（用于日志）
            retry: 重试次数
            wait: 每次重试间隔
            
        Returns:
            点击的坐标，未找到返回 None
        """
        for i in range(retry):
            interrupt_handler.check()
            
            pos = self._locate_multiple(image_names)
            if pos:
                print(f"  ✓ 找到 {desc} 位置: {pos}")
                # 添加随机偏移，模拟真人
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                click_x = pos[0] + offset_x
                click_y = pos[1] + offset_y
                pyautogui.moveTo(click_x, click_y, duration=0.3)
                time.sleep(0.2)
                pyautogui.click(click_x, click_y)
                return pos
            
            if i < retry - 1:
                print(f"  未找到 {desc}，重试 ({i + 1}/{retry})...")
                time.sleep(wait)
        
        print(f"  ✗ 未找到 {desc}")
        return None
    
    def load_followees(self) -> List[dict]:
        """
        加载 followees.json 用户列表
        
        Returns:
            用户列表
        """
        self._followees_path = CONFIG_DIR / "followees.json"
        if not self._followees_path.exists():
            print(f"✗ 未找到 followees.json: {self._followees_path}")
            return []
        
        with open(self._followees_path, "r", encoding="utf-8") as f:
            self._all_users = json.load(f)
        
        print(f"✓ 加载了 {len(self._all_users)} 个用户")
        return self._all_users
    
    def save_followees(self) -> None:
        """保存 followees.json 用户列表"""
        if hasattr(self, '_followees_path') and hasattr(self, '_all_users'):
            with open(self._followees_path, "w", encoding="utf-8") as f:
                json.dump(self._all_users, f, ensure_ascii=False, indent=2)
    
    def update_user_followed(self, user_openid: str, followed: bool = True) -> None:
        """
        更新用户的 followed 状态
        
        Args:
            user_openid: 用户的 openid
            followed: 是否已关注
        """
        if not hasattr(self, '_all_users'):
            return
        
        for user in self._all_users:
            if user.get("user_openid") == user_openid:
                user["followed"] = followed
                self.save_followees()
                print(f"  💾 已保存关注状态: {user.get('user_name')}")
                break
    
    def update_user_handled(self, user_openid: str, handled: bool = True) -> None:
        """
        更新用户的 handled 状态（已处理）
        
        Args:
            user_openid: 用户的 openid
            handled: 是否已处理
        """
        if not hasattr(self, '_all_users'):
            return
        
        for user in self._all_users:
            if user.get("user_openid") == user_openid:
                user["handled"] = handled
                self.save_followees()
                break
    
    def countdown(self, seconds: int = 5) -> None:
        """
        倒计时，等待用户打开微信搜一搜页面
        
        Args:
            seconds: 倒计时秒数
        """
        print(f"\n请打开微信搜一搜页面，{seconds} 秒后开始...")
        for i in range(seconds, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        print("开始执行！\n")
    
    def search_user(self, user_name: str) -> bool:
        """
        在搜一搜中搜索用户
        
        Args:
            user_name: 用户名
            
        Returns:
            是否成功
        """
        # 1. 找到搜一搜输入框并点击
        pos = self._find_and_click(self.SEARCH_INPUT_IMAGES, "搜一搜输入框")
        if not pos:
            return False
        
        time.sleep(0.3)
        
        # 2. 清空输入框（全选后删除）
        modifier = "command" if self.platform == "mac" else "ctrl"
        pyautogui.hotkey(modifier, "a")
        time.sleep(0.1)
        
        # 3. 输入用户名（使用剪贴板）
        pyperclip.copy(user_name)
        pyautogui.hotkey(modifier, "v")
        time.sleep(0.3)
        
        # 4. 按 Enter 启动搜索
        pyautogui.press("enter")
        print(f"  → 搜索: {user_name}")
        
        # 等待搜索结果加载
        time.sleep(1.5)
        
        return True
    
    def click_account_tab(self) -> bool:
        """
        点击账号标签
        
        Returns:
            是否成功
        """
        pos = self._find_and_click(self.ACCOUNT_TAB_IMAGES, "账号标签")
        if not pos:
            return False
        
        time.sleep(1.0)
        return True
    
    def click_gzh_tab(self) -> bool:
        """
        点击公众号标签
        
        Returns:
            是否成功
        """
        pos = self._find_and_click(self.GZH_TAB_IMAGES, "公众号标签")
        if not pos:
            return False
        
        # 记录公众号标签位置，用于后续点击卡片
        self._last_gzh_tab_pos = pos
        time.sleep(1.0)
        return True
    
    def click_shipinghao_tab(self) -> bool:
        """
        点击视频号标签
        
        Returns:
            是否成功
        """
        pos = self._find_and_click(self.SHIPINGHAO_TAB_IMAGES, "视频号标签")
        if not pos:
            return False
        
        time.sleep(1.0)
        return True
    
    def click_first_card(self) -> bool:
        """
        点击第一个公众号卡片（使用校准配置中 searched_gongzhonghao 区域）
        
        点击位置：区域正中间偏左侧 1/5 的位置
            
        Returns:
            是否成功
        """
        # 使用 OCR 区域配置计算点击位置（配置是物理像素）
        # 正中间偏左侧 1/5：x + width * 0.3（即 1/2 - 1/5 = 3/10）
        # 中间 Y：y + height / 2
        card_x_physical = self.searched_gzh_x + int(self.searched_gzh_width * 0.3)
        card_y_physical = self.searched_gzh_y + int(self.searched_gzh_height / 2)
        
        # 转换为逻辑坐标（pyautogui 使用逻辑坐标）
        card_x = int(card_x_physical / SCREEN_SCALE)
        card_y = int(card_y_physical / SCREEN_SCALE)
        
        print(f"  → 点击卡片位置: ({card_x}, {card_y}) [物理像素: ({card_x_physical}, {card_y_physical})]")
        
        # 添加随机偏移
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        
        pyautogui.moveTo(card_x + offset_x, card_y + offset_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click(card_x + offset_x, card_y + offset_y)
        
        time.sleep(2.0)
        return True
    
    ALREADY_FOLLOWED_IMAGE = "yiguanzhu.png"
    
    def click_follow_button(self) -> bool:
        """
        点击关注按钮
        
        Returns:
            是否成功（包括已关注的情况）
        """
        pos = self._find_and_click(self.FOLLOW_BUTTON_IMAGES, "关注按钮", retry=2)
        if pos:
            time.sleep(0.5)
            return True
        
        # 检查是否已关注（不点击，只检测）
        already_followed_pos = self._locate(self.ALREADY_FOLLOWED_IMAGE)
        if already_followed_pos:
            print("  ✓ 已关注，无需操作")
            return True
        
        print("  ⚠ 未找到关注按钮（页面未加载）")
        return False
    
    def close_card(self) -> None:
        """关闭卡片（使用 Command+W）"""
        modifier = "command" if self.platform == "mac" else "ctrl"
        pyautogui.hotkey(modifier, "w")
        print("  → 关闭卡片 (Cmd+W)")
        time.sleep(0.5)
    
    def click_search_logo(self) -> bool:
        """
        点击搜一搜 logo，返回搜索页
        
        Returns:
            是否成功
        """
        pos = self._find_and_click([self.SEARCH_LOGO_IMAGE], "搜一搜 logo")
        if not pos:
            return False
        
        time.sleep(0.5)
        return True
    
    def process_user(self, user: dict) -> bool:
        """
        处理单个用户的完整流程
        
        Args:
            user: 用户信息字典，包含 user_name, user_openid 等
            
        Returns:
            是否成功
        """
        user_name = user.get("user_name", "")
        user_openid = user.get("user_openid", "")
        
        print(f"\n📌 处理用户: {user_name}")
        
        try:
            # 1. 搜索用户
            if not self.search_user(user_name):
                print(f"  ✗ 搜索失败")
                return False
            
            # 2. 点击账号标签
            if not self.click_account_tab():
                print(f"  ✗ 点击账号标签失败")
                if not self.click_search_logo():
                    print(f"  ⚠ 点击搜一搜 logo 失败")
                return False
            
            gzh_followed = False
            sph_followed = False
            
            # ===== 关注公众号（完整流程）=====
            print(f"  --- 关注公众号 ---")
            # 3. 点击公众号标签
            if self.click_gzh_tab():
                # 3.5 OCR 验证第一个卡片名称是否匹配
                if self.verify_gzh_card_name(user_name):
                    # 4. 点击第一个卡片
                    if self.click_first_card():
                        # 5. 点击关注按钮
                        if self.click_follow_button():
                            print(f"  ✓ 已关注公众号")
                            gzh_followed = True
                        else:
                            print(f"  ⚠ 公众号关注按钮未找到（可能已关注）")
                        # 6. 关闭卡片
                        self.close_card()
                    else:
                        print(f"  ⚠ 点击公众号卡片失败")
                else:
                    print(f"  ⚠ 公众号名称不匹配，跳过公众号关注")
            else:
                print(f"  ⚠ 点击公众号标签失败")
            
            # ===== 关注视频号（完整流程）=====
            print(f"  --- 关注视频号 ---")
            # 7. 点击视频号标签
            if self.click_shipinghao_tab():
                # 7.5 OCR 验证第一个卡片名称是否匹配
                if self.verify_gzh_card_name(user_name):
                    # 8. 点击第一个卡片
                    if self.click_first_card():
                        # 9. 点击关注按钮
                        if self.click_follow_button():
                            print(f"  ✓ 已关注视频号")
                            sph_followed = True
                        else:
                            print(f"  ⚠ 视频号关注按钮未找到（可能已关注）")
                        # 10. 关闭卡片
                        self.close_card()
                    else:
                        print(f"  ⚠ 点击视频号卡片失败")
                else:
                    print(f"  ⚠ 视频号名称不匹配，跳过视频号关注")
            else:
                print(f"  ⚠ 未找到视频号标签，跳过视频号关注")
            
            # 更新 followed 状态（只要公众号或视频号关注成功就标记）
            if gzh_followed or sph_followed:
                self.update_user_followed(user_openid, True)
            
            # 11. 点击搜一搜 logo 返回搜索页
            if not self.click_search_logo():
                print(f"  ⚠ 点击搜一搜 logo 失败")
                return False
            
            print(f"  ✓ 用户 {user_name} 处理完成")
            return True
            
        except KeyboardInterrupt:
            print(f"\n⚠ 用户中断")
            raise
        except Exception as e:
            print(f"  ✗ 处理出错: {e}")
            return False
    
    def run_verify_only(self, countdown: int = 5) -> bool:
        """
        仅验证模式：截图并标记 OCR 识别区域，然后退出
        
        Args:
            countdown: 倒计时秒数
            
        Returns:
            是否成功
        """
        print("\n" + "=" * 50)
        print("验证模式：截图并标记 OCR 识别区域")
        print("=" * 50)
        print(f"\n请打开微信搜一搜页面，并搜索一个公众号")
        print(f"确保搜索结果中显示公众号卡片")
        print(f"\n{countdown} 秒后截图...")
        
        for i in range(countdown, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        
        print("\n正在截图并标记区域...")
        
        try:
            # 截取全屏（返回物理像素分辨率）
            full_screen = pyautogui.screenshot()
            draw = ImageDraw.Draw(full_screen)
            
            # 配置是物理像素，直接使用（因为截图也是物理像素）
            px = self.searched_gzh_x
            py = self.searched_gzh_y
            pw = self.searched_gzh_width
            ph = self.searched_gzh_height
            
            # 绘制红色矩形框标记 OCR 区域（物理像素坐标）
            draw.rectangle(
                [(px, py), (px + pw, py + ph)],
                outline="red",
                width=6  # 加粗线条，因为是物理像素
            )
            
            # 添加文字标注
            try:
                from PIL import ImageFont
                # 尝试加载系统字体（字体大小也用物理像素）
                font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 48)
            except Exception:
                font = ImageFont.load_default()
            
            draw.text((px, py - 60), "OCR: searched_gongzhonghao", fill="red", font=font)
            
            # 保存截图
            logs_dir = PROJECT_DIR / "logs"
            logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = logs_dir / f"verify_ocr_region_{timestamp}.png"
            full_screen.save(str(output_path))
            
            print(f"\n✓ 验证截图已保存: {output_path}")
            print("\n请检查截图中的标注位置是否正确：")
            print(f"  - 红色框: 公众号卡片名称 OCR 识别区域")
            print(f"  - 区域配置: x={self.searched_gzh_x}, y={self.searched_gzh_y}, "
                  f"w={self.searched_gzh_width}, h={self.searched_gzh_height}")
            config_file = "calibration-win.json" if platform.system() == "Windows" else "calibration.json"
            print(f"\n如需调整，请编辑 config/{config_file} 中的 searched_gongzhonghao_* 配置")
            
            # 同时进行 OCR 识别测试
            if self._ocr:
                print("\n正在测试 OCR 识别...")
                name = self.recognize_searched_gzh_name()
                if name:
                    print(f"  ✓ 识别结果: 【{name}】")
                else:
                    print("  ⚠ 未识别到文字，请检查区域配置")
            
            return True
            
        except Exception as e:
            print(f"✗ 验证失败: {e}")
            return False
    
    def run(self, interval_min: float = 2.0, interval_max: float = 5.0) -> None:
        """
        运行自动关注流程
        
        Args:
            interval_min: 用户间最小间隔（秒）
            interval_max: 用户间最大间隔（秒）
        """
        # 加载用户列表
        all_users = self.load_followees()
        if not all_users:
            return
        
        # 过滤未处理的用户（handled=false）
        users = [u for u in all_users if not u.get("handled", False)]
        handled_count = len(all_users) - len(users)
        print(f"已跳过 {handled_count} 个已处理用户")
        
        print(f"共 {len(users)} 个待处理")
        
        if not users:
            print("没有需要处理的用户")
            return
        
        # 倒计时
        self.countdown(5)
        
        # 重置中断标志
        interrupt_handler.reset()
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        try:
            for i, user in enumerate(users):
                interrupt_handler.check()
                
                user_name = user.get("user_name", "")
                if not user_name:
                    print(f"  ⚠ 跳过空用户名")
                    skip_count += 1
                    continue
                
                print(f"\n[{i + 1}/{len(users)}] 处理用户: {user_name}")
                
                if self.process_user(user):
                    success_count += 1
                else:
                    fail_count += 1
                
                # 无论成功还是失败，都标记为已处理
                self.update_user_handled(user.get("user_openid", ""), True)
                
                # 随机间隔
                if i < len(users) - 1:
                    wait_time = random.uniform(interval_min, interval_max)
                    print(f"  ⏳ 等待 {wait_time:.1f} 秒...")
                    interruptible_sleep(wait_time)
            
        except KeyboardInterrupt:
            print(f"\n\n⚠ 用户中断执行")
        
        finally:
            print(f"\n{'='*50}")
            print(f"执行完成！成功: {success_count}, 失败: {fail_count}, 跳过: {skip_count}")
            print(f"{'='*50}")


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="微信公众号自动关注")
    parser.add_argument(
        "--confidence", "-c",
        type=float,
        default=0.8,
        help="图像识别置信度（0-1，默认0.8）"
    )
    parser.add_argument(
        "--interval-min",
        type=float,
        default=2.0,
        help="用户间最小间隔秒数（默认2.0）"
    )
    parser.add_argument(
        "--interval-max",
        type=float,
        default=5.0,
        help="用户间最大间隔秒数（默认5.0）"
    )
    parser.add_argument(
        "-v", "--verify",
        action="store_true",
        help="仅验证模式：截图并标记 OCR 识别区域后退出"
    )
    
    args = parser.parse_args()
    
    follower = AutoFollower(confidence=args.confidence)
    
    # 仅验证模式
    if args.verify:
        follower.run_verify_only()
        return
    
    # 正常运行模式（只处理 handled=false 的用户）
    follower.run(
        interval_min=args.interval_min,
        interval_max=args.interval_max
    )


if __name__ == "__main__":
    main()
