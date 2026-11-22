"""A stick that installs macOS with no network at all.

Recovery downloads the rest of macOS during the install, which is no help on a
machine macOS has no network driver for. corpnewt's UnPlugged answers that: the
whole installer goes on the stick, and a script run in recovery builds
`Install macOS.app` from it and starts it. This puts that stick together from
any system:

  FAT32 (about 1 GB)   EFI/, com.apple.recovery.boot/
  ExFAT (the rest)     InstallAssistant.pkg and its friends, UnPlugged.command,
                       and for Sonoma and later the target's BaseSystem.dmg

Sonoma and later need one more turn, quoted in data/unplugged.toml: their
recovery will not mount FAT32 or ExFAT, so the stick boots Monterey's recovery
and the target's own BaseSystem rides on the ExFAT side for UnPlugged to use.

    python3 tools/offline.py --list
    python3 tools/offline.py --macos sequoia --fat /Volumes/OPENCORE \\
        --exfat /Volumes/UNPLUGGED --efi build/EFI

--fat and --exfat are folders: a stick's two volumes, or two ordinary folders
to copy onto one later. Everything downloaded comes from Apple or from the
upstream projects; nothing of Apple's is in this repository.
"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fullinstaller  # noqa: E402
import ocgen  # noqa: E402
import recovery  # noqa: E402
import stick  # noqa: E402
import ui  # noqa: E402
import unplugged  # noqa: E402

BOLD, DIM, GREEN, YELLOW, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'reset')
RULES = Path('data/unplugged.toml')
SLACK = 1024 ** 3            # the small packages, and the room a copy needs


def darwin_of(row):
    for r in ocgen.read_toml(Path('data/macos.toml'))['release']:
        if r['version'] == row['major'] or r['name'].lower() == row['name'].lower():
            return r['darwin']
    return None


def plan(row):
    """What goes where for this macOS. Pure: no download, no disk."""
    rules = ocgen.read_toml(RULES)['recovery']
    darwin = darwin_of(row)
    older = darwin is not None and darwin >= rules['boots_from_older_from_darwin']
    return {
        'macos': row,
        'darwin': darwin,
        # the recovery the stick boots, and whether the target's own has to
        # travel on the ExFAT side for UnPlugged
        'boot_recovery': rules['boot_with'] if older else row['name'],
        'basesystem_on_exfat': older,
    }


def steps(p):
    """What to do once the stick has booted, in UnPlugged's order."""
    big = stick.OFFLINE[1]
    approach = ('"Extract the Install ... app from BaseSystem.dmg"'
                if p['basesystem_on_exfat'] else
                '"Fully expand InstallAssistant.pkg"')
    booted = ('Monterey\'s recovery - Sonoma and later cannot read this stick from '
              'their own' if p['basesystem_on_exfat'] else
              f"{p['macos']['name']}'s recovery")
    return [
        f'Boot the stick and pick the recovery entry. It is {booted}.',
        'Disk Utility: View > Show All Devices, then erase the target *disk* '
        '(not a volume) as APFS with a GUID Partition Map. Quit Disk Utility.',
        f'Terminal: cd /Volumes/{big} and then bash UnPlugged.command',
        f'When it asks where the installer comes from, choose {approach}.',
        'Pick the volume you just erased, type y, and leave Terminal open: '
        'closing it closes the installer.',
    ]


def check_room(exfat, row):
    need = (row['size'] if row['size'] > 0 else 0) + SLACK
    free = shutil.disk_usage(exfat).free
    if free < need:
        return (f'{exfat} has {free / 1e9:.1f} GB free and this needs about '
                f'{need / 1e9:.1f} GB')
    return None


