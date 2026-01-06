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
    parser.add_argument("--mode", choices=["run", "test_assets", "test_comments"], default="run", help="模式")
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
    
    if args.mode == "test_comments":
        logger.info("测试获取历史评论功能... 请打开微信视频号评论窗口")
        logger.info("倒计时 5 秒，请切换到评论页面...")
        for i in range(5, 0, -1):
            logger.info(f"{i}...")
            time.sleep(1)
        
        comments = bot.get_history_comments(debug=True)
        if comments:
            logger.info(f"✅ 成功识别到 {len(comments)} 条评论:")
            for i, comment in enumerate(comments, 1):
                logger.info(f"  {i}. {comment}")
        else:
            logger.warning("❌ 未能识别到评论")
        return

    logger.info("Auto Mode starting ... Switch to WeChat NOW!")

    followed_count = 0
    liked_count = 0
    commented_count = 0
    interactived_count = 0

    while interactived_count < int(args.max_interactions):
        # 获取视频描述（已规范化处理）
        topic_text = bot.get_video_topic()
        if not topic_text:
            logger.warning("无法获取视频描述，跳过此视频")
            bot.scroll_next()
            continue
        
        # 使用 task_prompt.json 生成评论结果
        result = bot.generate_comment_from_task(topic_text)
        
        if not result:
            logger.warning("Failed to generate comment result from task. Skipping this video.")
            bot.scroll_next()
            continue
        
        interactived = False
        should_follow = False

        # result 存在，继续处理
        real_human_score = result.get("real_human_score", 0.0)
        follow_back_score = result.get("follow_back_score", 0.0)
        persona_consistency_score = result.get("persona_consistency_score", 0.0)
        
        # 判断互动策略
        # 当 persona_consistency_score < 0.8 或者 real_human_score < 0.8 时，跳过
        if persona_consistency_score < 0.8 or real_human_score < 0.8:
            logger.info(
                f"评分不达标 (consistency={persona_consistency_score:.2f}<0.8 或 "
                f"real_human={real_human_score:.2f}<0.8)，跳过互动"
            )
            bot.scroll_next()
            continue
            
        # 否则当 follow_back_score > 0.85 时，点赞+关注+评论
        if follow_back_score > 0.85:
            logger.info(f"回关评分高 (follow_back={follow_back_score:.2f}>0.85)，点赞+关注+评论")
            should_follow = True
        else:
            # 其他情况：点赞+评论（不关注）
            logger.info(f"评分正常，点赞+评论（不关注）")
        
        # 1. 评论（如果需要）- 优先执行，避免页面状态变化后无法获取视频描述
        if result and result.get("comment"):
            comment = result.get("comment")
            # 直接发送评论，此时页面状态还未变化，不需要重新获取 topic_text
            if comment and bot.send_comment(comment):
                commented_count += 1
                interactived = True
                logger.info(f"✅Commented this video, total: {commented_count}")
            else:
                logger.warning("评论发送失败")
        
        # 2. 关注（如果需要）
        if should_follow:
            time.sleep(random.uniform(0.5, 2))
            if bot.follow_current():
                followed_count += 1
                interactived = True
                logger.info("✅Followed video creator")
            else:
                logger.warning("关注失败")

        # 3. 点赞
        if bot.like_current():
            time.sleep(random.uniform(0.5, 2))
            liked_count += 1
            interactived = True
            logger.info(f"✅Liked this video, total: {liked_count}")
        else:
            logger.warning("点赞失败")

        if interactived: 
            interactived_count += 1
            logger.info(f"✅Interactived this video, total: {interactived_count}")
            bot.scroll_next(3, 20)
        else:
            logger.info("❌Not interacting with this video.")        
            bot.scroll_next()

    logger.info("Task finished.")

if __name__ == "__main__":
    main()
