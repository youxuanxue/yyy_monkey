# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# assets 目录在项目根目录 wechat/assets
# 数据文件在 wechat/data (如果有加密文件也可以添加)
# license 文件

a = Analysis(
    ['src/wechat_client/cli.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('data/*.txt', 'data'),
        ('data/*.json', 'data'),
        ('license.lic', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WeChatAutoLike',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WeChatAutoLike',
)



