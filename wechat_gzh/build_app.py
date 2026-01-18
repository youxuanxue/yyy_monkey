import os
import sys
import shutil
import subprocess
import platform

def build():
    print("="*60)
    print("开始构建微信公众号自动评论机器人")
    print("="*60)

    # 1. 检查依赖
    try:
        import PyInstaller
    except ImportError:
        print("错误: 未安装 PyInstaller。请运行 'uv add pyinstaller'")
        return

    # 2. 路径配置
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) # wechat_gzh/
    
    # 入口文件
    entry_point = os.path.join(current_dir, "gui_app.py")
    
    # 输出名称
    app_name = "WeChatAutoComment"
    
    # 资源文件
    # 格式: (源路径, 目标路径)
    # 注意: Windows 下分隔符是 ; Mac/Linux 是 :
    sep = ";" if platform.system() == "Windows" else ":"
    
    add_data = []
    # 示例: add_data.append(f"{os.path.join(current_dir, 'assets')}{sep}assets")
    
    # 3. 构建 PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",  # 单目录模式（推荐，因为有大文件）
        "--windowed", # 无控制台窗口
        "--name", app_name,
        "--clean",
        # 添加隐藏导入（防止某些库未被检测到）
        "--hidden-import", "pyautogui",
        "--hidden-import", "PIL",
        "--hidden-import", "tiktoken",
        entry_point
    ]
    
    # 添加数据文件参数
    for data in add_data:
        cmd.extend(["--add-data", data])
        
    print(f"执行命令: {' '.join(cmd)}")
    
    # 4. 执行构建
    subprocess.run(cmd, check=True)
    
    print("\n构建完成，正在处理依赖文件...")
    
    # 5. 后处理：复制配置文件和模型目录到 dist 目录
    dist_dir = os.path.join("dist", app_name)
    if platform.system() == "Darwin":
        # macOS: dist/WeChatAutoComment/WeChatAutoComment.app/Contents/MacOS/
        # 但 onedir 模式下，pyinstaller 并没有生成标准的 .app bundle 结构（除非指定了 --contents-directory 等）
        # 默认的 onedir 在 mac 上生成的是: dist/WeChatAutoComment/WeChatAutoComment (exec) 和依赖
        # 如果是 --windowed，会生成 .app。
        # 这里我们需要确认 PyInstaller 在 macOS --windowed --onedir 下的行为。
        # 通常是 dist/WeChatAutoComment.app
        app_bundle = os.path.join("dist", f"{app_name}.app")
        if os.path.exists(app_bundle):
            print(f"检测到 macOS App Bundle: {app_bundle}")
            # 目标资源目录：App同级目录（为了方便用户修改配置）
            # 或者放到 dist/ 根目录下
            target_root = "dist" 
        else:
            target_root = dist_dir
    else:
        target_root = dist_dir

    # 需要复制的目录
    dirs_to_copy = ["config", "logs", "assets", "runtime"]
    
    for d in dirs_to_copy:
        src = os.path.join(current_dir, d)
        dst = os.path.join(target_root, d)
        
        if not os.path.exists(src):
            if d == "runtime":
                print(f"提示: runtime 目录不存在（未下载 Ollama/模型），跳过复制")
                continue
            if d == "logs":
                os.makedirs(dst, exist_ok=True)
                continue
                
        print(f"复制 {d} -> {dst}")
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    print("="*60)
    print(f"构建成功！可执行文件位于: {target_root}")
    print("请确保将 'runtime' 目录（包含 ollama 和模型）放置在与可执行文件同级的目录下。")
    print("="*60)

if __name__ == "__main__":
    build()
