"""Fetch Apple's recovery installer onto the USB stick, beside the EFI.

The images this repository points at are whole installers, and a whole
installer does not fit on FAT32 - the partition an EFI lives on cannot hold a
file over 4 GB. Apple's recovery is the way around that: about 700 MB of
BaseSystem that boots and then downloads the rest of macOS itself.

OpenCore ships the tool that talks to Apple, so nothing here reimplements it.
`macrecovery.py` is vendored with the rest of the release and driven, and the
list of what can be fetched is read out of its own `boards.json` rather than
kept here - a list of ours would be one more thing to go stale.

    python3 tools/recovery.py --list
    python3 tools/recovery.py --macos 12.7.6 --out /Volumes/EFI

This is the one thing in this repository that opens a connection, and it only
does it when asked. The download comes from Apple, over Apple's own protocol;
what lands is verified against the chunklist Apple sends with it, by their
tool, not by ours.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen
import ui

BOLD, DIM, GREEN, YELLOW, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'reset')

VENDOR = Path('vendor/opencore')
FOLDER = 'com.apple.recovery.boot'
RELEASES = Path('data/macos.toml')
# macrecovery's own default, and the serial it documents for "no real Mac".
# Seventeen zeroes is not a serial anybody owns; Apple's server accepts it for
# recovery and refuses it for anything else, which is the point.
NO_SERIAL = '00000000000000000'


def vendored():
    """The vendored macrecovery, or None.

    It arrives with the OpenCore release and is pinned by that version: there
    is no separate thing to update, and no second place to look."""
    for version in sorted(p for p in VENDOR.iterdir() if p.is_dir()):
        tool = version / 'Utilities' / 'macrecovery' / 'macrecovery.py'
        if tool.exists():
            return tool
    return None


def _names():
    """macOS version -> the name people know it by."""
    if not RELEASES.exists():
        return {}
    return {r['version']: r['name'] for r in ocgen.read_toml(RELEASES)['release']}


def choices(tool=None):
    """What can be fetched, newest first, read from macrecovery's board list.

    boards.json records, for each board id, the newest macOS that board is
    offered. Grouping by that gives one entry per macOS - and the board id is
    the argument the download actually takes, so this is the list and the
    answer at once.

    Six boards are recorded as `latest` rather than a version. Those are the
    ones Apple keeps current, so they are how you ask for whatever macOS is
    newest today; what that is cannot be named here, and is not."""
    tool = tool or vendored()
    if tool is None:
        return []
    boards = json.loads((tool.parent / 'boards.json').read_text(encoding='utf-8'))
    grouped = {}
    for board, version in boards.items():
        grouped.setdefault(version, []).append(board)
    names = _names()
    out = []
    for version, ids in grouped.items():
        named = version[0].isdigit()
        short = (version.rsplit('.', 1)[0] if version.startswith('10.')
                 else version.split('.')[0]) if named else ''
        name = names.get(short, '')
        out.append({
            'version': version,
            'name': name,
            # what a person is offered. One place decides it, so a window and
            # a terminal cannot word the same row differently.
            'label': f'{name} {version}'.strip() if named
                     else 'Whatever Apple serves now',
            'note': '' if named else
                    'these boards are kept current, so this is the newest macOS '
                    'Apple is serving today - the board list does not name it in '
                    'advance, and neither does this',
            # deterministic: the same board every time, so two people asking
            # for the same macOS ask Apple the same question. For the current
            # one that lands on macrecovery's own default, which is the board
            # the tool uses when nobody names one.
            'board': sorted(ids)[0],
            'boards': len(ids),
        })
    # newest first, and the one with no number is newer than all of them
    out.sort(reverse=True, key=lambda c: [int(n) for n in c['version'].split('.')]
             if c['version'][0].isdigit() else [10 ** 6])
    return out


def find(wanted, tool=None):
    """One choice, by version, by name, or by 'latest'. None if nothing matches."""
    asked = (wanted or '').strip().lower()
    for choice in choices(tool):
        if asked and asked in (choice['version'].lower(),
                               choice['name'].lower(),
                               choice['label'].lower()):
            return choice
    return None


def present(into):
    """What is already in the recovery folder, if anything."""
    folder = Path(into) / FOLDER
    if not folder.is_dir():
        return []
    return sorted((f.name, f.stat().st_size) for f in folder.iterdir() if f.is_file())


def _load(tool):
    """Import the vendored script, so its own directory is where it looks.

    It reads boards.json from beside its `__file__`, which is the copy here."""
    for name in [n for n in sys.modules if n == 'macrecovery']:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location('macrecovery', tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Progress:
    """Somebody else's progress bar, on a surface that has no cursor.

    macrecovery redraws one line with \\r about seven hundred times for a
    700 MB image. A console can take that; a JSON stream would carry seven
    hundred events for it. Whole lines go straight through, and the redrawn
    one is passed on every few seconds so there is still something moving."""

    def __init__(self, every=2.0, out=None):
        # the stream from before the redirect. print() would come back here
        # and recurse, which it did.
        self.out = out or sys.stdout
        self.every, self.last, self.frame = every, 0.0, ''
        self.pending = ''

    def say(self, text):
        self.out.write(f'{DIM}    {text}{RESET}\n')

    def write(self, s):
        self.pending += s
        while True:
            cut = min((self.pending.index(c) for c in '\r\n'
                       if c in self.pending), default=-1)
            if cut < 0:
                return len(s)
            chunk, mark = self.pending[:cut], self.pending[cut]
            self.pending = self.pending[cut + 1:]
            if mark == '\n':
                self.frame = ''
                if chunk.strip():
                    self.say(chunk.strip())
            else:
                self.frame = chunk.strip()
                now = time.monotonic()
                if self.frame and now - self.last >= self.every:
                    self.last = now
                    self.say(self.frame)
        return len(s)

    def close(self):
        if self.frame:
            self.say(self.frame)
        if self.pending.strip():
            self.say(self.pending.strip())
        self.frame = self.pending = ''

    def flush(self):
        pass


def fetch(choice, into, tool=None, every=2.0):
    """Download one recovery into <into>/com.apple.recovery.boot.

    Returns (files, complaint). The tool verifies the image against Apple's
    chunklist itself and returns non-zero when that fails, so a bad download
    is not something this has to detect - only report."""
    tool = tool or vendored()
    if tool is None:
        return [], 'no macrecovery is vendored, so there is nothing to drive'
    folder = Path(into) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    before = {name for name, _ in present(into)}

    module = _load(tool)
    argv = ['macrecovery', 'download', '-b', choice['board'], '-m', NO_SERIAL,
            '-os', 'latest', '-o', str(folder)]
    was, sys.argv = sys.argv, argv
    # It asks the terminal how wide it is on every megabyte, and there is no
    # terminal: stdout is a pipe under a front end and a StringIO under a test.
    # Answering instead of letting it raise is the smallest thing that works;
    # forking the tool over a column count would not be.
    width, os.get_terminal_size = os.get_terminal_size, lambda *_: os.terminal_size((80, 24))
    said = Progress(every, out=sys.stdout)
    try:
        with redirect_stdout(said):
            code = module.main()
    except SystemExit as stopped:          # its argument parser, on a bad flag
        code = stopped.code if isinstance(stopped.code, int) else 1
    except Exception as broke:
        # urllib carries its own trust store; a network that inspects TLS
        # refuses it. The other fetchers here fall back to curl, but this is
        # somebody else's tool and patching it would be a fork.
        return _sweep(folder, before), f'the download stopped: {broke!r}'
    finally:
        sys.argv, os.get_terminal_size = was, width
        said.close()

    files = present(into)
    if code:
        return _sweep(folder, before), ('the tool could not verify what it '
                                       'downloaded')
    if not files:
        return [], 'the download reported success but wrote nothing'
    return files, None


def _sweep(folder, before):
    """Take back what this run left half written.

    There is no resuming a partial BaseSystem, and leaving one there means the
    next attempt refuses to start because the folder is not empty. Only files
    this run created go; anything that was already there is somebody else's."""
    for made in sorted(folder.iterdir()):
        if made.is_file() and made.name not in before:
            made.unlink()
    return sorted((f.name, f.stat().st_size) for f in folder.iterdir()
                  if f.is_file())


