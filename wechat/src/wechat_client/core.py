from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import pyautogui

try:
    from cnocr import CnOcr
    HAS_CNOCR = True
except ImportError:
    HAS_CNOCR = False
    CnOcr = None  # type: ignore

from wechat_client.platform_mgr import PlatformManager
from wechat_client.llm_client import LLMCommentGenerator

# 配置 pyautogui 安全设置
pyautogui.FAILSAFE = True  # 鼠标移动到角落触发异常
pyautogui.PAUSE = 0.5      # 默认操作间隔

logger = logging.getLogger("wechat-bot")

class BotCore:
    def __init__(self, asset_dir: Path, pm: PlatformManager, config_dir: Optional[Path] = None) -> None:
        self.asset_dir = asset_dir
        self.pm = pm
        self.confidence = 0.85  # 图像匹配置信度
        
        # 确定配置文件路径
        if config_dir is None:
            # 尝试自动查找配置文件
            possible_config_dirs = [
                asset_dir.parent / "config",
                Path.cwd() / "config",
                Path.cwd() / "wechat" / "config",
            ]
            for possible_dir in possible_config_dirs:
                config_file = possible_dir / "task_prompt.json"
                if config_file.exists():
                    config_dir = possible_dir
                    break
        
        config_path = None
        if config_dir:
            config_path = config_dir / "task_prompt.json"
        
        # LLM 评论生成器初始化
        self.llm_generator = LLMCommentGenerator(config_path=config_path)


    def generate_comment_with_llm(self, topic_text: str) -> Optional[str]:
        """
        使用大模型根据 topic_text 的语义生成适合的评论。
        要求：积极、正能量、含蓄地引导回访和关注。
        大模型会根据话题内容自动判断是否需要邀请对方参与"#小小谋略家"活动。
        
        Args:
            topic_text: 视频话题文本
            
        Returns:
            生成的评论文本，如果生成失败则返回 None
        """
        return self.llm_generator.generate_comment(topic_text)
    
    def generate_comment_from_task(
        self,
        video_description: str,
        comments: List[str]=[],
        persona: str = "yi_ba"
    ) -> Optional[Dict[str, Any]]:
        """
        根据 task_prompt.json 配置生成评论
        
        Args:
            video_description: 视频描述文本
            comments: 他人评论列表（最多取前3条）
            persona: 角色名称，默认为 "yi_ba"，可选 "yi_ma"
            
        Returns:
            生成的评论文本，如果生成失败或不符合条件，返回 None
        """
        result = self.llm_generator.generate_comment_from_task(
            video_description=video_description,
            comments=comments,
            persona=persona
        )
        
        return result

    def _locate_bounds(self, image_name: str, region: Optional[tuple[int, int, int, int]] = None) -> Optional[tuple[int, int, int, int]]:
        """
        查找图片并返回逻辑坐标包围盒 (x, y, w, h)。
        """
        img_path = self.asset_dir / self.pm.get_asset_dir_name() / image_name
        if not img_path.exists():
            img_path = self.asset_dir / image_name
        
        if not img_path.exists():
            return None

        try:
            box = pyautogui.locateOnScreen(str(img_path), confidence=self.confidence, region=region, grayscale=False)
            if box:
                # box is (left, top, width, height) in physical pixels (usually)
                # convert to logical
                sf = self.pm.scale_factor
                return (int(box.left / sf), int(box.top / sf), int(box.width / sf), int(box.height / sf))
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            logger.error(f"Locate bounds error: {e}")
        return None

    def _locate(self, image_name: str, region: Optional[tuple[int, int, int, int]] = None) -> Optional[tuple[int, int]]:
        """
        在屏幕上查找图片，返回中心坐标 (x, y)。
        image_name 不带路径，自动从 asset_dir/platform_name/ 下查找。
        """
        bounds = self._locate_bounds(image_name, region=region)
        if bounds:
            x, y, w, h = bounds
            return (x + w // 2, y + h // 2)
        return None

    def _normalize_text(self, text: str) -> str:
        """
        规范化文本，用于比较
        去除所有空白字符（包括换行、空格、制表符等），只保留可见字符
        """
        if not text:
            return ""
        # 去除所有空白字符
        return re.sub(r'\s+', '', text)
    
    def is_same_video(self, text1: str, text2: str) -> bool:
        """
        判断两个文本是否来自同一个视频
        输入的文本应该已经是规范化后的文本
        只比较前20个字符，使用宽松标准
        
        时间复杂度：O(1)，只比较固定长度的前缀
        """
        if not text1 or not text2:
            return False
        
        # 只取前20个字符进行比较
        prefix_len = 20
        prefix1 = text1[:prefix_len]
        prefix2 = text2[:prefix_len]
        
        # 如果前缀完全相同，认为是同一个视频
        if prefix1 == prefix2:
            return True
        
        # 如果其中一个前缀太短（少于5个字符），无法判断
        if len(prefix1) < 5 or len(prefix2) < 5:
            return False
        
        # 计算前20个字符的相似度（宽松标准）
        # 允许最多30%的字符差异
        min_prefix_len = min(len(prefix1), len(prefix2))
        diff_count = sum(1 for i in range(min_prefix_len) if prefix1[i] != prefix2[i])
        
        # 如果差异数不超过30%，认为是同一个视频
        similarity = 1.0 - (diff_count / min_prefix_len)
        return similarity >= 0.7  # 70%相似度即可
    
    def get_video_topic(self) -> Optional[str]:
        """
        根据 follow_btn/followed_btn 和 comment_icon 定位视频描述区域并进行 OCR 识别。
        follow_btn 或 followed_btn: 左下参照（优先尝试 follow_btn，如果找不到则尝试 followed_btn）
        comment_icon: 右下参照
        """
        if not HAS_CNOCR:
            logger.error("cnocr module not found. Please install it.")
            return None

        # 1. 寻找坐标
        # 优先尝试 follow_btn.png，如果找不到则尝试 followed_btn.png
        box_follow = self._locate_bounds("follow_btn.png")
        if not box_follow:
            box_follow = self._locate_bounds("followed_btn.png")
            if box_follow:
                logger.info("使用 followed_btn.png 作为左下参照")
        
        box_comment = self._locate_bounds("comment_icon.png")

        if not box_follow or not box_comment:
            logger.warning("无法找到识别锚点 (follow_btn/followed_btn 或 comment_icon)")
            return None

        # 2. 计算区域
        # 按照用户指示：follow_btn 为左下，comment_icon 为右下
        # 意味着描述区域在它们上方
        
        # 左边界：follow_btn 的左边缘 (向左偏移 400px，但不能小于 0)
        x_left = max(0, box_follow[0] - 200)
        # 右边界：comment_icon 的右边缘
        x_right = box_comment[0] + box_comment[2]
        
        # 下边界：取两个图标的上边缘的最小值 (即更高的那个位置，保证文字在上方)
        # 或者取两个图标的中心线... 既然是“左下、右下坐标”，意味着这两个点定义了底边
        # 我们取它们的 top 比较保险，避免截到按钮本身
        y_bottom = min(box_follow[1], box_comment[1])
        
        # 宽度
        width = x_right - x_left
        
        # 高度：预估值，视频描述一般不会超过 40px
        height = 40
        
        # 上边界
        y_top = y_bottom - height
        
        if width <= 0:
            return None

        # 3. 截图
        region = (x_left, y_top, width, height)
        logger.info(f"OCR Region: {region}")

        try:
            # region is (left, top, width, height)
            screenshot = pyautogui.screenshot(region=region)
            
            # 4. OCR
            # 强制使用已下载的 v3 检测模型
            ocr = CnOcr(det_model_name='ch_PP-OCRv3_det') 
            res = ocr.ocr(screenshot)
            
            # 提取文本
            text_lines = [line['text'] for line in res]
            full_text = "\n".join(text_lines)
            
            # 规范化处理（去除所有空白字符）
            normalized_text = self._normalize_text(full_text)
            
            logger.info(f"Recognized Topic Text: {normalized_text}")
            return normalized_text
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return None

    def _click_at(self, x: int, y: int, double: bool = False) -> None:
        """移动并点击"""
        # 增加随机偏移，模拟真人
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        if double:
            pyautogui.doubleClick(x + offset_x, y + offset_y)
        else:
            pyautogui.click(x + offset_x, y + offset_y)

    def find_and_click(self, image_name: str, retry: int = 3, wait: float = 1.0) -> bool:
        """
        查找并点击图标。
        retry: 重试次数
        wait: 每次重试间隔
        """
        for i in range(retry):
            pos = self._locate(image_name)
            if pos:
                logger.info(f"Found {image_name} at {pos}, clicking...")
                self._click_at(pos[0], pos[1])
                return True
            time.sleep(wait)
        logger.info(f"Not found: {image_name}")
        return False

    def send_comment(self, text: str) -> bool:
        """
        发送评论流程：
        1. 查找“评论输入框”图标 (comment_input.png) 或 “发送”按钮旁的空白区
        2. 点击激活焦点
        3. 粘贴文本
        4. 发送 (点击发送按钮 或 回车)
        """
        # 1. 寻找评论输入框特征
        # 建议截取“写评论...”那个灰色的框
        pos = self._locate("comment_input.png")
        if not pos:
            # 尝试寻找“评论图标”点击展开侧边栏（如果未展开）
            if self.find_and_click("comment_icon.png"):
                time.sleep(1.0)
                pos = self._locate("comment_input.png")
        
        if not pos:
            logger.warning("无法找到评论输入框")
            return False

        # 2. 点击激活
        self._click_at(pos[0], pos[1])
        time.sleep(0.5)

        # 3. 粘贴文本
        # 先全选删除旧的（如果有）
        self.pm.select_all()
        pyautogui.press("backspace")
        
        logger.info(f"Pasting comment: {text}")
        self.pm.copy_text(text)
        time.sleep(0.2)
        self.pm.paste()
        time.sleep(0.5)

        # 4. 发送
        # 优先尝试点击“发送”按钮 (send_btn.png)
        if self.find_and_click("send_btn.png"):
            logger.info("Clicked send button.")
            return True
        else:
            # 兜底：回车
            logger.info("Pressing Enter to send.")
            self.pm.enter()
            return True

    def like_current(self) -> bool:
        """
        点赞流程：
        寻找"未点赞的爱心" (like_empty.png)。
        如果找到"已点赞的爱心" (like_filled.png)，则跳过。
        """
        if self._locate("like_filled.png"):
            logger.info("Already liked. Skipping.")
            return True # 视为成功
        
        if self.find_and_click("like_empty.png"):
            logger.info("Liked video.")
            return True
        
        logger.warning("Like button not found.")
        return False
    
    def follow_current(self) -> bool:
        """
        关注流程：
        寻找"未关注的关注按钮" (follow_btn.png)。
        如果找到"已关注的按钮" (followed_btn.png)，则跳过。
        """
        if self._locate("followed_btn.png"):
            logger.info("Already followed. Skipping.")
            return True # 视为成功
        
        if self.find_and_click("follow_btn.png"):
            logger.info("Followed video creator.")
            return True
        
        logger.warning("Follow button not found.")
        return False

    def scroll_next(self, min_watch_time: float = 1.0, max_watch_time: float = 5.0) -> None:
        """
        切换到下一个视频。
        简单粗暴：鼠标滚轮向下，或者键盘 Down 键。
        为保证焦点在视频区域，先点击一下中心（或视频区域特征）。
        
        Args:
            min_watch_time: 滚动前随机播放的时间下限（秒），默认1秒
            max_watch_time: 滚动前随机播放的时间上限（秒），默认5秒
        """

        # 滚动前随机播放一段时间
        watch_time = random.uniform(min_watch_time, max_watch_time)
        if watch_time > 0:
            logger.info(f"Watching video for {watch_time:.2f}s before scrolling...")
            time.sleep(watch_time)

        # 假设屏幕中心是视频区
        w, h = pyautogui.size()
        pyautogui.moveTo(w // 2, h // 2)
        # pyautogui.click() # 慎点，可能会暂停视频
        
        logger.info("Scrolling to next video...")
        if self.pm.is_mac:
            # Mac 滚轮
            pyautogui.scroll(-5) 
        else:
            pyautogui.scroll(-300) 
        
        # 或者使用键盘
        # pyautogui.press("down") 
        
        
