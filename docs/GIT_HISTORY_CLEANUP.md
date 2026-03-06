# Git 历史敏感信息清理说明

## 已执行操作（约 2026-03-06）

- 使用 `git filter-repo` 从**全部历史**中移除了曾包含敏感凭证的文件：
  - `wechat_gzh/fetch_all_users.py`（历史版本中含微信公众号 TOKEN 与 COOKIES）
- 当前仓库中该文件已改为通过环境变量 `WX_MP_TOKEN`、`WX_MP_COOKIES` 读取凭证，无硬编码敏感信息。

## 推送到 GitHub 必须做的事

历史已被重写，与 `origin/main` 不再一致，**必须强制推送**才能更新远端：

```bash
git push --force-with-lease origin main
```

若存在其他已推送分支（如 `wip-douyin`、`wip-wx` 等），且也基于旧历史，需要按需 rebase 到新的 `main` 后再推送，或删除远端旧分支后重新推送。

## 协作与本地克隆

- **其他协作者**：需要基于新历史重新克隆或按 [Git 文档](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) 处理本地仓库，否则会再次带入旧历史。
- **本机其他克隆**：建议重新 `git clone` 或对该克隆执行一次 `git fetch origin && git reset --hard origin/main`（会丢弃该克隆上的本地提交）。

## 凭证本身

- 已泄露过的微信公众号 session（TOKEN/COOKIES）建议在后台重新登录或刷新会话，使旧会话失效。
- `config/twitter_credentials.json` 历史中仅为占位符，未发现真实 Twitter 密钥被提交。
