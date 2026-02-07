# 海外平台注册链接与API
_Exported on 2026/2/6 at GMT+8 17:27:25 from Cursor (2.4.21)_

---

**User**

@docs/content-series-plan.md:365-379 提到的海外平台，只有youtube有账号，其他的都哦没有账号，给一下注册链接，以及是否有API可以自动发布文章或者视频。

---

**Cursor**

根据你的发布计划，涉及的海外平台有 **Twitter、LinkedIn、Medium、Dev.to、YouTube**。你说 YouTube 已有账号，以下是其他四个平台的注册链接和 API 自动发布情况：

---

## 1. Twitter (现在叫 X)

- **注册链接**: https://x.com/i/flow/signup
- **API 自动发布**:
  - **支持**。X API v2 可以自动发布推文（包括线程/Thread）。
  - API 入口：https://developer.x.com/
  - 需要申请开发者账号，免费版（Free tier）支持每月 **1,500 条推文发布**，对你的需求绑绑有余。
  - 发推文的 API 端点：`POST /2/tweets`
  - **注意**：发布 Thread（线程）需要连续调用 API，每条推文通过 `reply` 参数关联上一条。

---

## 2. LinkedIn

- **注册链接**: https://www.linkedin.com/signup
- **API 自动发布**:
  - **支持**，但限制较多。
  - 需要创建 LinkedIn App：https://www.linkedin.com/developers/
  - 使用 **Share on LinkedIn API** 可以发布文章/帖子。
  - **限制**：个人账号发布需要通过 OAuth 2.0 认证，且 LinkedIn 对 API 审批比较严格，个人开发者获取权限可能需要等待审核。
  - 如果只是偶尔发（计划中只有 2 篇发 LinkedIn），**手动发布更现实**。

---

## 3. Medium

- **注册链接**: https://medium.com/m/signin?operation=register
  - 支持 Google / Facebook / Email 注册
- **API 自动发布**:
  - **支持**，Medium 有官方 API。
  - API 文档：https://github.com/Medium/medium-api-docs
  - 可以通过 `POST /v1/users/{{userId}}/posts` 自动创建文章。
  - 支持 Markdown 和 HTML 格式。
  - **注意**：Medium API 目前处于维护模式，功能有限但发布文章的核心功能仍可用。需要在 Settings > Security and apps > Integration tokens 中生成 Token。

---

## 4. Dev.to

- **注册链接**: https://dev.to/enter
  - 支持 GitHub / Twitter / Email 注册（推荐用 GitHub 注册，开发者社区氛围）
- **API 自动发布**:
  - **支持**，Dev.to 的 API 是最友好的。
  - API 文档：https://developers.forem.com/api/v1
  - 通过 `POST /api/articles` 即可发布文章。
  - 支持 **Markdown** 格式，非常适合技术类文章。
  - 在 Settings > Extensions > DEV Community API Keys 中生成 API Key 即可，**无需审批，即时可用**。
  - 还支持设置 `canonical_url`，可以指向你的独立站原文，对 SEO 有好处。

---

## 5. YouTube（已有账号）

- **API 自动发布**:
  - **支持**。YouTube Data API v3 可以自动上传视频。
  - API 文档：https://developers.google.com/youtube/v3
  - 需要在 Google Cloud Console 创建项目并启用 YouTube Data API。
  - 上传视频端点：`POST /youtube/v3/videos`
  - **注意**：新创建的 API 项目默认每天有上传配额限制，但对你的发布频率完全够用。

---

## 总结对比

| 平台 | 注册难度 | API 自动发布 | API 获取难度 | 推荐自动化 |
|------|---------|-------------|-------------|-----------|
| Twitter/X | 简单 | 支持 | 中等（需申请开发者） | 推荐，Thread 发布可自动化 |
| LinkedIn | 简单 | 支持 | 较难（审批严格） | 不推荐，手动发更省事 |
| Medium | 简单 | 支持 | 简单（生成 Token） | 推荐，Markdown 直接发 |
| Dev.to | 简单 | 支持 | 最简单（即时 API Key） | 强烈推荐，最适合自动化 |
| YouTube | 已有 | 支持 | 中等（需 Google Cloud） | 视情况，视频上传可自动化 |

如果你想做自动化发布，建议优先从 **Dev.to** 和 **Medium** 开始，这两个平台 API 最容易上手，而且都支持 Markdown，可以直接复用你的文章内容。

