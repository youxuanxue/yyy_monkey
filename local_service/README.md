# 本地服务（Control Plane）

MVP：本地运行的控制平面，提供配置、候选上报、动作下发、回执与审计能力。

## 运行（示例）

```bash
# 安装 uv（若尚未安装）
# macOS: brew install uv

uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 17890 --reload
```

访问 `http://127.0.0.1:17890/health` 应返回 `{"status":"ok", ...}`。


