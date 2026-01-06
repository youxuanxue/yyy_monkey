# YYY Monkey

这是一个针对短视频平台的自动化工具集，包含抖音网页端和微信视频号两个主要模块。两个模块都支持基于 **LLM 智能评分**的自动互动功能。

## 主要模块

### [Douyin Service (抖音网页端自动化)](douyin/README.md)

位于 `douyin/` 目录下。

**功能：**
- 全自动刷视频 (Follow 模式)
- **智能互动决策**（基于 LLM 评分）
- **AI 评论生成**（使用大语言模型）
- 自动点赞
- 模拟真人操作习惯
- 支持 Windows 一键打包部署 (.exe)

**快速开始：**

```bash
cd douyin
python src/douyin_auto_like/cli.py --help
```

### [WeChat Service (微信视频号自动化)](wechat/README.md)

位于 `wechat/` 目录下。

**功能：**
- 图像识别 (PyAutoGUI + OpenCV) 驱动
- 自动刷视频号
- **智能互动决策**（基于 LLM 评分）
- **AI 评论生成**（使用大语言模型）
- 自动点赞与关注
- 支持 Windows 一键打包部署 (.exe)

**快速开始：**

```bash
cd wechat
python src/wechat_client/cli.py --help
```

## 共同特性

### 智能互动系统

两个模块都使用相同的 LLM 客户端（`wechat/src/wechat_client/llm_client.py`），支持：

- **本地模型**：Ollama + qwen2.5:3b（推荐）
- **云端 API**：OpenAI API
- **角色设定**：通过 `task_prompt.json` 配置不同角色（yi_ba、yi_ma）
- **智能评分**：real_human_score、follow_back_score、persona_consistency_score

### 互动策略

两个模块使用相同的互动策略：

- `persona_consistency_score < 0.7` 或 `real_human_score < 0.8` → 只点赞，不评论
- `follow_back_score > 0.8` → 点赞 + 关注 + 评论（仅微信支持关注）
- 其他情况 → 点赞 + 评论

## 项目结构

```
yyy_monkey/
├── douyin/              # 抖音模块
│   ├── config/          # 配置文件
│   │   └── task_prompt.json
│   ├── src/
│   │   └── douyin_auto_like/
│   └── README.md
├── wechat/              # 微信模块
│   ├── config/          # 配置文件
│   │   └── task_prompt.json
│   ├── src/
│   │   └── wechat_client/
│   │       └── llm_client.py  # 共用的 LLM 客户端
│   └── README.md
└── README.md            # 本文件
```

## 环境要求

- Python >= 3.10
- `uv` 包管理器（推荐）或 `pip`
- Google Chrome 浏览器
- Ollama（推荐，用于本地 LLM）或 OpenAI API Key

## 快速开始

1. **安装依赖**：
   ```bash
   # 抖音模块
   cd douyin && uv sync
   
   # 微信模块
   cd wechat && uv sync
   ```

2. **配置 LLM**：
   ```bash
   # 安装 Ollama 并下载模型
   ollama pull qwen2.5:3b
   ```

3. **生成 License**：
   ```bash
   # 抖音
   cd douyin && python scripts/gen_license.py --days 30
   
   # 微信
   cd wechat && python scripts/gen_license.py --days 30
   ```

4. **运行**：
   ```bash
   # 抖音
   cd douyin && python src/douyin_auto_like/cli.py --manual-login
   
   # 微信
   cd wechat && python src/wechat_client/cli.py
   ```

## 许可证

请查看各模块的 License 文件。

## 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。
