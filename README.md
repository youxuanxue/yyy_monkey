# YYY Monkey

这是一个针对短视频平台的自动化工具集，包含抖音网页端和微信视频号两个主要模块。

## 主要模块

### [Douyin Service (抖音网页端自动化)](douyin/README.md)

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

### [WeChat Service (微信视频号自动化)](wechat/README.md)

位于 `wechat/` 目录下。

**功能：**
- 图像识别 (PyAutoGUI + OpenCV) 驱动
- 自动刷视频号
- 自动点赞与评论
- 支持 Windows 一键打包部署 (.exe)

**快速开始：**

```bash
cd wechat
python src/wechat_client/cli.py --help
```
