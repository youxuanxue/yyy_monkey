# -*- mode: python ; coding: utf-8 -*-
"""
微信公众号自动评论机器人 - PyInstaller 打包配置

这个 spec 文件用于将 web_app.py 打包成独立可执行文件。
包含所有依赖（cnocr/cnstd 模型、NiceGUI 资源等），但不包含 Ollama。

使用方法：
    uv run pyinstaller WeChatAutoComment.spec

打包输出在 dist/ 目录下。
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 获取项目根目录
SPEC_ROOT = os.path.dirname(os.path.abspath(SPEC))

# ============================
# 收集隐藏导入（动态导入的模块）
# ============================
hiddenimports = []

# NiceGUI 相关
hiddenimports += collect_submodules('nicegui')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('httptools')
hiddenimports += collect_submodules('websockets')

# OCR 相关
hiddenimports += collect_submodules('cnocr')
hiddenimports += collect_submodules('cnstd')
hiddenimports += collect_submodules('onnxruntime')

# 图像处理
hiddenimports += collect_submodules('PIL')
hiddenimports += collect_submodules('cv2')

# 其他
hiddenimports += ['pyautogui', 'pyperclip', 'numpy', 'openai', 'requests']

# ============================
# 收集数据文件
# ============================
datas = []

# 1. 项目资源文件（图片识别用）
datas.append((os.path.join(SPEC_ROOT, 'assets'), 'assets'))

# 2. 默认配置文件模板
# 注意：用户配置会在运行时创建到可执行文件旁边的 config 目录
config_src = os.path.join(SPEC_ROOT, 'config')
if os.path.exists(config_src):
    # 只包含模板文件，不包含历史记录
    for f in ['task_prompt.json', 'calibration.json', 'calibration-win.json']:
        fp = os.path.join(config_src, f)
        if os.path.exists(fp):
            datas.append((fp, 'config'))

# 3. NiceGUI 静态资源
datas += collect_data_files('nicegui', include_py_files=False)

# 4. cnocr 模型文件
datas += collect_data_files('cnocr', include_py_files=False)
datas += collect_data_files('cnstd', include_py_files=False)

# 5. onnxruntime 相关文件
datas += collect_data_files('onnxruntime', include_py_files=False)

# 6. uvicorn 模板
datas += collect_data_files('uvicorn', include_py_files=False)

# 7. wechat_gzh 包本身
datas.append((os.path.join(SPEC_ROOT, 'wechat_gzh'), 'wechat_gzh'))

# ============================
# 分析配置
# ============================
a = Analysis(
    [os.path.join(SPEC_ROOT, 'web_app.py')],
    pathex=[SPEC_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库
        'matplotlib',
        'scipy',
        'pandas',
        'torch',
        'tensorflow',
        'keras',
        'jupyter',
        'IPython',
        'notebook',
    ],
    noarchive=False,
    optimize=0,
)

# ============================
# 打包配置
# ============================
pyz = PYZ(a.pure)

# 单文件模式（onefile）- 更便于分发
# 如果遇到问题，可以改用 onedir 模式
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='微信公众号评论机器人',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # macOS 特定配置
    icon=None,  # 可以设置 .icns 图标
)

# macOS 应用程序包 (.app)
# 取消注释以下内容来生成 .app 包（仅 macOS）
# app = BUNDLE(
#     exe,
#     name='微信公众号评论机器人.app',
#     icon=None,
#     bundle_identifier='com.wechat.autocomment',
#     info_plist={
#         'CFBundleShortVersionString': '0.1.0',
#         'CFBundleVersion': '0.1.0',
#         'NSHighResolutionCapable': True,
#         'NSAppleEventsUsageDescription': '需要控制微信客户端进行自动评论',
#         'NSAccessibilityUsageDescription': '需要辅助功能权限来控制鼠标和键盘',
#     },
# )