def build(row, fat, exfat, efi=None, work=None, g=None, say=print):
    """Fill the two folders. Returns (plan, complaint)."""
    p = plan(row)
    fat, exfat = Path(fat), Path(exfat)
    for folder in (fat, exfat):
        if not folder.is_dir():
            return p, f'{folder} is not a folder this can write to'
    trouble = check_room(exfat, row)
    if trouble:
        return p, trouble

    say(f'{BOLD}UnPlugged.command{RESET}')
    path, complaint = unplugged.fetch(exfat)
    if complaint:
        return p, complaint
    say(f'      {GREEN}{path}{RESET}')

    if efi:
        written, complaint = stick.place(fat, efi=efi)
        if complaint:
            return p, complaint
        say(f'      {GREEN}EFI copied to {fat}{RESET}')

    say(f'{BOLD}Recovery to boot: {p["boot_recovery"]}{RESET}')
    choice = recovery.find(p['boot_recovery'])
    if not choice:
        return p, f'{p["boot_recovery"]} is not in macrecovery\'s board list'
    files, complaint = recovery.fetch(choice, fat)
    if complaint:
        return p, complaint

    if p['basesystem_on_exfat']:
        say(f'{BOLD}{row["name"]}\'s BaseSystem, for UnPlugged{RESET}')
        own = recovery.find(row['name'])
        if not own:
            return p, f'{row["name"]} is not in macrecovery\'s board list'
        with tempfile.TemporaryDirectory() as tmp:
            files, complaint = recovery.fetch(own, tmp)
            if complaint:
                return p, complaint
            for f in (Path(tmp) / recovery.FOLDER).glob('BaseSystem.*'):
                shutil.copy2(f, exfat / f.name)

    say(f'{BOLD}{row["name"]} {row["version"]} from Apple, '
        f'{fullinstaller.size_text(row["size"])}{RESET}')
    if g is None:
        g, complaint = fullinstaller.catalog(Path(work or tempfile.mkdtemp()) / 'gibmacos')
        if not g:
            return p, complaint
    files, complaint = fullinstaller.fetch(g, row, exfat)
    if complaint:
        return p, complaint
    return p, None


def listing(work=None):
    """What a front end draws: {'macos': [...], 'complaint': ''}."""
    work = Path(work or tempfile.mkdtemp())
    g, complaint = fullinstaller.catalog(work / 'gibmacos')
    if not g:
        return {'macos': [], 'complaint': complaint}
    out = []
    for r in fullinstaller.offered(g):
        p = plan(r)
        out.append({'name': r['name'], 'version': r['version'], 'build': r['build'],
                    'size': r['size'], 'boots': p['boot_recovery'],
                    'steps': steps(p)})
    return {'macos': out, 'complaint': ''}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--macos')
    ap.add_argument('--fat', help='the FAT32 volume, or a folder for it')
    ap.add_argument('--exfat', help='the ExFAT volume, or a folder for it')
    ap.add_argument('--efi', help='an EFI folder to put on the FAT32 side')
    ap.add_argument('--work', help='where gibMacOS keeps its catalog')
    a = ap.parse_args(argv)

    work = Path(a.work or tempfile.mkdtemp())
    g, complaint = fullinstaller.catalog(work / 'gibmacos')
    if not g:
        print(f'  {YELLOW}{complaint}{RESET}')
        return 1
    rows = fullinstaller.offered(g)
    if a.list or not a.macos:
        print(f'{BOLD}macOS that can be put on an offline stick{RESET}')
        for r in rows:
            p = plan(r)
            print(f"  {r['name']:14} {r['version']:10} {fullinstaller.size_text(r['size']):>9}"
                  f"   boots {p['boot_recovery']}'s recovery")
        return 0
    row = fullinstaller.find(rows, a.macos)
    if not row:
        print(f'  {YELLOW}{a.macos}: no installer by that name for Intel Macs{RESET}')
        return 1
    if not (a.fat and a.exfat):
        print(f'  {YELLOW}--fat and --exfat are both needed{RESET}')
        return 1
    p, complaint = build(row, a.fat, a.exfat, efi=a.efi, g=g)
    if complaint:
        print(f'  {YELLOW}{complaint}{RESET}')
        return 1
    print(f'\n{BOLD}In recovery{RESET}')
    for n, line in enumerate(steps(p), 1):
        print(f'  {n}. {line}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
