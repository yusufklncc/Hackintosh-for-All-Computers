# PyInstaller spec for the guided builder.
#
# Everything the tools read at runtime is bundled, so the executable is the
# whole thing: no clone, no Python, no downloads for the common path. setup.py
# chdirs into the unpacked bundle at startup, which is why the frozen build
# needs no separate code path.
#
# Paths are built from SPECPATH rather than written relative. PyInstaller
# resolves a relative script path against the spec's own directory, and this
# spec lives in tools/, so 'tools/setup.py' would look for tools/tools/setup.py.
import os

ROOT = os.path.dirname(SPECPATH)          # SPECPATH is <repo>/tools
TOOLS = os.path.join(ROOT, 'tools')

datas = [(os.path.join(ROOT, d), d) for d in ('profiles', 'data', 'EFI', 'vendor')]

a = Analysis(
    [os.path.join(TOOLS, 'setup.py')],
    pathex=[TOOLS],
    datas=datas,
    hiddenimports=['advise', 'audio', 'build', 'detect', 'gpu', 'igpu',
                   'inputdev', 'itlwm', 'netkexts', 'ocgen', 'summary'],
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
