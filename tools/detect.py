"""Read what the machine says about itself.

Detection never decides anything. It annotates the menus in setup.py so the
choice is easier, and it stays quiet when it is not confident: a wrong hint that
looks authoritative is worse than no hint, because the person following it has
no reason to doubt it.

Windows, Linux and macOS are all read through commands that ship with the OS,
so this needs no dependencies and no admin rights.

Detection reads the machine it runs on, which is not always the machine being
built for. `--report` writes everything it found to a file so the build can
happen somewhere else:

    python3 tools/detect.py --report machine.json     # on the target
    python3 tools/setup.py --machine machine.json     # anywhere
"""
import argparse
import datetime
import json
import platform
import re
import subprocess
from pathlib import Path


def _run(cmd, shell=False):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=25)
        return r.stdout if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def _ps(script):
    return _run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script])


def _read(path):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return ''


# --------------------------------------------------------------------------
# Intel and AMD both encode the generation in the model number, but only for
# part of their range, and the exceptions are what make a naive rule dangerous.
# Anything not listed here returns nothing rather than a guess.

INTEL_DESKTOP = {
    2: 'sandy-bridge', 3: 'ivy-bridge', 4: 'haswell', 5: 'broadwell',
    6: 'sky-lake', 7: 'kaby-lake', 8: 'coffe-lake', 9: 'coffe-lake',
    10: 'comet-lake', 11: 'rocket-lake', 12: 'alder-lake', 13: 'raptor-lake',
    14: 'raptor-lake',
}
INTEL_LAPTOP = {
    2: 'sandy-bridge-uefi-bios', 3: 'ivy-bridge', 4: 'haswell', 5: 'broadwell',
    6: 'sky-lake', 7: 'kaby-lake', 8: 'coffee-lake-whiskey-lake',
    9: 'coffe-lake-plus', 10: 'comet-lake', 11: 'ice-lake',
}


def cpu_generation(brand, laptop):
    """Profile name for a CPU brand string, or None when unsure.

    Intel Core parts carry the generation in the digits before the SKU:
    i5-7200U is 7th generation. Four-digit SKUs are 2nd generation onwards;
    three-digit ones are 1st generation Nehalem and are not covered here.
    """
    if not brand:
        return None
    b = brand.lower()
    if 'ryzen' in b or 'threadripper' in b or 'epyc' in b:
        return 'ryzen-threadripper'
    if re.search(r'\bfx-\d{4}\b', b) or re.search(r'\ba\d{1,2}-\d{4}\b', b):
        return 'bulldozer-jaguar'
    m = re.search(r'\bi[3579][- ](\d{4,5})(g\d)?[a-z]*\b', b)
    if m:
        digits, gsuffix = m.group(1), m.group(2)
        # A four-digit SKU normally names the generation with its first digit -
        # 2600K is 2nd generation. Ice Lake mobile breaks that: 1065G7 is 10th.
        # The G suffix is what separates the two cases.
        if len(digits) == 5 or gsuffix:
            gen = int(digits[:2])
        else:
            gen = int(digits[0])
        if laptop and gen == 10:
            # 10th generation mobile covers two architectures and the G suffix
            # is what tells them apart: 10510U is Comet Lake, 1065G7 is Ice Lake
            return 'ice-lake' if gsuffix else 'comet-lake'
        table = INTEL_LAPTOP if laptop else INTEL_DESKTOP
        return table.get(gen)
    if 'xeon' in b or 'core 2' in b or 'pentium' in b or 'celeron' in b:
        return None                       # too many families share these names
    return None


# --------------------------------------------------------------------------

OEM_ALIASES = {
    'hewlett-packard': 'hp', 'hp': 'hp', 'hp inc.': 'hp',
    'dell': 'dell', 'dell inc.': 'dell',
    'sony': 'sony', 'sony corporation': 'sony',
    'asus': 'asus', 'asustek computer inc.': 'asus', 'asustek': 'asus',
    'micro-star international co., ltd.': 'msi', 'msi': 'msi',
}


def normalise_oem(vendor):
    if not vendor:
        return None
    v = vendor.strip().lower()
    for key, val in OEM_ALIASES.items():
        if v == key or v.startswith(key):
            return val
    return None


# --------------------------------------------------------------------------

