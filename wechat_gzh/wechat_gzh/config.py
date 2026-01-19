"""
微信公众号自动留言 - 配置文件
"""

import os
import sys
from datetime import datetime

def get_app_root():
    """获取应用根目录（用户数据存储目录，配置/日志/模型等）"""
    if getattr(sys, 'frozen', False):
        # 打包后，返回可执行文件所在目录
        # 注意：在 macOS .app bundle 中，executable 在 Contents/MacOS/ 下
        # 我们希望配置在 .app 旁边，或者 .app/Contents/Resources/ 下？
        # 为了方便用户修改，还是建议放在 .app 同级目录下，或者用户的文档目录下
        # 这里简化处理：放在可执行文件旁边（Windows）或 .app 包外（Mac）
        
        exe_path = sys.executable
        exe_dir = os.path.dirname(exe_path)
        
        # 处理 macOS .app 的情况
        if os.path.basename(exe_dir) == "MacOS" and ".app" in exe_dir:
            # 回退到 .app 所在的目录
            return os.path.dirname(os.path.dirname(os.path.dirname(exe_dir)))
            
        return exe_dir
    else:
        # 开发模式，返回项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_root():
    """获取资源目录（代码、内置图片等只读资源）"""
    if getattr(sys, 'frozen', False):
        # 打包后，资源在临时解压目录
        return sys._MEIPASS
    else:
        # 开发模式，同项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 应用根目录（可读写）
PROJECT_DIR = get_app_root()
# 资源目录（只读）
RESOURCE_DIR = get_resource_root()

# 模块目录
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

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

# 日志文件目录
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

# 配置文件目录（校准配置等）
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")

# 历史记录文件路径
# 不再包含日期，所有历史记录合并到一个文件
HISTORY_FILE = os.path.join(
    CONFIG_DIR, 
    "comment_history.json"
)

# 确保必要的目录存在
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

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

# Ollama 配置（使用系统安装的 Ollama）
OLLAMA_CONFIG = {
    # 服务地址和端口
    "host": "127.0.0.1",
    "port": 11434,
}

# 坐标配置说明：
# 由于不同屏幕分辨率和微信窗口大小可能不同
# 建议首次运行时使用校准模式来获取准确坐标
# 运行: uv run python -c "from wechat_gzh.automation.utils import calibrate; calibrate()"
