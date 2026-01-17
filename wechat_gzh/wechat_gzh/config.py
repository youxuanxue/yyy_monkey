"""
微信公众号自动留言 - 配置文件
"""

import os
from datetime import datetime

# 获取模块根目录
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(MODULE_DIR)

# 留言内容
COMMENT_TEXT = "已关注，盼回。"

# 操作间隔时间配置（秒）
TIMING = {
    # 点击公众号后等待详情页加载
    "page_load_wait": 2.0,
    # 点击文章后等待文章页加载
    "article_load_wait": 3.0,
    # 滚动间隔
    "scroll_interval": 0.5,
    # 公众号之间的随机等待范围
    "account_interval_min": 2,
    "account_interval_max": 8,
    # 输入留言后等待发送的随机范围
    "comment_wait_min": 3,
    "comment_wait_max": 10,
}

# 历史记录文件路径（放在 config 目录，防止误删除）
# 文件名包含日期，每天单独一个文件
HISTORY_FILE = os.path.join(
    PROJECT_DIR, 
    "config", 
    f"comment_history_{datetime.now().strftime('%Y-%m-%d')}.json"
)

# 日志文件目录
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

# 配置文件目录（校准配置等）
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")

# 微信窗口配置
WECHAT = {
    # 微信窗口标题关键字
    "window_title": "微信",
    # 公众号列表区域相对于窗口的偏移（需要根据实际情况调整）
    "account_list_x_offset": 400,  # 公众号列表 X 偏移
    "account_list_y_start": 120,   # 公众号列表 Y 起始位置
    "account_item_height": 70,     # 每个公众号项的高度
    # 每次可见的公众号数量（大约）
    "visible_accounts": 10,
}

# 坐标配置说明：
# 由于不同屏幕分辨率和微信窗口大小可能不同
# 建议首次运行时使用校准模式来获取准确坐标
# 运行: uv run python -c "from wechat_gzh.automation.utils import calibrate; calibrate()"
