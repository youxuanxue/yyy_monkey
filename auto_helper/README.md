# YouTube Shorts Helper

Chrome 浏览器扩展插件，用于在浏览 YouTube Shorts 时自动执行互动操作（点赞、订阅、评论）。
基于本地 LLM (Ollama) 或 OpenAI API 进行智能内容分析和决策。

## ✨ 功能特性

- **自动检测**: 自动识别 Shorts 视频切换。
- **智能分析**: 提取视频标题，发送给 LLM 进行内容分析和决策。
- **自动互动**:
    - 根据 LLM 判断自动订阅频道。
    - 自动点赞优质视频。
    - 生成自然、友好的评论并自动发送。
- **自动刷视频**: 互动完成后自动划走，无需手动操作，实现全自动挂机。
- **安全机制**:
    - 每日互动次数限制。
    - 避免重复互动。
    - 低置信度跳过。
    - 随机延时模拟真人操作。
- **UI 提示**: 在页面右上角实时显示分析状态和决策结果。

## 🛠️ 安装指南

### 前置要求
1. **Google Chrome** (版本 88+)
2. **LLM 服务** (推荐 Ollama)
   - 安装 [Ollama](https://ollama.com/)
   - 拉取模型: `ollama pull qwen2.5:3b` (或其他模型)

### 关键配置：启用 CORS (重要！)

Ollama 默认不允许浏览器插件跨域访问。你需要带环境变量启动 Ollama：

```bash
# 停止已有的 Ollama 服务
pkill ollama

# 带 CORS 环境变量启动
OLLAMA_ORIGINS="*" ollama serve
```

> **注意**: 保持这个终端窗口打开，或者配置系统环境变量使其永久生效。

### 安装插件
1. 下载本项目代码。
2. 打开 Chrome 浏览器，访问 `chrome://extensions/`。
3. 开启右上角的 **"开发者模式"**。
4. 点击左上角的 **"加载已解压的扩展程序"**。
5. 选择本项目中的 `auto_helper/extension` 目录。

## ⚙️ 配置说明

### 1. 插件配置
点击插件图标 -> "⚙️ 设置"，进入配置页面。

- **LLM 配置**:
    - `API Base URL`: 默认 `http://localhost:11434/v1` (Ollama)
    - `API Key`: Ollama 随意填写 (如 `ollama`)，OpenAI 需填写真实 Key。
    - `Model`: 填写你运行的模型名称 (如 `qwen2.5:3b`)。
    - 点击 **"测试连接"** 确保配置正确。

- **安全设置**:
    - `每日最大互动数`: 建议设置在 30-50 之间，避免被 YouTube 风控。
    - `跳过已互动`: 开启后，不会对同一个视频重复互动。

### 2. 启动使用
1. 确保 Ollama 已正确启动（带 `OLLAMA_ORIGINS="*"`）。
2. 打开 [YouTube Shorts](https://www.youtube.com/shorts)。
3. 点击插件图标，确保 **"自动模式"** 开关已打开。
4. 开始刷视频！
    - 当你切换到一个新视频时，插件会自动开始分析。
    - 页面右上角会出现状态提示框。
    - 如果 LLM 认为值得互动，插件会自动点赞、订阅或评论。
    - 互动完成后，插件会自动划到下一个视频（5-25秒随机延时）。
    - 如果 LLM 决定跳过，也会自动划到下一个视频（3-6秒随机延时）。

## 📁 项目结构

```
auto_helper/
├── extension/               # 插件源码
│   ├── manifest.json        # 配置文件
│   ├── background/          # 后台服务 (LLM调用, 状态管理)
│   ├── content/             # 页面脚本 (信息提取, 互动执行, UI)
│   ├── popup/               # 弹出界面
│   ├── options/             # 设置页面
│   ├── utils/               # 工具函数
│   └── config/              # LLM Prompt 配置
└── README.md                # 本文档
```

## 🔧 调试方法

- **网页端日志**: 在 YouTube Shorts 页面按 `F12`，查看 Console，筛选 `[Content]` 或 `[Interactor]`。
- **后台日志**: 在 `chrome://extensions/` 找到插件，点击 "Service Worker" 链接，查看 Console。

## ⚠️ 注意事项

- **账号安全**: 建议使用小号测试，或严格控制每日互动数量。虽然模拟了真人操作，但自动化行为仍有被平台检测的风险。
- **评论内容**: LLM 生成的评论通常比较通用，但偶尔可能不准确。可以在 `config/llm_prompt.json` 中调整 Prompt。
- **CORS 问题**: 如果测试连接显示 "403" 或 "连接失败"，请确保 Ollama 使用 `OLLAMA_ORIGINS="*"` 启动。
- **刷新插件**: 修改代码后，需要在 `chrome://extensions/` 刷新插件，并刷新 YouTube 页面。

## 🤝 贡献与反馈

欢迎提交 Issue 或 PR 改进功能！
