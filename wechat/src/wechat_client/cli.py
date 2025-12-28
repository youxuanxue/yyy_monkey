from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path

# 添加 src 到路径以支持直接运行
sys.path.append(str(Path(__file__).resolve().parent.parent))

# 在导入其他模块之前先配置日志，确保所有 logger 都能输出到终端
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    force=True  # 强制重新配置，即使之前已经配置过
)

from wechat_client.core import BotCore
from wechat_client.platform_mgr import PlatformManager
from wechat_client.license import verify_license

logger = logging.getLogger("wechat-bot")

def main() -> None:
    
    # 1. 校验 License
    verify_license()
    
    parser = argparse.ArgumentParser(description="WeChat Client Auto Bot")
    parser.add_argument("--mode", choices=["run", "test_assets"], default="run", help="模式")
    parser.add_argument("--max-interactions", type=int, default=17, help="互动动作总数上限（>0 生效；达到后退出）")
    args = parser.parse_args()
    
    # 路径配置
    # 假设 wechat 目录是当前工作目录或上级目录
    # 运行时建议在 wechat/ 根目录下运行 python -m src.wechat_client.cli
    base_dir = Path.cwd()
    
    # 智能判断根目录：如果当前目录下没有 assets 但有 wechat 目录，则进入 wechat 目录
    if not (base_dir / "assets").exists() and (base_dir / "wechat").exists():
        base_dir = base_dir / "wechat"
    
    asset_dir = base_dir / "assets"

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

    liked_count = 0
    commented_count = 0
    interactived_count = 0
    INTERACTION_PROB = 0.31  # 互动概率阈值

    while interactived_count < int(args.max_interactions):
        topic_text = bot.get_video_topic()
        interactived = False
        
        # 1. 尝试点赞
        cur_prob = random.random()
        if cur_prob < INTERACTION_PROB:
            interactived = True
            watch_time = random.uniform(2.0, 6.0)
            logger.info(f"点赞前(prob={cur_prob:.2f}<{INTERACTION_PROB:.2f})：Watching for {watch_time:.1f}s...") 
            time.sleep(watch_time)
            bot.like_current()
            liked_count += 1
            logger.info(f"✅Liked this video, total: {liked_count}")
        else:
            logger.info(f"❌Not liking this video (prob={cur_prob:.2f}>={INTERACTION_PROB:.2f}).")
        # 2. 尝试评论 
        cur_prob = random.random()
        if cur_prob < INTERACTION_PROB:
            # 使用大模型根据 topic_text 生成评论
            txt = bot.generate_comment_with_llm(topic_text)
            
            # 如果大模型生成失败，跳过评论
            if not txt:
                logger.warning("LLM comment generation failed. Skipping comment.")
            else:
                interactived = True
                watch_time = random.uniform(1.0, 4.0)
                logger.info(f"评论前(prob={cur_prob:.2f}<{INTERACTION_PROB:.2f})：Watching for {watch_time:.1f}s...")   
                time.sleep(watch_time)
                bot.send_comment(txt)
                commented_count += 1
                logger.info(f"✅Commented this video, total: {commented_count}")
        else:
            logger.info(f"❌Not commenting this video (prob={cur_prob:.2f}>={INTERACTION_PROB:.2f}).")

        if interactived: 
            interactived_count += 1
            logger.info(f"✅Interactived this video, total: {interactived_count}")
            # 3. 互动后随机观看 (直到视频切换或超时)
            watch_time = random.uniform(3.0, 20.0)
            logger.info(f"After interation, watching remaining video for {watch_time:.1f}s...")
            time.sleep(watch_time)
        else:
            logger.info("❌Not liking/commenting this video.")
            # 不互动也随机观看 (短时间)
            time.sleep(random.uniform(1.0, 4.0))
        
        # 滑动下一条
        bot.scroll_next()

    logger.info("Task finished.")

if __name__ == "__main__":
    main()
