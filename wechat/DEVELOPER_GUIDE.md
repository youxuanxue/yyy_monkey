# WeChat Client 开发者入门手册

## 📋 目录

1. [项目概述](#项目概述)
2. [代码结构](#代码结构)
3. [核心模块详解](#核心模块详解)
4. [工作流程](#工作流程)
5. [配置说明](#配置说明)
6. [使用指南](#使用指南)
7. [开发指南](#开发指南)
8. [常见问题](#常见问题)

---

## 项目概述

### 功能简介

WeChat Client 是一个基于图像识别和 AI 大模型的微信视频号自动化互动工具，主要功能包括：

- ✅ **自动点赞**：识别视频并自动点赞
- ✅ **智能评论**：使用大模型根据视频话题生成个性化评论
- ✅ **自动刷视频**：模拟滚轮操作切换到下一个视频
- ✅ **OCR 识别**：识别视频描述文本，理解视频内容
- ✅ **跨平台支持**：支持 macOS 和 Windows

### 技术栈

- **图像识别**：PyAutoGUI + OpenCV
- **OCR 识别**：CnOCR
- **AI 大模型**：OpenAI API（兼容 Ollama 本地模型）
- **自动化**：pyautogui, pyperclip
- **包管理**：uv

---

## 代码结构

```
wechat/
├── src/wechat_client/          # 核心源代码
│   ├── __init__.py             # 包初始化
│   ├── cli.py                  # 命令行入口，主程序逻辑
│   ├── core.py                 # 核心功能：图像识别、OCR、操作控制
│   ├── llm_client.py           # 大模型客户端：评论生成、Ollama 管理
│   ├── platform_mgr.py         # 平台管理器：跨平台适配（Mac/Windows）
│   ├── adapter.py              # 平台适配器（旧版，已整合到 platform_mgr）
│   ├── controller.py           # UI 控制器（旧版，功能已整合到 core）
│   └── license.py              # License 验证
│
├── assets/                      # UI 图像资源（用于图像匹配）
│   ├── mac/                    # macOS 平台资源
│   │   ├── like_empty.png      # 未点赞图标
│   │   ├── like_filled.png     # 已点赞图标
│   │   ├── comment_icon.png    # 评论图标
│   │   ├── comment_input.png   # 评论输入框
│   │   ├── send_btn.png        # 发送按钮
│   │   └── follow_btn.png      # 关注按钮
│   └── win/                    # Windows 平台资源（同上）
│
├── data/                        # 数据文件
│   ├── comments_default.txt     # 默认评论库（降级使用）
│   ├── comments_education.txt  # 教育话题评论库（已废弃）
│   ├── comments_parenting.txt  # 亲子话题评论库（已废弃）
│   └── topic_config.json        # 话题配置（已废弃）
│
├── scripts/                     # 工具脚本
│   └── gen_license.py          # License 生成工具
│
├── tests/                       # 测试文件
│   └── test_llm_client.py      # LLM 客户端测试
│
├── pyproject.toml               # 项目配置和依赖
├── README.md                    # 项目说明
└── README_DEPLOY.md             # 部署指南
```

---

## 核心模块详解

### 1. `cli.py` - 命令行入口

**职责**：程序入口，主循环逻辑

**主要功能**：
- 解析命令行参数
- 初始化 BotCore
- 主循环：获取话题 → 点赞 → 评论 → 滑动

**关键代码**：
```python
def main() -> None:
    # 1. 校验 License
    verify_license()
    
    # 2. 初始化 BotCore
    bot = BotCore(asset_dir, pm)
    
    # 3. 主循环
    while liked_count < max_likes:
        topic_text = bot.get_video_topic()  # OCR 识别话题
        # 点赞（固定概率 0.7）
        if random.random() < 0.7:
            bot.like_current()
            # 评论（70% 概率）
            if random.random() < 0.7:
                txt = bot.generate_comment_with_llm(topic_text)
                bot.send_comment(txt)
        bot.scroll_next()  # 滑动下一个
```

---

### 2. `core.py` - 核心功能模块

**职责**：图像识别、OCR、UI 操作

**主要类**：`BotCore`

**核心方法**：

| 方法 | 功能 | 说明 |
|------|------|------|
| `get_video_topic()` | OCR 识别视频话题 | 定位描述区域，使用 CnOCR 识别文本 |
| `like_current()` | 点赞当前视频 | 识别 `like_empty.png` 并点击 |
| `send_comment(text)` | 发送评论 | 定位输入框 → 粘贴文本 → 发送 |
| `scroll_next()` | 滑动下一个视频 | 模拟滚轮向下滚动 |
| `generate_comment_with_llm()` | 生成评论 | 调用 LLM 客户端生成评论 |

**图像识别流程**：
1. 使用 `_locate_bounds()` 定位 UI 元素（返回坐标框）
2. 使用 `_locate()` 获取元素中心点坐标
3. 使用 `_click_at()` 执行点击（带随机偏移，模拟真人）

**OCR 识别流程**：
1. 定位 `follow_btn.png` 和 `comment_icon.png` 作为锚点
2. 计算描述文本区域（在锚点上方）
3. 截图并使用 CnOCR 识别文本

---

### 3. `llm_client.py` - 大模型客户端

**职责**：管理 LLM 服务，生成智能评论

**主要类**：

#### `OllamaServiceManager`
- **功能**：管理 Ollama 本地模型服务
- **方法**：
  - `is_running()`: 检查服务是否运行
  - `ensure_running()`: 确保服务运行（未运行则启动）
  - `cleanup()`: 程序退出时清理服务

#### `LLMCommentGenerator`
- **功能**：使用大模型生成评论
- **方法**：
  - `generate_comment(topic_text)`: 生成评论
    - 根据话题内容自动判断是否需要添加活动邀请
    - 如果话题与教育、育儿、成长相关 → 自然融入 `#小小谋略家`
    - 如果话题不相关 → 只生成普通评论

**支持的模型**：
- **默认**：`qwen2.5:1.5b`（推荐，速度快）
- **高质量**：`qwen2.5:3b`（更高质量，需要更多资源）
- **高质量**：`qwen2.5:7b`（追求质量）

**配置方式**：
```bash
# 使用默认 Ollama（自动启动）
export OLLAMA_MODEL="qwen2.5:1.5b"  # 默认模型
# 或使用更高质量的模型
# export OLLAMA_MODEL="qwen2.5:3b"

# 使用其他服务
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.example.com/v1"
export OPENAI_MODEL="gpt-3.5-turbo"
```

---

### 4. `platform_mgr.py` - 平台管理器

**职责**：跨平台适配（Mac/Windows）

**主要功能**：
- 检测操作系统类型
- 自动检测屏幕缩放因子（Retina 屏处理）
- 提供跨平台的快捷键操作：
  - `copy_text()`: 复制到剪贴板
  - `paste()`: 粘贴（Mac: Cmd+V, Win: Ctrl+V）
  - `select_all()`: 全选（Mac: Cmd+A, Win: Ctrl+A）
  - `enter()`: 回车
- 返回平台资源目录名（`mac` 或 `win`）

---

### 5. `license.py` - License 验证

**职责**：验证程序 License，控制使用期限

**验证流程**：
1. 读取 `license.lic` 文件
2. Base64 解码
3. 验证 HMAC-SHA256 签名
4. 检查是否过期

**生成 License**：
```bash
python scripts/gen_license.py --days 30
```

---

## 工作流程

### 完整执行流程

```
启动程序
  ↓
验证 License
  ↓
初始化 BotCore
  ├─ 初始化 LLMCommentGenerator
  │   ├─ 检查 Ollama 服务（如未运行则启动）
  │   └─ 初始化 OpenAI 客户端
  └─ 加载资源路径
  ↓
主循环开始
  ↓
获取视频话题（OCR）
  ├─ 定位 follow_btn 和 comment_icon
  ├─ 计算描述文本区域
  ├─ 截图
  └─ CnOCR 识别文本
  ↓
决定是否点赞（70% 概率）
  ├─ 是 → 点赞
  │   ├─ 定位 like_empty.png
  │   └─ 点击
  │   ↓
  │   决定是否评论（70% 概率）
  │   ├─ 是 → 生成评论
  │   │   ├─ 调用 LLM 生成评论
  │   │   │   ├─ 模型判断话题相关性
  │   │   │   └─ 决定是否包含活动邀请
  │   │   ├─ 如果失败 → 使用默认评论库
  │   │   └─ 发送评论
  │   └─ 否 → 跳过
  └─ 否 → 跳过
  ↓
滑动下一个视频
  ↓
重复循环（直到达到 max_likes）
  ↓
程序退出
  └─ 清理 Ollama 服务（如果由程序启动）
```

---

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `OLLAMA_MODEL` | Ollama 模型名称 | `qwen2.5:1.5b` | `qwen2.5:3b`（更高质量） |
| `OPENAI_API_KEY` | OpenAI API Key | `ollama` | `sk-xxx...` |
| `OPENAI_BASE_URL` | API 基础 URL | `http://localhost:11434/v1` | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | 根据 base_url 自动判断 | `gpt-3.5-turbo` |

### 命令行参数

```bash
python src/wechat_client/cli.py [选项]

选项：
  --mode {run,test_assets}  模式（默认：run）
                            - run: 正常运行
                            - test_assets: 测试资源识别
  
  --max-likes N             点赞总数上限（默认：10）
  
  --interval N              操作间隔秒数（默认：5.0）
```

### 资源文件

**图像资源位置**：
- macOS: `assets/mac/*.png`
- Windows: `assets/win/*.png`

**必需资源**：
- `like_empty.png` - 未点赞图标
- `like_filled.png` - 已点赞图标
- `comment_icon.png` - 评论图标
- `comment_input.png` - 评论输入框
- `send_btn.png` - 发送按钮
- `follow_btn.png` - 关注按钮（OCR 锚点）

---

## 使用指南

### 快速开始

#### 1. 安装依赖

```bash
cd wechat
uv sync
```

#### 2. 安装 Ollama（如使用本地模型）

```bash
# macOS
brew install ollama

# 下载模型
ollama pull qwen2.5:1.5b
```

#### 3. 生成 License

```bash
python scripts/gen_license.py --days 30
```

#### 4. 运行程序

```bash
# 使用默认配置（自动启动 Ollama）
python src/wechat_client/cli.py --max-likes 10

# 测试资源识别
python src/wechat_client/cli.py --mode test_assets
```

### 测试 LLM 评论生成

```bash
# 运行测试
python test_llm_client.py

# 或使用测试目录
python tests/test_llm_client.py
```

---

## 开发指南

### 添加新功能

#### 1. 添加新的 UI 操作

在 `core.py` 的 `BotCore` 类中添加方法：

```python
def new_action(self) -> bool:
    """新操作"""
    pos = self._locate("new_icon.png")
    if pos:
        self._click_at(pos[0], pos[1])
        return True
    return False
```

#### 2. 修改评论生成逻辑

编辑 `llm_client.py` 中的 `generate_comment()` 方法，修改提示词或逻辑。

#### 3. 添加新的平台支持

在 `platform_mgr.py` 中添加平台检测和适配逻辑。

### 调试技巧

#### 1. 测试资源识别

```bash
python src/wechat_client/cli.py --mode test_assets
```

#### 2. 查看日志

程序会输出详细日志，包括：
- OCR 识别结果
- 图像定位结果
- LLM 生成过程
- 操作执行状态

#### 3. 调试 OCR

如果 OCR 识别不准确，可以：
- 调整 `get_video_topic()` 中的区域计算
- 检查截图保存位置（代码中可添加保存截图逻辑）

### 代码规范

- 使用类型提示（Type Hints）
- 遵循 PEP 8 代码风格
- 添加详细的文档字符串
- 使用中文注释和日志

---

## 常见问题

### Q1: 图像识别失败

**原因**：
- 截图与当前屏幕分辨率不匹配
- UI 元素位置变化
- 资源文件路径错误

**解决**：
1. 重新截图并覆盖 `assets/` 目录下的图片
2. 检查 `platform_mgr.py` 中的缩放因子是否正确
3. 运行 `--mode test_assets` 测试识别率

### Q2: LLM 评论生成失败

**原因**：
- Ollama 服务未运行
- 模型未下载
- API 配置错误

**解决**：
1. 检查 Ollama 服务：程序会自动启动和管理 Ollama 服务，无需手动操作
2. 下载模型：`ollama pull qwen2.5:1.5b`（如果模型未下载）
3. 检查环境变量配置
4. 手动检查服务状态：`curl http://localhost:11434/api/tags`

### Q3: OCR 识别不准确

**原因**：
- 描述区域定位不准确
- 文字太小或模糊
- 背景干扰

**解决**：
1. 调整 `get_video_topic()` 中的区域计算参数
2. 检查锚点图标是否正确识别
3. 可以保存截图进行调试

### Q4: 程序运行缓慢

**原因**：
- 图像识别耗时
- LLM 生成评论耗时
- 网络延迟（如果使用远程 API）

**解决**：
1. 使用本地 Ollama 模型（推荐）
2. 默认已使用较小的模型（`qwen2.5:1.5b`），如需更高质量可使用 `qwen2.5:3b`
3. 减少操作间隔（但要注意避免被检测）

---

## 关键设计决策

### 1. 为什么使用图像识别而不是 API？

- 微信 PC 端没有公开 API
- 图像识别更稳定，不受 UI 更新影响
- 可以模拟真实用户行为

### 2. 为什么移除话题匹配逻辑？

- 大模型已经能够理解话题语义
- 减少代码复杂度
- 移除大型依赖（sentence-transformers）
- 更灵活，适应更多场景

### 3. 为什么使用 Ollama 而不是直接调用 API？

- 本地运行，无需 API Key
- 数据隐私更好
- 成本更低
- 支持离线使用

### 4. 为什么使用固定点赞概率？

- 简化逻辑
- 大模型已经能够生成智能评论
- 可以根据需要调整概率值

---

## 文件依赖关系

```
cli.py
  ├─ core.py (BotCore)
  │   ├─ platform_mgr.py (PlatformManager)
  │   └─ llm_client.py (LLMCommentGenerator)
  │       └─ llm_client.py (OllamaServiceManager)
  └─ license.py (verify_license)
```

---

## 扩展建议

### 未来可能的改进

1. **配置化**：将点赞概率、评论概率等参数提取到配置文件
2. **多模型支持**：支持同时使用多个 LLM 服务
3. **评论质量评估**：添加评论质量评分机制
4. **统计分析**：记录点赞、评论数据，生成统计报告
5. **GUI 界面**：开发图形界面，方便非技术用户使用

---

## 维护说明

### 定期检查项

1. **资源文件**：如果微信 UI 更新，需要重新截图
2. **依赖更新**：定期更新依赖包版本
3. **模型更新**：关注 Ollama 模型更新，使用更好的模型
4. **License**：定期更新 License 文件

### 代码修改记录

- **移除话题匹配**：已移除 `get_topic_match()` 和 sentence-transformers 依赖
- **添加 LLM 支持**：新增 `llm_client.py` 模块
- **自动管理 Ollama**：程序自动启动和管理 Ollama 服务

---

## 联系与支持

如有问题，请检查：
1. 日志输出
2. 测试模式运行结果
3. 环境配置是否正确

---

## API 参考

### BotCore 类

#### 初始化
```python
bot = BotCore(asset_dir: Path, pm: PlatformManager)
```

#### 主要方法

**`get_video_topic() -> Optional[str]`**
- 功能：OCR 识别视频话题文本
- 返回：识别到的文本，失败返回 None
- 依赖：需要 `follow_btn.png` 和 `comment_icon.png` 作为锚点

**`like_current() -> bool`**
- 功能：点赞当前视频
- 返回：成功返回 True，失败返回 False
- 逻辑：如果已点赞则跳过，否则点击 `like_empty.png`

**`send_comment(text: str) -> bool`**
- 功能：发送评论
- 参数：`text` - 要发送的评论文本
- 流程：定位输入框 → 点击 → 粘贴文本 → 发送

**`scroll_next() -> None`**
- 功能：滑动到下一个视频
- 逻辑：模拟滚轮向下滚动

**`generate_comment_with_llm(topic_text: str) -> Optional[str]`**
- 功能：使用大模型生成评论
- 参数：`topic_text` - 视频话题文本
- 返回：生成的评论文本，失败返回 None

### LLMCommentGenerator 类

#### 初始化
```python
generator = LLMCommentGenerator()
# 自动检测并启动 Ollama（如需要）
```

#### 主要方法

**`is_available() -> bool`**
- 功能：检查 LLM 客户端是否可用
- 返回：可用返回 True

**`generate_comment(topic_text: str, activity_tag: str = "#小小谋略家") -> Optional[str]`**
- 功能：生成评论
- 参数：
  - `topic_text`: 视频话题文本
  - `activity_tag`: 活动标签（默认 "#小小谋略家"）
- 返回：生成的评论文本

### PlatformManager 类

#### 主要方法

**`copy_text(text: str) -> None`**
- 功能：复制文本到剪贴板

**`paste() -> None`**
- 功能：模拟粘贴快捷键

**`select_all() -> None`**
- 功能：模拟全选快捷键

**`enter() -> None`**
- 功能：模拟回车键

**`get_asset_dir_name() -> str`**
- 功能：返回平台资源目录名（"mac" 或 "win"）

---

## 代码流程图

### 主程序流程

```
┌─────────────────┐
│  启动程序       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 验证 License    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 初始化 BotCore  │
│  ├─ PlatformMgr │
│  └─ LLMClient   │
│     └─ 启动     │
│        Ollama   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   主循环开始    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ OCR 识别话题    │
│ (get_video_topic)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 决定是否点赞    │
│ (70% 概率)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
   是         否
    │         │
    ▼         ▼
┌─────────┐ ┌─────────┐
│ 执行点赞│ │ 跳过    │
└────┬────┘ └────┬────┘
     │            │
     │            │
     ▼            │
┌─────────┐      │
│决定评论  │      │
│(70%概率) │      │
└────┬────┘      │
     │            │
  ┌──┴──┐         │
  是    否         │
  │     │         │
  ▼     ▼         ▼
┌────┐ ┌────┐ ┌──────┐
│生成│ │跳过│ │滑动下│
│评论│ │    │ │一个  │
└─┬──┘ └─┬──┘ └───┬──┘
  │      │        │
  │      │        │
  └──────┴────────┘
         │
         ▼
┌─────────────────┐
│  达到上限？     │
└────┬────────────┘
     │
  否 │ 是
     │
     ▼
┌─────────────────┐
│   继续循环      │
└─────────────────┘
```

### LLM 评论生成流程

```
┌─────────────────┐
│ generate_comment│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 检查客户端可用  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 构建提示词      │
│ - system_prompt │
│ - user_prompt   │
│   (包含话题)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 调用 LLM API    │
│ (OpenAI 兼容)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 获取生成结果    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 记录日志        │
│ (是否包含活动)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 返回评论文本    │
└─────────────────┘
```

---

## 数据流

### 评论生成数据流

```
视频话题文本 (OCR)
    ↓
LLMCommentGenerator.generate_comment()
    ↓
构建提示词
    ├─ system_prompt: 角色和规则定义
    └─ user_prompt: 话题内容 + 活动邀请判断指令
    ↓
OpenAI API / Ollama API
    ↓
模型生成评论
    ├─ 判断话题相关性
    ├─ 决定是否包含活动邀请
    └─ 生成自然评论
    ↓
返回评论文本
    ↓
发送到微信
```

---

## 关键配置参数

### core.py 中的配置

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `confidence` | `BotCore.__init__` | 0.85 | 图像匹配置信度 |
| `pyautogui.PAUSE` | 全局 | 0.5 | 操作间隔（秒） |
| `pyautogui.FAILSAFE` | 全局 | True | 安全模式（鼠标到角落退出） |

### llm_client.py 中的配置

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `max_wait` | `ensure_running()` | 10 | Ollama 启动等待时间（秒） |
| `wait_interval` | `ensure_running()` | 0.5 | 检查间隔（秒） |
| `temperature` | `generate_comment()` | 0.8 | LLM 生成温度 |
| `max_tokens` | `generate_comment()` | 150 | 最大生成 token 数 |

### cli.py 中的配置

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `like_prob` | 主循环 | 0.7 | 点赞概率 |
| `comment_prob` | 主循环 | 0.7 | 评论概率（在点赞后） |
| `watch_time_before_like` | 主循环 | 2.0-6.0 | 点赞前观看时间（秒） |
| `watch_time_before_comment` | 主循环 | 1.0-4.0 | 评论前观看时间（秒） |
| `watch_time_after_like` | 主循环 | 3.0-20.0 | 点赞后观看时间（秒） |

---

## 测试指南

### 运行测试

```bash
# 测试 LLM 评论生成
python test_llm_client.py

# 或使用测试目录
python tests/test_llm_client.py
```

### 测试资源识别

```bash
python src/wechat_client/cli.py --mode test_assets
```

这会测试所有资源文件是否能正确识别。

---

## 故障排查清单

### 问题：图像识别失败

**检查项**：
- [ ] 资源文件是否存在：`assets/{platform}/*.png`
- [ ] 截图是否与当前屏幕分辨率匹配
- [ ] 微信窗口是否在前台
- [ ] 缩放因子是否正确（查看日志中的 "Screen Scale Factor"）

**调试方法**：
```bash
# 运行测试模式
python src/wechat_client/cli.py --mode test_assets
```

### 问题：OCR 识别失败

**检查项**：
- [ ] `follow_btn.png` 和 `comment_icon.png` 是否能识别
- [ ] 描述文本区域计算是否正确
- [ ] CnOCR 是否已安装

**调试方法**：
- 在 `get_video_topic()` 中添加截图保存逻辑
- 检查截图区域是否正确

### 问题：LLM 生成失败

**检查项**：
- [ ] Ollama 服务是否运行：程序会自动启动，或手动检查 `curl http://localhost:11434/api/tags`
- [ ] 模型是否已下载：`ollama list`
- [ ] 环境变量是否正确设置
- [ ] 网络连接是否正常（如使用远程 API）

**调试方法**：
```bash
# 检查 Ollama 状态（程序会自动管理，也可手动检查）
curl http://localhost:11434/api/tags

# 测试模型
ollama run qwen2.5:1.5b "你好"

# 查看程序日志（会显示 Ollama 服务的启动和管理信息）
```

---

## 版本历史

### v0.1.0 (当前版本)

**主要特性**：
- ✅ 基于图像识别的自动化操作
- ✅ OCR 视频话题识别
- ✅ 大模型智能评论生成
- ✅ 自动管理 Ollama 服务
- ✅ 跨平台支持（Mac/Windows）
- ✅ License 验证机制

**已移除功能**：
- ❌ 话题匹配逻辑（`get_topic_match`）
- ❌ sentence-transformers 依赖
- ❌ 配置文件话题匹配

**原因**：简化代码，完全依赖大模型的语义理解能力。

---

**最后更新**：2025-12-27

