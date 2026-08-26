"""Run the vendored SSDTTime and fold what it writes into the config.

An SSDT is written against one machine's ACPI tables. Which renames a board
needs, which devices are missing, where the EC is - none of that can be worked
out from a device listing, and getting it wrong is worse than doing nothing. So
SSDTTime is vendored whole and driven: nothing here decides which patches a
machine needs, and nothing here writes AML.

What this does is the joining up. SSDTTime writes `.aml` files and a
`patches_OC.plist` into a `Results` folder beside itself; those become
`ACPI.Add` and `ACPI.Patch` entries and the AML is copied into `EFI/OC/ACPI`.

Three things about the tool decide how it has to be run:

  * it finds its ACPI tables by being handed a path, and can dump the running
    machine's on Windows and Linux with the acpidump beside it
  * it looks for iasl in its own `Scripts` directory, so the binaries go there
  * `Results` is relative to `SSDTTime.py`'s own `__file__`, so the tree is
    copied out to somewhere of ours and imported from there, which makes that
    path ours too

    python3 tools/acpi.py --tables ACPI/        # drive it against a dump
    python3 tools/acpi.py --dump ACPI/          # just dump this machine's tables
"""
import argparse
import hashlib
import importlib.util
import os
import plistlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

LOCK = Path('vendor/tools.lock')
VENDOR = Path('vendor/tools/SSDTTime')
IASL = Path('vendor/tools/iasl')

# What SSDTTime's Scripts/dsdt.py looks for, by platform. It checks its own
# directory and nothing else, which is why they are copied in rather than
# pointed at.
BINARIES = {
    'darwin': [('macos/iasl-stable', 'iasl-stable'),
               ('macos/iasl-legacy', 'iasl-legacy')],
    'linux': [('linux/iasl', 'iasl'),
              ('linux/iasl-legacy', 'iasl-legacy')],
    'win32': [('windows/iasl.exe', 'iasl.exe'),
              ('windows/iasl-legacy.exe', 'iasl-legacy.exe'),
              ('windows/acpidump.exe', 'acpidump.exe')],
}

# The legacy compiler is for macOS 10.6 and older, which some profiles here do
# cover. It is vendored not only for that: without it the tool downloads one on
# startup, and an offline build that quietly reaches for the network is worse
# than one that is a megabyte larger.


def platform_key():
    return 'win32' if sys.platform == 'win32' else (
        'darwin' if sys.platform == 'darwin' else
        'linux' if sys.platform.startswith('linux') else None)


def available():
    """The vendored tree, if it is here with a compiler this platform can use."""
    key = platform_key()
    if not key or not (VENDOR / 'SSDTTime.py').exists():
        return None
    if not all((IASL / src).exists() for src, _ in BINARIES[key]):
        return None
    return VENDOR


def verify():
    """(ok, detail) - the binaries have to be the ones that were checked."""
    if not LOCK.exists():
        return False, f'{LOCK} is missing'
    lock = ocgen.read_toml(LOCK)['tool']
    for src, _ in BINARIES[platform_key()]:
        entry = lock.get(f'iasl/{src}')
        if not entry:
            return False, f'iasl/{src} is not in {LOCK}'
        if not (IASL / src).exists():
            return False, f'{IASL / src} is missing'
        if getattr(sys, 'frozen', False):
            continue
        got = hashlib.sha256((IASL / src).read_bytes()).hexdigest()
        if got != entry['sha256']:
            return False, (f'{IASL / src} does not match {LOCK}; expected '
                           f'{entry["sha256"][:12]}, found {got[:12]}')
    version = lock['SSDTTime']['version']
    return True, (f'{version}, {hash_note()}' if getattr(sys, 'frozen', False)
                  else version)

def hash_note():
    """Why a hash is not checked inside a frozen build.

    PyInstaller rewrites the binaries it bundles - it re-signs Mach-O files, so
    what is unpacked is not byte for byte what was committed. The hash pins what
    is in the repository and CI checks it there; once the packer has been over
    it the guarantee belongs to the build, not to a check at run time. Saying so
    is better than a check that passes because it was quietly skipped."""
    return 'not hashed here: the packer rewrote it, so CI checks the repository copy'



