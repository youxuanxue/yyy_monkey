#!/usr/bin/env python3
"""
测试 LLMCommentGenerator 类
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到路径，确保可以导入 wechat_client
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# 设置使用已下载的模型（如果环境变量未设置）
if "OLLAMA_MODEL" not in os.environ:
    os.environ["OLLAMA_MODEL"] = "qwen2.5:1.5b"  # 使用已下载的模型

from wechat_client.llm_client import LLMCommentGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

def test_generate_comment():
    """测试评论生成功能"""
    print("=" * 60)
    print("测试 LLMCommentGenerator.generate_comment()")
    print("=" * 60)
    
    # 创建生成器实例
    generator = LLMCommentGenerator()
    
    # 检查是否可用
    if not generator.is_available():
        print("❌ LLM 客户端不可用，请检查：")
        print("   1. 是否安装了 openai 包：pip install openai")
        print("   2. Ollama 服务是否运行（如果使用本地模型）")
        print("   3. 环境变量配置是否正确")
        return False
    
    print("✅ LLM 客户端已初始化")
    print()
    
    # 测试话题文本
    topic_text = "育儿是一起成长，要说教，更要行动#家庭教育#行动力"
    
    print(f"📝 测试话题：{topic_text}")
    print()
    
    # 测试 1: 生成评论（默认参数，69% 概率包含活动邀请）
    print("测试 1: 生成评论（默认参数）")
    print("-" * 60)
    comment1 = generator.generate_comment(topic_text)
    if comment1:
        print(f"✅ 生成成功：{comment1}")
        print(f"   长度：{len(comment1)} 字")
        print(f"   包含活动标签：{'#小小谋略家' in comment1}")
    else:
        print("❌ 生成失败")
    print()
    
    # 测试 2: 强制包含活动邀请（100% 概率）
    print("测试 2: 生成评论（强制包含活动邀请）")
    print("-" * 60)
    comment2 = generator.generate_comment(
        topic_text, 
        activity_invite_prob=1.0,
        activity_tag="#小小谋略家"
    )
    if comment2:
        print(f"✅ 生成成功：{comment2}")
        print(f"   长度：{len(comment2)} 字")
        print(f"   包含活动标签：{'#小小谋略家' in comment2}")
    else:
        print("❌ 生成失败")
    print()
    
    # 测试 3: 不包含活动邀请（0% 概率）
    print("测试 3: 生成评论（不包含活动邀请）")
    print("-" * 60)
    comment3 = generator.generate_comment(
        topic_text, 
        activity_invite_prob=0.0,
        activity_tag="#小小谋略家"
    )
    if comment3:
        print(f"✅ 生成成功：{comment3}")
        print(f"   长度：{len(comment3)} 字")
        print(f"   包含活动标签：{'#小小谋略家' in comment3}")
    else:
        print("❌ 生成失败")
    print()
    
    # 测试 4: 空话题文本
    print("测试 4: 空话题文本")
    print("-" * 60)
    comment4 = generator.generate_comment("")
    if comment4 is None:
        print("✅ 正确处理空话题（返回 None）")
    else:
        print(f"⚠️  返回了结果：{comment4}")
    print()
    
    # 测试 5: 多次生成（测试随机性）
    print("测试 5: 多次生成（测试随机性和多样性）")
    print("-" * 60)
    comments = []
    for i in range(3):
        comment = generator.generate_comment(topic_text)
        if comment:
            comments.append(comment)
            print(f"   生成 {i+1}: {comment}")
    
    if len(comments) > 0:
        print(f"✅ 成功生成 {len(comments)} 条评论")
        # 检查是否有重复
        unique_comments = set(comments)
        if len(unique_comments) < len(comments):
            print("   ⚠️  存在重复评论（可能是随机性不足）")
        else:
            print("   ✅ 所有评论都是唯一的")
    else:
        print("❌ 所有生成都失败")
    print()
    
    # 清理资源
    generator.cleanup()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_generate_comment()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

