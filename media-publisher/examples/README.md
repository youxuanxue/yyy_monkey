# 使用示例

本目录包含使用 media-publisher 的各种示例代码。

## 示例列表

### publish_lesson_example.py

演示如何在主项目中使用 media-publisher 发布课程视频。

**用法:**

```bash
# 发布到微信视频号
python examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform wechat

# 发布到 YouTube Shorts
python examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform youtube

# 同时发布到两个平台
python examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform both

# 设置 YouTube 隐私为公开
python examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform youtube --privacy public

# 启用调试模式
python examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform wechat --debug
```

**功能:**

- 自动查找课程视频文件
- 从 script.json 读取发布信息
- 支持多平台发布
- 支持 YouTube 隐私设置

## 快速开始

### 1. 准备工作

确保已安装 media-publisher:

```bash
cd media-publisher
uv pip install -e .
```

### 2. 准备课程文件

确保课程目录结构如下:

```
series/
└── book_sunzibingfa/
    └── lesson02/
        ├── script.json          # 发布脚本
        └── media/
            └── videos/
                └── animate/
                    └── 1920p60/
                        └── *.mp4    # 视频文件
```

### 3. 准备 script.json

创建包含平台信息的 script.json:

```json
{
    "wechat": {
        "title": "标题(最多16字)",
        "description": "视频描述",
        "hashtags": ["#标签1", "#标签2"],
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

### 4. 配置 YouTube（可选）

如果要发布到 YouTube，需要配置 OAuth2 凭据:

1. 下载 OAuth2 凭据文件
2. 保存为项目根目录的 `config/youtube_credentials.json`
3. 首次运行时会在浏览器中完成授权

详见 [README.md](../README.md)

### 5. 运行示例

```bash
# 从项目根目录运行
python media-publisher/examples/publish_lesson_example.py book_sunzibingfa/lesson02 --platform both
```

## 自定义示例

你可以基于这些示例创建自己的发布脚本:

```python
from media_publisher import WeChatPublisher, YouTubePublisher
from media_publisher import WeChatPublishTask, YouTubePublishTask
from pathlib import Path

# 创建任务
video_path = Path("path/to/video.mp4")
wechat_task = WeChatPublishTask(
    video_path=video_path,
    title="标题",
    description="描述",
    hashtags=["#标签1", "#标签2"]
)

# 发布
with WeChatPublisher() as publisher:
    publisher.authenticate()
    success, message = publisher.publish(wechat_task)
    print(f"发布结果: {success}")
```

## 故障排除

如果遇到问题，请查看 [README.md](../README.md) 中的常见问题部分。
