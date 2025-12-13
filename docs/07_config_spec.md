# MVP 配置规格（插件 + 本地服务）

## 1. 账号与执行环境

### Account（MVP）
- `account_id`: `"default"`（先单账号；第二阶段扩展多账号）

### 本地服务端口
- `port`: `17890`
- 仅监听：`127.0.0.1`

## 2. 动作开关

- `like_enabled`: 默认 `true`
- `comment_enabled`: 默认 `false`（你明确需要时再打开）

## 3. 评论自动化门禁参数（硬约束）

### 3.1 速率限制（唯一硬限制）
- `comment_rate_limit_per_minute`: `2`

### 3.2 冷却时间（建议默认开启）
> 不是总量上限，但能避免连续两条评论紧挨着发出去造成体验与风险问题。

- `comment_cooldown_seconds`: 默认 `15`（可调）

### 3.3 模板白名单
- `comment_template_whitelist`: 多条短模板（版本化）
- 模板允许少量变量插槽（MVP 可先不做变量）

### 3.4 过滤器（必须）
- `blocked_keywords`: 敏感词/引流词/广告词
- `blocked_patterns`: 联系方式/二维码/外链等正则模式（MVP 可先少量规则）
- `max_comment_length`: 默认 `50`

## 4. 候选筛选（MVP）

- `exclude_keywords`: 命中即淘汰
- `min_score_to_like`: 默认 `0`（MVP 可先不评分）
- `min_score_to_comment`: 默认 `0`（建议后续提高阈值）

## 5. 审计与证据（MVP）

- `audit_enabled`: `true`
- `evidence_mode`: `"none" | "screenshot_path" | "html_snapshot"`
  - MVP 默认 `"none"`，后续再加截图/快照落盘


