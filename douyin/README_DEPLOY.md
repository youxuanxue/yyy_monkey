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

### 许可证生成 (License)

项目引入了简单的 License 验证机制。分发给用户前，需要生成 `license.lic` 文件。

```bash
# 生成一个有效期为 3 天的 license
python douyin/scripts/gen_license.py --days 3

# 或者生成 30 天
python douyin/scripts/gen_license.py --days 30
```
生成的 `license.lic` 文件会默认放在 `douyin/` 根目录下。
**注意**：`license.lic` 必须存在且在有效期内，程序才能运行。

## 2. 打包为 Windows 可执行程序 (exe)

本项目已提供一键打包脚本 `build_exe.bat`。

1. 进入 `douyin` 目录。
2. 确保 `license.lic` 文件已生成并存在于当前目录（它会被打包进去，或者你可以选择不打包让用户手动放置，当前配置默认会将根目录的 license.lic 打包进去作为默认试用）。
3. 双击运行 `build_exe.bat`。
   - 该脚本会自动创建虚拟环境、安装依赖、并执行 PyInstaller 打包。
4. 等待脚本执行完毕。

打包成功后，会在 `douyin/dist/` 目录下生成一个名为 `DouyinAutoLike` 的文件夹。

## 3. 运行与分发

### 文件结构
分发给用户时，请打包整个 `DouyinAutoLike` 文件夹：
- `DouyinAutoLike.exe`: 主程序
- `license.lic`: 许可证文件（如果过期，用户需要向你索要新的文件并替换此文件）。
- `data/`: 存放加密后的数据文件 (`*.enc`)。
- `logs/`: 程序运行日志。
- `.chrome_profile/`: 用户数据目录。

## 4. 常见问题

- **浏览器启动失败**: 确保系统安装了 Chrome 浏览器。
- **登录状态丢失**: 确保 `.chrome_profile` 目录存在且程序有读写权限。
- **数据文件未找到**: 确保 `data` 文件夹与 exe 在同一目录下，且包含 `.enc` 文件。

