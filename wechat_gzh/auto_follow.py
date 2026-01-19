#!/usr/bin/env python3
"""
微信公众号自动关注脚本

使用方法:
    uv run python auto_follow.py              # 从第1个用户开始
    uv run python auto_follow.py --start 10   # 从第11个用户开始
    uv run python auto_follow.py -c 0.7       # 使用0.7的图像识别置信度
    
运行前请确保:
1. 微信已打开并进入搜一搜页面
2. 相关图片资源已放到 assets/mac/ 或 assets/win/ 目录下
"""

from wechat_gzh.automation.auto_follow import main

if __name__ == "__main__":
    main()
