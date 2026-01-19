# wechat-gzh

微信公众号（GZH = 公众号）工具集，包含：

1. **API 客户端** - 通过微信公众号官方 API 获取用户信息
2. **自动留言** - 在已关注的公众号文章中自动留言

### 安装依赖

```bash
uv sync
```

### 功能一：获取用户信息

通过微信公众号 API 获取关注用户信息。

#### 配置

在 `.env` 文件中配置：

```
WX_APP_ID=your_app_id
WX_APP_SECRET=your_app_secret
```

#### 使用方法

```bash
uv run python -m wechat_gzh.get_users
```

#### 输出文件

- `users_info.json` - 用户详细信息
- `users_openid.txt` - 用户 OpenID 列表

---

### 功能二：公众号自动留言

自动遍历已关注的微信公众号，在每个公众号的最新文章中留言。

#### 功能特性

- 自动遍历公众号列表
- OCR 识别公众号名称和文章标题
- 随机等待时间（3-10秒），模拟人工操作
- 记录处理历史，避免重复留言
- 支持中断后继续处理
- 详细的日志记录
- **校准配置自动保存**，下次运行可直接使用

#### 前置要求

1. **操作系统**：macOS 或 Windows 11
2. **微信桌面客户端**（需要已登录）
3. **Python 依赖**：通过 `uv sync` 自动安装（包含 OCR 库）
4. **macOS 额外权限**：辅助功能权限（系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能）

#### Windows 适配特别说明

首次在 Windows 上运行时，需要准备图像识别资源：

1. 确保微信界面为默认皮肤（浅色模式）
2. 手动采集以下按钮图片并保存到 `wechat_gzh/assets/win/` 目录下（文件名必须一致）：
   - `comment_button.png` (写留言按钮)
   - `comment_input.png` (留言输入框)
   - `send_button.png` (发送按钮)

## 使用方法

### 图形化界面 (推荐)

我们提供了一个基于 Web 的现代化图形界面 (NiceGUI)，方便操作和监控。

```bash
# 在 wechat_gzh 目录下运行
uv run python web_app.py

# 或者从项目根目录运行
uv run python -m wechat_gzh.web_app
```

启动后，浏览器会自动打开 `http://localhost:8080`。你可以在界面上：
- 启动/停止自动留言任务
- 实时查看运行日志
- 修改 AI 提示词 (Prompt)
- 调整和保存坐标校准配置
- 生成校准验证截图

### 命令行运行

如果你更喜欢命令行：

```bash
# 正常运行（自动加载校准配置，如不存在则初始化默认值）
uv run python -m wechat_gzh.auto_comment

# 仅验证校准配置（生成标注截图，不执行自动留言）
uv run python -m wechat_gzh.auto_comment -v
uv run python -m wechat_gzh.auto_comment --verify

# 限制最多处理 10 个公众号
uv run python -m wechat_gzh.auto_comment -n 10
uv run python -m wechat_gzh.auto_comment --max-accounts 10
```

#### 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--verify` | `-v` | 仅验证校准配置（生成标注截图后退出） |
| `--max-accounts N` | `-n N` | 最大处理公众号数量，0 表示不限制 |
| `--debug-screenshot` | | 启用调试截图（保存调试截图和 OCR 区域截图） |

#### 校准验证

每次加载或完成校准后，会自动生成带标注的截图（保存在 `logs/` 目录），标注内容：

- 🔴 **红色点 (1-3)**: 公众号列表中的前3个位置
- 🟢 **绿色点**: 文章点击位置
- 🔵 **蓝色框**: 公众号名称 OCR 识别区域
- 🟠 **橙色框**: 文章标题 OCR 识别区域

**注意**：留言按钮、输入框和发送按钮已改用图片识别自动定位，无需手动校准坐标。

如需单独验证校准配置，运行 `uv run python -m wechat_gzh.auto_comment -v`

#### 配置

