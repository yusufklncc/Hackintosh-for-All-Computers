"""Build a whole macOS installer image, from an installer app, on a Mac.

What the guide walks somebody through by hand, done in one run: measure the
app, make a disk image the right size, partition it MBR with a FAT32 EFI
partition first and an HFS+ volume after, let Apple's own `createinstallmedia`
fill the second, make the first bootable on a BIOS machine with OpenCore's own
DuetPkg, and drop the EFI folder in. What comes out is a flat sector image that
balenaEtcher writes on any system.

    python3 tools/installer.py --app "/Applications/Install macOS Tahoe.app" \\
        --efi build/EFI --out ~/tahoe.raw

macOS only, and it says so rather than half-working: `createinstallmedia` is an
Apple binary that ships inside the app.

Two of the steps need root and there is no way around that - `createinstallmedia`
blesses a volume and BootInstall writes a master boot record. Nothing here
escalates by itself: `--script` prints the privileged half for a person to run,
and the window asks macOS for one administrator prompt and runs the same text.
The two are the same script, so what a person is asked to approve is what they
could have read.

Sizes are in GiB throughout, because that is what `hdiutil` and `du` speak.
`diskutil` prints decimal GB, which is the same number said differently and the
reason a stick comes out short: see the guide.
"""
import argparse
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours(
    'bold', 'dim', 'green', 'yellow', 'red', 'reset')

GiB = 1024 ** 3
# What createinstallmedia wants beyond the app itself. Measured on Tahoe
# 26.6.2: du reported 17.00 GiB and the volume it accepted was 19.15 GiB. Most
# of the difference is the recovery it lays down beside the installer - its own
# output says "Copying the macOS RecoveryOS...". Rounded up, because being over
# costs disk space and being under costs the whole run.
OVERHEAD = 2.5 * GiB
EFI_SIZE = 500 * 10 ** 6           # the FAT32 partition, in diskutil's units
VOLUME = 'USB'                      # what the HFS+ partition is called until
                                    # createinstallmedia renames it
EFI_LABEL = 'EFI'


def on_mac():
    return sys.platform == 'darwin'


def app_size(app):
    """What the installer app takes, in bytes."""
    total = 0
    for root, _, files in os.walk(app):
        for name in files:
            p = Path(root) / name
            try:
                if not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                pass
    return total


def app_version(app):
    """(name, version) out of the app's own Info.plist, or (None, None)."""
    plist = Path(app) / 'Contents' / 'Info.plist'
    if not plist.exists():
        return None, None
    try:
        d = plistlib.loads(plist.read_bytes())
    except Exception:
        return None, None
    return d.get('CFBundleDisplayName'), d.get('CFBundleShortVersionString')


