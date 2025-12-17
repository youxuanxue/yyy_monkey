## 微信视频号自动互动助手 (WeChat Auto Like)

这是一个基于图像识别 (PyAutoGUI + OpenCV) 的微信视频号 PC 端自动化工具，用于模拟人工操作进行视频互动。

### 功能特点

1.  **图像识别定位**：不依赖 DOM 或 API，完全基于屏幕截图匹配 UI 元素（如点赞图标、评论按钮等），抗干扰能力强。
2.  **自动点赞**：识别空心点赞图标并执行点击。
3.  **自动评论**：识别评论输入框，随机发送预设评论。
4.  **自动刷视频**：模拟鼠标滚轮滑动，自动切换到下一个视频。
5.  **模拟真人**：随机观看时长、随机互动概率，避免机械式操作。
6.  **License 验证**：支持生成和验证有时效限制的 License 文件。

### 目录结构

```
wechat/
├── assets/                 # 图像资源库 (用于匹配的 UI 截图)
│   ├── mac/                # macOS 资源
│   └── win/                # Windows 资源
├── data/                   # 数据文件目录
│   └── comments.txt        # 评论库
├── dist/                   # 打包后的可执行文件目录 (构建后生成)
├── src/                    # 源代码
│   ├── wechat_client/      # 核心逻辑
│   └── wechat_auto_like/   # 公共组件 (License等)
├── scripts/                # 工具脚本
│   └── gen_license.py      # License 生成脚本
├── build_exe.bat           # Windows 一键打包脚本
├── wechat_bot.spec         # PyInstaller 打包配置
├── requirements.txt        # 依赖列表
└── README_DEPLOY.md        # 部署与打包指南
```

### 快速开始 (开发环境)

#### 1. 环境准备
- Python >= 3.10
- PC 端微信

#### 2. 安装依赖

```bash
cd wechat
pip install -r requirements.txt
```

#### 3. 资源准备
由于不同分辨率下微信图标可能不同，建议先运行测试模式检查识别率。如果识别失败，需要重新截图覆盖 `assets` 目录下的图片。

#### 4. 生成 License
```bash
python scripts/gen_license.py --days 3
```

#### 5. 运行

```bash
python src/wechat_client/cli.py
```
启动后，程序会倒计时 5 秒。请在倒计时结束前切换到**微信视频号窗口**。

### Windows 打包部署

详情请参考 [README_DEPLOY.md](README_DEPLOY.md)。

简述：
1. 双击运行 `build_exe.bat`。
2. 分发 `dist/WeChatAutoLike` 文件夹。

### 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。
