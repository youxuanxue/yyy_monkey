# Douyin Monkey (Douyin Auto Like)

这是一个针对抖音网页端的自动化工具集，目前包含一个主要模块：**自动互动助手**。

## 主要模块

### [Douyin Service (本地自动化服务)](douyin/README.md)

位于 `douyin/` 目录下。

**功能：**
- 全自动刷视频 (Follow 模式)
- 智能点赞（基于时长策略）
- 自动发送评论与弹幕（内容加密）
- 模拟真人操作习惯
- 支持 Windows 一键打包部署 (.exe)

**快速开始：**

```bash
cd douyin
python src/douyin_auto_like/cli.py --help
```

详细文档请参考：[douyin/README.md](douyin/README.md)
