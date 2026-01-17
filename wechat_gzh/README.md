# wechat-gzh

微信公众号（GZH = 公众号）工具集，包含：

1. **API 客户端** - 通过微信公众号官方 API 获取用户信息
2. **自动留言** - 在已关注的公众号文章中自动留言

### 安装依赖

```bash
uv sync
```

### 功能一：获取用户信息

通过微信公众号 API 获取关注用户信息。

#### 配置

在 `.env` 文件中配置：

```
WX_APP_ID=your_app_id
WX_APP_SECRET=your_app_secret
```

#### 使用方法

```bash
uv run python -m wechat_gzh.get_users
```

#### 输出文件

- `users_info.json` - 用户详细信息
- `users_openid.txt` - 用户 OpenID 列表

---

### 功能二：公众号自动留言

自动遍历已关注的微信公众号，在每个公众号的最新文章中留言。

#### 功能特性

- 自动遍历公众号列表
- OCR 识别公众号名称和文章标题
- 随机等待时间（3-10秒），模拟人工操作
- 记录处理历史，避免重复留言
- 支持中断后继续处理
- 详细的日志记录
- **校准配置自动保存**，下次运行可直接使用

#### 前置要求

1. **macOS 系统**
2. **微信桌面客户端**（需要已登录）
3. **辅助功能权限**（系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能）
4. **tesseract OCR 引擎**（`brew install tesseract tesseract-lang`）

#### 使用方法

```bash
# 正常运行（首次需要校准，之后会询问是否使用上次配置）
uv run python -m wechat_gzh.auto_comment

# 跳过校准，直接使用上次保存的配置
uv run python -m wechat_gzh.auto_comment -s
uv run python -m wechat_gzh.auto_comment --skip-calibration

# 强制重新校准（忽略已保存的配置）
uv run python -m wechat_gzh.auto_comment -r
uv run python -m wechat_gzh.auto_comment --recalibrate

# 仅验证校准配置（生成标注截图，不执行自动留言）
uv run python -m wechat_gzh.auto_comment -v
uv run python -m wechat_gzh.auto_comment --verify

# 限制最多处理 10 个公众号
uv run python -m wechat_gzh.auto_comment -n 10
uv run python -m wechat_gzh.auto_comment --max-accounts 10

# 组合使用
uv run python -m wechat_gzh.auto_comment -s -n 5  # 跳过校准，处理 5 个
```

#### 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--skip-calibration` | `-s` | 跳过校准，直接使用上次保存的配置 |
| `--recalibrate` | `-r` | 强制重新校准（忽略已保存的配置） |
| `--verify` | `-v` | 仅验证校准配置（生成标注截图后退出） |
| `--max-accounts N` | `-n N` | 最大处理公众号数量，0 表示不限制 |
| `--debug-screenshot` | | 启用调试截图（保存调试截图和 OCR 区域截图） |

#### 校准验证

每次加载或完成校准后，会自动生成带标注的截图（保存在 `logs/` 目录），标注内容：

- 🔴 **红色点 (1-3)**: 公众号列表中的前3个位置
- 🟢 **绿色点**: 文章点击位置
- 🔵 **蓝色框**: 公众号名称 OCR 识别区域
- 🟠 **橙色框**: 文章标题 OCR 识别区域
- 🟣 **紫色点**: 留言按钮位置
- 🔵 **青色点**: 留言输入框位置
- 🟡 **黄色点**: 发送按钮位置

如需单独验证校准配置，运行 `uv run python -m wechat_gzh.auto_comment -v`

#### 配置

修改 `wechat_gzh/config.py`：

```python
# 留言内容
COMMENT_TEXT = "已关注，盼回。"

# 操作间隔时间配置（秒）
TIMING = {
    "account_interval_min": 3,   # 公众号间隔最小秒数
    "account_interval_max": 10,  # 公众号间隔最大秒数
    "comment_wait_min": 3,       # 留言发送前最小等待
    "comment_wait_max": 10,      # 留言发送前最大等待
}
```

#### 安全提示

- **紧急中断**：将鼠标移动到屏幕左上角
- **手动停止**：按 `Ctrl+C`
  - 校准阶段：直接退出
  - 主循环阶段：等待当前操作完成后安全退出

---

## 项目结构

```
wechat_gzh/                      # 项目根目录
├── wechat_gzh/                  # Python 包
│   ├── __init__.py              # 模块入口
│   ├── api.py                   # 微信公众号 API 客户端
│   ├── config.py                # 配置文件
│   ├── get_users.py             # 获取用户信息主程序
│   ├── auto_comment.py          # 自动留言主程序
│   ├── llm_client.py            # LLM 评论生成客户端
│   └── automation/              # GUI 自动化子模块
│       ├── __init__.py
│       ├── window.py            # 窗口管理
│       ├── navigator.py         # 导航操作
│       ├── commenter.py         # 留言操作
│       ├── ocr.py               # OCR 识别
│       ├── calibration.py       # 校准配置管理
│       ├── visualizer.py        # 校准可视化
│       └── utils.py             # 工具函数
├── assets/                      # 图像识别资源
│   ├── mac/                     # macOS 平台资源
│   │   ├── comment_button.png   # 留言按钮图片
│   │   ├── comment_input.png    # 输入框图片
│   │   └── send_button.png      # 发送按钮图片
│   └── README.md                # 资源说明
├── config/                      # 配置文件目录
│   ├── calibration.json         # 校准配置（自动保存）
│   ├── comment_history_*.json  # 留言历史记录（按日期）
│   └── task_prompt.json         # LLM 任务提示词配置
├── logs/                        # 日志目录（自动创建）
│   ├── auto_comment_*.log       # 运行日志
│   └── calibration_check_*.png  # 校准验证截图（可选）
├── .env                         # 环境变量配置（需自行创建，不提交）
├── .gitignore                   # Git 忽略文件
├── pyproject.toml               # 项目配置
├── uv.lock                      # 依赖锁定文件
└── README.md                    # 本文件
```

## 注意事项

1. 自动留言功能使用 GUI 自动化技术，依赖屏幕坐标
2. 首次运行需要进行位置校准，校准后配置会自动保存
3. 如果微信窗口位置/大小改变，需要重新校准（使用 `-r` 参数）
4. 请妥善保管 `.env` 文件
5. 建议先在测试账号上验证
