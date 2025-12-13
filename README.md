# yyy_monkey

抖音视频小助手（规划中）：**定时浏览/搜索指定主题的视频，并以“合规 + 可审计 + 可控速”的方式辅助互动**（点赞/收藏/关注/评论等）。

## 文档入口（必读）

- `docs/00_overview.md`：一页纸总览（目标、原则、范围）
- `docs/01_product_design.md`：产品方案（用户、场景、MVP、配置、审计）
- `docs/02_carrier_comparison.md`：载体对比（浏览器插件/后台脚本/RPA 等）与推荐组合
- `docs/03_tech_design.md`：技术方案（架构、模块、数据模型、调度、策略、可观测性）
- `docs/04_risk_compliance.md`：合规与风控（条款、隐私、安全、限速、人工确认）
- `docs/05_roadmap.md`：里程碑与交付计划
- `docs/06_api_spec.md`：本地服务 API 规格（MVP，可直接开工）
- `docs/07_config_spec.md`：MVP 配置规格（速率/门禁参数）

> 重要声明：本项目以“合规使用、尊重平台规则、保护隐私安全”为第一原则；默认设计为**人机协同**与**可审计**，不提供绕过平台风控/反自动化的能力。

## 开发/运行（MVP 骨架）

### 启动本地服务（uv）

在 `local_service/` 目录下：

```bash
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 17890 --reload
```

健康检查：
- `GET http://127.0.0.1:17890/health`

### 加载浏览器插件（MV3）

1. 打开 Chrome/Edge → 扩展程序 → 开启开发者模式
2. “加载已解压的扩展程序” → 选择 `extension/`
3. 打开任意页面 → 点击插件 popup 进行调试（提取候选/上报/拉任务）
