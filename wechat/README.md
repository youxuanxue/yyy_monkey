# WeChat Client Automation Bot

基于图像识别 (Computer Vision) 的微信 PC 客户端自动化助手。支持 Mac 和 Windows 双平台。

## 核心原理

不同于 Web 版的 Selenium 方案，本项目采用 **Screen Capture + Image Recognition**：
1.  **PyAutoGUI**: 控制鼠标点击、键盘输入、屏幕截图。
2.  **OpenCV**: 在屏幕截图中寻找目标图标（如点赞爱心、评论输入框）。
3.  **PyPerClip**: 使用系统剪贴板粘贴文本（解决中文输入问题）。

## 目录结构

```
wechat/
  ├── assets/            # 资源图片库 (必须手动截图填充!)
  │   ├── mac/           # Mac 专用截图
  │   └── win/           # Windows 专用截图
  ├── data/
  │   └── comments.txt   # 评论语料库
  ├── src/
  │   └── wechat_client/
  │       ├── core.py    # 视觉识别与动作核心
  │       ├── cli.py     # 命令行入口
  │       └── platform_mgr.py # 平台适配 (Ctrl vs Cmd)
  └── ...
```

## 准备工作 (至关重要!)

由于是基于“所见即所得”的图像识别，你必须**在你的电脑上截取并保存**以下图标到 `wechat/assets/mac/` (或 `win/`) 目录下。

**文件名必须严格一致 (PNG格式):**

1.  `like_empty.png`: 未点赞时的爱心图标 (通常是空心或白色)。
2.  `like_filled.png`: 已点赞时的爱心图标 (红色，用于跳过)。
3.  `comment_icon.png`: 视频右侧的评论气泡图标 (用于展开侧边栏)。
4.  `comment_input.png`: 评论输入框的特征区域 (如灰色的“写评论...”文字区域)。
5.  `send_btn.png`: 评论输入框旁边的“发送”按钮。

**截图技巧:**
*   截图范围不要太大，只截取图标本身和少量背景。
*   保持截图时的微信窗口大小与运行时一致（避免图标缩放）。
*   Mac 用户：推荐使用 `Cmd+Shift+4` 截图。

## 安装

```bash
cd wechat
pip install -r requirements.txt
```

## 运行

1.  打开微信电脑版，进入视频号窗口。
2.  在终端运行：

```bash
# 测试图片识别 (调试模式)
python -m src.wechat_client.cli --mode test_assets

# 开始自动刷视频 (默认模式)
python -m src.wechat_client.cli --count 20
```

3.  **迅速切换回微信视频号窗口**，不要遮挡。

## Mac 权限说明

首次运行时，macOS 会弹窗请求权限，请务必在“系统设置 -> 隐私与安全性”中授予 Terminal (或 Cursor/VSCode) 以下权限：
*   **屏幕录制 (Screen Recording)**: 用于截图识别。
*   **辅助功能 (Accessibility)**: 用于控制鼠标点击。

如果没有授权，程序将报错或无法点击。
