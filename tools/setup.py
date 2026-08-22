"""Interactive EFI builder.

Asks a short series of numbered questions and writes the EFI folder for one
machine. Where the running system can tell us something - that this is a laptop,
that the CPU is Kaby Lake, that the board is an HP - it is shown next to the
question as `detected`. It is never preselected and never chosen automatically:
detection can be wrong, and a wrong answer that arrives already ticked is one
nobody rechecks.

    python3 tools/setup.py

The first question is which machine the EFI is for, because detection reads the
machine this runs on and that is often not the target: a USB stick is usually
made on a computer that already works. Building for another machine either
reads a report taken from it, or asks by name and claims nothing it cannot know.

Standard library only, no network.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acpi
import advise
import audio
import build
import detect
import gpu
import igpu
import inputdev
import netkexts
import ocgen
import summary
import usbmap

PROFILES = Path('profiles')

CPU_LABELS = {
    'yonah-conroe-penryn-legacy-bios': 'Yonah / Conroe / Penryn, Legacy BIOS',
    'yonah-conroe-penryn-uefi-bios': 'Yonah / Conroe / Penryn, UEFI BIOS',
    'lynnfield-clarkdale-legacy-bios': 'Lynnfield / Clarkdale, Legacy BIOS',
    'lynnfield-clarkdale-uefi-bios': 'Lynnfield / Clarkdale, UEFI BIOS',
    'nehalem-westmere-legacy': 'Nehalem / Westmere, Legacy BIOS',
    'nehalem-westmere-uefi': 'Nehalem / Westmere, UEFI BIOS',
    'clarksfield-arrandale-legacy-bios': 'Clarksfield / Arrandale, Legacy BIOS',
    'clarksfield-arrandale-uefi-bios': 'Clarksfield / Arrandale, UEFI BIOS',
    'sandy-bridge-legacy': 'Sandy Bridge, Legacy BIOS',
    'sandy-bridge-uefi': 'Sandy Bridge, UEFI BIOS',
    'sandy-bridge-legacy-bios': 'Sandy Bridge, Legacy BIOS',
    'sandy-bridge-uefi-bios': 'Sandy Bridge, UEFI BIOS',
    'sandy-bridge-e-ivy-bridge-e': 'Sandy Bridge-E / Ivy Bridge-E',
    'ivy-bridge': 'Ivy Bridge', 'haswell': 'Haswell', 'haswell-e': 'Haswell-E',
    'broadwell': 'Broadwell', 'broadwell-e': 'Broadwell-E', 'sky-lake': 'Skylake',
    'skylake-x-w-cascade-lake-x-w': 'Skylake-X/W / Cascade Lake-X/W',
    'kaby-lake': 'Kaby Lake', 'coffe-lake': 'Coffee Lake',
    'coffe-lake-plus': 'Coffee Lake Plus', 'coffee-lake-whiskey-lake': 'Coffee Lake / Whiskey Lake',
    'comet-lake': 'Comet Lake', 'ice-lake': 'Ice Lake', 'rocket-lake': 'Rocket Lake',
    'alder-lake': 'Alder Lake', 'raptor-lake': 'Raptor Lake',
    'bulldozer-jaguar': 'Bulldozer / Jaguar', 'ryzen-threadripper': 'Ryzen / Threadripper',
}

BOLD, DIM, GREEN, YELLOW, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[0m'
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RESET = ''


SCRIPTED = []
SCRIPTING = False


def _answer():
    """The next scripted answer, or a typed one.

    Running out mid-run is a scripting mistake, not a prompt: with --answers the
    input is usually closed, so falling through to input() would end in an
    EOFError several frames away from the cause."""
    if SCRIPTED:
        raw = SCRIPTED.pop(0)
        print(f'      > {raw}')
        return raw
    if SCRIPTING:
        sys.exit('--answers ran out: this run asks more questions than it was given')
    return input('      > ').strip()


def prompt(question, note=None):
    """A free-text answer. Empty means the person declined."""
    print(f'\n{BOLD}{question}{RESET}')
    if note:
        print(f'      {DIM}{note}{RESET}')
    return _answer().strip()


def ask(step, total, question, options, detected=None, allow_skip=False,
        skip_label='none of these'):
    """One numbered menu. options is [(value, label)]. Returns the chosen value.

    `detected` is shown as a note and marks its row, but the person still types
    a number - the whole point is that the machine's guess is visible and
    overridable in the same glance."""
    # the first question runs before the total is known, since a laptop asks
    # fewer than a desktop; claiming a total there would only be wrong
    if not step:
        print(f'\n{BOLD}{question}{RESET}')            # a follow-up, not a numbered step
    else:
        counter = f'{step}/{total}' if total else f'{step}'
        print(f'\n{BOLD}[{counter}] {question}{RESET}')
    hint = dict(options).get(detected)
    if hint:
        print(f'      {GREEN}detected: {hint}{RESET}')
    elif detected:
        print(f'      {GREEN}detected: {detected}{RESET}')
    for i, (value, label) in enumerate(options, 1):
        mark = f' {GREEN}<- detected{RESET}' if value == detected else ''
        print(f'      {i:2d}) {label}{mark}')
    if allow_skip:
        print(f'      {len(options) + 1:2d}) {skip_label}')
    while True:
        raw = _answer()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1][0]
            if allow_skip and n == len(options) + 1:
                return None
        print(f'      {DIM}enter a number from the list{RESET}')


def available(kind):
    return sorted(p.stem.split('.', 1)[1]
                  for p in PROFILES.glob(f'overlay/{kind}.*.toml'))


def cpu_choices(platform_name):
    out = []
    for p in sorted(PROFILES.glob(f'cpu/{platform_name}/*.toml')):
        if '.' in p.stem:                      # per-core override, not a profile
            continue
        out.append((p.stem, CPU_LABELS.get(p.stem, p.stem)))
    return out


def unbundle():
    """When running as a frozen executable, work from the bundled copy.

    PyInstaller unpacks everything - profiles, data, EFI, vendor - into a temp
    directory, and every path in these tools is relative to the repository root.
    Moving there makes the frozen build behave exactly like the checkout, so
    there is no second code path to keep working. Only --out has to be pinned to
    where the person actually is first."""
    base = getattr(sys, '_MEIPASS', None)
    if not base:
        return None
    here = Path.cwd()
    os.chdir(base)
    return here


def check_tools():
    """Load every vendored tool, which is the thing a frozen build gets wrong.

    SSDTTime is imported at runtime from a copy of its tree, so PyInstaller
    cannot see what it imports and does not bundle it. Nothing catches that
    until somebody answers yes to a question - so this answers it instead, and
    CI runs it against the executable it just built."""
    import tempfile
    failed = []

    def report(name, ok, detail=''):
        print(f'  {"ok  " if ok else "FAIL"}  {name}' + (f'   {detail}' if detail else ''))
        if not ok:
            failed.append(name)

    if usbmap.available():
        ok, detail = usbmap.verify(usbmap.available())
        report('the USB mapper is the file that was checked', ok, detail)
    else:
        report('the USB mapper is here', False, 'it is not')

    if acpi.available():
        ok, detail = acpi.verify()
        report('every ACPI compiler is the file that was checked', ok, detail)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                work = acpi.prepare(Path(tmp) / 'acpi')
                module = acpi.load(work)
                ssdt = module.SSDT()
                report('SSDTTime loads, with everything it imports', True)
                # it quits with exit(0), which a frozen build does not have.
                # That killed the whole builder the first time somebody
                # finished their SSDTs, so it is asked here instead.
                try:
                    # it prints a goodbye on the way out, which is not wanted here
                    import contextlib
                    import io
                    with contextlib.redirect_stdout(io.StringIO()):
                        ssdt.u.custom_quit()
                    report('quitting it raises SystemExit, not something fatal',
                           False, 'it returned instead')
                except SystemExit:
                    report('quitting it raises SystemExit, not something fatal', True)
                except BaseException as exc:      # noqa: BLE001 - the whole point
                    report('quitting it raises SystemExit, not something fatal',
                           False, repr(exc))
                report('and finds the compiler beside it', bool(ssdt.d.iasl),
                       '' if ssdt.d.iasl else 'it did not')
                report('and the legacy one, so it never downloads',
                       bool(ssdt.d.iasl_legacy))
        except Exception as exc:                   # noqa: BLE001 - the whole point
            report('SSDTTime loads, with everything it imports', False, repr(exc))
    else:
        report('SSDTTime is usable here', False, f'not on {sys.platform}')

    print()
    if failed:
        print(f'  {len(failed)} failed: {", ".join(failed)}')
        return 1
    print('  all good')
    return 0


def profile_from(hw):
    """(platform, vendor, cpu, cores, oem) when detection answers all of it.

    None when anything is missing or has no profile. The fast path exists to
    save answering four questions whose answers are already on the screen; it
    must not be reachable on a guess, so every part has to be there and the
    profile has to exist."""
    gen = hw.get('generation')
    if not gen or hw.get('laptop') is None:
        return None
    plat = 'laptop' if hw['laptop'] else 'desktop'
    amd = gen in ('ryzen-threadripper', 'bulldozer-jaguar')
    if plat == 'laptop' and amd:
        return None                      # laptop profiles are Intel only
    vendor = ('amd' if amd else 'intel') if plat == 'desktop' else None
    pname = f'{plat}-{vendor}' if vendor else plat
    if not (PROFILES / 'cpu' / pname / f'{gen}.toml').exists():
        return None
    cores = hw.get('cores') if vendor == 'amd' else None
    if vendor == 'amd' and cores not in (4, 6, 8, 12, 16, 24, 32, 64):
        return None
    oem = hw.get('oem')
    if oem and not (PROFILES / 'overlay' / f'oem.{oem}.toml').exists():
        oem = None
    return plat, vendor, gen, cores, oem


def usb_notes():
    """The follow-up for a machine built without a port map."""
    return '\n'.join([
        'USB ports', '',
        '  This EFI has UTBDefault, which enables every port on the controller',
        '  without mapping any of them. macOS allows fifteen ports per controller;',
        '  a machine with more than that will have some that never work, and which',
        '  ones is not predictable.',
        '',
        '  A real map fixes that, and it cannot be worked out from a listing: it',
        '  takes plugging a device into every port in turn on the machine itself.',
        '',
        '  USBToolBox is bundled with this builder. Run it on Windows and it is',
        '  offered before the build; these are the steps either way.',
        '',
        '    1. On Windows, run this builder, or USBToolBox from',
        '       github.com/USBToolBox/tool',
        '    2. Run it, choose Discover Ports, and plug a USB 2 device and then a',
        '       USB 3 device into every port, watching which entries light up',
        '    3. Select the ports you want, set the port types, and build the kext',
        '    4. It writes UTBMap.kext. Build again with:',
        '',
        '         setup.py --usb-map UTBMap.kext',
        '',
        '  That copies your map in and removes UTBDefault, which upstream says',
        '  "is not needed and must be removed if you choose to map".',
        '',
        '  USBToolBox reads the ports from Windows, so it can be run on the target',
        '  machine and the kext carried back, the same way as a hardware report.',
        ''])


def show_machine(hw, label):
    """Print what a probe says, so the person can see it is the right machine."""
    if not hw.get('cpu'):
        return
    print(f'  {DIM}{label}:{RESET} {hw["cpu"]}'
          + (f', {hw["cores"]} cores' if hw.get('cores') else '')
          + (f', {hw["oem_raw"]}' if hw.get('oem_raw') else ''))
    if hw.get('written'):
        print(f'  {DIM}taken:{RESET}        {hw["written"]} on {hw.get("system", "?")}')
    for g in hw.get('gpu_devices', [])[:3]:
        print(f'  {DIM}graphics:{RESET}     {g["name"]}'
              + (f'  {DIM}[{g["id"]}]{RESET}' if g.get('id') else ''))
    if hw.get('gpu_virtual'):
        # named rather than dropped silently: someone who installed one of
        # these should see that it was recognised and set aside
        print(f'  {DIM}ignored:{RESET}      {", ".join(hw["gpu_virtual"])}'
              f'  {DIM}(virtual display adapters, not graphics hardware){RESET}')


def pick_network():
    """Ask by name which network hardware the other machine has.

    Reached only when there is no report to read. Nothing about that machine is
    known, so the options are the driver sets this repository ships rather than
    anything matched against device ids, and the answers stay the person's."""
    picked = set()
    known = netkexts.sets() + netkexts.variant_sets()
    for role, label in (('ethernet', 'Ethernet'), ('wifi', 'Wi-Fi'),
                        ('bluetooth', 'Bluetooth')):
        options = [(s['match'], s['label']) for s in known if s.get('role') == role]
        if not options:
            continue
        got = ask(0, 0, f'Which {label} does that machine have?', options,
                  allow_skip=True, skip_label='none, or I do not know')
        if got:
            picked.add(got)
    return picked


