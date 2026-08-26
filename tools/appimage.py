"""Wrap the published window in an AppImage, for Linux.

The same problem the .app solves, on the system with no agreed answer to it: a
folder of files is not how a program arrives. An AppImage is one file that runs
on whatever distribution somebody has, without installing anything - which is
the same promise the rest of this makes.

    python3 tools/appimage.py --from package --out HackintoshEFIBuilder.AppImage

It assembles the directory the format expects and then hands it to
`appimagetool`. Without that tool the AppDir is still written and named, so
what failed is the packing and not the packaging.

    AppDir/
        AppRun                        -> usr/bin/HackintoshEFIBuilder
        HackintoshEFIBuilder.desktop  what a menu shows
        HackintoshEFIBuilder.png      256px, the icon beside it
        usr/bin/                      the window, and the engine beside it

The engine stays *beside* the window rather than under Resources: on Linux the
window looks next to itself, and there is no bundle convention to follow.
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

NAME = 'Hackintosh EFI Builder'
BINARY = 'HackintoshEFIBuilder'
ENGINE = 'EFIBuilderEngine'
ICON = Path('gui/Assets/Icon/png/icon-256.png')

DESKTOP = f"""[Desktop Entry]
Type=Application
Name={NAME}
Comment=Build the OpenCore EFI folder this machine needs
Exec={BINARY}
Icon={BINARY}
Terminal=false
Categories=Utility;System;
"""

# exec, not source: the window is a binary, and $APPDIR is where the format
# unpacks itself
APPRUN = f"""#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/{BINARY}" "$@"
"""


def assemble(source, appdir):
    """Write the AppDir. Returns what went in, and what was left out."""
    source, appdir = Path(source), Path(appdir)
    window = source / BINARY
    if not window.exists():
        raise SystemExit(f'{window} is not there; publish the window first')
    if not (source / ENGINE).is_dir():
        raise SystemExit(f'{source / ENGINE} is not there. The window runs the '
                         f'engine; one without the other ships nothing that '
                         f'works.')

    if appdir.exists():
        shutil.rmtree(appdir)
    binaries = appdir / 'usr' / 'bin'
    binaries.mkdir(parents=True)

    # a keep-list, for the reason the .app has one: the published folder is
    # also where an exercised build writes its EFI and its notes
    put, left = [], []
    for item in sorted(source.iterdir()):
        if item.name == ENGINE and item.is_dir():
            shutil.copytree(item, binaries / ENGINE, symlinks=True)
            put.append(f'usr/bin/{ENGINE}/')
        elif item.is_file() and (item.name == BINARY or item.suffix == '.so'):
            shutil.copy2(item, binaries / item.name)
            os.chmod(binaries / item.name, item.stat().st_mode)
            put.append(f'usr/bin/{item.name}')
        else:
            left.append(item.name)

    (appdir / f'{BINARY}.desktop').write_text(DESKTOP, encoding='utf-8')
    put.append(f'{BINARY}.desktop')
    if ICON.exists():
        shutil.copy2(ICON, appdir / f'{BINARY}.png')
        put.append(f'{BINARY}.png')

    run = appdir / 'AppRun'
    run.write_text(APPRUN, encoding='utf-8')
    run.chmod(run.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    put.append('AppRun')
    return put, left


def pack(appdir, out):
    """Hand the AppDir to appimagetool, if it is here.

    `--appimage-extract-and-run` because the tool is itself an AppImage and a
    build machine usually has no FUSE for it to mount with."""
    tool = shutil.which('appimagetool')
    if not tool:
        return None, ('appimagetool is not on this machine, so the AppDir was '
                      'written but not packed')
    done = subprocess.run([tool, '--appimage-extract-and-run', str(appdir), str(out)],
                          capture_output=True, text=True,
                          env={**os.environ, 'ARCH': os.uname().machine})
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
        return None, 'appimagetool: ' + ' / '.join(tail)
    return Path(out), None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from', dest='source', default='package')
    ap.add_argument('--appdir', default='AppDir')
    ap.add_argument('--out', default=f'{BINARY}.AppImage')
    a = ap.parse_args(argv)

    put, left = assemble(a.source, a.appdir)
    for name in left:
        print(f'  left out  {name}')
    for name in put:
        print(f'  {name}')

    made, complaint = pack(a.appdir, a.out)
    if complaint:
        print(f'  {complaint}')
        return 1
    print(f'  -> {made}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
