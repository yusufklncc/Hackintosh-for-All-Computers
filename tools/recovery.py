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
import textwrap
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen
import ui

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'red', 'reset')

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


MARKS = Path('data/macosmark.toml')


def _marks():
    """The per-release colours, if the table is there."""
    try:
        import ocgen
        return ocgen.read_toml(MARKS)
    except Exception:
        return {}


def mark(name):
    """A letter and two colours for a release, by name.

    Drawn rather than fetched: Apple's release artwork is Apple's, and nothing
    of Apple's is redistributed here. See data/macos.toml.

    A release the table has never heard of still gets a mark - the hue comes
    from the name itself. The list of releases grows out of macrecovery's board
    table the day Apple serves something new, so a table that had to be edited
    first would put a hole in the grid every time that happened."""
    table = _marks()
    if not name:
        latest = table.get('latest') or {}
        return {'letter': latest.get('letter', '?'),
                'from': latest.get('from', '#3e3ba8'),
                'to': latest.get('to', '#6f6ad6'),
                'source': 'chosen' if latest else 'fallback'}
    for row in table.get('mark') or []:
        if row.get('name', '').lower() == name.lower():
            return {'letter': row.get('letter') or name[0].upper(),
                    'from': row['from'], 'to': row['to'], 'source': 'chosen'}

    # derived: a stable hue off the name, so the same release is the same
    # colour on every machine and in every run
    import colorsys
    import hashlib
    hue = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % 360

    def at(light, sat):
        r, g, b = colorsys.hls_to_rgb(hue / 360, light, sat)
        return '#%02x%02x%02x' % (round(r * 255), round(g * 255), round(b * 255))

    return {'letter': name[0].upper(), 'from': at(0.30, 0.55),
            'to': at(0.58, 0.50), 'source': 'derived'}


def carries(hw):
    """Can this machine finish a recovery install, and on what.

    Recovery is 700 MB that boots and then downloads the rest of macOS **on
    the machine being converted**. So the question is not whether the computer
    making the stick has a connection - it is whether the target has a card
    macOS drives, at install time, before anything has been configured.

    Nothing asked this before. The pane said "it boots, connects, and downloads
    the rest" and left the reader to work out that a Realtek Wi-Fi card makes
    that sentence false, which is the shape of more than one issue in this
    repository: the stick gets made, the BIOS gets set, the installer boots,
    and only there does it turn out there was never going to be a network.

    Returns (verdict, sentence). The verdict is one of:

      'ready'    a card macOS drives is there; recovery can complete
      'cable'    Wi-Fi is not driven but Ethernet is - it works, on a cable
      'no'       neither is driven; recovery boots and cannot download
      'unknown'  no report to read, so this declines to guess

    The 'cable' case is the one worth spelling out. A laptop with a Realtek
    Wi-Fi card and a Realtek Ethernet chip is extremely common, recovery works
    perfectly on it, and the only thing standing between the person and a
    finished install is knowing to plug a cable in first."""
    import summary

    if not hw:
        return 'unknown', ('No hardware report, so nothing here knows whether '
                           'the machine being installed has a network card '
                           'macOS drives. Recovery downloads macOS on that '
                           'machine; if it cannot reach the network, it boots '
                           'and stops.')

    # three states per role, not two. "No Ethernet port on this laptop" and
    # "an Ethernet chip nothing here drives" lead to the same verdict and want
    # different sentences, and collapsing them produces "no Ethernet macOS can
    # drive" about a machine that has no Ethernet at all.
    def state(part):
        seen = [r for r in summary.network_rows(hw) or []
                if r.get('part') == part]
        if not seen:
            return 'absent'
        if any(r.get('verdict') in (summary.SUPPORTED, summary.DRIVEN)
               for r in seen):
            return 'driven'
        if all(r.get('verdict') == summary.ABSENT for r in seen):
            return 'absent'
        if any(r.get('verdict') == summary.UNSUPPORTED for r in seen):
            return 'unsupported'
        return 'unknown'

    wifi, wired = state('Wi-Fi'), state('Ethernet')

    if wifi == 'driven':
        return 'ready', ('Wi-Fi on this machine has a macOS driver, so recovery '
                         'can connect and download during the install.')
    if wired == 'driven':
        # the case this function exists for: extremely common, works perfectly,
        # and fails for everybody who did not know to plug a cable in
        said = {'unsupported': 'The Wi-Fi card in this machine has no macOS driver here',
                'absent': 'This machine has no Wi-Fi card',
                'unknown': 'Nothing here recognises the Wi-Fi in this machine'}[wifi]
        return 'cable', (f'{said}, but its Ethernet is driven. Recovery will '
                         'work - plug in an Ethernet cable before you start '
                         'the install. The download happens on this machine, '
                         'and Wi-Fi will not be there to carry it.')
    if 'unsupported' in (wifi, wired):
        return 'no', ('Neither the Wi-Fi nor the Ethernet in this machine has '
                      'a macOS driver here. Recovery would boot and then have '
                      'nothing to download over: use a whole macOS image '
                      'instead, or fit a card that is supported.')
    if wifi == wired == 'absent':
        return 'no', ('No network card was found on this machine at all. '
                      'Recovery downloads macOS during the install and cannot '
                      'do it without one: use a whole macOS image instead.')
    return 'unknown', ('Nothing here recognised the network hardware in this '
                       'machine, so whether recovery can download during the '
                       'install is not something this can answer. It needs a '
                       'card macOS drives, on the machine being installed.')


