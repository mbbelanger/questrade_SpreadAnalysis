# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Questrade Options Trading System
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('watchlist.txt.example', '.'),  # Include example watchlist
    ],
    hiddenimports=[
        'requests',
        'python-dotenv',
        'strategy_selector',
        'trade_generator',
        'position_tracker',
        'trade_executor',
        'cleanup_utils',
        'questrade_utils',
        'config',
        'risk_analysis',
        'trend_analysis',
        'order_manager',
        'trade_logger',
        'run_tests',
        'test_strategy_selector',
        'test_order_manager',
        'test_risk_analysis',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuestradeTrading',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path here if you have one
)
