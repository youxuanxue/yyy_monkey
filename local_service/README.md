## 抖音网页端自动互动助手（Python + Selenium，uv 管理）

> 说明：抖音网页端会有风控/验证码/弹窗等不可控因素，本项目不做“绕过风控”。脚本默认使用**人工扫码登录**，并通过 Chrome Profile 复用登录态。如遇安全验证，脚本会暂停并提示人工处理。

### 环境准备

- **Chrome 浏览器**
- **Python >= 3.10**
- **uv**（包管理/运行）

#### Windows（PowerShell）快速安装/修复 `uv` 找不到

如果你执行 `uv sync` / `uv run ...` 提示 “无法将 uv 项识别为 cmdlet”，通常是 **uv 未安装** 或 **安装后未重启 PowerShell 导致 PATH 未刷新**。

在 PowerShell 里执行：

```powershell
# 安装 Python（>=3.10）与 uv
winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
winget install -e --id astral-sh.uv       --silent --accept-package-agreements --accept-source-agreements

# 不重启终端也能生效：刷新当前会话 PATH
$machine=[Environment]::GetEnvironmentVariable('Path','Machine')
$user=[Environment]::GetEnvironmentVariable('Path','User')
$env:Path="$machine;$user"

# 验证
uv --version
python --version
```

> 也可以直接 **关闭并重新打开 PowerShell**，让新 PATH 自动生效。

在 `local_service/` 目录执行：

```bash
cd /Users/xuejiao/Codes/yyy_monkey/local_service
uv sync
```

> 如果你还没创建虚拟环境，`uv sync` 会自动处理；也可以先 `uv venv` 再 `uv sync`。

### 主要功能

1.  **自动点赞**：双击视频区域点赞（带概率控制与防重复策略）。
2.  **自动弹幕**：发送自定义弹幕内容。
3.  **自动评论**：精准定位 Draft.js 编辑器，支持占位符激活，自动发送并验证结果。
4.  **模拟观看**：在互动前根据视频时长随机等待，模拟真实观看行为。
5.  **Follow 模式**：持续监控页面 URL 变化（针对自动播放/滑走场景），对新视频执行互动。
6.  **安全验证处理**：自动检测验证码弹窗并暂停，支持人工介入。

### 用法

#### 1）对“指定视频链接”点赞一次

```bash
uv run douyin-like --video-url "https://www.douyin.com/video/xxxxxxxxxxxx"
```

首次运行会打开浏览器，请你在弹出的抖音页面里**手动扫码登录**；脚本会把登录态保存在默认的 Chrome Profile（`local_service/.chrome_profile/`），下次无需重复登录。

建议首次显式开启 `--manual-login`（脚本会暂停，等你扫码完成后继续）：

```bash
uv run douyin-like --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --manual-login
```

> 融合策略：在 `like` 模式下，当视频命中“点赞概率”进入点赞分支时，会再以 **62%** 的概率自动发送一条弹幕（默认“哇塞，赞赞赞”，可用 `--text` 自定义）。

#### 2）自动发送一条弹幕（文本默认“哇塞，赞赞赞”）

```bash
uv run douyin-like --mode danmaku --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --manual-login
```

可自定义弹幕内容：

```bash
uv run douyin-like --mode danmaku --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --text "哇塞，赞赞赞" --manual-login
```

#### 3）自动发送一条评论（文本默认“好开心看到你的视频”）

```bash
uv run douyin-like --mode comment --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --manual-login
```

可自定义评论内容：

```bash
uv run douyin-like --mode comment --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --text "好开心看到你的视频" --manual-login
```

**功能说明**：
- 脚本会自动寻找并点击评论图标打开评论区。
- 如果评论输入框是折叠/占位符状态，脚本会自动点击激活，等待 Draft.js 编辑器渲染。
- 支持发送后自动验证（检查评论列表中是否出现该文本）。
- 全程支持验证码检测与暂停等待。

#### 4）全自动互动模式（点赞 + 弹幕 + 评论）

```bash
uv run douyin-like --mode all --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --manual-login
```

**互动策略**：
- **点赞**：命中“感兴趣”概率后必点。
- **弹幕**：点赞成功后，以 **62%** 概率尝试发送。
- **评论**：点赞成功后，以 **30%** 概率尝试发送。

**关于文案**：
- 如果你通过 `--text` 指定了内容，弹幕和评论都会使用这同一段文本。
- 如果**不指定** `--text`（推荐），脚本会使用各自默认的文案：
  - 弹幕：“哇塞，赞赞赞”
  - 评论：“好开心看到你的视频”

### 常用参数

- `--profile-dir`：指定 Chrome Profile 目录（用于复用登录态）
- `--headless`：无头模式（不建议用于首次登录）
- `--interval`：每次操作间隔秒数（默认 2.0）
- `--manual-login`：打开页面后暂停，等待你扫码/登录完成后继续
- `--dump-cookies`：把 cookies 导出 JSON（排查登录态）
- `--verbose`：输出更详细的执行日志
- `--follow`：点赞后持续监控 URL（URL 变化则对新视频继续决策/点赞；遇到 live 跳过）
- `--check-interval`：follow 模式 URL 检测间隔秒数（默认 5）
- `--refresh-on-change`：follow 模式 URL 变化时先 `refresh` 再抓信息（轻量）
- `--restart-driver-on-change`：follow 模式 URL 变化时重启 WebDriver（复用 profile，更慢但更稳）
- `--max-likes`：点赞动作总数上限（>0 生效；达到后退出）

### 点赞方式说明

当前实现**只使用“双击视频区域”点赞**，不再尝试定位点赞按钮，也不会判断“是否已点赞”。
如果你对已经点过赞的视频再次执行双击，可能会出现“重复触发/状态变化”的风险（以页面实际行为为准）。

另外：在 **like 模式**下，若视频命中点赞决策（like-prob），会以 **62% 概率**自动尝试发送一条弹幕（文本用 `--text`，默认“哇塞，赞赞赞”）。

### 点赞概率与播放速率策略

- **点赞概率**：
  - 10 秒以下：**0%**（直接跳过并滑走）
  - 10 秒 ~ 3 分钟：**67%**
  - 3 分钟以上：**34%**
  - 未命中概率：不点赞并模拟“滑走下一条”
- **播放速率**：固定 **1.5x**

### 日志

启动后会在 `local_service/logs/` 下按启动时间生成日志文件，并同步输出到终端。

follow 模式每个 tick 会输出一行 `TICK {...}`（JSON），包含 URL、标题与视频时长/进度/倍速等关键字段，便于离线分析。

### 免责声明

仅供学习自动化测试/个人效率用途。请遵守平台规则与法律法规，避免高频操作造成账号风险。


