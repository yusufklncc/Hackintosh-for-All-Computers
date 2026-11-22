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


def intact(folder):
    """Whether a BaseSystem.dmg in this folder matches its chunklist.

    macrecovery's own check, the one it runs after every download."""
    folder = Path(folder)
    dmg, cnk = folder / 'BaseSystem.dmg', folder / 'BaseSystem.chunklist'
    if not (dmg.exists() and cnk.exists()):
        return False
    tool = recovery.vendored()
    if tool is None:
        return False
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            recovery._load(tool).verify_image(str(dmg), str(cnk))
        return True
    except Exception:          # a short or damaged image raises; fetch it again
        return False


def plan(row):
    """What goes where for this macOS. Pure: no download, no disk."""
    rules = ocgen.read_toml(RULES)['recovery']
    darwin = darwin_of(row)
    older = darwin is not None and darwin >= rules['boots_from_older_from_darwin']
    # High Sierra to Catalina come as InstallESD, and Apple's package carries
    # its own BaseSystem: that is the recovery, and it needs nothing from
    # macrecovery - which has no Mojave to offer anyway
    packaged = row['major'].startswith('10.')
    return {
        'macos': row,
        'darwin': darwin,
        # the recovery the stick boots, and whether the target's own has to
        # travel on the ExFAT side for UnPlugged
        'boot_recovery': rules['boot_with'] if older else row['name'],
        'basesystem_on_exfat': older,
        'recovery_from_package': packaged,
    }


def steps(p):
    """What to do once the stick has booted, in UnPlugged's order."""
    big = stick.OFFLINE[1]
    if p.get('recovery_from_package'):
        approach = None
    elif p['basesystem_on_exfat']:
        approach = '"Extract the Install ... app from BaseSystem.dmg"'
    else:
        approach = '"Fully expand InstallAssistant.pkg"'
    booted = ('Monterey\'s recovery - Sonoma and later cannot read this stick from '
              'their own' if p['basesystem_on_exfat'] else
              f"{p['macos']['name']}'s recovery")
    return [
        f'Boot the stick and pick the recovery entry. It is {booted}.',
        'Disk Utility: View > Show All Devices, then erase the target *disk* '
        '(not a volume) as APFS with a GUID Partition Map. Quit Disk Utility.',
        f'Terminal: cd /Volumes/{big} and then bash UnPlugged.command',
        (f'When it asks where the installer comes from, choose {approach}.'
         if approach else
         'It finds InstallESDDmg.pkg and the files beside it by itself; '
         'check what it lists and go on.'),
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

    if p['recovery_from_package']:
        return _from_package(p, row, fat, exfat, work, g, say)

    say(f'{BOLD}Recovery to boot: {p["boot_recovery"]}{RESET}')
    choice = recovery.find(p['boot_recovery'])
    if not choice:
        return p, f'{p["boot_recovery"]} is not in macrecovery\'s board list'
    if intact(fat / recovery.FOLDER):
        # a second go after the window closed: what is there already checks
        # out against Apple's chunklist, so 700 MB is not fetched again
        say(f'      {GREEN}already on the stick, and it checks out{RESET}')
    else:
        files, complaint = recovery.fetch(choice, fat)
        if complaint:
            return p, complaint

    if p['basesystem_on_exfat']:
        say(f'{BOLD}{row["name"]}\'s BaseSystem, for UnPlugged{RESET}')
        own = recovery.find(row['name'])
        if not own:
            return p, f'{row["name"]} is not in macrecovery\'s board list'
        if intact(exfat):
            say(f'      {GREEN}already on the stick, and it checks out{RESET}')
        else:
            with tempfile.TemporaryDirectory() as tmp:
                files, complaint = recovery.fetch(own, tmp)
                if complaint:
                    return p, complaint
                for f in (Path(tmp) / recovery.FOLDER).glob('BaseSystem.*'):
                    shutil.copy2(f, exfat / f.name)

    complaint = _installer(row, exfat, work, g, say)
    return p, complaint or None


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
                    'size': r['size'], 'newest': r['newest'],
                    'boots': ('its own, from the package' if p['recovery_from_package']
                              else p['boot_recovery']),
                    'steps': steps(p)})
    return {'macos': out, 'complaint': ''}


def _installer(row, exfat, work, g, say):
    say(f'{BOLD}{row["name"]} {row["version"]} ({row["build"]}) from Apple, '
        f'{fullinstaller.size_text(row["size"])}{RESET}')
    if g is None:
        g, complaint = fullinstaller.catalog(Path(work or tempfile.mkdtemp()) / 'gibmacos')
        if not g:
            return complaint
    complaint = fullinstaller.fetch(g, row, exfat)[1]
    if complaint:
        return complaint
    say(f'{BOLD}Checking it against Apple\'s integrity data{RESET}')
    return fullinstaller.check(row, exfat, say=lambda s: say(f'      {s}'))


def _from_package(p, row, fat, exfat, work, g, say):
    """High Sierra to Catalina: the installer, then its own BaseSystem as the
    recovery. Apple checks a BaseSystem against its chunklist; both travel."""
    complaint = _installer(row, exfat, work, g, say)
    if complaint:
        return p, complaint
    found = sorted(Path(exfat).glob('BaseSystem.*'))
    if not any(f.suffix == '.dmg' for f in found):
        return p, f'Apple\'s {row["name"]} package came without a BaseSystem.dmg'
    target = Path(fat) / recovery.FOLDER
    target.mkdir(parents=True, exist_ok=True)
    for f in found:
        shutil.copy2(f, target / f.name)
    say(f'      {GREEN}its BaseSystem is the recovery, in {target}{RESET}')
    return p, None


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
            boots = ('its own recovery, from the package' if p['recovery_from_package']
                     else f"{p['boot_recovery']}'s recovery")
            print(f"  {r['name']:14} {r['version']:10} {r['build']:9} "
                  f"{fullinstaller.size_text(r['size']):>9}   boots {boots}")
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
