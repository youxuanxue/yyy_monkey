## 抖音网页端自动点赞（Python + Selenium，uv 管理）

> 说明：抖音网页端会有风控/验证码/弹窗等不可控因素，本项目不做“绕过风控”。脚本默认使用**人工扫码登录**，并通过 Chrome Profile 复用登录态。

### 环境准备

- **Chrome 浏览器**
- **Python >= 3.10**
- **uv**（包管理/运行）

在 `local_service/` 目录执行：

```bash
cd /Users/xuejiao/Codes/yyy_monkey/local_service
uv sync
```

> 如果你还没创建虚拟环境，`uv sync` 会自动处理；也可以先 `uv venv` 再 `uv sync`。

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

#### 2）自动发送一条弹幕（文本默认“哇塞，赞赞赞”）

```bash
uv run douyin-danmaku --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --manual-login
```

可自定义弹幕内容：

```bash
uv run douyin-danmaku --video-url "https://www.douyin.com/video/xxxxxxxxxxxx" --text "哇塞，赞赞赞" --manual-login
```

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


