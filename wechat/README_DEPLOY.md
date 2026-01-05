# 微信视频号自动互动助手 - 部署与打包指南

本指南介绍如何在 Windows 10/11 环境下打包和运行本项目。

## 1. 准备工作

### 系统要求
- Windows 10 或 Windows 11
- 已安装 Python 3.10 或更高版本
- 已安装 PC 端微信 (建议最新版)

### 许可证生成 (License)
项目引入了 License 验证机制。分发给用户前，需要生成 `license.lic` 文件。

```bash
# 在项目根目录下运行
# 生成一个有效期为 3 天的 license
python wechat/scripts/gen_license.py --days 3

# 或者生成 30 天
python wechat/scripts/gen_license.py --days 30
```
生成的 `license.lic` 文件会默认放在 `wechat/` 根目录下。

## 2. 打包为 Windows 可执行程序 (exe)

本项目已提供一键打包脚本 `build_exe.bat`。

1. 进入 `wechat` 目录。
2. 确保 `license.lic` 文件已生成并存在于当前目录（会被打包进去作为默认试用）。
3. 双击运行 `build_exe.bat`。
   - 该脚本会自动创建虚拟环境、安装依赖、并执行 PyInstaller 打包。
4. 等待脚本执行完毕。

打包成功后，会在 `wechat/dist/` 目录下生成一个名为 `WeChatAutoLike` 的文件夹。

## 3. 运行与分发

### 启动程序
打开 `dist/WeChatAutoLike` 文件夹，双击运行 `WeChatAutoLike.exe` 即可。

**使用说明**：
1. 启动程序后，根据提示选择模式（或直接运行）。
2. 程序会提示“Auto Mode starting in 5 seconds...”。
3. **关键步骤**：在倒计时结束前，迅速切换到微信 PC 端，并打开**视频号**窗口，保持该窗口在前台可见。
4. 程序将自动识别图标进行点赞和评论。

### 文件结构
分发给用户时，请打包整个 `WeChatAutoLike` 文件夹：
- `WeChatAutoLike.exe`: 主程序
- `license.lic`: 许可证文件。
- `assets/`: 图像识别资源库（必须保留）。
- `data/`: 评论库等数据文件。

## 4. 常见问题

- **识别失败/鼠标乱点**: 
    - 确保微信视频号窗口没有被遮挡。
    - 确保系统缩放比例为 100% (Windows 设置 -> 显示 -> 缩放与布局)。如果不是 100%，图像识别坐标可能会偏移。
    - 检查 `assets/` 下的截图是否与当前微信版本图标一致，如果不一致需要重新截图替换。






