# media-publisher 独立仓库化与 blue-ocean 调度接入方案

## 1. 结论（先回答你的核心问题）

`media-publisher` 可以作为独立仓库、独立工具包，被 `/Users/xuejiao/Codes/blue-ocean` 的「1 人公司 + 多 Agent + 飞书」组织结构调度；并且建议优先走 **“独立包 + 命令行契约 + blue-ocean 适配层”** 路径，而不是在 `blue-ocean` 内重复实现发布逻辑。

但要稳定落地，当前至少有 4 个必须先补的阻断项：

1. 模块级副作用（`youtube.py` 导入即改环境变量）
2. `__init__.py` eager import（会连带触发重模块初始化）
3. 账号/ID 未做路径安全校验（存在 `..`、`/` 注入风险）
4. 全量状态文件写入非原子（崩溃可能产生不完整文件）

---

## 2. 现状评估（基于当前代码）

### 2.1 已经具备独立能力的部分

- 已有标准 Python 打包基础：`pyproject.toml`、`[project.scripts]`、`src/` 布局。
- 核心能力可复用：多平台发布器、`EpisodeAdapter`、CLI/GUI 双入口。
- 与业务仓库强耦合不多：主要问题集中在入口脚本和导出策略，不是领域逻辑本身。

### 2.2 与“可调度工具包”目标冲突的点

- **副作用冲突**：`core/youtube.py` 在导入时执行 `_setup_proxy()`。
- **导出层冲突**：`media_publisher/__init__.py` 与 `core/__init__.py` 都是重度 eager import。
- **输入安全不足**：`account` 被拼入认证文件路径，缺少格式白名单校验。
- **持久化健壮性不足**：报告文件与部分状态文件直接覆盖写入，缺原子写。
- **编排契约不足**：CLI 主要是人读日志，不是“机器可判定结果（JSON contract）”。

---

## 3. 目标架构（给 blue-ocean 用的最终形态）

将 `media-publisher` 明确为三层能力：

1. `media_publisher.domain`（任务模型、校验、平台抽象）
2. `media_publisher.application`（发布用例、重试、幂等键、结果模型）
3. `media_publisher.interfaces`（CLI/GUI/未来 RPC）

blue-ocean 只依赖最外层稳定接口，不直接触碰 Playwright/API 细节。

建议在 blue-ocean 中新增一个薄适配器（例如 `blue_ocean/org/media_publisher_adapter.py`）：

- 入参：`action_id`、平台、素材路径、账号标识、幂等键
- 调用：子进程执行 `media-publisher job run ... --json`
- 出参：标准 JSON（`status`、`artifacts`、`retryable`、`error_code`）
- 回写：写入 `reports/org-runs/<id>/`，并推送飞书卡片

---

## 4. 落地路线图（分阶段，可执行）

## Phase 0（1 周）：仓库独立化“硬门槛”改造

目标：做到“可被任何上层系统安全调用”。

必须完成：

- `youtube.py` 去模块级副作用：把代理设置移到显式调用点（如 `authenticate()` 前）。
- `__init__.py` 去 eager import：仅暴露轻量符号；重模块改 lazy import 或子模块显式导入。
- 新增 `sanitize_identifier()`：对 `account`/外部 id 使用白名单（`[a-zA-Z0-9_-]{1,64}`），拒绝 `..`、`/`。
- 新增 `atomic_write_text()` / `atomic_write_json()` 工具，统一替代覆盖写入。
- 给 CLI 增加 `--json` 输出模式（成功/失败都返回结构化结果）。

验收标准：

- `python -c "import media_publisher"` 不触发环境变量修改、网络请求或浏览器启动。
- 恶意 `account="../../x"` 被拒绝并返回明确错误码。
- 断电模拟后不存在空报告文件。

## Phase 1（1 周）：调度契约与运行治理

目标：让 blue-ocean 像调度“标准执行单元”一样调度它。

必须完成：

- 新增命令：`media-publisher job run --job-file <json> --result-file <json>`
- 约定结果 schema：
  - `status`: `success|failed|partial`
  - `retryable`: `true|false`
  - `artifacts`: 产物路径列表
  - `metrics`: 平台耗时、重试次数
  - `error`: `{code, message, platform}`
- 增加超时与幂等：`job_id + platform + content_hash` 防重复发布。

验收标准：

- blue-ocean 在不改核心流程前提下可通过适配器拉起任务并解析结果。
- 失败可区分“可重试/不可重试”，飞书卡片可给出下一步动作。

## Phase 2（0.5~1 周）：blue-ocean 接入与组织编排

目标：接入现有“CEO 审批 -> 执行 -> 回写”闭环。

必须完成（在 blue-ocean）：

- 在审批通过后的执行节点调用 `media_publisher_adapter`。
- 将结果写入 `evidence_refs`，并在飞书卡片中展示发布结果与重试按钮。
- 对接现有 `org-feishu-*` 回调链路，支持 `retry publish` 与 `manual takeover`。

