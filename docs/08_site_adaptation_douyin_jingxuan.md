# 站点适配：抖音精选分栏页（/jingxuan/*）

## 入口

以“亲子”分栏为例：
- `https://www.douyin.com/jingxuan/child?modal_id=...`

> 该页面常用 `modal_id` 打开视频详情弹窗；候选提取优先从页面上可见的 `modal_id`/链接入手。

## 候选提取策略（MVP）

插件侧（`extension/content.js`）采用启发式：
- 优先抓取带 `modal_id` 的链接（`a[href*="modal_id="]`）
- 以链接所在的“卡片容器”为上下文，尽量提取：
  - `video_id`: `modal_id`
  - `url`: 当前页面 URL + `modal_id`（canonical）
  - `title`: 卡片内标题/文本（启发式）
  - `author_name`: 卡片内 `@xxx`（启发式）
  - `duration`: `mm:ss`（若可见）
  - `heat`: 卡片内数字（若可见）

提取不到时回退到通用链接抓取（保证 MVP 不至于空结果）。

## 注意事项

- 页面结构变化频繁：后续应引入“站点适配层”与回归用例（固定入口 + 快照）
- 合规与风险：只处理页面公开可见信息；互动动作必须遵循项目风控与审计要求