def _windows():
    out = {}
    cpu = _ps('(Get-CimInstance Win32_Processor | Select-Object -First 1).Name')
    out['cpu'] = cpu.strip()
    cores = _ps('(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores')
    out['cores'] = int(cores.strip()) if cores.strip().isdigit() else None
    out['vendor'] = _ps('(Get-CimInstance Win32_ComputerSystem).Manufacturer').strip()
    chassis = _ps('(Get-CimInstance Win32_SystemEnclosure).ChassisTypes -join ","')
    types = {int(x) for x in re.findall(r'\d+', chassis)}
    if types:
        # 8-14 and 30-32 are the portable chassis codes in the DMTF table
        out['laptop'] = bool(types & {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32})
    # Win32_VideoController lists every display adapter, including virtual ones
    # a remote desktop or a dummy-monitor tool installs. Those enumerate under
    # ROOT rather than PCI, so the bus is what separates the graphics card from
    # a driver pretending to be one.
    out['gpu'] = [l.strip() for l in
                  _ps('Get-CimInstance Win32_VideoController | ForEach-Object '
                      '{ "$($_.PNPDeviceID)|$($_.Name)" }').splitlines() if l.strip()]
    out['pci'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like "PCI*" } | '
        'ForEach-Object { "$($_.PNPDeviceID)|$($_.Name)" }')
    out['usb'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like "USB*" } | '
        'ForEach-Object { "$($_.PNPDeviceID)|$($_.Name)" }')
    out['peripherals'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object '
        '{ $_.PNPClass -in @("Camera","Image","SDHost","MTD","Mouse","Keyboard") } '
        '| ForEach-Object '
        '{ "$($_.PNPClass)|$($_.PNPDeviceID)|$($_.Name)" }')
    # BusType 17 is NVMe in the storage WMI classes, which is a cleaner answer
    # than guessing from a PCI class code or a model string.
    out['storage'] = _ps(
        'Get-CimInstance -Namespace root/Microsoft/Windows/Storage '
        '-ClassName MSFT_PhysicalDisk | ForEach-Object '
        '{ "$($_.BusType)|$($_.FriendlyName)" }')
    # The HD Audio codec is a device behind the controller and carries its own
    # VEN/DEV, which is what AppleALC keys its layouts on.
    out['hda'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like "HDAUDIO*" } | '
        'ForEach-Object { "$($_.PNPDeviceID)|$($_.Name)" }')
    return out


