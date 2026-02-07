"""
自动关注公众号模块

业务流程：
1. 从多个 followees_*.json 合并用户列表，并去除当前账号已关注用户（followeds_*_{wechat_account}.json）
2. 待处理列表保存到 followed_by_followee_{wechat_account}.json，标记 followed/handled
3. 倒计时5秒，等用户打开微信搜一搜页面
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

# followees 来源文件（多个公众号的关注列表）
FOLLOWEES_SOURCE_FILES = [
    "followees_20260207_ririshengjinririfu.json",
    "followees_20260207_yiqichengzhang.json",
    "followees_20260207_zhichangluosidao.json",
]


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
    
    def __init__(self, confidence: float = 0.8, wechat_account: str = "mia"):
        """
        初始化自动关注器
        
        Args:
            confidence: 图像识别置信度 (0-1)
            wechat_account: 当前微信账号标识，用于选择 followeds 与结果文件（默认 mia）
        """
        self.confidence = confidence
        self.wechat_account = wechat_account
        
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
        
        # 搜一搜公众号/视频号第一个卡片 OCR 区域（逻辑坐标，与 pyautogui.size() 一致；Retina 下校对时按“点”量）
        self.searched_gzh_x = 800
        self.searched_gzh_y = 150
        self.searched_gzh_width = 1500
        self.searched_gzh_height = 100
        
        # 账号标签 Y 上限（逻辑坐标）：超过则视为误匹配，位置错误
        self.account_tab_y_max = 180
        
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
            if "account_tab_y_max" in ocr_config:
                self.account_tab_y_max = int(ocr_config["account_tab_y_max"])
                print(f"✓ 账号标签 Y 上限: {self.account_tab_y_max}")
        except Exception as e:
            print(f"⚠ 加载校准配置出错: {e}")
    
    def _capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        截取屏幕指定区域。配置为逻辑坐标；Retina 下 region 与截图像素一致，需乘以 SCREEN_SCALE。
        
        Args:
            x, y: 左上角逻辑坐标
            width, height: 宽高（逻辑）
            
        Returns:
            PIL Image 对象
        """
        physical_x = int(x * SCREEN_SCALE)
        physical_y = int(y * SCREEN_SCALE)
        physical_width = int(width * SCREEN_SCALE)
        physical_height = int(height * SCREEN_SCALE)
        return pyautogui.screenshot(region=(physical_x, physical_y, physical_width, physical_height))
    
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
    
    def _capture_ocr_region(self) -> Optional[Image.Image]:
        """
        截取当前 OCR 识别区域（搜一搜第一个卡片名称区域）。
        校准配置为逻辑坐标，pyautogui.screenshot(region=) 使用逻辑坐标，直接传配置值。
        """
        try:
            logical_x = int(self.searched_gzh_x)
            logical_y = int(self.searched_gzh_y)
            logical_w = int(self.searched_gzh_width)
            logical_h = int(self.searched_gzh_height)
            screen_w, screen_h = pyautogui.size()
            logical_x = max(0, min(logical_x, screen_w - 1))
            logical_y = max(0, min(logical_y, screen_h - 1))
            logical_w = max(1, min(logical_w, screen_w - logical_x))
            logical_h = max(1, min(logical_h, screen_h - logical_y))
            return pyautogui.screenshot(region=(logical_x, logical_y, logical_w, logical_h))
        except Exception as e:
            print(f"  OCR 区域截图出错: {e}")
            return None

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
            image = self._capture_ocr_region()
            if image is None:
                return ""

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
    
    def verify_gzh_card_name(self, expected_name: str, context: str = "公众号") -> bool:
        """
        验证搜索结果中的公众号/视频号卡片名称是否匹配。

        Args:
            expected_name: 期望的名称
            context: 当前场景，用于调试输出（"公众号" 或 "视频号"）
            
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
                self._save_ocr_debug_crop(context, expected_name, recognized_name)
                return False

        # 检查是否包含（因为 OCR 可能识别到额外内容）
        if norm_expected in norm_recognized or norm_recognized in norm_expected:
            print(f"  ✓ 名称匹配: 【{expected_name}】")
            return True
        else:
            print(f"  ✗ 名称不匹配: 期望【{expected_name}】, 识别【{recognized_name}】")
            self._save_ocr_debug_crop(context, expected_name, recognized_name)
            return False

    def _save_ocr_debug_crop(self, context: str, expected: str, recognized: str) -> None:
        """名称不匹配时保存 OCR 区域截图到 logs/，便于核对区域是否对准卡片名称。"""
        import re
        crop = self._capture_ocr_region()
        if crop is None:
            return
        logs_dir = PROJECT_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = lambda s: re.sub(r'[/\\:*?"<>|]', "_", str(s))[:30]
        name = f"ocr_mismatch_{context}_期望{safe(expected)}_识别{safe(recognized)}_{timestamp}.png"
        path = logs_dir / name
        try:
            crop.save(str(path))
            print(f"  📷 已保存 OCR 区域截图便于核对: {path}")
            print(f"  📐 当前 OCR 区域(逻辑): x={self.searched_gzh_x}, y={self.searched_gzh_y}, "
                  f"w={self.searched_gzh_width}, h={self.searched_gzh_height} (calibration searched_gongzhonghao_*)")
        except Exception as e:
            print(f"  ⚠ 保存调试截图失败: {e}")
    
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
    
    def _get_followeds_path(self) -> Optional[Path]:
        """获取当前账号的已关注列表文件路径（followeds_*_{wechat_account}.json，取最新一份）"""
        pattern = f"followeds_*_{self.wechat_account}.json"
        candidates = sorted(CONFIG_DIR.glob(pattern))
        return candidates[-1] if candidates else None

    def load_followees(self) -> List[dict]:
        """
        从多个 followees 源文件合并用户列表，去除当前账号已关注用户，
        并合并已保存的 followed/handled 状态，结果写入 followed_by_followee_{wechat_account}.json。
        
        Returns:
            用户列表（已去重、已去除当前账号已关注）
        """
        # 1. 从多个源文件合并
        merged: List[dict] = []
        seen_openid: set = set()
        for filename in FOLLOWEES_SOURCE_FILES:
            path = CONFIG_DIR / filename
            if not path.exists():
                print(f"⚠ 未找到 {filename}，跳过")
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    users = json.load(f)
            except Exception as e:
                print(f"⚠ 读取 {filename} 失败: {e}，跳过")
                continue
            for u in users:
                openid = u.get("user_openid")
                if openid and openid not in seen_openid:
                    seen_openid.add(openid)
                    merged.append({
                        **u,
                        "followed": u.get("followed", False),
                        "handled": u.get("handled", False),
                    })
            print(f"✓ 从 {filename} 加载 {len(users)} 条")
        if not merged:
            print("✗ 未从任何 followees 源文件加载到用户")
            self._all_users = []
            self._followees_path = CONFIG_DIR / f"followed_by_followee_{self.wechat_account}.json"
            return []
        print(f"✓ 合并去重共 {len(merged)} 人")

        # 2. 去除当前账号已关注用户（按 user_name 匹配 followeds 文件）
        followeds_path = self._get_followeds_path()
        followeds_names: set = set()
        if followeds_path and followeds_path.exists():
            try:
                with open(followeds_path, "r", encoding="utf-8") as f:
                    followeds_list = json.load(f)
                followeds_names = {item.get("user_name", "").strip() for item in followeds_list if item.get("user_name")}
                print(f"✓ 从 {followeds_path.name} 读取已关注 {len(followeds_names)} 个用户名，将予以排除")
            except Exception as e:
                print(f"⚠ 读取已关注列表失败: {e}，不排除")
        before = len(merged)
        merged = [u for u in merged if (u.get("user_name") or "").strip() not in followeds_names]
        excluded = before - len(merged)
        if excluded:
            print(f"✓ 排除当前账号已关注 {excluded} 人，剩余 {len(merged)} 人")

        # 3. 合并已保存的 followed/handled 状态（followed_by_followee_{wechat_account}.json）
        result_path = CONFIG_DIR / f"followed_by_followee_{self.wechat_account}.json"
        if result_path.exists():
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                state_by_openid = {u["user_openid"]: u for u in saved if u.get("user_openid")}
                for u in merged:
                    openid = u.get("user_openid")
                    if openid and openid in state_by_openid:
                        u["followed"] = state_by_openid[openid].get("followed", False)
                        u["handled"] = state_by_openid[openid].get("handled", False)
                print(f"✓ 已合并已保存状态: {result_path.name}")
            except Exception as e:
                print(f"⚠ 读取已保存状态失败: {e}，不合并")

        self._followees_path = result_path
        self._all_users = merged
        self.save_followees()
        print(f"✓ 当前待处理列表共 {len(self._all_users)} 人，已保存到 {result_path.resolve()}")
        return self._all_users

    def save_followees(self) -> None:
        """保存用户列表到 followed_by_followee_{wechat_account}.json"""
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
        点击账号标签。若识别到的 Y 超过 account_tab_y_max，视为位置错误（不点击）。
        
        Returns:
            是否成功
        """
        for i in range(3):
            interrupt_handler.check()
            pos = self._locate_multiple(self.ACCOUNT_TAB_IMAGES)
            if not pos:
                if i < 2:
                    print(f"  未找到 账号标签，重试 ({i + 1}/3)...")
                    time.sleep(1.0)
                else:
                    print(f"  ✗ 未找到 账号标签")
                continue
            if pos[1] > self.account_tab_y_max:
                print(f"  ✗ 账号标签位置错误: Y 超出阈值 (y={pos[1]}, 阈值={self.account_tab_y_max})，未点击")
                return False
            print(f"  ✓ 找到 账号标签 位置: {pos}")
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            click_x = pos[0] + offset_x
            click_y = pos[1] + offset_y
            pyautogui.moveTo(click_x, click_y, duration=0.3)
            time.sleep(0.2)
            pyautogui.click(click_x, click_y)
            time.sleep(1.0)
            return True
        return False
    
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
        # 使用 OCR 区域配置计算点击位置（配置为逻辑坐标，pyautogui 使用逻辑坐标）
        # 正中间偏左侧 1/5：x + width * 0.3；中间 Y：y + height / 2
        card_x = self.searched_gzh_x + int(self.searched_gzh_width * 0.3)
        card_y = self.searched_gzh_y + int(self.searched_gzh_height / 2)
        
        print(f"  → 点击卡片位置(逻辑): ({card_x}, {card_y})")
        
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
        time.sleep(1.5)  # 增加延迟，确保卡片完全关闭
    
    def _locate_box(self, image_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        在屏幕上查找图片，返回完整的 box 信息（逻辑坐标）
        
        Args:
            image_name: 图片文件名
            region: 搜索区域 (x, y, width, height)
            
        Returns:
            (left, top, width, height) 逻辑坐标，未找到返回 None
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
                left = int(box.left / SCREEN_SCALE)
                top = int(box.top / SCREEN_SCALE)
                width = int(box.width / SCREEN_SCALE)
                height = int(box.height / SCREEN_SCALE)
                return (left, top, width, height)
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            print(f"  图像识别出错: {e}")
        
        return None
    
    def close_gzh_card(self) -> None:
        """
        关闭公众号弹窗页面：识别 close_gzh.png 的位置，在右边沿点击关闭
        
        如果找不到图片，则回退到使用 close_card() 方法
        """
        close_image = "close_gzh.png"
        box = self._locate_box(close_image)
        
        if box:
            left, top, width, height = box
            # 在右边沿点击：x = left + width - 偏移，y = top + height / 2（垂直居中）
            # 偏移量出 3 像素
            offset = 3
            click_x = left + width - offset
            click_y = top + int(height / 2)
            
            # 添加随机偏移，模拟真人
            offset_x = random.randint(-2, 2)
            offset_y = random.randint(-2, 2)
            final_click_x = click_x + offset_x
            final_click_y = click_y + offset_y
            
            # 调试截图：标记 close_gzh.png 位置和点击位置
            try:
                full_screen = pyautogui.screenshot()
                draw = ImageDraw.Draw(full_screen)
                
                # 转换为物理像素坐标用于绘制
                box_physical_left = int(left * SCREEN_SCALE)
                box_physical_top = int(top * SCREEN_SCALE)
                box_physical_width = int(width * SCREEN_SCALE)
                box_physical_height = int(height * SCREEN_SCALE)
                click_physical_x = int(final_click_x * SCREEN_SCALE)
                click_physical_y = int(final_click_y * SCREEN_SCALE)
                
                # 绘制 close_gzh.png 的 box（绿色框）
                draw.rectangle(
                    [(box_physical_left, box_physical_top), 
                     (box_physical_left + box_physical_width, box_physical_top + box_physical_height)],
                    outline="green",
                    width=3
                )
                
                # 绘制点击位置（红色圆圈）
                circle_radius = 10
                draw.ellipse(
                    [(click_physical_x - circle_radius, click_physical_y - circle_radius),
                     (click_physical_x + circle_radius, click_physical_y + circle_radius)],
                    outline="red",
                    width=3
                )
                # 绘制十字线
                draw.line(
                    [(click_physical_x - 15, click_physical_y),
                     (click_physical_x + 15, click_physical_y)],
                    fill="red",
                    width=2
                )
                draw.line(
                    [(click_physical_x, click_physical_y - 15),
                     (click_physical_x, click_physical_y + 15)],
                    fill="red",
                    width=2
                )
                
                # 保存截图
                logs_dir = PROJECT_DIR / "logs"
                logs_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = logs_dir / f"close_gzh_debug_{timestamp}.png"
                full_screen.save(str(output_path))
                print(f"  📸 调试截图已保存: {output_path}")
                print(f"     绿色框: close_gzh.png 位置 ({left}, {top}, {width}x{height})")
                print(f"     红色标记: 点击位置 ({final_click_x}, {final_click_y})")
            except Exception as e:
                print(f"  ⚠ 调试截图失败: {e}")
            
            pyautogui.moveTo(final_click_x, final_click_y, duration=0.3)
            time.sleep(0.2)
            pyautogui.click(final_click_x, final_click_y)
            print(f"  → 关闭公众号弹窗 (点击位置: ({final_click_x}, {final_click_y}))")
            time.sleep(1.5)  # 等待弹窗关闭
        else:
            # 如果找不到图片，回退到使用快捷键方式
            print(f"  ⚠ 未找到 {close_image}，使用快捷键关闭")
            self.close_card()
    
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
                        self.close_gzh_card()
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
                # 7.5 OCR 验证第一个卡片名称是否匹配（与公众号共用同一区域配置，若不准确可考虑单独配置）
                if self.verify_gzh_card_name(user_name, context="视频号"):
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
            # 截取全屏（Retina 下为物理像素分辨率）
            full_screen = pyautogui.screenshot()
            draw = ImageDraw.Draw(full_screen)
            
            # 配置为逻辑坐标，全屏截图为物理像素，需乘以 SCREEN_SCALE 再绘制
            px = int(self.searched_gzh_x * SCREEN_SCALE)
            py = int(self.searched_gzh_y * SCREEN_SCALE)
            pw = int(self.searched_gzh_width * SCREEN_SCALE)
            ph = int(self.searched_gzh_height * SCREEN_SCALE)
            
            # 绘制红色矩形框标记 OCR 区域（换算到物理像素以匹配截图）
            draw.rectangle(
                [(px, py), (px + pw, py + ph)],
                outline="red",
                width=6
            )
            
            # 添加文字标注
            try:
                from PIL import ImageFont
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
            print(f"  - 红色框: 公众号/视频号第一个卡片名称 OCR 识别区域（逻辑坐标 ×{SCREEN_SCALE} 后绘制）")
            print(f"  - 区域配置(逻辑坐标): x={self.searched_gzh_x}, y={self.searched_gzh_y}, "
                  f"w={self.searched_gzh_width}, h={self.searched_gzh_height}")
            config_file = "calibration-win.json" if platform.system() == "Windows" else "calibration.json"
            print(f"\n如需调整，请编辑 config/{config_file} 中的 searched_gongzhonghao_*（逻辑坐标，与屏幕“点”一致）")
            
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
    
    def run(self, interval_min: float = 2.0, interval_max: float = 5.0, max_users: Optional[int] = None) -> None:
        """
        运行自动关注流程
        
        Args:
            interval_min: 用户间最小间隔（秒）
            interval_max: 用户间最大间隔（秒）
            max_users: 最多处理的用户数，不传则不限制
        """
        # 加载用户列表
        all_users = self.load_followees()
        if not all_users:
            return
        
        # 过滤未处理的用户（handled=false）
        users = [u for u in all_users if not u.get("handled", False)]
        handled_count = len(all_users) - len(users)
        print(f"已跳过 {handled_count} 个已处理用户")
        
        if max_users is not None and max_users > 0:
            users = users[:max_users]
            print(f"本次最多处理 {max_users} 个用户")
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
    parser.add_argument(
        "-w", "--wechat",
        type=str,
        default="mia",
        dest="wechat_account",
        help="当前微信账号标识，用于 followeds 与结果文件（默认 mia）"
    )
    parser.add_argument(
        "-n", "--max-users",
        type=int,
        default=50,
        metavar="N",
        help="最多处理的用户数，不传则不限制"
    )
    
    args = parser.parse_args()
    
    follower = AutoFollower(confidence=args.confidence, wechat_account=args.wechat_account)
    
    # 仅验证模式
    if args.verify:
        follower.run_verify_only()
        return
    
    # 正常运行模式（只处理 handled=false 的用户）
    follower.run(
        interval_min=args.interval_min,
        interval_max=args.interval_max,
        max_users=args.max_users
    )


if __name__ == "__main__":
    main()
