#!/usr/bin/env python3
"""
微信公众号自动评论机器人 - 打包脚本

这个脚本用于将应用打包成独立可执行文件。
支持 macOS 和 Windows 平台。

使用方法：
    # 使用 uv 运行
    uv run python build.py
    
    # 或者直接运行（需要激活虚拟环境）
    python build.py
    
    # 指定输出目录
    uv run python build.py --output ./my_dist

打包输出：
    - macOS: dist/微信公众号评论机器人 (可执行文件)
    - Windows: dist/微信公众号评论机器人.exe

分发给用户时，需要一起提供：
    1. 可执行文件
    2. config/ 目录（包含配置模板，首次运行会自动创建）
    3. 用户使用说明（见 README）
"""

import os
import sys
import shutil
import argparse
import subprocess
import platform
from pathlib import Path


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent.absolute()


def clean_build_dirs(project_root: Path):
    """清理之前的构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"清理目录: {dir_path}")
            shutil.rmtree(dir_path)
    
    # 清理 .pyc 文件
    for pyc in project_root.rglob('*.pyc'):
        pyc.unlink()
    for pycache in project_root.rglob('__pycache__'):
        if pycache.exists():
            shutil.rmtree(pycache)


def run_pyinstaller(project_root: Path, output_dir: Path = None):
    """运行 PyInstaller 打包"""
    spec_file = project_root / 'WeChatAutoComment.spec'
    
    if not spec_file.exists():
        print(f"错误: 找不到 spec 文件: {spec_file}")
        sys.exit(1)
    
    cmd = ['pyinstaller', str(spec_file), '--clean', '--noconfirm']
    
    if output_dir:
        cmd.extend(['--distpath', str(output_dir)])
    
    print(f"运行命令: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode != 0:
        print(f"错误: PyInstaller 打包失败，退出码: {result.returncode}")
        sys.exit(1)
    
    return True


def copy_user_files(project_root: Path, dist_dir: Path):
    """复制用户需要的配置文件"""
    
    # 创建 config 目录
    config_dest = dist_dir / 'config'
    config_dest.mkdir(exist_ok=True)
    
    config_src = project_root / 'config'
    
    # 复制配置模板文件
    files_to_copy = ['task_prompt.json']
    # 根据平台复制对应的校准文件
    if platform.system() == 'Windows':
        files_to_copy.append('calibration-win.json')
    else:
        files_to_copy.append('calibration.json')
    
    for filename in files_to_copy:
        src = config_src / filename
        if src.exists():
            dest = config_dest / filename
            # 如果是 calibration-win.json，复制为 calibration.json
            if filename == 'calibration-win.json':
                dest = config_dest / 'calibration.json'
            print(f"复制配置文件: {src} -> {dest}")
            shutil.copy2(src, dest)
    
    # 创建空的历史记录文件
    history_file = config_dest / 'comment_history.json'
    if not history_file.exists():
        history_file.write_text('{}', encoding='utf-8')
    
    # 创建 logs 目录
    logs_dir = dist_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / '.gitkeep').touch()
    
    print(f"用户配置文件已复制到: {config_dest}")


def create_readme_for_users(dist_dir: Path):
    """创建用户使用说明"""
    
    readme_content = """# 微信公众号自动评论机器人 - 使用说明

## 前置要求

1. **Ollama** - 需要单独安装
   - macOS: `brew install ollama`
   - Windows: 从 https://ollama.com 下载安装
   
2. **拉取模型**（首次使用）
   ```bash
   ollama pull qwen2.5:3b
   ```
   
3. **启动 Ollama 服务**
   ```bash
   ollama serve
   ```

4. **微信客户端**
   - 确保微信已登录并打开
   - 进入"订阅号消息"页面

5. **权限设置**
   - macOS: 系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能，添加本应用
   - Windows: 以管理员身份运行（如需要）

## 使用方法

### 第一步：启动 Ollama
确保 Ollama 服务正在运行（在终端运行 `ollama serve`）

### 第二步：运行应用
- macOS: 双击 `微信公众号评论机器人`
- Windows: 双击 `微信公众号评论机器人.exe`

