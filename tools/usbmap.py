"""Run the vendored USBToolBox and take the map it writes.

A USB port map cannot be worked out from a device listing. It takes plugging
something into every port in turn and watching which entry lights up, which is
what USBToolBox does and what this cannot. So the tool is vendored whole and
driven: nothing here reimplements it, and the kext it writes is the kext that
goes in.

Two details from its own code decide how it has to be run. `shared.current_dir`
is `Path(sys.executable).parent` for a frozen build, so it writes the map beside
itself - which would be inside the unpacked bundle, and gone the moment this
program exits. And it writes one of three names depending on which classes were
chosen, only one of which needs USBToolBox.kext alongside it.

    python3 tools/usbmap.py --out somewhere      # run it and keep the result
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

LOCK = Path('vendor/tools.lock')
TOOL = 'USBToolBox/Windows.exe'
VENDOR = Path('vendor/tools')

# Which of the three it wrote says what else the EFI needs. UTBMap rides on
# USBToolBox.kext; the native maps do not, and shipping it with them would put
# a driver in for hardware nothing is claiming.
OUTPUTS = {
    'UTBMap.kext': {'needs': ['USBToolBox.kext'], 'drops': ['UTBDefault.kext']},
    'USBMap.kext': {'needs': [], 'drops': ['UTBDefault.kext', 'USBToolBox.kext']},
    'USBMapLegacy.kext': {'needs': [], 'drops': ['UTBDefault.kext', 'USBToolBox.kext']},
}


def available():
    """The vendored tool, if it is here and intact."""
    path = VENDOR / TOOL
    if not path.exists() or not LOCK.exists():
        return None
    return path


def verify(path):
    """(ok, complaint) - the file has to be the one that was checked."""
    entry = ocgen.read_toml(LOCK)['tool'].get(TOOL)
    if not entry:
        return False, f'{TOOL} is not in {LOCK}'
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != entry['sha256']:
        return False, (f'{path} does not match the hash in {LOCK}; '
                       f'expected {entry["sha256"][:12]}, found {got[:12]}')
    return True, entry['version']


def runnable_here():
    """Whether the vendored build can run on this system at all."""
    return sys.platform == 'win32'


def run(work_dir):
    """Run it in a directory of ours and return (kext path, what it implies).

    The directory is ours rather than the bundle's because the tool writes
    beside its own executable, and a frozen bundle is a temporary directory that
    disappears."""
    tool = available()
    if not tool:
        return None, f'{VENDOR / TOOL} is not here'
    ok, detail = verify(tool)
    if not ok:
        return None, detail

    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    local = work / 'USBToolBox.exe'
    shutil.copy2(tool, local)
    shutil.copy2(tool.parent / 'LICENSE', work / 'USBToolBox-LICENSE.txt')

    # inherit the terminal: the whole point is that a person answers its menus
    result = subprocess.run([str(local)], cwd=str(work), check=False)
    local.unlink(missing_ok=True)

    for name, implies in OUTPUTS.items():
        made = work / name
        if (made / 'Contents' / 'Info.plist').exists():
            return made, implies
    return None, ('no map was written'
                  + (f' (it exited {result.returncode})' if result.returncode else ''))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='build/usbmap', help='where to run it')
    a = ap.parse_args(argv)
    tool = available()
    if not tool:
        sys.exit(f'{VENDOR / TOOL} is not here')
    ok, detail = verify(tool)
    print(f'  {TOOL}  {"v" + detail if ok else detail}')
    if not ok:
        return 1
    if not runnable_here():
        print(f'  it is a Windows build, and this is {sys.platform}')
        return 0
    made, implies = run(a.out)
    if not made:
        print(f'  {implies}')
        return 1
    print(f'  wrote {made}')
    print(f'  build with: setup.py --usb-map {made}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