def quiet_screen(ssdt):
    """Stop the tool clearing the screen, which it does through the shell.

    `cls()` runs `os.system("cls")` on Windows, and that spawns a process which
    inherits this one's stdout. Under a front end stdout is the JSON protocol,
    so the clear lands in the middle of it and the line it interrupts arrives
    as text nobody can parse - which is what a window showed: raw JSON in the
    transcript, in the middle of the ACPI step. There is nothing to clear when
    the output is a pipe.

    On Unix the tool already guards this with $TERM, which is why it only ever
    happened on Windows."""
    ssdt.u.cls = lambda *_args, **_kw: None
    return ssdt


def prepare(work):
    """Copy the tree and the compiler somewhere of ours, and return the copy."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(VENDOR, work)
    for src, name in BINARIES[platform_key()]:
        target = work / 'Scripts' / name
        shutil.copy2(IASL / src, target)
        target.chmod(0o755)
    shutil.copy2(IASL / 'ACPICA-LICENSE.txt', work / 'ACPICA-LICENSE.txt')
    return work


def restore_site_builtins():
    """Put back the names a frozen build takes away.

    SSDTTime quits with `exit(0)`. That name comes from site.py, which
    PyInstaller does not run, so in the frozen build it is a NameError rather
    than a SystemExit - and an unhandled one, which killed the whole builder the
    moment somebody finished making their SSDTs. Restoring the name is putting
    back what the interpreter normally provides, not patching their code."""
    import builtins
    for name in ('exit', 'quit'):
        if not hasattr(builtins, name):
            setattr(builtins, name, _Quitter(name))


class _Quitter:
    """What site.py installs: calling it raises SystemExit."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'Use {self.name}() to exit'

    def __call__(self, code=None):
        raise SystemExit(code)


