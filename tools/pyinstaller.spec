# PyInstaller spec for the guided builder.
#
# Everything the tools read at runtime is bundled, so the executable is the
# whole thing: no clone, no Python, no downloads for the common path. setup.py
# chdirs into the unpacked bundle at startup, which is why the frozen build
# needs no separate code path.
import os

datas = [(d, d) for d in ('profiles', 'data', 'EFI', 'vendor')]

a = Analysis(
    ['tools/setup.py'],
    pathex=['tools'],
    datas=datas,
    hiddenimports=['advise', 'build', 'detect', 'itlwm', 'netkexts', 'ocgen'],
    excludes=['tkinter', 'unittest', 'pydoc_data', 'test'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='HackintoshEFIBuilder',
    console=True,
    upx=False,
    disable_windowed_traceback=False,
)