def served(tool=None):
    """board id -> the newest macOS macrecovery's list records for it.

    The same file the Recovery tab's list comes from, read whole rather than
    grouped: smbios.py asks it the other way round, board first."""
    tool = tool or vendored()
    if tool is None:
        return {}
    return json.loads((tool.parent / 'boards.json').read_text(encoding='utf-8'))


def recorded():
    """The newest macOS Apple was serving when data/mac.toml was refreshed.

    The `latest` rows fetch whatever is newest and boards.json will not name
    it, so the row used to read "Whatever Apple serves now" and left everybody
    asking whether that meant Tahoe. It did.

    Apple's own metadata answers it, and this repository already keeps that
    answer: tools/mactable.py --refresh writes every macOS line Apple serves
    into data/mac.toml, and the refresh workflow keeps it current. Reading the
    top of that list names the row without opening a connection, which is what
    makes it usable the moment the pane opens.

    It is a record rather than a reading: what Apple served when the table was
    last refreshed. `newest()` asks Apple directly, and the pane offers it."""
    try:
        import ocgen
        lines = ocgen.read_toml(Path('data/mac.toml')).get('lines') or []
    except Exception:
        return None
    usable = [v for v in lines if v and v[0].isdigit()]
    if not usable:
        return None
    top = max(usable, key=lambda v: [int(n) for n in v.split('.') if n.isdigit()])
    short = top.rsplit('.', 1)[0] if top.startswith('10.') else top.split('.')[0]
    return {'version': top, 'name': _names().get(short, '')}


def newest(url=None):
    """What macOS Apple is serving right now, asked of Apple.

    The `latest` rows in boards.json are the Macs Apple still updates, so they
    fetch whatever is newest - but the table does not name what that is, and
    neither can a binary that was built months ago. The row therefore reads
    "Whatever Apple serves now", which is honest and leaves everybody asking
    the same question: *is that Tahoe?*

    This answers it from Apple's own device-management metadata, the same
    endpoint tools/mactable.py reads. It opens a connection, so nothing calls
    it on its own - it is behind a button, like the download is.

    Returns (version, name) or (None, complaint).
    """
    import mactable

    try:
        payload = mactable.fetch(url or mactable.SOURCE)
    except Exception as exc:
        return None, f'Apple could not be asked: {exc}'

    seen = set()
    for asset in (payload.get('AssetSets') or {}).get('macOS') or []:
        version = asset.get('ProductVersion') or ''
        if version and version[0].isdigit():
            seen.add(version)
    if not seen:
        return None, 'Apple answered, and listed no macOS in it'

    def order(v):
        return [int(n) for n in v.split('.') if n.isdigit()]

    top = max(seen, key=order)
    short = top.rsplit('.', 1)[0] if top.startswith('10.') else top.split('.')[0]
    return {'version': top, 'name': _names().get(short, ''),
            'mark': mark(_names().get(short, ''))}, None


def _latest_label():
    """What to call the row the board table leaves unnamed."""
    said = recorded()
    if not said:
        return 'Whatever Apple serves now'
    return f"{said['name']} {said['version']}".strip() or said['version']


def _latest_note():
    said = recorded()
    if not said:
        return ('these boards are kept current, so this is the newest macOS '
                'Apple is serving today - the board list does not name it in '
                'advance, and neither does this')
    return (f"these boards are kept current, so this row asks for whatever "
            f"macOS is newest rather than for a version. boards.json does not "
            f"name it; data/mac.toml does, from Apple's own metadata, and it "
            f"said {said['name']} {said['version']} when that table was last "
            f"refreshed. Press the button to ask Apple for today's answer.")


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
            # What a person is offered. One place decides it, so a window and
            # a terminal cannot word the same row differently.
            #
            # The name, not the number. The number is the newest macOS the
            # board list records for that board, which is not the image Apple
            # hands back: asked for the 12.7.6 board, Apple served a 12.6
            # BaseSystem. Recovery then fetches the rest, so what gets
            # installed is a current build - but printing "Monterey 12.7.6" on
            # a row that downloads 12.6 is a claim nothing here can keep.
            'label': name or version if named else _latest_label(),
            'note': (f'the board list records {version} as the newest this board '
                     f'reaches. The image Apple hands back is some build of '
                     f'{name or version}; recovery downloads the rest during the '
                     f'install.') if named else
                    _latest_note(),
            # deterministic: the same board every time, so two people asking
            # for the same macOS ask Apple the same question. For the current
            # one that lands on macrecovery's own default, which is the board
            # the tool uses when nobody names one.
            'board': sorted(ids)[0],
            'boards': len(ids),
            # drawn by the front end, decided here: a window and a terminal
            # colouring the same release differently is the same failure as
            # wording the same row differently
            'mark': mark(name if named else ((recorded() or {}).get('name') or '')),
            # which release to draw an icon for. Separate from `name`, which
            # stays empty on the `latest` row: the day boards.json grows a real
            # Tahoe row, `find('tahoe')` must not match two of them.
            'art': name if named else ((recorded() or {}).get('name') or ''),
        })
    # newest first, and the one with no number is newer than all of them
    out.sort(reverse=True, key=lambda c: [int(n) for n in c['version'].split('.')]
             if c['version'][0].isdigit() else [10 ** 6])
    return out


