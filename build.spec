# build.spec - PyInstaller spec para ArkRaidMonitor.exe
# Uso: pyinstaller build.spec

import os
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('config.json', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageTk',
        'mss',
        'mss.windows',
        'pytesseract',
        'telegram',
        'telegram.ext',
        'requests',
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

# Incluir archivos de customtkinter (temas, fuentes)
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)
a.datas += [(os.path.join(ctk_path, f), os.path.join('customtkinter', f))
            for f in os.listdir(ctk_path)
            if os.path.isfile(os.path.join(ctk_path, f))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ArkRaidMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    onefile=True,
)
