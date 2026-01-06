# 抖音网页端智能互动助手 (Douyin Auto Like)

这是一个基于 Python + Selenium 的抖音网页端自动化工具，使用 **LLM 智能评分**进行视频互动决策，支持自动点赞和评论。支持 Windows 本地一键打包部署。

## 功能特点

1. **智能互动决策**：基于 LLM 评分自动决定是否点赞和评论
   - `persona_consistency_score < 0.8` 或 `real_human_score < 0.8` → 跳过互动
   - 其他情况 → 点赞 + 评论

2. **AI 评论生成**：使用大语言模型（LLM）根据视频内容自动生成个性化评论
   - 支持本地 Ollama 模型（推荐 qwen2.5:3b）
   - 支持 OpenAI API
   - 基于 `config/task_prompt.json` 配置角色和提示词

3. **自动点赞**：双击视频区域点赞，智能模拟真人观看时长

4. **模拟真人**：
   - 随机观看时长（不看完、中途划走）
   - 根据视频时长智能调整观看时间
   - 操作间隔随机化

5. **Follow 模式**：全自动刷视频模式，监控页面 URL 变化，对新视频执行智能互动策略，自动划走

6. **安全验证处理**：自动检测验证码弹窗并暂停，提示人工介入处理

## 目录结构

```
douyin/
├── config/                  # 配置文件目录
│   └── task_prompt.json     # LLM 评论生成任务配置
├── dist/                    # 打包后的可执行文件目录 (构建后生成)
├── logs/                    # 运行日志
├── src/                     # 源代码
│   └── douyin_auto_like/
│       ├── cli.py           # 入口与主逻辑
│       ├── douyin.py        # 页面交互逻辑封装
│       ├── browser.py       # 浏览器驱动封装
│       └── license.py       # License 验证
├── scripts/                 # 工具脚本
│   └── gen_license.py       # License 生成脚本
├── build_exe.bat            # Windows 一键打包脚本
├── douyin_bot.spec          # PyInstaller 打包配置
├── pyproject.toml           # 项目配置（使用 uv）
├── requirements.txt         # 依赖列表
├── license.lic              # License 文件
└── README.md                # 本文档
```

## 快速开始

### 1. 环境准备

- Python >= 3.10
- Google Chrome 浏览器
- `uv` 包管理器（推荐）或 `pip`
- Ollama（推荐，用于本地 LLM）或 OpenAI API Key

### 2. 安装依赖

```bash
cd douyin
# 使用 uv（推荐）
uv sync
# 或者使用 pip
pip install -r requirements.txt
```

### 3. 配置 LLM（必需）

#### 方式一：使用 Ollama（推荐，本地运行）

1. 安装 Ollama：访问 https://ollama.ai 下载安装
2. 下载模型：
   ```bash
   ollama pull qwen2.5:3b
   ```
3. 程序会自动启动和管理 Ollama 服务

#### 方式二：使用 OpenAI API

设置环境变量：
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选，默认使用 Ollama
```

### 4. 配置任务提示词（可选）

编辑 `config/task_prompt.json` 自定义角色和提示词。默认支持：
- `yi_ba`：懿爸角色（35岁二孩父亲）
- `yi_ma`：懿妈角色（细腻温和的二孩妈妈）

### 5. 生成 License

```bash
python scripts/gen_license.py --days 30
```

### 6. 运行

```bash
# 启动智能互动模式（推荐首次使用时开启 --manual-login 手动登录）
python src/douyin_auto_like/cli.py \
    --video-url "https://www.douyin.com/jingxuan?modal_id=7577987307542720243" \
    --max-interactions 17 \
    --manual-login

# 调试模式（仅打开浏览器，不执行自动化）
python src/douyin_auto_like/cli.py --mode open --video-url "..."

# 查看帮助
python src/douyin_auto_like/cli.py --help
```

## 命令行参数

### 必需参数

- `--video-url`: 起始视频链接（默认：精选页面）

### 可选参数

- `--mode`: 运行模式
  - `follow`（默认）：智能互动模式（基于 LLM 评分）
  - `open`：调试模式（仅打开浏览器，不执行自动化）

- `--max-interactions`: 互动动作总数上限（默认：17，达到后退出）

- `--manual-login`: 启动后暂停，等待用户手动操作（如扫码登录，**推荐首次使用开启**）

- `--profile-dir`: 指定 Chrome Profile 目录，默认为项目下的 `.chrome_profile`

- `--verbose`: 输出详细调试日志

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OLLAMA_MODEL` | Ollama 模型名称 | `qwen2.5:3b` |
| `OPENAI_API_KEY` | OpenAI API Key | `ollama` |
| `OPENAI_BASE_URL` | API 基础 URL | `http://localhost:11434/v1` |
| `OPENAI_MODEL` | OpenAI 模型名称 | `qwen2.5:3b` (Ollama) 或 `gpt-3.5-turbo` (OpenAI) |

## 智能互动策略

程序会根据 LLM 生成的评分自动决定互动策略：

1. **评分不达标**（`persona_consistency_score < 0.8` 或 `real_human_score < 0.8`）
   - 跳过互动，直接滑走
   - 避免生成低质量或不合适的评论