def _size(count):
    """A chunklist is kilobytes and an image is hundreds of megabytes.

    One unit for both printed the chunklist as 0.0 MB, which reads like a
    file that failed to download."""
    if count >= 1024 * 1024:
        return f'{count / (1024 * 1024):.1f} MB'
    return f'{count / 1024:.1f} KB'


def describe(choice, files):
    """What was fetched, in the terms the person asked in."""
    total = sum(size for _, size in files) / (1024 * 1024)
    return f"{choice['label']}, {len(files)} files, {total:.0f} MB"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true',
                    help='what can be fetched; needs no network')
    ap.add_argument('--macos', help='a version or a name, as --list prints them')
    ap.add_argument('--out', default='.',
                    help='the drive to write to; the folder goes at its root')
    a = ap.parse_args(argv)

    tool = vendored()
    if tool is None:
        print(f'{YELLOW}no macrecovery is vendored{RESET}')
        return 1

    if a.list or not a.macos:
        print(f'{BOLD}Recovery installers Apple will serve{RESET}')
        for choice in choices(tool):
            print(f"  {choice['version']:9} {choice['label']:28} "
                  f"{choice['board']}  {DIM}({choice['boards']} boards){RESET}")
            if choice['note']:
                print(f"{DIM}            {choice['note']}{RESET}")
        print(f"{DIM}\n  read from macrecovery's own boards.json, which records the "
              f"newest macOS\n  each board is offered. Ask for one by version, by "
              f"name, or 'latest'.{RESET}")
        return 0

    choice = find(a.macos, tool)
    if choice is None:
        print(f'{YELLOW}{a.macos} is not one of the versions macrecovery '
              f'lists{RESET}')
        return 1

    standing = present(a.out)
    if standing:
        print(f'{YELLOW}{Path(a.out) / FOLDER} already holds '
              f'{", ".join(n for n, _ in standing)}{RESET}')
        print(f'{DIM}  delete them first; this will not overwrite a download '
              f'somebody may be part way through{RESET}')
        return 1

    print(f"{BOLD}Fetching {choice['label']} from Apple{RESET}")
    print(f"{DIM}  board {choice['board']}, serial {NO_SERIAL}, into "
          f"{Path(a.out) / FOLDER}{RESET}")
    files, complaint = fetch(choice, a.out, tool)
    if complaint:
        print(f'{YELLOW}  {complaint}{RESET}')
        return 1
    for name, size in files:
        print(f'  {name:28} {_size(size):>10}')
    print(f'\n  {GREEN}{describe(choice, files)}{RESET}')
    print(f'{DIM}  OpenCore lists it at the boot menu; it needs a wired '
          f'connection or a\n  card macOS already drives, because the rest of '
          f'macOS comes down during\n  the install.{RESET}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
