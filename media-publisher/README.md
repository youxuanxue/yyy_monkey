# 📹 Media Publisher

一键发布视频到多个短视频平台，支持微信视频号和YouTube Shorts。

## ✨ 功能特性

- 🎯 **多平台支持**: 同时支持微信视频号和YouTube Shorts
- 🎨 **简洁 GUI**: 基于 Gradio 的 Web 界面，操作简单直观
- 📄 **脚本支持**: 支持从 JSON 文件自动读取发布信息
- 🔐 **登录记忆**: 自动保存登录状态，无需重复认证
- 📦 **合集支持**: 微信视频号可自动选择合集
- 🎪 **活动支持**: 微信视频号可自动参加平台活动
- 📋 **播放列表**: YouTube 可自动添加到播放列表
- 💻 **命令行模式**: 支持命令行直接发布

## 🚀 快速开始

### 1. 安装

```bash
cd media-publisher

# 使用 uv 安装（推荐）
uv pip install -e .

# 安装 Playwright 浏览器（用于微信视频号发布）
uv run playwright install chromium
```

### 2. 验证安装

```bash
python verify_install.py
```

### 3. 配置 YouTube API（可选）

如果需要发布到 YouTube Shorts，需要先配置 YouTube API：

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建或选择项目
3. 启用 YouTube Data API v3
4. 创建 OAuth 2.0 凭据（桌面应用）
5. **重要**: 添加授权重定向 URI: `http://localhost:8080/`
6. 下载凭据文件并保存为 `config/youtube_credentials.json`

## 📖 使用方法

### 方式 1: GUI 界面

```bash
# 启动 GUI
media-publisher

# 或使用 Python 模块
python -m media_publisher

# 指定端口
media-publisher --port 8080

# 如遇 localhost 问题，使用 share 模式
media-publisher --share
```

启动后会自动打开浏览器访问 `http://localhost:7860`。

### 方式 2: 命令行模式（推荐）

```bash
# 发布到微信视频号
media-publisher --video /path/to/video.mp4 --platform wechat --script /path/to/script.json

# 发布到 YouTube Shorts
media-publisher --video /path/to/video.mp4 --platform youtube --script /path/to/script.json

# 同时发布到两个平台
media-publisher --video /path/to/video.mp4 --platform both --script /path/to/script.json

# 设置 YouTube 为公开
media-publisher --video /path/to/video.mp4 --platform youtube --privacy public --script /path/to/script.json
```

### 方式 3: Python 代码

```python
from media_publisher import (
    WeChatPublisher,
    YouTubePublisher,
    WeChatPublishTask,
    YouTubePublishTask,
)

# 微信视频号
with WeChatPublisher(headless=False) as publisher:
    publisher.authenticate()
    task = WeChatPublishTask.from_json(video_path, script_data)
    success, message = publisher.publish(task)

# YouTube Shorts
with YouTubePublisher() as publisher:
    task = YouTubePublishTask.from_json(video_path, script_data)
    success, video_url = publisher.publish(task)
```

## 📋 JSON 脚本格式

```json
{
    "wechat": {
        "title": "视频标题（最多16字）",
        "description": "视频描述内容",
        "hashtags": ["#标签1", "#标签2", "#标签3"],
        "heji": "合集名称",
        "huodong": "活动名称"
    },
    "youtube": {
        "title": "YouTube 视频标题",
        "description": "YouTube 视频描述",
        "tags": ["标签1", "标签2"],
        "playlists": "播放列表名称",
        "privacy": "private"
    }
}
```

### 字段说明

#### 微信视频号 (wechat)

| 字段 | 必需 | 说明 |
|------|------|------|
| `title` | 否 | 视频短标题，最多16个字符 |
| `description` | 否 | 视频描述 |
| `hashtags` | 否 | 话题标签数组，会自动拼接到描述末尾 |
| `heji` | 否 | 合集名称，程序会自动选择对应合集 |
| `huodong` | 否 | 活动名称，程序会自动搜索并参加活动 |

