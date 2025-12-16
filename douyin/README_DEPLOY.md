# 抖音自动点赞工具 - 部署与打包指南

本指南介绍如何在 Windows 10/11 环境下打包和运行本项目。

## 1. 准备工作

### 系统要求
- Windows 10 或 Windows 11
- 已安装 Python 3.10 或更高版本
- 已安装 Google Chrome 浏览器

### 数据加密
项目中的评论和弹幕数据需要先加密才能被程序读取。
在打包之前，请确保已运行加密脚本生成 `.enc` 文件：

```bash
# 在项目根目录下运行
python douyin/scripts/encrypt_data.py
```
这将在 `douyin/data/` 目录下生成 `comments.enc` 和 `danmaku.enc`。

## 2. 打包为 Windows 可执行程序 (exe)

本项目已提供一键打包脚本 `build_exe.bat`。

1. 进入 `douyin` 目录。
2. 双击运行 `build_exe.bat`。
   - 该脚本会自动创建虚拟环境、安装依赖、并执行 PyInstaller 打包。
3. 等待脚本执行完毕。

打包成功后，会在 `douyin/dist/` 目录下生成一个名为 `DouyinAutoLike` 的文件夹。

## 3. 运行与分发

### 启动程序
打开 `dist/DouyinAutoLike` 文件夹，双击运行 `DouyinAutoLike.exe` 即可（它是命令行程序，会弹出一个黑框终端）。

**注意**：由于这是一个命令行工具，直接双击运行可能会因为没有参数而迅速关闭（虽然代码里有默认参数，但通常建议通过 CMD/PowerShell 运行以查看日志）。
推荐方式：
1. 在文件夹地址栏输入 `cmd` 并回车，打开终端。
2. 输入 `DouyinAutoLike.exe --help` 查看帮助。
3. 输入 `DouyinAutoLike.exe --video-url "你的视频链接"` 开始运行。

### 文件结构
分发给用户时，请打包整个 `DouyinAutoLike` 文件夹：
- `DouyinAutoLike.exe`: 主程序
- `data/`: 存放加密后的数据文件 (`*.enc`)。用户如果需要更新话术，可以使用 `encrypt_data.py` 生成新的 enc 文件替换这里的同名文件。
- `logs/`: 程序运行日志会自动保存在这里。
- `.chrome_profile/`: 程序首次运行后会自动生成此目录，用于保存登录状态（Cookie 等）。

## 4. 常见问题

- **浏览器启动失败**: 确保系统安装了 Chrome 浏览器。
- **登录状态丢失**: 确保 `.chrome_profile` 目录存在且程序有读写权限。
- **数据文件未找到**: 确保 `data` 文件夹与 exe 在同一目录下，且包含 `.enc` 文件。

