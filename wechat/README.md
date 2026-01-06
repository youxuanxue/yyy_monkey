# 微信视频号智能互动助手 (WeChat Auto Like)

基于图像识别的微信视频号 PC 端自动化工具，使用 **LLM 智能评分**进行视频互动决策，支持自动点赞、评论和关注。

## 功能特点

- **智能互动决策**：基于 LLM 评分自动决定是否点赞、关注和评论
- **AI 评论生成**：使用大语言模型（LLM）根据视频话题自动生成个性化评论
- **自动点赞**：识别并点击点赞图标
- **自动关注**：根据评分自动关注优质创作者
- **视频切换检测**：发送评论前验证视频是否已切换，避免误操作
- **模拟真人**：随机观看时长，避免机械式操作
- **本地大模型支持**：支持 Ollama 本地模型，自动管理服务生命周期

## 快速开始

### 环境要求

- Python >= 3.10
- PC 端微信
- `uv` 包管理器

### 安装步骤

1. **安装依赖**：`uv sync`

2. **配置大模型**（推荐使用 Ollama）：
   - 安装 Ollama 并下载模型：`ollama pull qwen2.5:1.5b`
   - 程序会自动启动和管理 Ollama 服务

3. **生成 License**：`python scripts/gen_license.py --days 3`

4. **运行程序**：`python src/wechat_client/cli.py`
   - 启动后倒计时 5 秒，请在倒计时结束前切换到**微信视频号窗口**

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OLLAMA_MODEL` | Ollama 模型名称 | `qwen2.5:1.5b` |
| `OPENAI_API_KEY` | OpenAI API Key | `ollama` |
| `OPENAI_BASE_URL` | API 基础 URL | `http://localhost:11434/v1` |

### task_prompt.json

配置文件位于 `config/task_prompt.json`，用于配置 LLM 评论生成任务的提示词模板和角色设定。

支持角色：`yi_ba`（懿爸）、`yi_ma`（懿妈）

### 智能互动策略

- `persona_consistency_score < 0.7` 或 `real_human_score < 0.8` → 只点赞，不评论
- `follow_back_score > 0.8` → 点赞 + 关注 + 评论
- 其他情况 → 点赞 + 评论（不关注）

## 命令行参数

- `--mode {run,test_assets,test_comments}`: 模式选择（默认：run）
  - `run`: 智能互动模式
  - `test_assets`: 测试资源识别
  - `test_comments`: 测试评论获取
- `--max-interactions`: 互动动作总数上限（默认：17）

## 注意事项

1. **首次使用**：启动后倒计时 5 秒，请在倒计时结束前切换到微信视频号窗口
2. **LLM 配置**：确保 Ollama 已安装并下载模型，或配置 OpenAI API Key
3. **License**：运行前需要生成有效的 License 文件
4. **图像资源**：确保 `assets/` 目录下有所需的图像资源文件

## 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。

