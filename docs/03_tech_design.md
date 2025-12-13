# 技术方案（Tech Design）

## 1. 总体架构（分层）

推荐采用“控制平面（Control Plane）+ 执行平面（Execution Plane）”：

- **控制平面**：存储配置、生成计划、排队、限流、审计、报表、告警
- **执行平面**：在真实交互环境（浏览器/执行器）中完成内容发现与动作执行，并回传证据

逻辑数据流：
主题配置 → 生成任务计划 → 拉取候选 → 评分筛选 → 进入执行队列 → 执行动作 → 回执与证据 → 报表与审计

## 2. 模块划分

### 2.1 控制平面服务（建议：Node.js 或 Python）
- **Topic Service**：主题/黑白名单/模板管理
- **Scheduler**：时间窗口触发（cron）→ 生成 run（一次执行批次）
- **Queue / Orchestrator**：候选队列、动作队列、重试队列；并发控制
- **Policy Engine**：规则评分、阈值、配额计算、抽检策略
- **Audit & Evidence**：保存决策与执行证据（截图/HTML快照/录像链接）
- **Reporting**：统计、报表、导出、告警（邮件/IM）

### 2.2 执行器（Browser Extension / Playwright Worker）
统一抽象为 **Executor API**：
- `discover(query|feed, options) -> candidates[]`
- `act(candidate, action) -> receipt`
- `capture(candidate) -> evidence`

执行器负责：
- 打开页面、滚动、分页、收集候选
- 通过 UI 交互完成低风险动作
- 对高风险动作发起“待确认”并提供上下文（截图、候选信息、草稿）

### 2.3 运营控制台（Web UI）
最小实现可先用“本地页面 + 简易后端”，后续升级为完整管理后台。

## 3. 数据模型（建议）

> 先从能支撑审计与回放的最小字段开始，避免过度建模。

### Topic
- `id`
- `name`
- `keywords[]`, `exclude_keywords[]`
- `locale`（语言/地域偏好）
- `policy_id`
- `created_at`, `updated_at`

### Job（调度配置）
- `id`, `topic_id`
- `schedule`（cron 或时间窗口）
- `daily_quota`（按 action 细分）
- `enabled`

### Run（一次执行批次）
- `id`, `job_id`
- `started_at`, `ended_at`
- `status`（running/succeeded/failed/cancelled）
- `metrics`（候选数、执行数、失败数、风控命中等）

### Candidate（候选内容）
- `id`, `run_id`, `topic_id`
- `source`（search/feed）
- `url` / `video_id`（若可得）
- `author_id/name`（若可得）
- `title/desc`（若可得）
- `score`, `reasons[]`
- `evidence_ref`（截图/快照）
- `created_at`

### ActionTask（动作任务）
- `id`, `candidate_id`
- `action_type`（like/favorite/follow/comment_draft/comment_submit）
- `status`（queued/running/succeeded/failed/review_required/cancelled）
- `quota_bucket`（用于限流与配额）
- `error_code/error_message`
- `evidence_ref`
- `created_at`, `updated_at`

### ReviewItem（人工审核）
- `id`, `action_task_id`
- `drafts[]`（评论草稿）
- `decision`（approved/rejected/edited）
- `reviewer`, `reviewed_at`

## 4. 调度、限流与风控（关键）

### 4.1 速率与配额
- **按账号、按动作、按小时/天**设置硬上限
- **随机等待**仅作为体验策略，不作为“规避检测”目的；核心是低频与可控
- 失败重试采用指数退避；同类错误快速熔断

### 4.2 风险分级
将动作分级：
- 低风险：浏览、收藏
- 中风险：点赞、关注（配额低、触发更多校验）
- 高风险：评论提交（MVP 支持“受限自动评论”，但必须满足强约束与可熔断；默认仍建议人工确认）

### 4.3 熔断策略（示例）
出现以下情况立即暂停相关账号的执行队列并告警：
- 连续 N 次动作失败（网络/页面结构变化）
- 登录失效/要求二次验证
- 疑似风控提示（以可识别的页面文案/状态为准）

## 5. 候选筛选与评分（从简单到复杂）

### 5.1 规则评分（MVP）
- 关键词命中加分、排除词命中直接淘汰
- 作者黑名单淘汰、白名单加分
- 发布时间、时长范围、内容类型偏好

### 5.2 AI 评分（可选）
仅在**合规允许且数据最小化**前提下：
- 输入：标题/描述/可见文本（不上传敏感信息）
- 输出：相关性分 + 风险提示（是否适合互动、是否可能敏感）

## 6. 证据留存与可回放

最低要求：
- 每次候选发现保存截图或 HTML 快照
- 每次动作保存动作前后关键截图（或短录像链接）
- 审计流水包含：谁/何时/为何（reasons）/做了什么/结果如何

## 6.1 自动评论的执行管线（MVP）

为了把风险可控在工程层面，自动评论必须走统一“门禁（Guardrails）”：

- **Eligibility Gate（资格门）**
  - 主题/作者白名单：不强制（按产品策略允许对所有候选开放）
  - 候选评分达到阈值；命中排除词/黑名单直接拒绝
  - **速率限制**：按账号每分钟评论提交次数不超过 2 次（硬限制）
  - 满足冷却时间
- **Content Gate（内容门）**
  - 仅允许模板白名单生成（模板版本可审计）
  - 敏感词/引流词/联系方式模式过滤
  - 长度限制（短评论）与字符集限制（避免异常字符）
- **Execution Gate（执行门）**
  - 提交前截图（含输入框内容）+ 提交后确认态截图
  - 失败分类（网络/页面变化/登录失效/风控提示），按类型退避与熔断
- **Sampling Review（抽检复核）**
  - 按比例把“已自动提交”的样本推入复核队列用于质量与合规巡检
  - 若复核发现模板问题或投诉风险，支持模板版本一键下线与策略回滚

## 7. 可观测性

- 指标：run 成功率、动作成功率、平均耗时、失败类型分布、熔断次数
- 日志：结构化日志（run_id/job_id/topic_id/action_task_id 贯穿）
- 告警：登录失效、失败率突增、队列积压、存储异常

## 8. 技术栈建议（可替换）

- 控制平面：Node.js（NestJS）或 Python（FastAPI）
- 存储：PostgreSQL（审计强）+ 对象存储（证据）
- 队列：Redis（BullMQ/Celery）或 RabbitMQ
- 执行器：浏览器插件（MV3）+（可选）Playwright Worker
- 控制台：React/Next.js


