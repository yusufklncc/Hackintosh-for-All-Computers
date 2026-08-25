"""Move this repository to a new OpenCore release.

Everything an EFI is built from comes out of one release: the boot files, the
drivers, the tools, the Sample.plist every config is layered onto, and the
ocvalidate that checks the result. Updating any of them separately is how a
config drifts from the OpenCore it will run under, so this does all of it at
once and refuses to do half.

    python3 tools/opencore.py 1.0.7          # what would change
    python3 tools/opencore.py 1.0.7 --write  # change it

What it touches:

    EFI/BOOT/BOOTx64.efi          replaced from the release
    EFI/OC/OpenCore.efi           replaced
    EFI/OC/Drivers/*.efi          the ones already here, replaced
    EFI/OC/Tools/*.efi            the ones already here, replaced
    vendor/opencore/<version>/    Sample.plist, the two Utilities, macrecovery
    profiles/catalogue.toml       rehashed, if the new sample changed anything
                                  the profiles actually layer onto

Only files already present are replaced. A release ships eighty drivers and
this repository uses six; taking all of them would put drivers in an EFI that
nobody chose. Adding one is a decision, and a decision is not an update.

Needs the network for the download. Nothing else here does.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_oc
import ocgen

EFI = Path('EFI')
# The drivers OpenCore does not build. HfsPlus.efi lives in acidanthera's
# OcBinaryData and ships on its own schedule, which is why an OpenCore bump
# leaves it alone - and why it needs a step of its own or it never moves.
BINARY_DATA = 'https://raw.githubusercontent.com/acidanthera/OcBinaryData/master'
BINARY_LOCK = Path('vendor/ocbinarydata.lock')
VENDOR = Path('vendor/opencore')
# the boot files, and then whatever is already in these folders
FIXED = ('BOOT/BOOTx64.efi', 'OC/OpenCore.efi')
FOLDERS = ('OC/Drivers', 'OC/Tools')
# Utilities that are programs, vendored whole so the build never needs a
# download, and macrecovery, which is a script plus the board list it reads.
# recovery.py drives it; boards.json is where the version list comes from, so
# taking the script without it would leave us keeping a list of our own.
PROGRAMS = ('ocvalidate', 'macserial')
SCRIPTS = {'macrecovery': ('macrecovery.py', 'boards.json', 'README.md')}


def binaries():
    """Refresh the drivers that come from OcBinaryData, and record them.

    Only the ones already here. Their repository states no licence at all, and
    in this one the absence of a licence is not permission - so this updates
    what is already shipped and writes down that nobody has said what may be
    done with it, rather than quietly adding more."""
    import hashlib
    import urllib.error
    import urllib.request

    here = sorted(p for p in (EFI / 'OC' / 'Drivers').glob('Hfs*.efi'))
    if not here:
        return []
    rows, moved = [], 0
    for driver in here:
        url = f'{BINARY_DATA}/Drivers/{driver.name}'
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                incoming = r.read()
        except urllib.error.URLError:
            import shutil as _sh
            import subprocess as _sub
            if not _sh.which('curl'):
                raise
            got = _sub.run(['curl', '-sSL', '--max-time', '120', url],
                           capture_output=True)
            if got.returncode != 0 or not got.stdout:
                sys.exit(f'could not read {url}')
            incoming = got.stdout
        before = hashlib.sha256(driver.read_bytes()).hexdigest()
        after = hashlib.sha256(incoming).hexdigest()
        if before != after:
            driver.write_bytes(incoming)
            moved += 1
        rows.append({'file': f'OC/Drivers/{driver.name}', 'sha256': after})
        print(f'  {"->  " if before != after else "same"}  '
              f'OC/Drivers/{driver.name:<22} {before[:12]} '
              f'{after[:12] if before != after else ""}')
    ocgen.write_toml(BINARY_LOCK, {
        'source': 'https://github.com/acidanthera/OcBinaryData',
        'licence': 'none stated',
        'driver': rows,
    }, "# Drivers this repository ships that OpenCore does not build.\n"
       "#\n"
       "# Refreshed by tools/opencore.py alongside an OpenCore bump, because\n"
       "# they ship on their own schedule and would otherwise never move.\n"
       "#\n"
       "# The project states no licence. That is recorded rather than read as\n"
       "# permission: these files were already here before anybody looked, and\n"
       "# this says so instead of pretending the question was settled.\n")
    print(f'  {moved} of {len(rows)} moved -> {BINARY_LOCK}')
    return rows


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None


def plan(release):
    """[(relative path, from, to)] for every file this would replace."""
    source = release / 'X64' / 'EFI'
    out = []
    for name in FIXED:
        out.append((name, EFI / name, source / name))
    for folder in FOLDERS:
        for here in sorted((EFI / folder).glob('*.efi')):
            out.append((f'{folder}/{here.name}', here, source / folder / here.name))
    return out


def split(changes):
    """(from this release, from somewhere else).

    Not everything in EFI/OC/Drivers comes from OpenCore. HfsPlus.efi is
    acidanthera's OcBinaryData and ships on its own schedule, so an OpenCore
    bump has nothing to say about it. Replacing it would mean deleting it."""
    ours = [c for c in changes if c[2].exists()]
    theirs = [c for c in changes if not c[2].exists()]
    return ours, theirs


def check(release, changes):
    """Complain about anything the release cannot supply."""
    for name, _, incoming in changes:
        if name in FIXED and not incoming.exists():
            return f'the release does not carry {name}, which every EFI needs'
    if not (release / 'Docs' / 'Sample.plist').exists():
        return 'the release carries no Sample.plist'
    for tool in PROGRAMS:
        if not (release / 'Utilities' / tool / tool).exists():
            return f'the release carries no {tool}'
    for tool, wanted in SCRIPTS.items():
        for name in wanted:
            if not (release / 'Utilities' / tool / name).exists():
                return f'the release carries no {tool}/{name}'
    return None


def apply(version, release, changes):
    for _, here, incoming in changes:
        shutil.copy2(incoming, here)
    into = VENDOR / version
    into.mkdir(parents=True, exist_ok=True)
    shutil.copy2(release / 'Docs' / 'Sample.plist', into / 'Sample.plist')
    for tool, wanted in SCRIPTS.items():
        target = into / 'Utilities' / tool
        target.mkdir(parents=True, exist_ok=True)
        for name in wanted:
            shutil.copy2(release / 'Utilities' / tool / name, target / name)
    for tool in PROGRAMS:
        target = into / 'Utilities' / tool
        target.mkdir(parents=True, exist_ok=True)
        for built in (release / 'Utilities' / tool).iterdir():
            if not built.is_file():
                continue
            copied = target / built.name
            shutil.copy2(built, copied)
            # a program has to be runnable wherever it came from. Git records
            # the bit and a missing one is not visible until the build stops.
            if copied.suffix != '.exe' and copied.name.startswith(tool):
                copied.chmod(0o755)
    # The sample decides what every config is layered onto, and the newest
    # vendored one is the one a build picks. Two of them would mean the answer
    # depends on which sorts last, which is not a thing anybody should have to
    # know.
    for old in sorted(VENDOR.iterdir()):
        if old.is_dir() and old.name != version:
            shutil.rmtree(old)


def regenerate():
    """Rewrite the catalogue hashes from what the profiles now produce.

    verify.py --rehash, not extract.py --catalogue. The second one reads an
    existing tree of config files and writes profiles from it - the direction
    this repository was built in, once. Run against a tree that is not there it
    records that the profiles produce nothing, which is how it emptied the
    catalogue the first time this was written."""
    return subprocess.run([sys.executable, 'tools/verify.py', '--rehash'],
                          capture_output=True, text=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('version', help='an OpenCore tag, or "latest"')
    ap.add_argument('--write', action='store_true',
                    help='make the changes; without it, only say what they are')
    a = ap.parse_args(argv)

    have = sorted(p.name for p in VENDOR.iterdir() if p.is_dir())
    tag, release = fetch_oc.fetch(a.version)
    print(f'{", ".join(have) or "nothing"} vendored now; this release is {tag}')

    changes = plan(release)
    complaint = check(release, changes)
    if complaint:
        sys.exit(complaint)
    changes, foreign = split(changes)
    for name, _, _ in foreign:
        print(f'  left    {name:<34} not part of an OpenCore release')

    moved = [(name, digest(here), digest(incoming))
             for name, here, incoming in changes]
    for name, before, after in moved:
        print(f'  {"same" if before == after else "->  "}  {name:<34} '
              f'{before} {"" if before == after else after}')
    print(f'  {sum(1 for _, b, c in moved if b != c)} of {len(moved)} binaries differ')

    if not a.write:
        print('\nNothing was changed. Pass --write to do it, then read the diff.')
        print('  The catalogue is rehashed afterwards. Whether any hash moves')
        print('  depends on the new Sample.plist: 1.0.5 to 1.0.7 moved none of')
        print('  them, because nothing the profiles layer onto changed.')
        return 0

    apply(tag, release, changes)
    print('\nthe drivers OpenCore does not build:')
    binaries()
    print(f'\nvendored {tag}; regenerating every config against its Sample.plist')
    done = regenerate()
    sys.stdout.write(done.stdout[-2000:])
    if done.returncode:
        sys.stderr.write(done.stderr[-2000:])
        sys.exit('the configs did not regenerate; nothing else was done')
    print('\nNow: python3 tools/selftest.py, then read the diff.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
