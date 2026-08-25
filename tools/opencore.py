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
    vendor/opencore/<version>/    Sample.plist and the two Utilities
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
VENDOR = Path('vendor/opencore')
# the boot files, and then whatever is already in these folders
FIXED = ('BOOT/BOOTx64.efi', 'OC/OpenCore.efi')
FOLDERS = ('OC/Drivers', 'OC/Tools')


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
    for tool in ('ocvalidate', 'macserial'):
        if not (release / 'Utilities' / tool / tool).exists():
            return f'the release carries no {tool}'
    return None


def apply(version, release, changes):
    for _, here, incoming in changes:
        shutil.copy2(incoming, here)
    into = VENDOR / version
    into.mkdir(parents=True, exist_ok=True)
    shutil.copy2(release / 'Docs' / 'Sample.plist', into / 'Sample.plist')
    for tool in ('ocvalidate', 'macserial'):
        target = into / 'Utilities' / tool
        target.mkdir(parents=True, exist_ok=True)
        for built in (release / 'Utilities' / tool).iterdir():
            if built.is_file():
                shutil.copy2(built, target / built.name)
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