def _linux():
    out = {}
    cpuinfo = _read('/proc/cpuinfo')
    m = re.search(r'^model name\s*:\s*(.+)$', cpuinfo, re.M)
    out['cpu'] = m.group(1).strip() if m else ''
    ids = set(re.findall(r'^core id\s*:\s*(\d+)$', cpuinfo, re.M))
    out['cores'] = len(ids) or None
    out['vendor'] = _read('/sys/class/dmi/id/sys_vendor')
    chassis = _read('/sys/class/dmi/id/chassis_type')
    if chassis.isdigit():
        out['laptop'] = int(chassis) in {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
    out['pci'] = _run(['lspci', '-nn'])
    out['gpu'] = [f"PCI|{l.split(': ', 1)[-1]}" for l in out['pci'].splitlines()
                  if 'VGA compatible controller' in l or '3D controller' in l]
    out['usb'] = _run(['lsusb'])
    # ALSA prints the codec's full HDA id as one 8-digit word
    out['hda'] = ''.join(_read(p) for p in
                         __import__('glob').glob('/proc/asound/card*/codec#*'))
    out['peripherals'] = '\n'.join(
        f'Camera|{l}' for l in (out.get('usb') or '').splitlines() if 'cam' in l.lower())
    import glob as _glob
    out['storage'] = '\n'.join(
        f'17|{_read(p + "/model")}' for p in sorted(_glob.glob('/sys/class/nvme/nvme*')))
    return out


def _macos():
    out = {}
    out['cpu'] = _run(['sysctl', '-n', 'machdep.cpu.brand_string']).strip()
    cores = _run(['sysctl', '-n', 'hw.physicalcpu']).strip()
    out['cores'] = int(cores) if cores.isdigit() else None
    model = _run(['sysctl', '-n', 'hw.model']).strip()
    if model:
        out['laptop'] = model.startswith(('MacBook',))
    out['vendor'] = ''
    out['pci'] = _run(['system_profiler', 'SPPCIDataType'])
    out['usb'] = _run(['system_profiler', 'SPUSBDataType'])
    out['storage'] = '\n'.join(
        f'17|{m}' for m in re.findall(r'^\s{6}(\S.*?):$',
                                      _run(['system_profiler', 'SPNVMeDataType']), re.M))
    out['gpu'] = [f'PCI|{m.strip()}' for m in re.findall(
        r'^\s*Chipset Model:\s*(.+)$',
        _run(['system_profiler', 'SPDisplaysDataType']), re.M)]
    return out


# --------------------------------------------------------------------------
# Each OS words its device list differently; all three end up as vendor:device
# in lower-case hex, which is what the kexts declare and what the table keys on.

PCI_PATTERNS = [
    re.compile(r'ven_([0-9a-f]{4})&dev_([0-9a-f]{4})', re.I),        # Windows PNPDeviceID
    re.compile(r'\[([0-9a-f]{4}):([0-9a-f]{4})\]', re.I),            # Linux lspci -nn
]
USB_PATTERNS = [
    re.compile(r'vid_([0-9a-f]{4})&pid_([0-9a-f]{4})', re.I),        # Windows
    re.compile(r'\bID\s+([0-9a-f]{4}):([0-9a-f]{4})\b', re.I),       # Linux lsusb
]


HDA_PATTERNS = [
    re.compile(r'hdaudio\\func_\d+&ven_([0-9a-f]{4})&dev_([0-9a-f]{4})', re.I),  # Windows
    re.compile(r'Vendor Id:\s*0x([0-9a-f]{4})([0-9a-f]{4})', re.I),               # ALSA
]


def _pairs(text, patterns):
    out = set()
    for pat in patterns:
        for a, b in pat.findall(text or ''):
            out.add(f'{a.lower()}:{b.lower()}')
    return out


def _apple_pairs(text, vendor_key, device_key):
    """system_profiler prints the two halves on separate lines within a block."""
    out, vendor = set(), None
    for line in (text or '').splitlines():
        m = re.search(rf'{vendor_key}:\s*0x([0-9a-fA-F]{{1,4}})', line)
        if m:
            vendor = m.group(1).lower().zfill(4)
            continue
        m = re.search(rf'{device_key}:\s*0x([0-9a-fA-F]{{1,4}})', line)
        if m and vendor:
            out.add(f'{vendor}:{m.group(1).lower().zfill(4)}')
            vendor = None
    return out


def split_graphics(entries):
    """(real graphics cards, virtual adapters) from "bus-or-id|name" strings.

    Reporting a virtual adapter as the graphics card is worse than reporting
    nothing: it is the kind of wrong answer that looks right, and someone would
    configure an EFI around it."""
    real, virtual = [], []
    for e in entries or []:
        ident, _, name = e.partition('|')
        name = (name or ident).strip()
        if not name:
            continue
        pci = _pairs(e, PCI_PATTERNS)   # the id may sit in either half
        if ident.upper().startswith('PCI') or pci:
            real.append({'name': name, 'id': next(iter(sorted(pci)), None)})
        else:
            virtual.append({'name': name, 'id': None})
    return real, virtual


def peripherals(text):
    """Cameras and card readers, with the bus each is on.

    The bus is the only part worth reporting: a USB camera is handled by the
    class driver macOS already has, while one that is not on USB is an IPU or
    MIPI sensor with no macOS driver at all. Which specific reader or sensor
    works is not something this repository has data for, so it is not claimed."""
    out = []
    for line in (text or '').splitlines():
        parts = line.split('|')
        if len(parts) < 2:
            continue
        kind, ident = parts[0].strip(), parts[1]
        name = parts[2].strip() if len(parts) > 2 else ident
        if not name:
            continue
        out.append({'kind': 'camera' if kind.lower() in ('camera', 'image') else 'card reader',
                    'name': name, 'usb': ident.upper().startswith('USB')})
    return out


def nvme_drives(text):
    """Model names of the NVMe drives, from "bustype|model" lines.

    Apple's own NVMe is named as such and is the one case NVMeFix is not for,
    so the name is kept rather than just a count."""
    out = []
    for line in (text or '').splitlines():
        bus, _, model = line.partition('|')
        if bus.strip() == '17' and model.strip():
            out.append(model.strip())
    return out


def probe():
    """Everything the machine will tell us, with the gaps left as None."""
    system = platform.system()
    raw = {'Windows': _windows, 'Linux': _linux, 'Darwin': _macos}.get(
        system, lambda: {})()
    laptop = raw.get('laptop')
    return {
        'system': system,
        'cpu': raw.get('cpu') or None,
        'cores': raw.get('cores'),
        'laptop': laptop,
        'oem': normalise_oem(raw.get('vendor')),
        'oem_raw': (raw.get('vendor') or '').strip() or None,
        'gpu': [g['name'] for g in split_graphics(raw.get('gpu'))[0]],
        'gpu_devices': split_graphics(raw.get('gpu'))[0],
        'gpu_virtual': [g['name'] for g in split_graphics(raw.get('gpu'))[1]],
        'pci': raw.get('pci') or '',
        'pci_ids': sorted(_pairs(raw.get('pci'), PCI_PATTERNS)
                          | (_apple_pairs(raw.get('pci'), 'Vendor ID', 'Device ID')
                             if system == 'Darwin' else set())),
        'usb_ids': sorted(_pairs(raw.get('usb'), USB_PATTERNS)
                          | (_apple_pairs(raw.get('usb'), 'Vendor ID', 'Product ID')
                             if system == 'Darwin' else set())),
        'hda_ids': sorted(_pairs(raw.get('hda'), HDA_PATTERNS)),
        'nvme': nvme_drives(raw.get('storage')),
        'peripherals': peripherals(raw.get('peripherals')),
        'ps2': 'PNP0F13' in (raw.get('peripherals') or '').upper()
               or 'PNP0303' in (raw.get('peripherals') or '').upper(),
        'generation': cpu_generation(raw.get('cpu'), bool(laptop)),
    }


# --------------------------------------------------------------------------
# A probe is a plain dictionary of strings, numbers and lists, so it survives a
# round trip through JSON unchanged. That is what makes building for another
# machine possible: run this there, carry the file, build here.

REPORT_VERSION = 1


def describe(hw):
    """One line naming the machine a probe came from, for confirming it."""
    parts = [hw.get('cpu') or 'unknown CPU']
    if hw.get('cores'):
        parts.append(f'{hw["cores"]} cores')
    if hw.get('oem_raw'):
        parts.append(hw['oem_raw'])
    if hw.get('laptop') is not None:
        parts.append('laptop' if hw['laptop'] else 'desktop')
    return ', '.join(parts)


def write_report(path):
    """Write this machine's probe to a file. Returns what was written."""
    data = probe()
    data['report_version'] = REPORT_VERSION
    data['written'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    # `pci` is the raw command output the ids were parsed out of. It is large,
    # it can name a serial number, and nothing downstream reads it, so a file
    # meant to be sent to someone else does not carry it.
    data.pop('pci', None)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    return data


def read_report(path):
    """(probe, complaint) from a file written by write_report.

    A complaint is returned rather than raised: a report that cannot be used is
    a reason to fall back to asking, not a reason to stop."""
    p = Path(path)
    if not p.exists():
        return None, f'{p} does not exist'
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return None, f'{p} could not be read: {exc}'
    if not isinstance(data, dict) or 'report_version' not in data:
        return None, (f'{p} is not a hardware report; make one with '
                      f'"detect.py --report {p.name}" on the machine you are building for')
    if data['report_version'] > REPORT_VERSION:
        return None, (f'{p} was written by a newer version of this tool '
                      f'(report {data["report_version"]}, this one reads {REPORT_VERSION})')
    data.setdefault('pci', '')
    return data, None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', metavar='FILE',
                    help='write what was found to a file, to build for this '
                         'machine from a different one')
    args = ap.parse_args()
    if args.report:
        written = write_report(args.report)
        print(f'  wrote {args.report}')
        print(f'  {describe(written)}')
        print(f'  {len(written["pci_ids"])} PCI, {len(written["usb_ids"])} USB, '
              f'{len(written["hda_ids"])} audio ids')
        print(f'\n  Copy it to the machine you build on and run:'
              f'\n      setup.py --machine {args.report}')
        raise SystemExit(0)
    for k, v in probe().items():
        if k == 'pci':
            print(f'  {k:10s} {len(v.splitlines())} lines')
        elif k in ('gpu_devices',):
            for g in v:
                print(f'  {k:10s} {g["name"]}' + (f'  [{g["id"]}]' if g['id'] else ''))
        elif k in ('pci_ids', 'usb_ids', 'hda_ids'):
            print(f'  {k:10s} {len(v)}: ' + ', '.join(v[:8]) + (' ...' if len(v) > 8 else ''))
        else:
            print(f'  {k:10s} {v}')
