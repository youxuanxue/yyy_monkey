## 抖音网页端自动互动助手 (Douyin Auto Like)

这是一个基于 Python + Selenium 的抖音网页端自动化工具，用于模拟人工操作进行视频互动（点赞、评论、弹幕）。支持 Windows 本地一键打包部署。

### 功能特点

1.  **自动点赞**：双击视频区域点赞，支持基于视频时长的概率控制（短视频跳过，长视频低频，中等时长高频）。
2.  **自动弹幕**：从加密的数据文件中随机读取弹幕内容发送（默认概率 0.46）。
3.  **自动评论**：从加密的数据文件中随机读取评论内容发送，精准定位编辑器，支持自动验证（默认概率 0.67）。
4.  **模拟真人**：
    -   随机观看时长（不看完、中途划走）。
    -   随机互动概率（不是每个视频都点赞/评论）。
    -   操作间隔随机化。
5.  **Follow 模式**：全自动刷视频模式，监控页面 URL 变化，对新视频执行互动策略，自动划走。
6.  **安全验证处理**：自动检测验证码弹窗并暂停，提示人工介入处理。
7.  **数据加密**：评论和弹幕数据文件使用 XOR + Base64 加密存储，防止明文泄露。

### 目录结构

```
local_service/
├── data/                   # 数据文件目录
│   ├── comments.enc        # 加密后的评论库
│   ├── danmaku.enc         # 加密后的弹幕库
│   ├── comments.txt        # (开发用/源文件) 明文评论库
│   └── danmaku.txt         # (开发用/源文件) 明文弹幕库
├── dist/                   # 打包后的可执行文件目录 (构建后生成)
├── logs/                   # 运行日志
├── src/                    # 源代码
│   └── douyin_auto_like/
│       ├── cli.py          # 入口与主逻辑
│       ├── douyin.py       # 页面交互逻辑封装
│       └── browser.py      # 浏览器驱动封装
├── scripts/                # 工具脚本
│   └── encrypt_data.py     # 数据加密脚本
├── build_exe.bat           # Windows 一键打包脚本
├── douyin_bot.spec         # PyInstaller 打包配置
├── requirements.txt        # 依赖列表
└── README_DEPLOY.md        # 部署与打包指南
```

### 快速开始 (开发环境)

#### 1. 环境准备
- Python >= 3.10
- Google Chrome 浏览器
- uv (推荐) 或 pip

#### 2. 安装依赖

```bash
cd local_service
# 使用 uv
uv sync
# 或者使用 pip
pip install -r requirements.txt
```

#### 3. 数据准备

如果需要修改评论或弹幕内容：
1. 编辑 `data/comments.txt` 或 `data/danmaku.txt`。
2. 运行加密脚本重新生成 `.enc` 文件：
   ```bash
   python scripts/encrypt_data.py
   ```

#### 4. 运行

```bash
# 启动自动刷视频模式 (Follow 模式)
# --manual-login 推荐首次使用时开启，方便手动扫码登录
python src/douyin_auto_like/cli.py --video-url "https://www.douyin.com/video/xxxxxxxx" --manual-login

# 仅发送一条弹幕
python src/douyin_auto_like/cli.py --mode danmaku --video-url "..." --text "测试弹幕"

# 查看帮助
python src/douyin_auto_like/cli.py --help
```

### 参数说明

- `--video-url`: **(必填)** 起始视频链接。
- `--mode`: 运行模式，默认为 `follow` (全自动)。可选 `danmaku` (单发弹幕), `comment` (单发评论), `open` (仅打开浏览器调试)。
- `--max-likes`: Follow 模式下点赞达到该数量后停止（默认 10）。
- `--manual-login`: 启动后暂停，等待用户手动操作（如扫码登录）。
- `--headless`: 无头模式运行（不显示浏览器界面，**首次登录不建议开启**）。
- `--profile-dir`: 指定 Chrome Profile 目录，默认为项目下的 `.chrome_profile`。
- `--verbose`: 输出详细调试日志。
- `--seed`: 随机种子（复现用）。
- `--restart-driver-on-change`: Follow 模式下，每次切换视频都重启浏览器（更慢但更稳定，用于规避某些风控）。
- `--refresh-on-change`: Follow 模式下，每次切换视频都刷新页面。

### Windows 打包部署

详情请参考 [README_DEPLOY.md](README_DEPLOY.md)。

简述：
1. 确保安装 Python 和 Chrome。
2. 双击运行 `local_service/build_exe.bat`。
3. 分发 `local_service/dist/DouyinAutoLike` 文件夹。

### 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。
