"""Interactive EFI builder.

Asks a short series of numbered questions and writes the EFI folder for one
machine. Where the running system can tell us something - that this is a laptop,
that the CPU is Kaby Lake, that the board is an HP - it is shown next to the
question as `detected`. It is never preselected and never chosen automatically:
detection can be wrong, and a wrong answer that arrives already ticked is one
nobody rechecks.

    python3 tools/setup.py

Standard library only, no network.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise
import audio
import build
import detect
import gpu
import netkexts
import ocgen

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


def ask(step, total, question, options, detected=None, allow_skip=False):
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
        print(f'      {len(options) + 1:2d}) none of these')
    while True:
        if SCRIPTED:
            raw = SCRIPTED.pop(0)
            print(f'      > {raw}')
        else:
            raw = input('      > ').strip()
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='build/EFI')
    ap.add_argument('--no-detect', action='store_true',
                    help='skip hardware detection and just ask')
    ap.add_argument('--ids', help='PCI ids to use instead of probing, comma separated')
    ap.add_argument('--usb-ids', help='USB ids to use instead of probing, comma separated')
    ap.add_argument('--hda-ids', help='HD audio codec ids to use instead of probing')
    ap.add_argument('--nvme', help='NVMe drive models to use instead of probing')
    ap.add_argument('--answers', help='answer the menus non-interactively, comma separated; '
                                      'for scripting and for CI')
    a = ap.parse_args()

    if a.answers:
        SCRIPTED.extend(x.strip() for x in a.answers.split(',') if x.strip())

    started_in = unbundle()
    if started_in:
        a.out = str((started_in / a.out).resolve())

    hw = {} if a.no_detect else detect.probe()
    if a.ids is not None or a.usb_ids is not None:
        hw['pci_ids'] = [x.strip() for x in (a.ids or '').split(',') if x.strip()]
        hw['usb_ids'] = [x.strip() for x in (a.usb_ids or '').split(',') if x.strip()]
    if a.hda_ids is not None:
        hw['hda_ids'] = [x.strip() for x in a.hda_ids.split(',') if x.strip()]
    if a.nvme is not None:
        hw['nvme'] = [x.strip() for x in a.nvme.split(',') if x.strip()]
    print(f'{BOLD}OpenCore EFI builder{RESET}')
    if hw.get('cpu'):
        print(f'  {DIM}this machine:{RESET} {hw["cpu"]}'
              + (f', {hw["cores"]} cores' if hw.get('cores') else '')
              + (f', {hw["oem_raw"]}' if hw.get('oem_raw') else ''))
        for g in hw.get('gpu_devices', [])[:3]:
            print(f'  {DIM}graphics:{RESET}     {g["name"]}'
                  + (f'  {DIM}[{g["id"]}]{RESET}' if g.get('id') else ''))
        if hw.get('gpu_virtual'):
            # named rather than dropped silently: someone who installed one of
            # these should see that it was recognised and set aside
            print(f'  {DIM}ignored:{RESET}      {", ".join(hw["gpu_virtual"])}'
                  f'  {DIM}(virtual display adapters, not graphics hardware){RESET}')
    elif not a.no_detect:
        print(f'  {DIM}could not read this machine; every question is still answerable{RESET}')

    # a laptop never asks for vendor or core count, so the count is worked out
    # rather than fixed: "[2/3]" should mean two of three questions left
    total = 0
    step = [0]

    def nxt():
        step[0] += 1
        return step[0]

    plat = ask(nxt(), total, 'What kind of machine is this?',
               [('desktop', 'Desktop'), ('laptop', 'Laptop')],
               detected=('laptop' if hw.get('laptop') else
                         'desktop' if hw.get('laptop') is False else None))

    total = 3            # laptop: platform, generation, brand
    vendor = None
    if plat == 'desktop':
        det = ('amd' if hw.get('generation') in ('ryzen-threadripper', 'bulldozer-jaguar')
               else 'intel' if hw.get('generation') else None)
        # this answer decides whether a core count is asked for, so like the
        # first question it cannot honestly claim a total yet
        vendor = ask(nxt(), 0, 'Which CPU vendor?',
                     [('intel', 'Intel'), ('amd', 'AMD')], detected=det)
        total = 5 if vendor == 'amd' else 4
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
        lines, gpu_args = gpu.report(hw['gpu_devices'], cpu)
        print('\n'.join(lines))
        if gpu_args:
            print(f'\n      {GREEN}boot arguments needed: {" ".join(gpu_args)}{RESET}')
            print(f'      {DIM}added to the config below{RESET}')

    notes = []
    boot_args = []
    if hw.get('gpu_devices'):
        boot_args += gpu.report(hw['gpu_devices'], cpu)[1]

    if hw.get('hda_ids'):
        print(f'\n{BOLD}Audio{RESET}')
        alines, alcid, asteps = audio.report(hw['hda_ids'], oem or hw.get('oem_raw'))
        print('\n'.join(alines))
        if alcid is not None:
            boot_args.append(f'alcid={alcid}')
            notes.append(asteps)

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

    if hw.get('peripherals'):
        print(f'\n{BOLD}Camera and card reader{RESET}')
        for dev in hw['peripherals']:
            where = 'on USB' if dev['usb'] else 'not on USB'
            print(f'  {dev["name"]}  {DIM}({dev["kind"]}, {where}){RESET}')
        if any(d['kind'] == 'camera' and d['usb'] for d in hw['peripherals']):
            print(f'      {DIM}a USB camera is handled by the class driver macOS already '
                  f'has, so it usually needs nothing{RESET}')
        if any(d['kind'] == 'camera' and not d['usb'] for d in hw['peripherals']):
            print(f'      {YELLOW}a camera that is not on USB is an IPU or MIPI sensor, '
                  f'which macOS has no driver for{RESET}')
        print(f'      {DIM}beyond that this repository has no support data for these, '
              f'so nothing is claimed or added{RESET}')

    extra_file = None
    matched = advise.matched_kexts(hw.get('pci_ids', []), hw.get('usb_ids', []))
    # storage has no version ambiguity, so it rides along with the same question
    # rather than adding one - but it must not depend on there being network
    # hardware to match, or a machine with neither gets nothing
    if matched or storage_kexts:
        if matched:
            print(f'\n{BOLD}Network kexts{RESET}')
            advise.report(hw['pci_ids'], hw['usb_ids'], 'this machine')
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
            entries += storage_kexts
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
            import json
            import tempfile
            fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
            json.dump(entries, fh)
            fh.close()
            extra_file = fh.name

    # build.main is called rather than spawned. sys.executable is this program
    # when frozen, not a Python interpreter, so a subprocess would re-invoke the
    # menus with build's arguments.
    cmd = ['--platform', plat, '--cpu', cpu, '--out', a.out]
    if boot_args:
        cmd += ['--boot-args', ' '.join(boot_args)]
    notes_file = None
    if notes:
        import tempfile
        fh = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        fh.write('Follow-up for this EFI\n' + '=' * 22 + '\n\n' + '\n'.join(notes))
        fh.close()
        notes_file = fh.name
        cmd += ['--notes', notes_file]
    if extra_file:
        cmd += ['--add-kexts', extra_file]
    if vendor:
        cmd += ['--vendor', vendor]
    if cores:
        cmd += ['--cores', str(cores)]
    if row['oem']:
        cmd += ['--oem', row['oem']]

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
    elif hw.get('pci_ids') or hw.get('usb_ids'):
        print()
        advise.report(hw['pci_ids'], hw['usb_ids'], 'this machine')

    print(f'\n  Copy the {BOLD}EFI{RESET} folder from {BOLD}{a.out}{RESET} to the EFI '
          f'partition of your USB drive.')
    print(f'  {DIM}ROM is still a placeholder - set it to your own MAC address, see the '
          f'README Post Installation section.{RESET}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
