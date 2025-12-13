# 浏览器插件（Execution Plane）

MVP：MV3 原生插件骨架，提供：
- popup：手动触发“上报候选 / 拉取任务 / 回报结果”的调试按钮
- content script：从当前页面提取候选（MVP 先做 demo）

## 本地加载

1. 打开 Chrome/Edge → 扩展程序 → 开启开发者模式
2. “加载已解压的扩展程序” → 选择本目录 `extension/`

> 插件与本地服务通过 `http://127.0.0.1:17890` 通信；如遇到跨域限制，需由插件端使用 host permissions 与 fetch。


