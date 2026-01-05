# 微信视频号自动互动助手 (WeChat Auto Like)

基于图像识别的微信视频号 PC 端自动化工具，用于模拟人工操作进行视频互动。

## 功能特点

- **自动点赞**：识别并点击点赞图标
- **智能评论**：使用 AI 大模型根据视频话题自动生成个性化评论
- **自动关注**：根据评分自动关注优质创作者
- **智能互动策略**：根据 LLM 评分自动决策点赞/关注/评论策略
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

- `--mode {run,test_assets}`: 模式选择（默认：run）
  - `run`: 正常运行
  - `test_assets`: 测试资源识别
- `--max-interactions N`: 互动动作总数上限（默认：17）

## Windows 打包部署

1. **生成 License**：`python wechat/scripts/gen_license.py --days 3`

2. **执行打包**：
   - 进入 `wechat` 目录
   - 确保 `license.lic` 文件已存在
   - 双击运行 `build_exe.bat`

3. **打包结果**：在 `wechat/dist/` 目录下生成 `WeChatAutoLike` 文件夹

4. **运行**：双击运行 `dist/WeChatAutoLike/WeChatAutoLike.exe`

**分发文件**：打包整个 `WeChatAutoLike` 文件夹，包含：
- `WeChatAutoLike.exe`: 主程序
- `license.lic`: 许可证文件
- `assets/`: 图像识别资源库（必须保留）
- `config/`: 配置文件目录

## 常见问题

### Q1: 图像识别失败

**解决**：
1. 重新截图并覆盖 `assets/` 目录下的图片
2. 运行 `--mode test_assets` 测试识别率
3. 确保系统缩放比例为 100%

### Q2: LLM 评论生成失败

**解决**：
1. 检查 Ollama 服务：程序会自动启动，无需手动操作
2. 下载模型：`ollama pull qwen2.5:1.5b`
3. 检查环境变量配置

### Q3: 识别失败/鼠标乱点

**解决**：
1. 确保微信视频号窗口没有被遮挡
2. 确保系统缩放比例为 100%
3. 检查 `assets/` 下的截图是否与当前微信版本图标一致

## 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。
