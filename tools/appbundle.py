"""Wrap the published window in a macOS .app.

A bare Mach-O works, and everything about meeting it is wrong: double-clicking
it opens Terminal, the Dock shows a generic icon, and the menu bar says
"Avalonia Application" because nothing has told macOS otherwise. All three come
out of the same missing thing - an `Info.plist` - so this writes one.

    python3 tools/appbundle.py --from dist --out "Hackintosh EFI Builder.app"

`--from` is a published folder: the window, the native libraries beside it, and
the engine. They all move inside, because a .app that reads files next to
itself stops working the moment somebody drags it to Applications.

    Hackintosh EFI Builder.app/Contents/
        Info.plist
        MacOS/HackintoshEFIBuilder      the window, and its dylibs
        Resources/HackintoshEFIBuilder.icns
        Resources/EFIBuilderEngine/     the engine, found beside the window

It is ad-hoc signed at the end. On Apple silicon an unsigned binary does not
run at all, and the toolchain's own signature stops being valid the moment the
files are moved - so the last thing done here is sign what was assembled.
"""
import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

NAME = 'Hackintosh EFI Builder'
BINARY = 'HackintoshEFIBuilder'
ENGINE = 'EFIBuilderEngine'
ICNS = Path('gui/Assets/Icon/HackintoshEFIBuilder.icns')
IDENTIFIER = 'com.github.yusufklncc.hackintosh-efi-builder'


def plist(version):
    return {
        # CFBundleName is what the menu bar says. Without it macOS falls back
        # to the process name, which is how "Avalonia Application" ended up
        # in the menu bar of a program nobody named that.
        'CFBundleName': NAME,
        'CFBundleDisplayName': NAME,
        'CFBundleExecutable': BINARY,
        'CFBundleIdentifier': IDENTIFIER,
        'CFBundleIconFile': ICNS.name,
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': version,
        'CFBundleVersion': version,
        'CFBundleInfoDictionaryVersion': '6.0',
        'LSMinimumSystemVersion': '11.0',
        # it draws a window; without this it is a background process with no
        # Dock icon and no menu bar at all
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        # it writes an EFI folder and a recovery wherever the person points it
        'NSDesktopFolderUsageDescription':
            'to write the EFI folder where you asked for it',
        'NSRemovableVolumesUsageDescription':
            'to put the EFI and the installer on the USB stick you picked',
    }


def build(source, out, version, engine=True):
    source, out = Path(source), Path(out)
    window = source / BINARY
    if not window.exists():
        raise SystemExit(f'{window} is not there; publish the window first')
    # A bundle without the engine opens to "no engine found" and nothing else.
    # From a clone the window walks up and finds tools/setup.py, which is why
    # this is easy to miss: inside /Applications there is nothing above it.
    if engine and not (source / ENGINE).is_dir():
        raise SystemExit(f'{source / ENGINE} is not there. A .app carries the '
                         f'engine inside it - built from a clone the window '
                         f'finds one above itself, and once it is installed '
                         f'there is nothing above it. Pass --no-engine to make '
                         f'one anyway.')

    if out.exists():
        shutil.rmtree(out)
    macos = out / 'Contents' / 'MacOS'
    resources = out / 'Contents' / 'Resources'
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    # A keep-list, not a delete-list. The published folder is also where a
    # build writes its EFI and its notes, and a list of things to leave out is
    # a list somebody forgets to add to: NEXT-STEPS.txt and a .DS_Store went
    # into the first bundle this made.
    moved, left = [], []
    for item in sorted(source.iterdir()):
        if item.name == ENGINE and item.is_dir():
            shutil.copytree(item, resources / ENGINE, symlinks=True)
            moved.append(f'Resources/{ENGINE}/')
        elif item.is_file() and (item.name == BINARY or item.suffix == '.dylib'):
            shutil.copy2(item, macos / item.name)
            os.chmod(macos / item.name, item.stat().st_mode)
            moved.append(f'MacOS/{item.name}')
        else:
            left.append(item.name)

    if ICNS.exists():
        shutil.copy2(ICNS, resources / ICNS.name)
        moved.append(f'Resources/{ICNS.name}')

    with open(out / 'Contents' / 'Info.plist', 'wb') as fh:
        plistlib.dump(plist(version), fh)
    (out / 'Contents' / 'PkgInfo').write_text('APPL????', encoding='ascii')

    # last, because signing covers what is inside and moving a file after
    # invalidates it. Ad-hoc: there is no certificate, and on Apple silicon a
    # binary with no signature at all will not start.
    if sys.platform == 'darwin':
        done = subprocess.run(['codesign', '--force', '--deep', '--sign', '-',
                               str(out)], capture_output=True, text=True)
        if done.returncode != 0:
            print(f'  codesign said: {done.stderr.strip()[:200]}')
        else:
            moved.append('ad-hoc signed')
    for name in left:
        print(f'  left out  {name}')
    return moved


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from', dest='source', default='gui/dist',
                    help='the published folder to wrap')
    ap.add_argument('--out', default=f'{NAME}.app')
    ap.add_argument('--no-engine', action='store_true',
                    help='wrap the window without the engine, which only makes '
                         'sense for a bundle that will sit inside a clone')
    ap.add_argument('--version', default='1.0.7',
                    help='the OpenCore version this builds, which is the '
                         'release number')
    a = ap.parse_args(argv)
    for line in build(a.source, a.out, a.version, engine=not a.no_engine):
        print(f'  {line}')
    print(f'  -> {a.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