def find(wanted, tool=None):
    """One choice, by version, by name, or by 'latest'. None if nothing matches.

    Two passes, and the order is the point. The `latest` row is now labelled
    with the release Apple was serving when data/mac.toml was refreshed, so
    asking for "tahoe" should reach it - but only while no row of its own says
    Tahoe. The day boards.json grows a real one, that row has to win, and a
    single pass over a list that holds both would return whichever came
    first."""
    asked = (wanted or '').strip().lower()
    if not asked:
        return None
    offered = choices(tool)
    for choice in offered:
        if asked in (choice['version'].lower(),
                     choice['name'].lower(),
                     choice['label'].lower()):
            return choice
    # then the release the unnamed row currently stands for
    for choice in offered:
        if not choice['name'] and asked == (choice.get('art') or '').lower():
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
        # the last lines that went past, so a caller can say what the tool
        # complained about rather than only that it did
        self.frames = []

    def say(self, text):
        self.frames.append(text)
        del self.frames[:-40]
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


def fetch(choice, into, tool=None, every=0.5):
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
        # Two very different failures arrive with the same exit code. A hash
        # mismatch means the bytes are wrong and downloading again is the
        # answer. A missing file means what was written is no longer where it
        # was written - the folder was renamed or moved while the download ran,
        # which is easy to do and impossible to guess at from "could not
        # verify".
        gone = any('No such file or directory' in line
                   for line in said.frames[-12:])
        if gone:
            return _sweep(folder, before), (
                f'the download finished and then {FOLDER} was not where it had '
                f'been written. Something moved or renamed it while it ran - '
                f'leave that folder alone until it finishes, and try again')
        return _sweep(folder, before), ('the tool could not verify what it '
                                       'downloaded against Apple\'s chunklist, '
                                       'so the bytes are not the ones Apple '
                                       'sent; downloading it again is the fix')
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


def _say_network(report):
    """The verdict on the machine being installed, on a console.

    Same sentence as the window draws, from the same function: two surfaces
    that disagree about whether a machine can finish an install are worse than
    one that says nothing."""
    hw = None
    if report:
        try:
            import detect
            hw = detect.read_report(report)
        except Exception:
            hw = None
    else:
        try:
            import detect
            hw = detect.probe()
        except Exception:
            hw = None
    verdict, said = carries(hw)
    colour = {'ready': GREEN, 'cable': YELLOW, 'no': RED}.get(verdict, DIM)
    lead = {'ready': 'This machine can download during the install',
            'cable': 'Use an Ethernet cable for the install',
            'no': 'Recovery cannot finish on this machine'}.get(
                verdict, 'Not known for this machine')
    print(f'\n  {colour}{lead}{RESET}')
    for line in textwrap.wrap(said, 72):
        print(f'  {DIM}{line}{RESET}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true',
                    help='what can be fetched; needs no network')
    ap.add_argument('--macos', help='a version or a name, as --list prints them')
    ap.add_argument('--out', default='.',
                    help='the drive to write to; the folder goes at its root')
    ap.add_argument('--machine', metavar='FILE',
                    help='a hardware report for the machine being installed, '
                         'so this can say whether recovery can reach the '
                         'network there')
    a = ap.parse_args(argv)

    tool = vendored()
    if tool is None:
        print(f'{YELLOW}no macrecovery is vendored{RESET}')
        return 1

    if a.list or not a.macos:
        print(f'{BOLD}Recovery installers Apple will serve{RESET}')
        for choice in choices(tool):
            print(f"  {choice['label']:28} {choice['board']}  "
                  f"{DIM}{choice['version']:9} {choice['boards']} boards{RESET}")
        print(f"{DIM}\n  The number is what the board list records as that board's "
              f"newest, not\n  the image Apple hands back: asked for the 12.7.6 "
              f"board it served a 12.6\n  BaseSystem. Recovery downloads the rest "
              f"during the install.{RESET}")
        print(f"{DIM}  Read from macrecovery's own boards.json. Ask for one by "
              f"version, by name,\n  or 'latest'.{RESET}")
        _say_network(a.machine)
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

    _say_network(a.machine)
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
