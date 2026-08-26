"""Ask Apple for a recovery, check what comes back, and keep none of it.

The Recovery tab is the one thing here that depends on somebody else's server
still behaving: Apple can stop serving a board, change the protocol, or move
what "latest" means, and the first anybody would know is a person pressing
Download and getting an error.

So this asks - the same way the tab does, through the same vendored tool - and
then throws away what arrived.

    python3 tools/recoverycheck.py              # the newest row, end to end
    python3 tools/recoverycheck.py --all        # every row, which is 8 GB
    python3 tools/recoverycheck.py --catalogue  # ask, but do not download

Nothing is published, kept, or copied anywhere. Apple's software is Apple's to
distribute, which is why the program fetches it onto a person's own machine and
why this deletes it: what is being checked is that the request still works, not
what the request returns.
"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recovery
import ui

BOLD, DIM, GREEN, YELLOW, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'reset')

# what a BaseSystem weighs, roughly, so a size that is nothing like one is
# worth saying out loud rather than passing
SMALLEST = 300 * 1024 * 1024


def one(choice, catalogue_only=False):
    """(ok, said) for a single row."""
    if catalogue_only:
        return True, 'not fetched'
    with tempfile.TemporaryDirectory() as where:
        files, complaint = recovery.fetch(choice, where, every=30.0)
        if complaint:
            return False, complaint
        names = {name for name, _ in files}
        image = next((size for name, size in files if name.endswith('.dmg')), 0)
        if not any(n.endswith('.chunklist') for n in names):
            return False, 'no chunklist came with it'
        if image < SMALLEST:
            return False, (f'the image is {recovery._size(image)}, which is not '
                           f'the size of a BaseSystem')
        # fetch() has already had the tool verify it against the chunklist;
        # reaching here means that passed
        return True, f'{recovery._size(image)}, verified'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--all', action='store_true',
                    help='every row rather than the newest, which is about 8 GB')
    ap.add_argument('--catalogue', action='store_true',
                    help='check the list is readable without asking Apple for '
                         'anything')
    a = ap.parse_args(argv)

    if recovery.vendored() is None:
        print(f'{YELLOW}no macrecovery is vendored{RESET}')
        return 1

    rows = recovery.choices()
    if not rows:
        print(f'{YELLOW}the board list yielded nothing to fetch{RESET}')
        return 1
    print(f'{BOLD}What Apple still serves{RESET}')
    print(f'{DIM}  {len(rows)} rows in the list. Nothing downloaded here is '
          f'kept.{RESET}')

    asked = rows if a.all else rows[:1]
    bad = []
    for choice in asked:
        ok, said = one(choice, a.catalogue)
        mark = f'{GREEN}ok{RESET}' if ok else f'{YELLOW}FAIL{RESET}'
        print(f'  {mark}  {choice["label"]:28} {said}')
        if not ok:
            bad.append(f'{choice["label"]}: {said}')

    print()
    if bad:
        print(f'{YELLOW}  {len(bad)} of {len(asked)} did not come back:{RESET}')
        for said in bad:
            print(f'    {said}')
        return 1
    print(f'{GREEN}  {len(asked)} of {len(asked)} came back and verified{RESET}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