2. **评分正常**
   - 点赞 + 评论
   - 评论内容由 LLM 根据视频描述和角色设定生成

## 配置说明

### task_prompt.json

配置文件位于 `config/task_prompt.json`，用于配置 LLM 评论生成任务的提示词模板和角色设定。

**支持角色：**
- `yi_ba`：懿爸，35岁二孩父亲，说话克制、真实
- `yi_ma`：懿妈，细腻温和的二孩妈妈，重感受和细节

**配置结构：**
```json
{
  "task_comment_generation": {
    "yi_ba": {
      "system_prompt": "...",
      "user_prompt": "..."
    }
  }
}
```

## Windows 打包部署

### 准备工作

#### 系统要求
- Windows 10 或 Windows 11
- 已安装 Python 3.10 或更高版本
- 已安装 Google Chrome 浏览器
- Ollama（推荐，用于本地 LLM）或 OpenAI API Key

#### LLM 配置

程序需要 LLM 支持才能生成智能评论。有两种方式：

**方式一：使用 Ollama（推荐）**

1. 安装 Ollama：访问 https://ollama.ai 下载安装
2. 下载模型：
   ```bash
   ollama pull qwen2.5:3b
   ```
3. 程序会自动启动和管理 Ollama 服务

**方式二：使用 OpenAI API**

设置环境变量（打包后需要在系统环境变量中设置）：
- `OPENAI_API_KEY`: 你的 API Key
- `OPENAI_BASE_URL`: API 地址（可选，默认使用 Ollama）

#### 配置文件

确保 `config/task_prompt.json` 文件存在且配置正确。该文件用于配置 LLM 评论生成的角色和提示词。

#### 许可证生成 (License)

项目引入了简单的 License 验证机制。分发给用户前，需要生成 `license.lic` 文件。

```bash
# 生成一个有效期为 3 天的 license
python scripts/gen_license.py --days 3

# 或者生成 30 天
python scripts/gen_license.py --days 30
```

生成的 `license.lic` 文件会默认放在 `douyin/` 根目录下。
**注意**：`license.lic` 必须存在且在有效期内，程序才能运行。

### 打包为 Windows 可执行程序 (exe)

本项目已提供一键打包脚本 `build_exe.bat`。

1. 进入 `douyin` 目录。
2. 确保 `license.lic` 文件已生成并存在于当前目录（它会被打包进去，或者你可以选择不打包让用户手动放置，当前配置默认会将根目录的 license.lic 打包进去作为默认试用）。
3. 双击运行 `build_exe.bat`。
   - 该脚本会自动创建虚拟环境、安装依赖、并执行 PyInstaller 打包。
4. 等待脚本执行完毕。

打包成功后，会在 `douyin/dist/` 目录下生成一个名为 `DouyinAutoLike` 的文件夹。

### 运行与分发

#### 文件结构

分发给用户时，请打包整个 `DouyinAutoLike` 文件夹：
- `DouyinAutoLike.exe`: 主程序
- `license.lic`: 许可证文件（如果过期，用户需要向你索要新的文件并替换此文件）
- `config/`: 配置文件目录
  - `task_prompt.json`: LLM 评论生成任务配置
- `logs/`: 程序运行日志
- `.chrome_profile/`: 用户数据目录（自动创建）

#### 用户使用说明

1. **首次运行**：
   - 确保已安装 Chrome 浏览器
   - 如果使用 Ollama，确保已安装并下载模型
   - 如果使用 OpenAI API，设置环境变量 `OPENAI_API_KEY`
   - 运行程序时使用 `--manual-login` 参数手动登录

2. **运行参数**：
   ```bash
   DouyinAutoLike.exe --video-url "..." --max-interactions 17 --manual-login
   ```

## 常见问题

- **浏览器启动失败**: 确保系统安装了 Chrome 浏览器
- **登录状态丢失**: 确保 `.chrome_profile` 目录存在且程序有读写权限
- **LLM 不可用**: 
  - 如果使用 Ollama，确保已安装并下载模型（`ollama pull qwen2.5:3b`）
  - 如果使用 OpenAI API，确保设置了正确的环境变量
- **评论生成失败**: 检查 `config/task_prompt.json` 文件是否存在且格式正确
- **License 过期**: 联系管理员获取新的 `license.lic` 文件并替换

## 注意事项

1. **首次使用**：建议使用 `--manual-login` 参数，手动完成登录后再继续
2. **LLM 配置**：确保 Ollama 已安装并下载模型，或配置 OpenAI API Key
3. **License**：运行前需要生成有效的 License 文件
4. **Chrome Profile**：程序会复用 Chrome Profile，保持登录状态
5. **验证码**：如遇到验证码，程序会自动暂停，等待手动处理

## 与微信版本的差异

- **视频信息获取**：抖音使用 `get_page_info()` 从页面元数据提取，微信使用 OCR 识别
- **互动方式**：抖音专注于点赞和评论，微信支持点赞、评论和关注

## 免责声明

本工具仅供学习和技术研究使用。请勿用于任何商业用途或违反平台规则的行为。使用本工具产生的任何后果由使用者自行承担。