### 第三步：使用 Web 界面
应用启动后会自动打开浏览器 (http://localhost:8080)

1. 在"运行控制"页面点击"启动自动评论"
2. 在"参数配置"页面可以修改 AI 提示词和校准参数
3. 首次使用建议先点击"验证校准"检查坐标是否正确

## 文件说明

```
├── 微信公众号评论机器人      # 主程序
├── config/                   # 配置文件目录
│   ├── calibration.json     # 坐标校准配置
│   ├── task_prompt.json     # AI 提示词配置
│   └── comment_history.json # 评论历史记录
└── logs/                     # 日志目录
```

## 常见问题

### Q: 提示"无法连接到 Ollama"
A: 请确保 Ollama 服务正在运行。在终端运行 `ollama serve`

### Q: 点击位置不准确
A: 进入"参数配置"页面调整坐标值，或点击"验证校准"查看当前坐标位置

### Q: macOS 上无法控制鼠标
A: 请在系统偏好设置中授予辅助功能权限

## 安全提示

- **紧急停止**: 将鼠标快速移动到屏幕左上角
- **正常停止**: 点击界面上的"停止运行"按钮
"""
    
    readme_path = dist_dir / '使用说明.md'
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"用户说明已创建: {readme_path}")


def create_startup_script(dist_dir: Path):
    """创建启动脚本（方便用户使用）"""
    
    if platform.system() == 'Darwin':
        # macOS 启动脚本
        script_content = '''#!/bin/bash
# 微信公众号自动评论机器人启动脚本

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 检查 Ollama 是否在运行
if ! pgrep -x "ollama" > /dev/null; then
    echo "警告: Ollama 服务似乎没有运行"
    echo "请先在终端运行: ollama serve"
    echo ""
    read -p "按回车键继续（如果 Ollama 已在其他终端运行）..."
fi

# 启动应用
./微信公众号评论机器人
'''
        script_path = dist_dir / '启动.command'
        script_path.write_text(script_content, encoding='utf-8')
        os.chmod(script_path, 0o755)
        print(f"启动脚本已创建: {script_path}")
        
    else:
        # Windows 启动脚本
        script_content = '''@echo off
chcp 65001 >nul
title 微信公众号自动评论机器人

echo 正在检查 Ollama 服务...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [警告] Ollama 服务似乎没有运行
    echo 请先启动 Ollama 服务
    echo.
    pause
)

echo 正在启动应用...
start "" "微信公众号评论机器人.exe"
'''
        script_path = dist_dir / '启动.bat'
        script_path.write_text(script_content, encoding='gbk')
        print(f"启动脚本已创建: {script_path}")


def main():
    parser = argparse.ArgumentParser(description='微信公众号自动评论机器人 - 打包脚本')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出目录（默认为 dist/）')
    parser.add_argument('--no-clean', action='store_true',
                        help='不清理之前的构建目录')
    args = parser.parse_args()
    
    project_root = get_project_root()
    dist_dir = Path(args.output) if args.output else project_root / 'dist'
    
    print("=" * 60)
    print("微信公众号自动评论机器人 - 打包脚本")
    print("=" * 60)
    print(f"项目目录: {project_root}")
    print(f"输出目录: {dist_dir}")
    print(f"操作系统: {platform.system()}")
    print("=" * 60)
    
    # 1. 清理构建目录
    if not args.no_clean:
        print("\n[1/4] 清理构建目录...")
        clean_build_dirs(project_root)
    
    # 2. 运行 PyInstaller
    print("\n[2/4] 运行 PyInstaller 打包...")
    run_pyinstaller(project_root, dist_dir if args.output else None)
    
    # 3. 复制用户文件
    print("\n[3/4] 复制配置文件...")
    copy_user_files(project_root, dist_dir)
    
    # 4. 创建用户文档和启动脚本
    print("\n[4/4] 创建用户文档...")
    create_readme_for_users(dist_dir)
    create_startup_script(dist_dir)
    
    print("\n" + "=" * 60)
    print("打包完成！")
    print("=" * 60)
    print(f"\n输出目录: {dist_dir}")
    print("\n分发时请将整个 dist 目录打包给用户。")
    print("用户使用前需要：")
    print("  1. 安装 Ollama (https://ollama.com)")
    print("  2. 运行 'ollama pull qwen2.5:3b' 下载模型")
    print("  3. 运行 'ollama serve' 启动服务")
    print("  4. 双击应用程序启动")


if __name__ == '__main__':
    main()
