# 本地服务 API 规格（MVP）

> 目标：插件（执行面）通过 HTTP 调用本地服务（控制面），完成配置下发、候选上报、动作下发、回执与审计。

## 1. 基本约定

- Base URL：`http://127.0.0.1:17890`
- 数据格式：JSON
- 时间：ISO8601（UTC 或本地时区需声明，MVP 可用本地时区）
- 身份：MVP 单用户/单账号，可先不做鉴权；第二阶段加 `X-API-Key`

## 2. 资源模型（简化）

- `Topic`：主题（关键词/排除词/策略）
- `Job`：调度配置（时间窗口、动作开关）
- `Run`：一次执行批次（由调度器创建）
- `Candidate`：候选视频（插件采集上报）
- `ActionTask`：动作任务（本地服务生成/下发，插件执行）
- `AuditLog`：审计流水（服务端追加写入）

## 3. API 列表

### 3.1 Health

#### GET `/health`

返回：
- `status`: `"ok"`
- `version`: string

### 3.2 Topics

#### POST `/v1/topics`
请求：
- `name`: string
- `keywords`: string[]
- `exclude_keywords`: string[]

#### GET `/v1/topics`

#### GET `/v1/topics/{topic_id}`

#### PATCH `/v1/topics/{topic_id}`

#### DELETE `/v1/topics/{topic_id}`

### 3.3 Jobs（调度配置）

#### POST `/v1/jobs`
请求：
- `topic_id`: string
- `schedule`: string（cron 或时间窗口表达式，MVP 可先存字符串不解析）
- `enabled`: boolean
- `actions`:
  - `like_enabled`: boolean
  - `comment_enabled`: boolean

#### GET `/v1/jobs`

#### PATCH `/v1/jobs/{job_id}`

### 3.4 Runs（一次批次）

#### POST `/v1/runs`
用途：手动触发（MVP 方便调试）
请求：
- `job_id`: string

#### GET `/v1/runs/{run_id}`

### 3.5 Candidates（候选上报）

#### POST `/v1/candidates:batchUpsert`
用途：插件把“搜索/浏览得到的候选列表”上报
请求：
- `run_id`: string
- `items`: array of
  - `source`: `"search" | "feed"`
  - `url`: string
  - `video_id`: string | null
  - `author_name`: string | null
  - `title`: string | null
  - `raw_text`: string | null（可见文本摘要）
  - `evidence`: object（可选，MVP 可先不传）

返回：
- `candidate_ids`: string[]

### 3.6 ActionTasks（动作下发与回执）

#### POST `/v1/actionTasks:next`
用途：插件请求下一条待执行任务（拉模式）
请求：
- `account_id`: string（MVP 可固定 `"default"`）

返回：
- `task`: ActionTask | null

ActionTask（核心字段）：
- `id`
- `candidate_id`
- `candidate_url`（MVP 已提供，便于执行器一键打开任务页面）
- `candidate_title`（可选）
- `action_type`: `"like" | "comment_submit"`
- `payload`：
  - like: `{ }`
  - comment_submit: `{ "template_id": string, "comment_text": string }`

#### POST `/v1/actionTasks/{task_id}:report`
用途：插件回传执行结果与证据
请求：
- `status`: `"succeeded" | "failed" | "review_required"`
- `error_message`: string | null
- `evidence`: object（截图路径/摘要等，MVP 可先传空）

### 3.7 评论模板与过滤（MVP 先最小化）

#### GET `/v1/commentTemplates`
返回模板白名单列表（用于 comment_submit payload 生成）

#### POST `/v1/commentTemplates`
新增模板（MVP 可先本地文件/SQLite）

## 4. 风控门禁（服务端必须保证）

- **评论速率硬限制**：每账号每分钟 ≤ 2（超限则 `ActionTask` 不下发或下发后拒绝执行）
- **模板白名单**：评论只能来自模板白名单
- **强过滤**：敏感词/引流/联系方式模式命中则不生成 `comment_submit`
- **审计**：生成/下发/执行/失败原因写入 `AuditLog`

## 5. 自动评论任务的生成方式（你已选择 A）

MVP 默认策略：
- 候选上报（`/v1/candidates:batchUpsert`）后，由本地服务根据 `Job.comment_enabled` 与 `Topic.keywords/exclude_keywords` **自动生成** `comment_submit` 任务
- 评论文本只来自“启用的模板白名单”（`/v1/commentTemplates`）
- 任务派发时强制 **每账号每分钟 ≤ 2 条** 的速率硬限制


