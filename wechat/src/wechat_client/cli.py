from __future__ import annotations

import os
# 禁用 tokenizers 并行，避免 fork 后的警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import argparse
import logging
from math import log
import random
import sys
import time
from pathlib import Path

# 添加 src 到路径以支持直接运行
sys.path.append(str(Path(__file__).resolve().parent.parent))

from wechat_client.core import BotCore
from wechat_client.platform_mgr import PlatformManager
from wechat_client.license import verify_license

def _setup_logger() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger("wechat-bot")

def _load_comments(data_dir: Path) -> list[str]:
    # 优先加载 comments_default.txt
    p = data_dir / "comments_default.txt"
    if not p.exists():
        p = data_dir / "comments.txt"
        
    if p.exists():
        try:
            return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as e:
            logging.error(f"Failed to load comments from {p}: {e}")

    return ["支持博主", "感谢分享", "666"]

def main() -> None:
    # 1. 校验 License
    verify_license()
    
    parser = argparse.ArgumentParser(description="WeChat Client Auto Bot")
    parser.add_argument("--mode", choices=["run", "test_assets"], default="run", help="模式")
    parser.add_argument("--max-likes", type=int, default=10, help="点赞动作总数上限（>0 生效；达到后退出）")
    parser.add_argument("--interval", type=float, default=5.0, help="操作间隔(秒)")
    args = parser.parse_args()

    logger = _setup_logger()
    
    # 路径配置
    # 假设 wechat 目录是当前工作目录或上级目录
    # 运行时建议在 wechat/ 根目录下运行 python -m src.wechat_client.cli
    base_dir = Path.cwd()
    
    # 智能判断根目录：如果当前目录下没有 assets 但有 wechat 目录，则进入 wechat 目录
    if not (base_dir / "assets").exists() and (base_dir / "wechat").exists():
        base_dir = base_dir / "wechat"
    
    asset_dir = base_dir / "assets"
    data_dir = base_dir / "data"

    pm = PlatformManager()
    bot = BotCore(asset_dir, pm)

    logger.info(f"Started WeChat Bot on {pm.os_name}")
    logger.info(f"Asset dir: {asset_dir / pm.get_asset_dir_name()}")

    if args.mode == "test_assets":
        logger.info("Testing asset recognition... Please open WeChat Channels window.")
        time.sleep(5)
        for img in ["like_empty.png", "like_filled.png", "comment_input.png", "send_btn.png", "comment_icon.png", "follow_btn.png"]:
            pos = bot._locate(img)
            res = "FOUND" if pos else "NOT FOUND"
            logger.info(f"Asset '{img}': {res} {pos if pos else ''}")
        return

    logger.info("Auto Mode starting ... Switch to WeChat NOW!")

    comments = _load_comments(data_dir)

    liked_count = 0
    commented_count = 0
    while liked_count < int(args.max_likes):
        topic_text = bot.get_video_topic()
        
        # 计算点赞概率和推荐评论
        like_prob, topic_comments = bot.get_topic_match(topic_text)
        logger.info(f"Like Probability: {like_prob}")

        # 1. 尝试点赞
        if random.random() < like_prob:
            watch_time = random.uniform(2.0, 6.0)
            logger.info(f"点赞前：Watching for {watch_time:.1f}s...") 
            time.sleep(watch_time)
            bot.like_current()
            liked_count += 1
            logger.info(f"Liked this video, total: {liked_count}")

            # 2. 尝试评论 
            if random.random() < 0.7:
                # 优先使用话题匹配的评论，否则使用默认评论库
                if topic_comments and len(topic_comments) > 0:
                    txt = random.choice(topic_comments)
                    logger.info("Using topic-specific comment.")
                else:
                    txt = random.choice(comments)
                    logger.info("Using default comment.")
                    
                watch_time = random.uniform(1.0, 4.0)
                logger.info(f"评论前：Watching for {watch_time:.1f}s...")   
                time.sleep(watch_time)
                bot.send_comment(txt)
                commented_count += 1
                logger.info(f"Commented this video, total: {commented_count}")
            else:
                logger.info("Not commenting this video.")
            
            # 3. 随机观看 (直到视频切换或超时)
            watch_time = random.uniform(3.0, 20.0)
            logger.info(f"Watching remaining video (waiting for scene change or {watch_time:.1f}s)...")
            time.sleep(watch_time)
        else:
            logger.info("Not liking this video.")
            # 不点赞也随机观看 (短时间)
            time.sleep(random.uniform(1.0, 4.0))
        
        # 滑动下一条
        bot.scroll_next()

    logger.info("Task finished.")

if __name__ == "__main__":
    main()