修改 `wechat_gzh/config.py`：

```python
# 留言内容
COMMENT_TEXT = "已关注，盼回。"

# 操作间隔时间配置（秒）
TIMING = {
    "account_interval_min": 3,   # 公众号间隔最小秒数
    "account_interval_max": 10,  # 公众号间隔最大秒数
    "comment_wait_min": 3,       # 留言发送前最小等待
    "comment_wait_max": 10,      # 留言发送前最大等待
}
```

#### 安全提示

- **紧急中断**：将鼠标移动到屏幕左上角
- **手动停止**：按 `Ctrl+C`
  - 校准阶段：直接退出
  - 主循环阶段：等待当前操作完成后安全退出

---

## 项目结构

```
wechat_gzh/                      # 项目根目录
├── web_app.py                   # Web 界面主程序（推荐）
├── wechat_gzh/                  # Python 包
│   ├── __init__.py              # 模块入口
│   ├── api.py                   # 微信公众号 API 客户端
│   ├── config.py                # 配置文件
│   ├── get_users.py             # 获取用户信息主程序
│   ├── auto_comment.py          # 自动留言主程序
│   ├── llm_client.py            # LLM 评论生成客户端
│   └── automation/              # GUI 自动化子模块
│       ├── __init__.py
│       ├── navigator.py         # 导航操作
│       ├── commenter.py         # 留言操作（图片识别）
│       ├── ocr.py               # OCR 识别
│       ├── calibration.py       # 校准配置管理
│       ├── visualizer.py        # 校准可视化
│       └── utils.py             # 工具函数
├── assets/                      # 图像识别资源
│   ├── mac/                     # macOS 平台资源
│   │   ├── comment_button*.png  # 留言按钮图片（用于图片识别）
│   │   ├── comment_input*.png   # 输入框图片（用于图片识别）
│   │   └── send_button.png      # 发送按钮图片（用于图片识别）
│   └── win/                     # Windows 平台资源
├── config/                      # 配置文件目录
│   ├── calibration.json         # 校准配置（导航和 OCR）
│   └── task_prompt.json         # LLM 任务提示词配置
├── scripts/                     # 实用脚本
├── pyproject.toml               # 项目配置
├── uv.lock                      # 依赖锁定文件
└── README.md                    # 本文件
```

## 打包分发

如果需要将应用打包成独立可执行文件分发给没有代码基础的用户，可以使用以下方式：

### 一键打包

```bash
# macOS/Linux
chmod +x build.sh
./build.sh

# Windows
build.bat
```

### 手动打包

```bash
# 同步依赖（包括 pyinstaller）
uv sync

# 运行打包脚本
uv run python build.py
```

### 打包输出

打包完成后，`dist/` 目录包含：

```
dist/
├── 微信公众号评论机器人      # 主程序（Windows 为 .exe）
├── config/                   # 配置文件目录
│   ├── calibration.json     # 坐标校准配置
│   ├── task_prompt.json     # AI 提示词配置
│   └── comment_history.json # 评论历史记录
├── logs/                     # 日志目录
├── 启动.command / 启动.bat   # 启动脚本
└── 使用说明.md               # 用户使用说明
```

### 分发注意事项

打包后的应用**不包含 Ollama**，用户需要自行安装：

1. 安装 Ollama: https://ollama.com
2. 拉取模型: `ollama pull qwen2.5:3b`
3. 启动服务: `ollama serve`

然后双击应用即可使用。

---

## 注意事项

1. 自动留言功能使用 GUI 自动化技术，依赖屏幕坐标
2. 首次运行会自动生成默认校准配置 `wechat_gzh/config/calibration.json`
3. 建议首次运行后使用 `-v` 参数验证位置，并根据实际情况修改配置文件
4. 如果微信窗口位置/大小改变，请更新配置文件
5. 请妥善保管 `.env` 文件
6. 建议先在测试账号上验证
