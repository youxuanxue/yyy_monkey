# 公众号内容规划工具

抓取参考公众号数据、分析内容特征、生成日更规划。

## 使用

```bash
# 安装依赖
uv sync

# 1. 抓取文章数据（需扫码登录 mp.weixin.qq.com）
uv run python -m creator scrape

# 2. 分析数据并生成报告
uv run python -m creator analyze
# -> 审阅 output/analysis_report.md，确认后继续

# 3. 生成日更规划
uv run python -m creator plan

# 或一键执行抓取+分析（到人工确认节点暂停）
uv run python -m creator run
```

## 配置

编辑 `config/target.json` 设置目标账号、参考账号和栏目体系。

## LLM 配置

规划生成阶段需要 LLM API，通过环境变量配置：

```bash
export OPENAI_API_KEY="your-key"
# 如使用 DeepSeek/Qwen 等兼容 API：
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_MODEL="deepseek-chat"
```