def load(work):
    """Import SSDTTime from the copy, so its own __file__ is in our directory.

    Any earlier copy has to be forgotten first. The tree is copied to a fresh
    directory each time, but `SSDTTime` and its `Scripts` package stay in
    sys.modules, so a second run would take SSDTTime.py from the new copy and
    Scripts from the old one - which by then has been deleted. Running the SSDTs
    twice in one session is an ordinary thing to do."""
    restore_site_builtins()
    for name in [n for n in sys.modules
                 if n == 'SSDTTime' or n == 'Scripts' or n.startswith('Scripts.')]:
        del sys.modules[name]
    sys.path.insert(0, str(work))
    spec = importlib.util.spec_from_file_location('SSDTTime', work / 'SSDTTime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(work, tables=None, unattended=False, outcomes=None, ask=None):
    """Drive the tool. Returns the Results folder it wrote into, or None.

    unattended runs the self-deciding patches and returns, instead of handing
    the menus to a person.

    `ask` is where the tool's own questions go when there is no terminal to put
    them on. The tool has exactly one input function and this module already
    replaces it, so a front end can answer the menus the same way it answers
    everything else - the questions are the tool's, only the surface changes.
    Without it a window had to send people to the console for this one step."""
    tool = available()
    if not tool:
        return None, f'{VENDOR} is not usable on {sys.platform}'
    ok, detail = verify()
    if not ok:
        return None, detail

    # prepare() empties the working copy before filling it. If that is the
    # same directory the tables are in, the tables go with it - and on Windows
    # and macOS "ACPI" and "acpi" are the same directory, which is how a dump
    # of 22 tables became "no valid .aml files were found".
    # samefile, not a string comparison: on a case-insensitive filesystem
    # "acpi" and "ACPI" are one directory and two different strings, and
    # comparing the strings is what let this through the first time
    if (tables and Path(work).exists() and Path(tables).exists()
            and os.path.samefile(work, tables)):
        return None, (f'the working copy and the tables are the same folder '
                      f'({work}); the working copy is emptied first, so this '
                      f'would delete them')
    work = prepare(work)
    here = Path.cwd()
    outcomes = outcomes if outcomes is not None else []
    module = load(work)
    ssdt = quiet_screen(module.SSDT())
    if tables:
        # handing it the tables up front saves the person finding them again.
        # Loading them prompts too - "press enter" on a table it could not read,
        # and worse on an empty folder - so unattended has to cover this as well,
        # or a script hangs before it reaches the patches.
        original = ssdt.u.grab
        if unattended:
            ssdt.u.grab = _auto_grab
        try:
            ssdt.dsdt = ssdt.load_dsdt(str(Path(tables).resolve()))
        except _Unattended as exc:
            return None, f'the tables could not be loaded without asking: {exc}'
        finally:
            ssdt.u.grab = original
    try:
        if unattended:
            if not ssdt.dsdt:
                return None, 'no ACPI tables were loaded, so there is nothing to read'
            outcomes.extend(automatic(ssdt, work / 'Results'))
            raise SystemExit(0)
        if ask:
            ssdt.u.grab = ask
        while True:
            ssdt.main()
    except SystemExit:
        pass
    except BaseException as exc:                   # noqa: BLE001
        # a half-finished EFI is not worth losing to the tool falling over, and
        # whatever went wrong is worth naming rather than swallowing
        print(f'  SSDTTime stopped: {exc!r}')
    finally:
        os.chdir(here)
        if str(work) in sys.path:
            sys.path.remove(str(work))
    results = work / 'Results'
    if not results.exists():
        return None, 'it wrote no Results folder'
    return results, ''


# what a dump leaves behind, and nothing else
DUMPED = ('.aml', '.dat', '.dsl', '.txt')


def clear_dump(into):
    """Empty the folder a dump is about to be written into.

    The dumper writes `.dat` and renames them to `.aml`, and it does not
    replace what is already there: run it twice into the same folder and both
    spellings of every table survive. SSDTTime then refuses the lot - "multiple
    files with DSDT signature passed" - and the step ends with nothing loaded.

    Only files a dump makes are removed, and only from a folder that holds
    nothing else: this is somebody's directory, not ours."""
    into = Path(into)
    if not into.exists():
        return True, ''
    stray = [f.name for f in into.iterdir()
             if f.is_file() and f.suffix.lower() not in DUMPED]
    if stray or any(f.is_dir() for f in into.iterdir()):
        # SSDTTime's own tree, uppercased, is what a run before the ACPI/acpi
        # collision was fixed left in here. Naming it saves somebody working
        # out why LICENSE is in a folder of tables.
        theirs = {'LICENSE', 'README.MD', 'SSDTTIME.PY'} & set(stray)
        return False, (f'{into} holds things a dump did not write '
                       f'({", ".join(sorted(stray)[:3]) or "a folder"}); '
                       + ('this looks like what an older build left here, so '
                          'deleting the folder is safe. ' if theirs else '')
                       + 'Empty it yourself or point somewhere else')
    for f in into.iterdir():
        f.unlink()
    return True, ''


def dump(work, into):
    """Dump this machine's ACPI tables, using the tool's own dumper."""
    tool = available()
    if not tool:
        return None, f'{VENDOR} is not usable on {sys.platform}'
    if platform_key() == 'darwin':
        # a Mac's own tables are not the target machine's, and there is no
        # acpidump for macOS in the first place
        return None, 'ACPI tables cannot be dumped from macOS'
    ok, complaint = clear_dump(into)
    if not ok:
        return None, complaint
    work = prepare(work)
    module = load(work)
    ssdt = quiet_screen(module.SSDT())
    # the dumper asks too - "press [enter]" on a table it could not read - and
    # a window has no stdin to answer with. run() covers its own prompts and
    # this one was left reading a closed pipe.
    ssdt.u.grab = _auto_grab
    try:
        out = ssdt.d.dump_tables(str(Path(into).resolve()))
    except _Unattended as exc:
        return None, f'the tables could not be dumped without asking: {exc}' 
    return (Path(out) if out else None), ('' if out else 'nothing was dumped')


# Every key OpenCore requires of an ACPI patch, with the value it takes when
# nothing else is said. These are not invented: they are the defaults SSDTTime's
# own get_oc_patch fills in, which are OpenCore's. Filling them here matters
# because a patch missing one does not fail loudly - ocvalidate rejects the
# whole config, and the build that produced it looked fine.
PATCH_DEFAULTS = {
    'Base': '', 'BaseSkip': 0, 'Comment': '', 'Count': 0, 'Enabled': True,
    'Find': b'', 'Limit': 0, 'Mask': b'', 'OemTableId': b'', 'Replace': b'',
    'ReplaceMask': b'', 'Skip': 0, 'TableLength': 0, 'TableSignature': b'',
}


def normalise_patch(patch):
    """A patch with every key OpenCore wants, whatever the tool left out."""
    return {**PATCH_DEFAULTS, **patch}


def same_purpose(one, other):
    """Whether two SSDT filenames are two goes at the same job.

    The profiles carry SSDT-PLUG-DRTNIA and SSDT-EC-USBX-LAPTOP; SSDTTime writes
    SSDT-PLUG and SSDT-EC. Neither pair is a duplicate by name and both pairs
    would fight, so the comparison is on what the name says the table is for -
    the part before the contributor's suffix."""
    def family(name):
        stem = Path(name).stem.upper()
        parts = stem.split('-')
        # SSDT-EC-USBX-LAPTOP and SSDT-EC are the same family; SSDT-PNLF is not
        # the same as SSDT-PLUG
        return '-'.join(parts[:2]) if len(parts) > 1 else stem
    return family(one) == family(other)


# The patches SSDTTime works out entirely from the tables, with nothing to ask.
# Each one inspects the machine and produces nothing when it is not needed -
# "Named EC device located - no fake needed", "no bridge needed", "Could not
# locate a valid bus device! Aborting" - so running them is not this repository
# deciding anything. It is the tool deciding without a person pressing the same
# keys fourteen times.
#
# What is deliberately not here: PNLF asks five questions, XOSI and USBX and
# DMAR ask one each, and answering those for somebody is the thing this must not
# do. The laptop profiles already carry a generic XOSI and PNLF, so the gap that
# leaves is smaller than it looks. USB Reset is left out for a different reason:
# it is for hardware port querying and belongs with the USB map, not here.
AUTOMATIC = [
    ('fake_ec', 'SSDT-EC', 'a fake EC, or nothing if the machine has a real one'),
    ('plugin_type', 'SSDT-PLUG', 'plugin-type on the first CPU object'),
    ('ssdt_awac', 'SSDT-AWAC', 'the AWAC clock, if this board has one'),
    ('ssdt_pmc', 'SSDT-PMC', 'native NVRAM on a true 300-series board'),
    # fix_hpet stays in the list: with no conflicts it says so and writes
    # nothing, and with conflicts it asks which devices to patch - which is a
    # real choice, and saying so points at the menu rather than hiding it
    ('fix_hpet', 'SSDT-HPET', 'IRQ conflicts, if there are any'),
    ('smbus', 'SSDT-SBUS-MCHC', 'MCHC and BUS0, if there is a bus device'),
]


# The ones never attempted unattended, and what they would ask about. Named so
# that choosing the automatic run does not leave them invisible: somebody who
# needs PNLF should be told it exists, not left to find out.
ASKS = [
    ('SSDT-PNLF', 'laptop backlight; asks about the panel'),
    ('SSDT-XOSI', 'which Windows versions _OSI should answer to'),
    ('SSDT-USBX', 'USB power properties'),
    ('DMAR', 'reserved memory regions; asks which to drop'),
    ('SSDT-USB-Reset', 'for USB port mapping, which is its own step'),
    ('SSDT-Bridge', 'needs the device path of the bridge to create'),
    ('SSDT-IMEI', 'asks which bridge to define'),
]


class _Unattended(Exception):
    """Raised when a patch asks something a person would have to answer."""


def _auto_grab(prompt=''):
    """Answer "press enter" and refuse anything else.

    The list above is the set that asks nothing, but that is read off today's
    code. If a patch ever grows a real question, this stops rather than sending
    a blank line into it - a wrong answer nobody gave is worse than no SSDT."""
    if 'press [enter]' in str(prompt).lower():
        return ''
    raise _Unattended(str(prompt).strip() or 'a question with no prompt')


def automatic(ssdt, results=None):
    """Run the self-deciding patches. Returns [(name, outcome, detail)]."""
    import contextlib
    import io
    results = Path(results) if results else None
    done = []
    original = ssdt.u.grab

    def files():
        return set(results.glob('*.aml')) if results and results.exists() else set()

    try:
        ssdt.u.grab = _auto_grab
        for method, name, what in AUTOMATIC:
            run = getattr(ssdt, method, None)
            if not run:
                done.append((name, NOT_NEEDED, 'not in this version of the tool'))
                continue
            before = files()
            printed = io.StringIO()
            try:
                with contextlib.redirect_stdout(printed):
                    run()
                done.append((name, *_outcome(printed.getvalue(), before, files())))
            except _Unattended as exc:
                # not a failure: the patch found something that needs an answer.
                # fix_hpet does this the moment there is an IRQ conflict, which
                # is the only time it has anything to do at all.
                done.append((name, ASKED, str(exc)))
            except Exception as exc:                # noqa: BLE001
                done.append((name, 'stopped', repr(exc)))
    finally:
        ssdt.u.grab = original
    return done

# Three outcomes, and they are the whole story: it wrote something, it looked
# and there was nothing to write, or it wanted an answer. Anything else is the
# tool falling over, which is reported as itself.
WROTE, NOT_NEEDED, ASKED = 'written', 'not needed on this machine', 'needs a choice'


def _outcome(output, before, after):
    """What happened, judged by whether a file appeared rather than by the screen."""
    fresh = after - before
    if fresh:
        return WROTE, ', '.join(sorted(p.name for p in fresh))
    for line in reversed(output.splitlines()):
        line = line.strip().lstrip('->  ')
        if line and not line.startswith(('#', 'Press')):
            return NOT_NEEDED, line
    return NOT_NEEDED, ''

def collect(results):
    """(aml files, ACPI.Add entries, ACPI.Patch entries) from a Results folder.

    The patches are the tool's own patches_OC.plist rather than anything read
    off the screen, so what goes in the config is what it decided."""
    results = Path(results)
    aml = sorted(p for p in results.glob('*.aml'))
    add = [{'Comment': p.stem, 'Enabled': True, 'Path': p.name} for p in aml]
    patches = []
    plist = results / 'patches_OC.plist'
    if plist.exists():
        with open(plist, 'rb') as fh:
            loaded = plistlib.load(fh)
        patches = [normalise_patch(x)
                   for x in (loaded.get('ACPI', {}).get('Patch', []) or [])]
    return aml, add, patches


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', default='build/acpi', help='where to run it')
    ap.add_argument('--tables', help='a folder of ACPI tables to load')
    ap.add_argument('--dump', metavar='DIR', help='dump this machine\'s tables and stop')
    a = ap.parse_args(argv)

    if not available():
        print(f'  SSDTTime is not usable on {sys.platform}')
        return 1
    ok, detail = verify()
    print(f'  SSDTTime {detail if ok else detail}')
    if not ok:
        return 1
    if a.dump:
        out, complaint = dump(a.work, a.dump)
        print(f'  {"dumped to " + str(out) if out else complaint}')
        return 0 if out else 1
    results, complaint = run(a.work, a.tables)
    if not results:
        print(f'  {complaint}')
        return 1
    aml, add, patches = collect(results)
    print(f'  {len(aml)} SSDTs and {len(patches)} patches in {results}')
    for entry in add:
        print(f'      {entry["Path"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