验收标准：

- 从飞书点击“发布”到回写状态全链路成功。
- 失败后可一键重试，不会重复发布已成功平台。

## Phase 3（可选）：Skill 化与组件化增强

可选增强，不阻塞主线：

- 提供 Cursor Skill 封装（面向人工触发场景）。
- 提供轻量 HTTP Worker（仅内网），支持统一调度入口。
- 平台插件化（新平台以 entry points 注册，避免主仓频繁改动）。

---

## 5. 与 blue-ocean 现有计划的关系（避免重复建设）

`blue-ocean` 当前已有“公众号草稿发布”规划。建议调整为：

- 保留 `blue-ocean` 的治理、审批、回写、飞书编排职责；
- 将发布执行能力下沉到独立 `media-publisher`；
- blue-ocean 只保留“适配器 + 契约层”，不复制 Playwright 细节实现。

这样可以避免双份自动化脚本长期分叉。

---

## 6. 风险与控制

- **平台 UI 变更风险（微信等）**：用页面对象封装 + 冒烟测试用例 + 失败截图归档。
- **凭据与登录态风险**：统一凭据目录规范，明确多账号命名规则和过期策略。
- **长任务稳定性风险**：引入心跳日志、阶段性 checkpoint、可恢复执行。
- **审计一致性风险**：所有执行结果统一落地 JSON，并附版本号与 schema 校验。

---

## 7. 里程碑与工期建议

- M1（第 1 周末）：完成 Phase 0，达到“可安全 import + 可安全写入 + 可安全入参”。
- M2（第 2 周末）：完成 Phase 1，拿到稳定 `job` 契约。
- M3（第 3 周中）：完成 Phase 2，在 blue-ocean 完成审批到发布闭环。

整体建议：**2.5~3 周可落地首个稳定版本**。

---

## 8. 自检与迭代记录（第 1 轮）

第 1 轮自检结论：方案可执行，但还有三个不足需要修正：

1. 缺少“必须改哪些文件”的落地颗粒度。
2. 缺少“失败分类与错误码最小集合”。
3. 缺少“回滚策略”（尤其多平台部分成功场景）。

修正动作（已纳入下轮）：

- 增加文件级改造清单；
- 增加错误码建议；
- 增加失败回滚/补偿策略。

---

## 9. 迭代后补充（第 2 轮修正）

### 9.1 文件级改造清单（media-publisher）

- `src/media_publisher/core/youtube.py`：移除导入时 `_setup_proxy()`，改为显式调用。
- `src/media_publisher/__init__.py`：删减 eager import，只保留版本与轻量导出。
- `src/media_publisher/core/__init__.py`：改为轻量导出或延迟导入。
- `src/media_publisher/core/wechat.py`、`core/browser.py`：账号标识校验与安全路径拼接。
- `src/media_publisher/__main__.py`：新增 `job run`、`--json`、结构化退出码。
- `src/media_publisher/shared/io.py`（新建）：原子写工具与统一 JSON 写入。

### 9.2 错误码最小集合（建议）

- `MP_INPUT_INVALID`：输入不合法（路径、账号、平台参数）
- `MP_AUTH_REQUIRED`：需要重新认证
- `MP_PLATFORM_TIMEOUT`：平台侧超时
- `MP_PLATFORM_CHANGED`：页面结构变化导致自动化失败
- `MP_RATE_LIMIT`：平台限流/配额问题
- `MP_INTERNAL_ERROR`：内部未知异常

### 9.3 回滚/补偿策略

- 采用“平台粒度提交”，不做跨平台事务回滚（现实不可逆）。
- 对已成功平台记录 `published_artifacts`，重试时跳过成功项，仅重试失败平台。
- 对不可重试错误直接标记 `manual_takeover_required=true`，交给人工处理。

### 9.4 第 2 轮自检结果（反思后定稿）

- **完整性**：通过。已覆盖仓库独立、调度契约、blue-ocean 接入、审计回写。
- **安全性**：通过。已显式纳入路径注入防护、模块副作用治理、原子写要求。
- **可实施性**：通过。给出分阶段工期、验收标准、文件级改造清单。
- **可运维性**：部分通过。监控与告警方案有方向，但具体告警阈值待 Phase 1 落地时补齐。

结论：可按本方案直接开工；未决项仅剩“告警阈值配置”，不阻塞首版落地。

---

## 10. 最终建议（可直接执行）

先做 Phase 0 + Phase 1，再接 blue-ocean。不要先在 blue-ocean 里复制发布器实现。

最小可执行顺序：

1. 在 `media-publisher` 完成“无副作用 import + 安全输入 + 原子写 + JSON 契约”。
2. 在 `blue-ocean` 增加 `media_publisher_adapter`，打通飞书审批后的执行调用。
3. 用单平台（先公众号）跑通，再扩展到 YouTube/TikTok/Instagram。

这个顺序成本最低，且能最快形成“可治理、可审计、可重试”的组织级发布能力。