def overrides(a, hw):
    """Fold the ids a caller passed into a probe, in place.

    Applied as soon as the machine is settled rather than just before the build,
    so the summary describes what will actually be built for."""
    if a.ids is not None or a.usb_ids is not None:
        hw['pci_ids'] = [x.strip() for x in (a.ids or '').split(',') if x.strip()]
        hw['usb_ids'] = [x.strip() for x in (a.usb_ids or '').split(',') if x.strip()]
    if a.hda_ids is not None:
        hw['hda_ids'] = [x.strip() for x in a.hda_ids.split(',') if x.strip()]
    if a.nvme is not None:
        hw['nvme'] = [x.strip() for x in a.nvme.split(',') if x.strip()]
    if a.acpi_ids is not None:
        hw['acpi_ids'] = [x.strip().upper() for x in a.acpi_ids.split(',') if x.strip()]
    return hw


def describe_machine(hw, label, source):
    """The banner and the summary for one machine."""
    show_machine(hw, label)
    if summary.worth_showing(hw):
        print()
        print('\n'.join(summary.render(hw, source)))
    elif hw:
        print(f'  {DIM}nothing here is in any table this repository has, so there is '
              f'no summary to give{RESET}')


def load_machine(path):
    """(probe, label) for a report file, or (None, complaint) if unusable."""
    hw, complaint = detect.read_report(path)
    if complaint:
        return None, complaint
    return hw, f'report {Path(path).name}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='build/EFI')
    ap.add_argument('--no-detect', action='store_true',
                    help='skip hardware detection and ask the profile questions only')
    ap.add_argument('--machine', metavar='FILE',
                    help='build for the machine in this hardware report instead '
                         'of the one this runs on')
    ap.add_argument('--report', metavar='FILE',
                    help='write this machine\'s hardware report and stop, so an '
                         'EFI for it can be built elsewhere')
    ap.add_argument('--check', action='store_true',
                    help='print what the hardware means for macOS and stop')
    ap.add_argument('--check-tools', action='store_true',
                    help='load the vendored tools and stop, which is what a '
                         'frozen build has to be able to do')
    ap.add_argument('--ids', help='PCI ids to use instead of probing, comma separated')
    ap.add_argument('--usb-ids', help='USB ids to use instead of probing, comma separated')
    ap.add_argument('--hda-ids', help='HD audio codec ids to use instead of probing')
    ap.add_argument('--nvme', help='NVMe drive models to use instead of probing')
    ap.add_argument('--acpi-ids', help='ACPI hardware ids to use instead of probing')
    ap.add_argument('--acpi-tables', metavar='DIR',
                    help='a folder of ACPI tables dumped from the target machine')
    ap.add_argument('--usb-map', help='a UTBMap.kext made with the USBToolBox tool')
    ap.add_argument('--answers', help='answer the menus non-interactively, comma separated; '
                                      'for scripting and for CI')
    a = ap.parse_args()

    if a.answers:
        global SCRIPTING
        SCRIPTING = True
        SCRIPTED.extend(x.strip() for x in a.answers.split(',') if x.strip())

    started_in = unbundle()
    if started_in:
        a.out = str((started_in / a.out).resolve())
        # every path a caller passes is theirs, not the bundle's. Leaving
        # acpi_tables out of this meant the frozen build looked for the dumped
        # tables inside its own unpacked copy, where they never are.
        for opt in ('machine', 'report', 'usb_map', 'acpi_tables'):
            if getattr(a, opt):
                setattr(a, opt, str((started_in / getattr(a, opt)).resolve()))

    if a.check_tools:
        return check_tools()

    if a.report:
        a.report = str(Path(a.report).expanduser().resolve())
        written = detect.write_report(a.report)
        print(f'{BOLD}Hardware report{RESET}')
        print(f'  wrote {a.report}')
        print(f'  {detect.describe(written)}')
        # the SSDTs have to be written against this machine's tables, so they
        # travel with the report rather than being asked for later
        tables = None
        if acpi.available() and acpi.platform_key() != 'darwin':
            beside = Path(a.report).parent / 'ACPI'
            tables, complaint = acpi.dump(Path(a.out).parent / 'acpi-dump', beside)
            print(f'  {"and its ACPI tables to " + str(beside) if tables else complaint}')
        print(f'\n  Copy {"them" if tables else "it"} to the machine you build on '
              f'and pass {"them" if tables else "it"} back:')
        print(f'      setup.py --machine {Path(a.report).name}'
              + (' --acpi-tables ACPI' if tables else ''))
        return 0

    # a laptop never asks for vendor or core count, so the count is worked out
    # rather than fixed: "[2/3]" should mean two of three questions left
    total = 0
    step = [0]

    def nxt():
        step[0] += 1
        return step[0]

    print(f'{BOLD}OpenCore EFI builder{RESET}')

    if a.check:
        if a.machine:
            checked, complaint = load_machine(a.machine)
            if checked is None:
                sys.exit(complaint)
            where = f'report {Path(a.machine).name}'
        else:
            checked, where = detect.probe(), 'this machine'
        print()
        print('\n'.join(summary.render(checked, where)))
        return 0

    # Which machine the EFI is for has to be settled before anything is shown as
    # detected, because detection reads the machine this runs on. A hint from
    # the wrong computer is worse than none: it looks like an answer.
    hw, source, manual = {}, None, False
    if a.machine:
        hw, source = load_machine(a.machine)
        if hw is None:
            sys.exit(source)
        describe_machine(overrides(a, hw), 'building for', source)
    elif a.no_detect:
        pass
    else:
        local = overrides(a, detect.probe())
        # the summary goes above the first question, not after it: the point of
        # showing it is that nobody answers anything before seeing it
        describe_machine(local, 'this machine', 'this machine')
        if not local.get('cpu'):
            print(f'  {DIM}could not read this machine; every question is still '
                  f'answerable{RESET}')
        choice = ask(nxt(), 0, 'Which machine is this EFI for?',
                     [('this', 'This machine'),
                      ('file', 'Another machine, and I have its hardware report'),
                      ('other', 'Another machine, and I do not have one'),
                      ('report', 'Neither - just write this machine\'s report, '
                                 'to build for it elsewhere')],
                     detected='this' if local.get('cpu') else None)
        if choice == 'report':
            # named in full before it is written, not after: "enter for
            # machine.json" does not say which directory that lands in, and for
            # the frozen build that is wherever the executable was started
            # started_in is where the person actually is; when frozen the working
            # directory has already moved into the unpacked bundle
            base = started_in or Path.cwd()
            default = base / 'machine.json'
            typed = prompt('Where should the report go?',
                           f'a path, or enter for {default}')
            out = str((base / Path(typed).expanduser()).resolve()) if typed else str(default)
            written = detect.write_report(out)
            print(f'\n  wrote {out}')
            print(f'  {detect.describe(written)}')
            print(f'\n  Copy it to the machine you build on and pass it back:')
            print(f'      setup.py --machine {Path(out).name}')
            return 0
        if choice == 'this':
            hw, source = local, 'this machine'
        elif choice == 'file':
            while True:
                path = prompt('Where is the report?',
                              'a path, or enter to answer the questions instead')
                if not path:
                    break
                if started_in:
                    path = str((started_in / path).resolve())
                hw, source = load_machine(path)
                if hw is not None:
                    describe_machine(overrides(a, hw), 'building for', source)
                    break
                print(f'      {YELLOW}{source}{RESET}')
                hw = {}
            manual = not hw
        else:
            manual = True
        if manual:
            print(f'\n  {DIM}Nothing is known about that machine, so nothing is '
                  f'detected for it.\n  Graphics, audio and the trackpad need a report '
                  f'taken there:\n      setup.py --report machine.json{RESET}')

    if a.no_detect:
        overrides(a, hw)
    if source is None and (hw.get('pci_ids') or hw.get('hda_ids')
                           or hw.get('nvme') or hw.get('acpi_ids')):
        source = 'the ids you passed'

    asked = step[0]      # the scope question, when it was asked at all

    # Everything the profile questions ask for is on the screen already when
    # detection worked, so offer to take it in one answer. Shown and confirmed,
    # never assumed: a wrong guess that arrives already applied is the thing
    # this whole flow is arranged to avoid.
    ready = profile_from(hw)
    if ready:
        r_plat, r_vendor, r_cpu, r_cores, r_oem = ready
        described = ', '.join(x for x in [
            r_plat.capitalize(),
            CPU_LABELS.get(r_cpu, r_cpu),
            f'{r_cores} cores' if r_cores else None,
            (r_oem.upper().replace('-', ' / ') if r_oem else 'no board overlay'),
        ] if x)
        if ask(nxt(), 0, 'Use what was detected, or answer for yourself?',
               [('go', f'Use it: {described}'),
                ('ask', 'Answer the questions myself')],
               detected='go') == 'go':
            plat, vendor, cpu, cores, oem = ready
            pname = f'{plat}-{vendor}' if vendor else plat
            print(f'      {DIM}the profile questions are answered; everything below '
                  f'is still asked{RESET}')
        else:
            ready = None
        asked = step[0]

    if not ready:
        plat = ask(nxt(), total, 'What kind of machine is this?',
                   [('desktop', 'Desktop'), ('laptop', 'Laptop')],
                   detected=('laptop' if hw.get('laptop') else
                             'desktop' if hw.get('laptop') is False else None))

        total = asked + 3    # laptop: platform, generation, brand
        vendor = None
        if plat == 'desktop':
            det = ('amd' if hw.get('generation') in ('ryzen-threadripper', 'bulldozer-jaguar')
                   else 'intel' if hw.get('generation') else None)
            # this answer decides whether a core count is asked for, so like the
            # first question it cannot honestly claim a total yet
            vendor = ask(nxt(), 0, 'Which CPU vendor?',
                         [('intel', 'Intel'), ('amd', 'AMD')], detected=det)
            total = asked + (5 if vendor == 'amd' else 4)
        else:
            print(f'\n      {DIM}laptop profiles cover Intel only, so no vendor question{RESET}')

        pname = f'{plat}-{vendor}' if vendor else plat
        choices = cpu_choices(pname)
        if not choices:
            sys.exit(f'no profiles for {pname}')
        gen = hw.get('generation')
        cpu = ask(nxt(), total, 'Which CPU generation?', choices,
                  detected=gen if any(v == gen for v, _ in choices) else None)

        cores = None
        if vendor == 'amd':
            opts = [(n, f'{n} cores') for n in (4, 6, 8, 12, 16, 24, 32, 64)]
            cores = ask(nxt(), total, 'How many physical cores?', opts,
                        detected=hw.get('cores') if any(v == hw.get('cores') for v, _ in opts) else None)

        oem = ask(nxt(), total, 'Board or laptop brand?',
                  [(o, o.upper().replace('-', ' / ')) for o in available('oem')],
                  detected=hw.get('oem'), allow_skip=True)

    row = dict(path='', platform=plat, vendor=vendor, cpu=cpu,
               chipset=None, oem=oem, variant=None, cores=cores)
    if not (PROFILES / 'cpu' / pname / f'{cpu}.toml').exists():
        sys.exit(f'no profile for {cpu}')
    if oem and not (PROFILES / 'overlay' / f'oem.{oem}.toml').exists():
        print(f'\n  {DIM}no {oem} overlay for this combination; using the generic profile{RESET}')
        row['oem'] = None

    # network hardware: only offered when something was actually recognised,
    # so nobody is asked to decide about a device they do not have
    if hw.get('gpu_devices'):
        print(f'\n{BOLD}Graphics{RESET}')
        lines, gpu_args = gpu.report(hw['gpu_devices'], cpu, hw.get('cpu'))
        print('\n'.join(lines))
        if gpu_args:
            print(f'\n      {GREEN}boot arguments needed: {" ".join(gpu_args)}{RESET}')
            print(f'      {DIM}added to the config below{RESET}')

    notes = []
    boot_args = []

    if hw.get('gpu_devices'):
        boot_args += gpu.report(hw['gpu_devices'], cpu, hw.get('cpu'))[1]

    if hw.get('hda_ids'):
        print(f'\n{BOLD}Audio{RESET}')
        alines, alcid, asteps = audio.report(hw['hda_ids'], oem or hw.get('oem_raw'))
        print('\n'.join(alines))
        if alcid is not None:
            boot_args.append(f'alcid={alcid}')
            notes.append(asteps)

    acpi_results = None
    # neither of the vendored tools can be driven by --answers: both are menus a
    # person works through, and offering one to a script means a build that
    # hangs waiting for a keystroke nobody is there to press
    interactive = not SCRIPTING
    # the automatic set asks nothing by construction, so it is the one thing here
    # a script may have. Without this it could not be tested against a real
    # machine's tables anywhere, which is the only place it means anything.
    if SCRIPTING and a.acpi_tables and acpi.available():
        print(f'\n{BOLD}ACPI{RESET}')
        got, complaint = acpi.run(Path(a.out).parent / 'acpi', a.acpi_tables,
                                  unattended=True)
        if got:
            aml, add, patches = acpi.collect(got)
            print(f'      {GREEN}{len(aml)} SSDTs and {len(patches)} patches{RESET}')
            acpi_results = str(got)
        else:
            print(f'      {YELLOW}{complaint}{RESET}')
    if interactive and acpi.available() and (
            a.acpi_tables or acpi.platform_key() != 'darwin'):
        # SSDTs are written against one machine's tables. Offer it where there
        # are tables to write against: either a dump that came with the report,
        # or this machine, which is the target when it is the target.
        print(f'\n{BOLD}ACPI{RESET}')
        where = a.acpi_tables or ('this machine' if not manual and source ==
                                  'this machine' else None)
        if where:
            print(f'  {DIM}A laptop usually needs a few SSDTs - a fake EC, PLUG for '
                  f'power\n  management, PNLF for the backlight - and each is written '
                  f'against the\n  machine\'s own tables. SSDTTime does that and is '
                  f'bundled here.{RESET}')
            print(f'      {DIM}Six of them decide entirely from the tables and ask '
                  f'nothing:\n      {", ".join(n for _, n, _ in acpi.AUTOMATIC)}.\n'
                  f'      The rest ask questions only you can answer, so they are '
                  f'in the menus.{RESET}')
            picked = ask(0, 0, 'Work out the SSDTs now?',
                         [('auto', 'Yes, the six that decide for themselves'),
                          ('menu', f'Yes, and let me choose, against {where}'),
                          ('no', 'No, the profile\'s generic SSDTs will do')])
            if picked != 'no':
                got, complaint = acpi.run(Path(a.out).parent / 'acpi',
                                          a.acpi_tables,
                                          unattended=picked == 'auto')
                if got:
                    aml, add, patches = acpi.collect(got)
                    print(f'      {GREEN}{len(aml)} SSDTs and {len(patches)} '
                          f'patches{RESET}')
                    acpi_results = str(got)
                else:
                    print(f'      {YELLOW}{complaint}; the profile\'s SSDTs stay'
                          f'{RESET}')
        else:
            print(f'  {DIM}SSDTs need the target machine\'s ACPI tables. Take them '
                  f'there with\n      detect.py --report machine.json --acpi ACPI/'
                  f'{RESET}')

    smbus_disable = []
    usb_implies = None
    queued = []
    if interactive and not a.usb_map and usbmap.available() and usbmap.runnable_here():
        # the tool is here and this is the machine it runs on, so offer it
        # rather than describing it: the map has to be made somewhere and this
        # is the only place it can be
        print(f'\n{BOLD}USB ports{RESET}')
        print(f'  {DIM}UTBDefault turns every port on without mapping any. A real map '
              f'takes\n  plugging a device into each port in turn, which USBToolBox '
              f'does and this\n  cannot - so it is here, and it can run now.{RESET}')
        if ask(0, 0, 'Map the USB ports now?',
               [('yes', 'Yes, run USBToolBox'),
                ('no', 'No, use UTBDefault and map later')]) == 'yes':
            made, implies = usbmap.run(Path(a.out).parent / 'usbmap')
            if made:
                print(f'      {GREEN}{made.name} written{RESET}')
                a.usb_map = str(made)
                usb_implies = implies
            else:
                print(f'      {YELLOW}{implies}; UTBDefault stays in{RESET}')
    if not a.usb_map:
        # UTBDefault claims every port on the controller, which boots but is not
        # a map: macOS allows fifteen ports per controller and a machine with
        # more than that loses whichever the default happens to reach last.
        print(f'\n{BOLD}USB ports{RESET}')
        print(f'  {DIM}UTBDefault is going in, which turns every port on without '
              f'mapping any.\n  That boots. It is not the same as a map, and sleep and '
              f'USB 3 ports are\n  where the difference shows.{RESET}')
        print(f'      {DIM}To make one: run USBToolBox on the target machine under '
              f'Windows, plug a\n      device into every port when it asks, and it '
              f'writes a UTBMap.kext.\n      Then build again with --usb-map '
              f'UTBMap.kext and it replaces the default.{RESET}')
        if usbmap.available():
            print(f'      {DIM}It is bundled here: on Windows this builder offers to '
                  f'run it for you.{RESET}')
        else:
            print(f'      {DIM}github.com/USBToolBox/tool{RESET}')
        notes.append(usb_notes())
    if a.usb_map:
        mapped = Path(a.usb_map)
        if not (mapped / 'Contents' / 'Info.plist').exists():
            sys.exit(f'{mapped} does not look like a kext')
        print(f'\n{BOLD}USB port map{RESET}')
        print(f'  {mapped.name}')
        print(f'      {DIM}goes in, and UTBDefault comes out - upstream: "it is not needed '
              f'and must be removed if you choose to map"{RESET}')
        queued.append({'Arch': 'x86_64', 'BundlePath': mapped.name,
                        'Comment': 'USB port map', 'Enabled': True,
                        'ExecutablePath': '', 'MaxKernel': '', 'MinKernel': '',
                        'PlistPath': 'Contents/Info.plist',
                        'SourcePath': str(mapped.resolve())})

    device_props = {}
    if hw.get('gpu_devices'):
        # a framebuffer id cannot rescue an iGPU that has been run and found
        # not to accelerate, so the field report suppresses the whole section
        state = gpu.igpu_verdict(cpu)[0]
        field = gpu.field_igpu(hw.get('cpu'))
        works = state == 'works' and not (field and field['status'] != 'works')
        ilines, iprops, isteps = igpu.report(cpu, plat == 'laptop', works)
        if field and not works:
            # the profiles ship a placeholder. Leaving it because the section was
            # skipped would put a value in the config that nobody chose.
            print(f'\n{BOLD}Intel graphics framebuffer{RESET}')
            print(f'      {YELLOW}none written: this iGPU has been reported not to '
                  f'accelerate, and a framebuffer id will not change that{RESET}')
            device_props.update(igpu.props_for(None))
        if ilines:
            print(f'\n{BOLD}Intel graphics framebuffer{RESET}')
            print('\n'.join(ilines))
            notes.append(isteps)
            device_props.update(iprops)
            cands = igpu.candidates(cpu, plat == 'laptop')
            if len(cands) > 1:
                # the first option is what would have gone in anyway, so pressing
                # 1 is the old behaviour and the rest is a choice, not a chore
                options = [(c['value'], f'{c["value"]}  {c["label"]}') for c in cands]
                options.append((igpu.NO_ACCELERATION['value'],
                                f'{igpu.NO_ACCELERATION["value"]}  '
                                f'{igpu.NO_ACCELERATION["label"]}'))
                options.append((None, 'leave the key out; WhateverGreen picks'))
                picked = ask(0, 0, 'Which framebuffer id?', options,
                             detected=cands[0]['value'])
                by_value = {c['value']: c for c in cands}
                by_value[igpu.NO_ACCELERATION['value']] = igpu.NO_ACCELERATION
                device_props = {k: v for k, v in device_props.items()
                                if k != igpu.IGPU_PATH}
                device_props.update(igpu.props_for(by_value.get(picked)))
                if picked == igpu.NO_ACCELERATION['value']:
                    print(f'      {YELLOW}{igpu.NO_ACCELERATION["note"]}{RESET}')

    input_lines, input_kexts = inputdev.entries(hw.get('pci_ids'), hw.get('ps2'),
                                                hw.get('acpi_ids'))
    pointing = [d for d in hw.get('peripherals', [])
                if d['kind'] in ('pointing device', 'keyboard')]
    aside = [d['name'] for d in pointing if d.get('virtual')]
    pointing = [d for d in pointing if not d.get('virtual')]
    if input_lines or pointing:
        print(f'\n{BOLD}Trackpad and keyboard{RESET}')
        for dev in pointing:
            on_ps2 = ' on the PS/2 controller' if dev.get('driver') == 'i8042prt' else ''
            print(f'  {dev["name"]}  {DIM}({dev["kind"]}'
                  + (f', {dev["id"]}' if dev.get('id') else '') + f'{on_ps2}){RESET}')
        if aside:
            print(f'      {DIM}ignored: {", ".join(aside)}  (remote desktop input, '
                  f'not this machine\'s){RESET}')
        bus, smbus_id, smbus_name = inputdev.smbus_trackpad(hw.get('device_names'))
        if bus:
            rule = inputdev.smbus_rule(bus)
            print(f'      {GREEN}{smbus_name}  [{smbus_id}]{RESET}')
            print(f'      {DIM}Windows named the SMBus controller after the driver '
                  f'bound to it, which\n      is this machine saying the trackpad is '
                  f'on SMBus and not PS/2.{RESET}')
            print(f'      {DIM}"{rule["quote"]}"{RESET}')
            print(f'      {DIM}{len(rule["kexts"])} kexts in the order the project '
                  f'gives, and {len(rule.get("disable", []))} of the profile\'s '
                  f'turned off:\n'
                  + '\n'.join(f'        + {k}' for k in rule['kexts'])
                  + ''.join(f'\n        - {k}' for k in rule.get('disable', []))
                  + RESET)
            if rule.get('macos_check'):
                print(f'      {DIM}Confirm it in macOS afterwards: '
                      f'"{rule["macos_check"]}"{RESET}')
            if ask(0, 0, 'Set the trackpad up for SMBus?',
                   [('yes', 'Yes, as the project says'),
                    ('no', 'No, VoodooPS2 alone')]) == 'yes':
                for bundle in rule['kexts']:
                    entry = {'Arch': 'x86_64', 'BundlePath': bundle,
                             'Comment': rule['label'], 'Enabled': True,
                             'ExecutablePath': '', 'MinKernel':
                                 rule.get('min_kernel', ''), 'MaxKernel': '',
                             'PlistPath': 'Contents/Info.plist'}
                    input_kexts.append(entry)
                smbus_disable = list(rule.get('disable', []))
        if input_lines:
            print('\n'.join(input_lines))
        elif pointing and not bus:
            print(f'      {DIM}no I2C controller here; if the trackpad turns out to be '
                  f'on SMBus, NEXT-STEPS.txt names the two kexts for that{RESET}')
        # the follow-up is written either way: a PS/2 laptop is the one most
        # likely to have an SMBus trackpad and used to be told nothing
        notes.append(inputdev.notes(hw.get('pci_ids'), hw.get('acpi_ids')))

    storage_kexts, storage_drives = netkexts.storage_entries(hw.get('nvme'))
    if hw.get('nvme'):
        print(f'\n{BOLD}Storage{RESET}')
        for drive in hw['nvme']:
            print(f'  {drive}')
        if storage_drives:
            print(f'      {GREEN}NVMeFix improves Apple\'s NVMe driver for '
                  f'third-party SSDs; adding it{RESET}')
        else:
            print(f'      {DIM}Apple NVMe, which is the case NVMeFix is not for{RESET}')

    # the same query answers two questions, so it is split by what each device
    # is rather than printed under one heading that fits only half of them
    real = [d for d in hw.get('peripherals', []) if not d.get('virtual')]
    media = [d for d in real if d['kind'] in ('camera', 'card reader')]
    if media:
        print(f'\n{BOLD}Camera and card reader{RESET}')
        for dev in media:
            where = 'on USB' if dev['usb'] else 'not on USB'
            print(f'  {dev["name"]}  {DIM}({dev["kind"]}, {where}){RESET}')
        if any(d['kind'] == 'camera' and d['usb'] for d in media):
            print(f'      {DIM}a USB camera is handled by the class driver macOS already '
                  f'has, so it usually needs nothing{RESET}')
        if any(d['kind'] == 'camera' and not d['usb'] for d in media):
            print(f'      {YELLOW}a camera that is not on USB is an IPU or MIPI sensor, '
                  f'which macOS has no driver for{RESET}')
        print(f'      {DIM}beyond that this repository has no support data for these, '
              f'so nothing is claimed or added{RESET}')

    matched = advise.matched_kexts(hw.get('pci_ids', []), hw.get('usb_ids', []))
    if manual and not matched:
        # no ids to match, so the person names the hardware instead. Asked only
        # here: where ids exist, matching them beats being asked to remember.
        print(f'\n{BOLD}Network{RESET}')
        print(f'  {DIM}These come from what this repository ships drivers for. Pick what '
              f'that\n  machine has; anything else is left out rather than guessed at.{RESET}')
        matched = pick_network()
    # storage has no version ambiguity, so it rides along with the same question
    # rather than adding one - but it must not depend on there being network
    # hardware to match, or a machine with neither gets nothing
    # a real map replaces the catch-all; keeping both would have UTBDefault
    # claim the controllers the map is for
    # which kexts a map replaces depends on which map it is: the native ones
    # need no USBToolBox.kext, and leaving it in would inject a driver for
    # hardware nothing is claiming
    cmd_extra_drop = list(usb_implies['drops']) if usb_implies else (
        ['UTBDefault.kext'] if a.usb_map else [])
    if matched or storage_kexts or input_kexts:
        if matched and not manual:
            print(f'\n{BOLD}Network kexts{RESET}')
            advise.report(hw.get('pci_ids', []), hw.get('usb_ids', []),
                          source or 'the ids you passed', hw.get('device_names'))
        mode = ask(0, 0, 'Add these to the EFI?',
                   [('all', 'Yes, for every macOS version they support'),
                    ('one', 'Yes, for one macOS version only'),
                    ('no', 'No, leave them out')])
        if mode != 'no':
            darwin = None
            if mode == 'one' and matched:
                rels = netkexts.releases()
                darwin = ask(0, 0, 'Which macOS are you installing?',
                             [(r['darwin'], f"{r['name']} {r['version']}") for r in rels])
            # Intel Wi-Fi resolves to one build, so the every-version mode has
            # to ask which macOS after all - but only when such a card is there
            wifi_darwin = darwin
            if netkexts.wifi_entry(matched, 0)[1] and wifi_darwin is None:
                print(f'\n      {DIM}Intel Wi-Fi is built separately for each macOS release, '
                      f'so it needs one.{RESET}')
                rels = netkexts.releases()
                wifi_darwin = ask(0, 0, 'Which macOS for the Wi-Fi kext?',
                                  [(r['darwin'], f"{r['name']} {r['version']}") for r in rels],
                                  allow_skip=True)
            entries, chosen = netkexts.entries(matched, darwin) if matched else ([], [])
            entries += storage_kexts + input_kexts
            if wifi_darwin is not None:
                wifi, note = netkexts.wifi_entry(matched, wifi_darwin)
                if wifi:
                    entries.append(wifi)
                if note:
                    print(f'      {GREEN if wifi else YELLOW}{note}{RESET}')
            netkexts.fill_executables(entries)
            for s_, kexts in chosen:
                print(f'      {GREEN}{s_["label"]}{RESET}  '
                      + ', '.join(k['bundle'].replace('.kext', '') for k in kexts))
            queued += entries

    # build.main is called rather than spawned. sys.executable is this program
    # when frozen, not a Python interpreter, so a subprocess would re-invoke the
    # menus with build's arguments.
    cmd = ['--platform', plat, '--cpu', cpu, '--out', a.out]
    if boot_args:
        cmd += ['--boot-args', ' '.join(boot_args)]
    if cmd_extra_drop:
        cmd += ['--drop-kexts', ','.join(cmd_extra_drop)]

    import json
    import tempfile

    props_file = None
    if device_props:
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(device_props, fh)
        fh.close()
        props_file = fh.name
        cmd += ['--device-props', props_file]
    notes_file = None
    if notes:
        fh = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        fh.write('Follow-up for this EFI\n' + '=' * 22 + '\n\n' + '\n'.join(notes))
        fh.close()
        notes_file = fh.name
        cmd += ['--notes', notes_file]
    extra_file = None
    if queued:
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(queued, fh)
        fh.close()
        extra_file = fh.name
        cmd += ['--add-kexts', extra_file]
    if vendor:
        cmd += ['--vendor', vendor]
    if cores:
        cmd += ['--cores', str(cores)]
    if row['oem']:
        cmd += ['--oem', row['oem']]
    if acpi_results:
        cmd += ['--acpi', acpi_results]
    if smbus_disable:
        cmd += ['--disable-kexts', ','.join(smbus_disable)]

    print(f'\n{BOLD}Building{RESET}')
    print(f'  {DIM}build {" ".join(cmd)}{RESET}\n')
    sys.stdout.flush()
    try:
        rc = build.main(cmd)
    except SystemExit as exc:
        rc = exc.code or 0
    if rc:
        return rc
    if extra_file:
        os.unlink(extra_file)
    if notes_file:
        os.unlink(notes_file)
    if props_file:
        os.unlink(props_file)
    if not matched and (hw.get('pci_ids') or hw.get('usb_ids')):
        # nothing matched, so no kext question was asked: say what was seen
        print()
        advise.report(hw.get('pci_ids', []), hw.get('usb_ids', []),
                      source or 'the ids you passed')

    print(f'\n  Copy the {BOLD}EFI{RESET} folder from {BOLD}{a.out}{RESET} to the EFI '
          f'partition of your USB drive.')
    print(f'  {DIM}ROM is still a placeholder - set it to your own MAC address, see the '
          f'README Post Installation section.{RESET}')
    return 0


def hold():
    """Keep the window open when there is nobody else keeping it open.

    A frozen build started from a file manager gets a console of its own, and
    that console dies with the process - taking the summary, the warnings and
    the path to the EFI with it. Somebody who double-clicked the executable sees
    a window flash and nothing else.

    Only there: from a shell the window outlives the program, and a run with
    --answers has nobody to press the key."""
    if not getattr(sys, 'frozen', False) or SCRIPTING:
        return
    try:
        if not sys.stdin.isatty():
            return
        input('\n  Press enter to close.')
    except (EOFError, OSError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    try:
        code = main()
    except SystemExit as exc:
        # a message rather than a number is how the tools refuse; printing it
        # before the pause is the whole point of pausing
        if isinstance(exc.code, str):
            print(exc.code)
            code = 1
        else:
            code = exc.code or 0
    except KeyboardInterrupt:
        print('\n  stopped')
        code = 130
    hold()
    sys.exit(code)
