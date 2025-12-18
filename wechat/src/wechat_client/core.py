from __future__ import annotations

import logging
import random
import time
import json
import difflib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import cv2
import numpy as np
import pyautogui
from PIL import Image

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

from wechat_client.platform_mgr import PlatformManager

# 配置 pyautogui 安全设置
pyautogui.FAILSAFE = True  # 鼠标移动到角落触发异常
pyautogui.PAUSE = 0.5      # 默认操作间隔

logger = logging.getLogger("wechat-bot")

class BotCore:
    def __init__(self, asset_dir: Path, pm: PlatformManager) -> None:
        self.asset_dir = asset_dir
        self.pm = pm
        self.confidence = 0.85  # 图像匹配置信度
        
        # 向量模型相关
        self.embedding_model = None
        self.keyword_embeddings = {} # { keyword_str: tensor }
        
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                # 使用轻量级中文模型
                # 注意：首次运行会自动下载模型
                self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("SentenceTransformer model loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer model: {e}")
        
        self.topic_config = self._load_topic_config()

    def _load_topic_config(self) -> List[Dict[str, Any]]:
        """加载话题配置并预计算向量"""
        logger.info("Loading topic config...")
        # asset_dir = .../wechat/assets, parent = .../wechat
        data_dir = self.asset_dir.parent / "data"
        config_path = data_dir / "topic_config.json"
        logger.info(f"Config path: {config_path}")
        config = []
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8")
                config = json.loads(content)
                
                # 预加载评论文件
                for item in config:
                    comment_file = item.get("comment_file")
                    if comment_file:
                        p = data_dir / comment_file
                        if p.exists():
                            item["comments"] = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
                        else:
                            logger.warning(f"Comment file not found: {comment_file}")
                
                # 日志只打印关键词和概率，不打印具体的评论内容（太长）
                log_config = []
                for item in config:
                    log_item = {k: v for k, v in item.items() if k != 'comments'}
                    log_item['comments_count'] = len(item.get('comments', []))
                    log_config.append(log_item)
                logger.info(f"Topic config loaded: {json.dumps(log_config, ensure_ascii=False)}")

            except Exception as e:
                logger.error(f"Failed to load topic config: {e}")
        
        # 预计算关键词向量
        if self.embedding_model and config:
            logger.info("Pre-calculating keyword embeddings...")
            for item in config:
                keywords = item.get("keywords", [])
                for kw in keywords:
                    if kw not in self.keyword_embeddings:
                        try:
                            self.keyword_embeddings[kw] = self.embedding_model.encode(kw, convert_to_tensor=True)
                        except Exception as e:
                            logger.error(f"Failed to embed keyword '{kw}': {e}")
        
        return config

    def get_topic_match(self, current_topic: str) -> Tuple[float, Optional[List[str]]]:
        """
        根据当前话题匹配配置，返回 (点赞概率, 推荐评论列表)。
        优先使用向量语义相似度，降级使用字符串包含匹配。
        """
        default_prob = 0
        default_comments = None

        if not current_topic:
            return default_prob, default_comments

        max_similarity = 0.0
        best_match = None
        
        # 1. 向量相似度匹配
        if self.embedding_model and self.keyword_embeddings:
            try:
                topic_emb = self.embedding_model.encode(current_topic, convert_to_tensor=True)
                
                for item in self.topic_config:
                    keywords = item.get("keywords", [])
                    
                    for kw in keywords:
                        if kw in self.keyword_embeddings:
                            kw_emb = self.keyword_embeddings[kw]
                            # 计算余弦相似度
                            sim = util.pytorch_cos_sim(topic_emb, kw_emb).item()
                            if sim > max_similarity:
                                max_similarity = sim
                                best_match = item
                
                # 设定一个语义相似度阈值，例如 0.35
                if max_similarity > 0.35 and best_match:
                    logger.info(f"Best match: {best_match.get('keywords')}, Similarity: {max_similarity:.4f}")
                    return best_match.get("like_prob", default_prob), best_match.get("comments")
                    
            except Exception as e:
                logger.error(f"Vector similarity calculation failed: {e}")

        # 2. 降级：简单关键词包含匹配
        for item in self.topic_config:
            keywords = item.get("keywords", [])
            for keyword in keywords:
                if keyword in current_topic:
                    logger.info(f"Matched keyword (string match): '{keyword}'")
                    return item.get("like_prob", default_prob), item.get("comments")
                
        logger.info(f"No specific topic matched. Using default settings.")
        return default_prob, default_comments

    def _locate_bounds(self, image_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int, int, int]]:
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

    def _locate(self, image_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int]]:
        """
        在屏幕上查找图片，返回中心坐标 (x, y)。
        image_name 不带路径，自动从 asset_dir/platform_name/ 下查找。
        """
        bounds = self._locate_bounds(image_name, region=region)
        if bounds:
            x, y, w, h = bounds
            return (x + w // 2, y + h // 2)
        return None

    def get_video_topic(self) -> Optional[str]:
        """
        根据 follow_btn 和 comment_icon 定位视频描述区域并进行 OCR 识别。
        follow_btn: 左下参照
        comment_icon: 右下参照
        """
        try:
            from cnocr import CnOcr
        except ImportError:
            logger.error("cnocr module not found. Please install it.")
            return None

        # 1. 寻找坐标
        box_follow = self._locate_bounds("follow_btn.png")
        box_comment = self._locate_bounds("comment_icon.png")

        if not box_follow or not box_comment:
            logger.warning("无法找到识别锚点 (follow_btn or comment_icon)")
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
            
            logger.info(f"Recognized Topic Text: {full_text}")
            return full_text
            
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
        寻找“未点赞的爱心” (like_empty.png)。
        如果找到“已点赞的爱心” (like_filled.png)，则跳过。
        """
        if self._locate("like_filled.png"):
            logger.info("Already liked. Skipping.")
            return True # 视为成功
        
        if self.find_and_click("like_empty.png"):
            logger.info("Liked video.")
            return True
        
        logger.warning("Like button not found.")
        return False

    def scroll_next(self) -> None:
        """
        切换到下一个视频。
        简单粗暴：鼠标滚轮向下，或者键盘 Down 键。
        为保证焦点在视频区域，先点击一下中心（或视频区域特征）。
        """
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
        time.sleep(1.5)
