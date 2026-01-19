# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/xuejiao/Codes/yyy_monkey/wechat_gzh/gui_app.py'],
    pathex=[],
    binaries=[('/Users/xuejiao/.local/share/uv/python/cpython-3.13.0-macos-aarch64-none/lib/python3.13/tkinter', 'tkinter')],
    datas=[],
    hiddenimports=['pyautogui', 'PIL', 'tiktoken', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.scrolledtext'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WeChatAutoComment',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WeChatAutoComment',
)
app = BUNDLE(
    coll,
    name='WeChatAutoComment.app',
    icon=None,
    bundle_identifier=None,
)