def plan(app):
    """How big the image has to be, and why. Sizes in bytes."""
    used = app_size(app)
    volume = used + OVERHEAD
    image = volume + EFI_SIZE
    # whole GiB, rounded up: hdiutil takes a number and a suffix, and a
    # fractional one is a way to be a hundred megabytes short
    gib = int(-(-image // GiB))
    return {'app': used, 'overhead': OVERHEAD, 'volume_needs': volume,
            'efi': EFI_SIZE, 'image': gib * GiB, 'gib': gib}


def creator(app):
    """The createinstallmedia inside an installer app, or None."""
    where = Path(app) / 'Contents' / 'Resources' / 'createinstallmedia'
    return where if where.exists() else None


def legacy_tools():
    """The vendored DuetPkg folder, or None. Driven, never reimplemented."""
    root = Path('vendor/opencore')
    if not root.is_dir():
        return None
    for version in sorted(root.iterdir()):
        where = version / 'Utilities' / 'LegacyBoot'
        if (where / 'BootInstall_X64.tool').exists():
            return where
    return None


def _run(*argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def create(into, gib):
    """An empty raw image of that many GiB. Returns (path, complaint)."""
    out = Path(into).expanduser()
    # hdiutil appends .dmg whatever it is asked for, so it is named without a
    # suffix here and renamed at the end to whatever was wanted
    stem = out.with_suffix('')
    made = stem.with_suffix('.dmg')
    if made.exists():
        return None, f'{made} is already there; move it or pick another name'
    done = _run('hdiutil', 'create', '-size', f'{gib}g', '-type', 'UDIF',
                '-layout', 'NONE', '-o', str(stem))
    if done.returncode:
        return None, f'the image could not be made: {done.stderr.strip()}'
    return made, None


def attach(image):
    """Attach without mounting. Returns (/dev/diskN, complaint)."""
    done = _run('hdiutil', 'attach', '-nomount', str(image))
    if done.returncode:
        return None, f'the image could not be attached: {done.stderr.strip()}'
    found = re.search(r'(/dev/disk\d+)', done.stdout)
    if not found:
        return None, f'nothing in hdiutil\'s answer looks like a disk: {done.stdout!r}'
    return found.group(1), None


def detach(device):
    _run('hdiutil', 'detach', str(device))


def partition(device):
    """MBR, FAT32 first, HFS+ for the rest.

    The order is not a preference. BootInstall looks at disk<N>s1 and refuses a
    disk whose first partition is not FAT32 - put the installer volume first
    and it stops on a layout that is otherwise perfectly good."""
    done = _run('diskutil', 'partitionDisk', str(device), 'MBR',
                'MS-DOS FAT32', EFI_LABEL, f'{EFI_SIZE // 10 ** 6}M',
                'JHFS+', VOLUME, 'R')
    if done.returncode:
        return f'the image could not be partitioned: {done.stderr.strip() or done.stdout.strip()}'
    return None


def mounted(label):
    """Where a volume of that name is, or None."""
    where = Path('/Volumes') / label
    return where if where.is_dir() else None


def privileged(app, device, legacy=True):
    """The half that needs root, as one script.

    One script and not two calls, so a person is asked to approve once and can
    read the whole of what they are approving. It is printed by --script and
    run by the window; neither builds a different one."""
    steps = [
        '#!/bin/sh',
        '# Written by tools/installer.py. Everything here needs root:',
        '#   createinstallmedia blesses a volume,',
        '#   BootInstall writes a master boot record.',
        'set -e',
        '',
        'echo "==> Writing the installer (this is the long part)"',
        f'{shlex.quote(str(creator(app)))} \\',
        f'  --volume {shlex.quote(f"/Volumes/{VOLUME}")} --nointeraction',
    ]
    tools = legacy_tools()
    if legacy and tools:
        number = re.sub(r'\D', '', Path(device).name)
        steps += [
            '',
            'echo "==> Making it bootable on a legacy BIOS"',
            f'cd {shlex.quote(str(tools.resolve()))}',
            # the tool asks which disk on stdin; it is driven, not reimplemented
            f'echo {number} | ./BootInstall_X64.tool',
        ]
    return '\n'.join(steps) + '\n'


def ask_macos(script, why):
    """Run a script under one administrator prompt.

    osascript is how a Mac asks. The window has no way to type a password into
    sudo, and running the whole engine as root to reach two commands would put
    everything else there too."""
    told = f'{why}'
    quoted = script.replace('\\', '\\\\').replace('"', '\\"')
    done = _run('osascript', '-e',
                f'do shell script "{quoted}" with prompt "{told}" '
                f'with administrator privileges')
    if done.returncode:
        said = (done.stderr or '').strip()
        if 'User canceled' in said or '-128' in said:
            return 'you cancelled the password prompt, so nothing was written'
        return said or 'the privileged step failed with nothing to say'
    return None


def place_efi(efi, label=EFI_LABEL):
    """The EFI folder onto the FAT32 partition, beside whatever boots it."""
    root = mounted(label)
    if root is None:
        return f'no volume called {label} is mounted'
    source = Path(efi).expanduser()
    if source.name.upper() != 'EFI' and (source / 'EFI').is_dir():
        source = source / 'EFI'
    if not (source / 'BOOT' / 'BOOTx64.efi').exists():
        return (f'{source} has no BOOT/BOOTx64.efi in it, so it is not an EFI '
                f'folder OpenCore would boot')
    target = root / 'EFI'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return None


def _size(n):
    return f'{n / GiB:.2f} GiB' if n >= GiB else f'{n / 10 ** 6:.0f} MB'


def describe(app):
    """What would be done, without doing any of it."""
    name, version = app_version(app)
    p = plan(app)
    return {'name': name, 'version': version, **p,
            'creator': str(creator(app)) if creator(app) else None,
            'legacy': str(legacy_tools()) if legacy_tools() else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--app', help='the Install macOS ....app to build from')
    ap.add_argument('--efi', help='the EFI folder to put on it')
    ap.add_argument('--out', help='where the image goes')
    ap.add_argument('--no-legacy', action='store_true',
                    help='skip the DuetPkg step; UEFI machines do not need it')
    ap.add_argument('--plan', action='store_true',
                    help='say what would be done and what size, and stop')
    ap.add_argument('--script', action='store_true',
                    help='print the part that needs root, to run yourself')
    ap.add_argument('--json', action='store_true', help='for a front end')
    a = ap.parse_args(argv)

    if not on_mac():
        said = ('This builds a macOS installer with Apple\'s own '
                'createinstallmedia, which only runs on macOS.')
        print(json.dumps({'t': 'installer', 'available': False,
                          'why': said}) if a.json else f'{YELLOW}{said}{RESET}')
        return 1

    if not a.app:
        ap.error('--app is needed')
    app = Path(a.app).expanduser()
    if not app.is_dir() or creator(app) is None:
        said = f'{app} is not a macOS installer app: it has no createinstallmedia in it'
        print(json.dumps({'t': 'installer', 'available': False, 'why': said})
              if a.json else f'{YELLOW}{said}{RESET}')
        return 1

    told = describe(app)
    if a.json and a.plan:
        print(json.dumps({'t': 'installer', 'available': True, **told}))
        return 0

    if a.plan or not a.out:
        print(f'{BOLD}{told["name"] or app.name} {told["version"] or ""}{RESET}')
        print(f'  the app is           {_size(told["app"]):>12}')
        print(f'  createinstallmedia wants about {_size(told["overhead"])} more')
        print(f'  so the volume needs  {_size(told["volume_needs"]):>12}')
        print(f'  plus an EFI partition of {_size(told["efi"])}')
        print(f'  {GREEN}image: {told["gib"]} GiB{RESET}')
        print(f'{DIM}  hdiutil and du count in GiB; diskutil prints decimal GB, '
              f'which is\n  the same number said differently.{RESET}')
        if not a.out:
            return 0

    if a.script:
        print(privileged(app, '/dev/diskN', legacy=not a.no_legacy))
        return 0

    made, complaint = create(a.out, told['gib'])
    if complaint:
        print(f'{YELLOW}{complaint}{RESET}')
        return 1
    print(f'  made {made}')

    device, complaint = attach(made)
    if complaint:
        print(f'{YELLOW}{complaint}{RESET}')
        return 1
    print(f'  attached as {device}')

    try:
        complaint = partition(device)
        if complaint:
            print(f'{YELLOW}{complaint}{RESET}')
            return 1
        print(f'  partitioned {device}: {EFI_LABEL} then {VOLUME}')

        script = privileged(app, device, legacy=not a.no_legacy)
        print(f'\n{BOLD}This next part needs an administrator password{RESET}')
        print(f'{DIM}  createinstallmedia blesses a volume and BootInstall '
              f'writes a master\n  boot record; neither can be done without '
              f'it. Run it yourself with\n  --script if you would rather.{RESET}')
        complaint = ask_macos(script, 'Build the macOS installer image')
        if complaint:
            print(f'{YELLOW}{complaint}{RESET}')
            return 1

        if a.efi:
            complaint = place_efi(a.efi)
            if complaint:
                print(f'{YELLOW}{complaint}{RESET}')
                return 1
            print(f'  put the EFI folder on {EFI_LABEL}')
    finally:
        detach(device)

    final = Path(a.out).expanduser()
    if final != made:
        made.rename(final)
    print(f'\n  {GREEN}{final} is ready{RESET}')
    print(f'{DIM}  It is a flat sector image: rename it .raw or .img and '
          f'balenaEtcher\n  writes it from Windows, Linux or macOS.{RESET}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