#### YouTube Shorts (youtube)

| 字段 | 必需 | 说明 |
|------|------|------|
| `title` | 是 | 视频标题 |
| `description` | 是 | 视频描述 |
| `tags` | 否 | 标签数组 |
| `playlists` | 否 | 播放列表名称（不存在会自动创建）|
| `privacy` | 否 | 隐私设置：`public`、`unlisted`、`private`（默认）|

## 🔐 认证状态保存

### 微信视频号

登录状态保存在用户主目录下：

```
~/.media-publisher/wechat_auth.json
```

首次使用需要扫码登录，之后会自动使用保存的登录状态。

### YouTube

OAuth2 认证信息保存在：

```
config/youtube_credentials.json  # OAuth2 客户端凭据（需手动配置）
config/youtube_token.json        # 访问令牌（自动生成）
```

## 🛠️ 项目结构

```
media-publisher/
├── pyproject.toml              # 项目配置
├── README.md                   # 说明文档
├── verify_install.py           # 安装验证脚本
├── src/
│   └── media_publisher/
│       ├── __init__.py         # 模块入口
│       ├── __main__.py         # 命令行入口
│       ├── core/
│       │   ├── base.py         # 发布器基类和接口
│       │   ├── wechat.py       # 微信视频号发布器
│       │   └── youtube.py      # YouTube 发布器
│       └── gui/
│           └── app.py          # Gradio GUI
├── examples/
│   ├── README.md               # 示例说明
│   └── publish_lesson_example.py
└── docs/                       # 文档
```

## 📦 集成到其他项目

### 安装

```bash
cd media-publisher
uv pip install -e .
```

### 导入使用

```python
from media_publisher import (
    Platform,
    WeChatPublisher,
    YouTubePublisher,
    WeChatPublishTask,
    YouTubePublishTask,
)
```

### 迁移旧代码

如果之前使用 `src/publish/` 中的发布模块，更新导入：

```python
# 旧的导入
# from src.publish.wx_channel import WeChatChannelPublisher, VideoPublishTask
# from src.publish.youtube_publisher import YouTubePublisher, YouTubePublishTask

# 新的导入
from media_publisher import WeChatPublisher, WeChatPublishTask
from media_publisher import YouTubePublisher, YouTubePublishTask
```

类名变更：
- `WeChatChannelPublisher` → `WeChatPublisher`
- `VideoPublishTask` → `WeChatPublishTask`
- `login()` → `authenticate()`

## ❓ 常见问题

### 导入错误

```
ModuleNotFoundError: No module named 'media_publisher'
```

**解决**: 确保已安装模块：
```bash
cd media-publisher
uv pip install -e .
```

### Playwright 浏览器无法启动

**解决**: 重新安装浏览器：
```bash
uv run playwright install chromium
```

### YouTube API 认证失败

检查以下几点：
1. `config/youtube_credentials.json` 文件是否存在
2. Google Cloud Console 中是否添加了重定向 URI: `http://localhost:8080/`
3. 是否启用了 YouTube Data API v3

### GUI localhost 访问问题

**解决**: 使用 share 模式：
```bash
media-publisher --share
```

### 微信视频号需要手动点击发布

是的，出于安全考虑，程序会自动填写所有信息，但最后的"发布"按钮需要人工确认。

## ⚠️ 注意事项

### 微信视频号

1. 发布过程中会打开 Chrome 浏览器窗口，请勿关闭
2. 视频上传完成后，需要在浏览器中手动点击「发布」按钮
3. 需要稳定的网络连接

### YouTube Shorts

1. YouTube API 每日有使用配额限制
2. 竖屏视频（9:16）会自动识别为 Shorts
3. 首次授权需要在浏览器中完成 OAuth2 授权

### 通用

- 支持的视频格式: MP4、MOV、AVI
- 建议视频分辨率: 1080x1920 (9:16 竖屏)

## 📄 License

MIT License
