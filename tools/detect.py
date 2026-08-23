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
import os
import json
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path


def _run(cmd, shell=False):
    """Output of a command, or an empty string. Never raises, never returns None.

    text=True alone decodes with the locale encoding and no error handling, so on
    a Turkish Windows a device name carrying a byte cp1254 has no character for
    killed the reader thread inside subprocess. The traceback printed, stdout
    came back as None, and the whole listing was lost - not just that one name.
    That is how a laptop with a full complement of PCI devices reported none."""
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, timeout=25,
                           text=True, encoding='utf-8', errors='replace')
        return (r.stdout or '') if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError, ValueError):
        return ''


# PowerShell writes in the console code page unless told otherwise, which is not
# UTF-8 on a non-English Windows. Setting it per call costs nothing and means the
# bytes match how they are decoded; errors='replace' above covers the rest.
PS_UTF8 = '[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; '


def _ps(script):
    return _run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                 PS_UTF8 + script])


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



# Names a machine reports of itself that name nothing. A field a vendor left at
# its default is worse than an empty one: it looks like an answer.
PLACEHOLDER_MODELS = {
    'system product name', 'to be filled by o.e.m.', 'default string',
    'not specified', 'not applicable', 'none', 'invalid', 'system name',
    'to be filled by oem', 'oem', 'product name', 'system version',
    'undefined', 'x.x', '123456789', 'na', 'n/a', '.',
}


def model_name(raw):
    """What this machine calls itself, or None.

    A laptop names itself in SMBIOS type 1 and that is the name people use for
    it. A desktop is whatever board went into it, so the board is the more
    useful of the two - and where the vendor never filled either in, this says
    nothing rather than repeating their placeholder back."""
    def usable(value):
        text = (value or '').strip()
        if not text or text.lower() in PLACEHOLDER_MODELS:
            return None
        # "1.0", "A1", "Rev 1.02" - a version, which is what most vendors put
        # in the field Lenovo uses for the name
        if re.fullmatch(r'(?i)(rev\.?\s*)?[vA-Z]?[\d.]+[a-z]?', text):
            return None
        return text

    model, board = usable(raw.get('model')), usable(raw.get('board'))
    version = usable(raw.get('version'))
    if raw.get('laptop'):
        return version or model or board
    # a desktop's type 1 is often the board's name with less of it
    return board or model


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
    # SMBIOS type 1 (the system) and type 2 (the board). A laptop puts its name
    # in the first - "ThinkPad E570" - and a desktop usually has nothing there
    # worth reading, because the machine is whatever board somebody chose.
    out['model'] = _ps('(Get-CimInstance Win32_ComputerSystem).Model').strip()
    # Lenovo puts the machine type in Model - "20H5006TTX" - and the name
    # people know it by in the type 1 Version field. Most other vendors leave
    # Version at something like "1.0", which is filtered out below rather than
    # special-cased per vendor.
    out['version'] = _ps('(Get-CimInstance Win32_ComputerSystemProduct).Version').strip()
    out['board'] = _ps('$b = Get-CimInstance Win32_BaseBoard; '
                       '"$($b.Manufacturer) $($b.Product)"').strip()
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
    # the driver Windows bound is carried along, because it is the only honest
    # answer to "is this on the PS/2 controller". The PnP id is not: this laptop
    # calls its PS/2 keyboard ACPI\\TOS7407 and its Alps trackpad ACPI\\TTP1000,
    # neither of which is the standard PNP0303 or PNP0F13.
    out['peripherals'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object '
        '{ $_.PNPClass -in @("Camera","Image","SDHost","MTD","Mouse","Keyboard") } '
        '| ForEach-Object '
        '{ "$($_.PNPClass)|$($_.PNPDeviceID)|$($_.Name)|$($_.Service)" }')
    # ACPI-enumerated devices, for the I2C controllers that have no PCI id at
    # all: on Haswell and Broadwell they are INT33C2 and friends, and AMD's are
    # only ever named this way.
    out['acpi'] = _ps(
        'Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like "ACPI*" } | '
        'ForEach-Object { $_.PNPDeviceID }')
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
    # the same two SMBIOS records, as the kernel exposes them
    out['model'] = _read('/sys/class/dmi/id/product_name')
    out['version'] = _read('/sys/class/dmi/id/product_version')
    out['board'] = ' '.join(x for x in (_read('/sys/class/dmi/id/board_vendor'),
                                        _read('/sys/class/dmi/id/board_name')) if x)
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
    # BUS_I8042 is 0x11 in the kernel's input.h, so a device on bus 0011 is on
    # the PS/2 controller by the kernel's own reckoning
    out['input'] = _read('/proc/bus/input/devices')
    # /sys/bus/acpi/devices holds one directory per device, named INT33C2:00
    out['acpi'] = '\n'.join(sorted(
        Path(d).name for d in __import__('glob').glob('/sys/bus/acpi/devices/*')))
    import glob as _glob
    out['storage'] = '\n'.join(
        f'17|{_read(p + "/model")}' for p in sorted(_glob.glob('/sys/class/nvme/nvme*')))
    return out



def _ioreg(cls):
    """Every node of one IOKit class, flattened, as plain dictionaries.

    -a asks for a plist, which is a tree of the same dictionaries ioreg would
    otherwise pretty-print. Parsing that beats parsing the drawing of it."""
    raw = _run(['ioreg', '-a', '-r', '-c', cls, '-l'])
    if not raw.strip():
        return []
    try:
        tree = plistlib.loads(raw.encode('utf-8', 'replace'))
    except Exception:
        return []
    out = []

    def walk(nodes):
        for node in nodes or []:
            if isinstance(node, dict):
                out.append(node)
                walk(node.get('IORegistryEntryChildren'))
    walk(tree if isinstance(tree, list) else [tree])
    return out


def _le(value):
    """A little-endian id as IOKit stores it: <e4140000> is 14e4."""
    if not isinstance(value, bytes) or len(value) < 2:
        return None
    return f'{value[1]:02x}{value[0]:02x}'


def _text(value):
    if isinstance(value, bytes):
        return value.split(b'\x00', 1)[0].decode('utf-8', 'replace').strip()
    return str(value).strip() if value else ''


def _pci_name(node):
    """What the registry calls a device, in the plainest form it offers.

    `model` where there is one. Otherwise the entry's own name - "wlan",
    "pcie-sdreader" - and the chip out of `compatible`, which is where the
    part number lives: "wlan-pcie,bcm4387".  Neither is a marketing name and
    neither is invented."""
    model = _text(node.get('model'))
    if model:
        return model
    name = _text(node.get('IORegistryEntryName') or node.get('name'))
    chip = _text(node.get('compatible')).split(',')[-1]
    # no brackets: the name reader strips those, because on an lspci line they
    # hold "(rev 04)" and nothing worth keeping
    worth_saying = (chip and chip.lower() not in name.lower()
                    # a part number has letters in it. "9755" is the device id
                    # again, and "pcie-bridge" is what the name already said
                    and any(c.isalpha() for c in chip)
                    and any(c.isdigit() for c in chip)
                    and 'bridge' not in chip.lower())
    return f'{name}, {chip}' if worth_saying else name


# What the IORegistry calls a device is the machine naming its own hardware,
# and on a Mac it is the only thing that does: no kext here claims an Apple
# chip, so nothing else can say which of them is the Wi-Fi. Only names that
# have actually been seen are listed; a name nobody has observed would be a
# guess with a table around it.
REGISTRY_ROLES = (
    ('wlan', 'wifi'), ('airport', 'wifi'),
    ('bluetooth', 'bluetooth'),
    ('ethernet', 'ethernet'),
    ('sdreader', 'card reader'), ('sdxc', 'card reader'),
)


def _pci_role(node):
    """What this device is, in the machine's own words, or None.

    Substrings rather than exact names: the same part is "wlan" on one Mac and
    "wlan-pcie" on another, and both are the machine saying Wi-Fi."""
    # The entry name first and on its own. A combo chip gives both of its
    # functions the same `compatible` - the Bluetooth half of a BCM4387 reads
    # "wlan-pcie,bcm4387" too - so matching that first calls the Bluetooth
    # Wi-Fi. The names are "wlan" and "bluetooth-pcie", and those are right.
    for text in (_text(node.get('IORegistryEntryName') or node.get('name')),
                 _text(node.get('compatible'))):
        for fragment, role in REGISTRY_ROLES:
            if fragment in text.lower():
                return role
    return None


def _pci_driver(node):
    """The macOS driver attached to this device, or None.

    A PCI node's first child is whatever claimed it. That is not a guess about
    whether the device works - it is the running system saying which driver it
    handed the device to, on a machine that is running macOS while being asked."""
    for child in node.get('IORegistryEntryChildren') or []:
        found = _text(child.get('IOClass') or child.get('IORegistryEntryName'))
        if found:
            # a DriverKit driver is a userspace one and the registry names the
            # wrapper rather than the driver; saying so beats saying IOUserService
            return 'a DriverKit driver' if found == 'IOUserService' else found
    return None


def macos_devices():
    """This Mac's PCI, USB and audio devices, in the shapes the parsers expect.

    system_profiler is the wrong place to ask. SPPCIDataType reports nothing at
    all on Apple silicon - measured on an M1 Pro, zero lines - while the same
    machine's IORegistry has the Wi-Fi, the Bluetooth and the card reader with
    their vendor and device ids. This matters most on a PC already running
    macOS, which is a machine somebody may well be rebuilding an EFI for.

    The lines come out looking like lspci and lsusb because those are already
    parsed here; a third format would be a third thing to keep working."""
    pci, roles, drivers = [], {}, {}
    for node in _ioreg('IOPCIDevice'):
        vendor, device = _le(node.get('vendor-id')), _le(node.get('device-id'))
        if not (vendor and device):
            continue
        pci.append(f'[{vendor}:{device}]' + (f'|{_pci_name(node)}'
                                             if _pci_name(node) else ''))
        role = _pci_role(node)
        if role:
            roles[f'{vendor}:{device}'] = role
        driver = _pci_driver(node)
        if driver:
            drivers[f'{vendor}:{device}'] = driver

    usb = []
    for node in _ioreg('IOUSBHostDevice'):
        vendor, product = node.get('idVendor'), node.get('idProduct')
        if not (isinstance(vendor, int) and isinstance(product, int)):
            continue
        name = _text(node.get('USB Product Name') or node.get('kUSBProductString'))
        usb.append(f'ID {vendor:04x}:{product:04x}' + (f'|{name}' if name else ''))

    hda = []
    for node in _ioreg('IOHDACodecDevice'):
        codec = node.get('IOHDACodecVendorID')
        if isinstance(codec, int):
            hda.append(f'Vendor Id: 0x{codec:08x}')

    return '\n'.join(pci), '\n'.join(usb), '\n'.join(hda), roles, drivers


CAMERA_DRIVER = re.compile(r'\+-o (\w*Cam\w*)\s+<class \1,[^>]*\bmatched\b')


def macos_camera_driver():
    """The class macOS matched to this Mac's camera, or None.

    Read from the tree drawing rather than a plist, because the class name is
    what has to be searched for and it changes with the chip - AppleH13CamIn
    here, AppleH10CamIn on an older one. "matched" in the same line is the
    registry saying a driver took the device, not merely that it exists."""
    found = CAMERA_DRIVER.search(_run(['ioreg', '-l']))
    return found.group(1) if found else None


def macos_board():
    """The name a Mac calls its own logic board.

    Apple silicon puts it first in the platform node's `compatible` - the whole
    property reads J314sAP, MacBookPro18,3, AppleARM - and Intel has a
    `board-id` of the Mac-XXXXXXXX form. Apple's own support metadata is keyed
    on exactly these, which is what makes it possible to say which macOS a
    given Mac still runs.

    The serial number is right beside both of these and is never read."""
    nodes = _ioreg('IOPlatformExpertDevice')
    if not nodes:
        return None
    node = nodes[0]
    board = _text(node.get('board-id'))
    if board:
        return board
    first = _text(node.get('compatible')).split(chr(0))[0].strip()
    return first or None


def _macos_peripherals():
    """The camera and the card reader, as their own sections report them.

    Written in the same "class|id|name" shape the Windows query produces, so
    the one parser reads both. PCI rather than USB on Apple silicon, which is
    the distinction the camera row turns on."""
    lines = []
    camera = _run(['system_profiler', 'SPCameraDataType'])
    for name in re.findall(r'^\s{4}(\S.*?):$', camera, re.M):
        # a built-in Mac camera is on neither bus this knows; PCI is the honest
        # half of the answer, since what matters downstream is "not USB"
        lines.append(f'Camera|PCI\\{name.strip()}|{name.strip()}')
    reader = _run(['system_profiler', 'SPCardReaderDataType'])
    names = re.findall(r'^\s{4}(\S.*?):$', reader, re.M)
    ids = re.findall(r'Vendor ID:\s*0x([0-9a-fA-F]{4}).*?Device ID:\s*0x([0-9a-fA-F]{4})',
                     reader, re.S)
    for i, name in enumerate(names):
        ident = (f'PCI\\VEN_{ids[i][0].upper()}&DEV_{ids[i][1].upper()}'
                 if i < len(ids) else f'PCI\\{name.strip()}')
        lines.append(f'SDHost|{ident}|{name.strip()}')
    return '\n'.join(lines)


def _macos():
    out = {}
    out['cpu'] = _run(['sysctl', '-n', 'machdep.cpu.brand_string']).strip()
    cores = _run(['sysctl', '-n', 'hw.physicalcpu']).strip()
    out['cores'] = int(cores) if cores.isdigit() else None
    model = _run(['sysctl', '-n', 'hw.model']).strip()
    out['model'] = model
    if model:
        out['laptop'] = model.startswith(('MacBook',))
    out['vendor'] = ''
    # both sources: the registry is the one that answers on Apple silicon, and
    # system_profiler is left in because an Intel Mac fills it in and no machine
    # here can prove what it looks like there
    pci, usb, hda, roles, drivers = macos_devices()
    out['pci'] = pci + '\n' + _run(['system_profiler', 'SPPCIDataType'])
    out['usb'] = usb + '\n' + _run(['system_profiler', 'SPUSBDataType'])
    out['hda'] = hda
    nvme = _run(['system_profiler', 'SPNVMeDataType'])
    out['storage'] = '\n'.join(
        f'17|{m.strip()}' for m in re.findall(r'^\s+Model:\s*(.+)$', nvme, re.M))
    out['peripherals'] = _macos_peripherals()
    out['board'] = macos_board()
    out['machine_roles'] = roles
    out['machine_drivers'] = drivers
    # a MacBook's trackpad is not on PS/2 or I2C; it is its own device class
    out['multitouch'] = bool(_ioreg('AppleMultitouchDevice'))
    out['camera_driver'] = macos_camera_driver()
    # the codec query finds nothing on Apple silicon, but the devices are named
    out['audio_devices'] = [m.strip() for m in re.findall(
        r'^\s{8}(\S.*?):$', _run(['system_profiler', 'SPAudioDataType']), re.M)]
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


def _names(text, patterns):
    r"""{id: name} for the lines an id was found on.

    The machine already prints the model beside the id and it was being thrown
    away, so a Wi-Fi card the tool had fully identified was reported as the name
    of the driver set it belongs to - "Intel Wi-Fi" rather than what it is.

    Each source puts the name somewhere different, and the id itself says which:

        Windows   PCI\VEN_8086&DEV_1559&...|Intel(R) Ethernet Connection I218-V
        lspci     00:19.0 Ethernet controller: Intel Corporation I218-V [8086:1559] (rev 04)
        lsusb     Bus 001 Device 004: ID 8087:07dc Intel Corp. Bluetooth
    """
    out = {}
    for line in (text or '').splitlines():
        for pat in patterns:
            m = pat.search(line)
            if not m:
                continue
            key = f'{m.group(1).lower()}:{m.group(2).lower()}'
            if '|' in line:
                name = line.rsplit('|', 1)[1]                # Windows
            elif line[m.start():m.start() + 1] == '[':
                # lspci, where the id is bracketed and the model comes before it,
                # after the device class. Anything after is "(rev 04)".
                name = line[:m.start()].split(': ', 1)[-1]
            else:
                name = line[m.end():]                        # lsusb
            name = name.strip().strip('()').strip()
            if name and key not in out:
                out[key] = name
            break
    return out


# Two shapes, and both are anchored: an instance path like 2&daba3ff&2 has a
# run of hex in it that a loose pattern happily reads as an ACPI id.
ACPI_PATTERNS = [
    re.compile(r'ACPI\\([A-Z]{3,4}[0-9A-F]{4})'),        # Windows PNPDeviceID
    re.compile(r'^([A-Z]{3,4}[0-9A-F]{4}):\d+$', re.M),   # Linux /sys/bus/acpi/devices
]


def acpi_names(text):
    """ACPI hardware ids in a device listing, without the instance that follows."""
    out = set()
    for pat in ACPI_PATTERNS:
        out |= set(pat.findall((text or '').upper()))
    return sorted(out)


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


# The classes the peripherals query asks for, and what each one is. Everything
# that was not a camera used to fall through to "card reader", so a PS/2
# keyboard, a remote desktop mouse and an Alps trackpad were all reported as
# card readers - on screen as well as in the report.
PNP_CLASS_KIND = {
    'camera': 'camera', 'image': 'camera',
    'sdhost': 'card reader', 'mtd': 'card reader',
    'mouse': 'pointing device', 'keyboard': 'keyboard',
}


def hardware_id(ident):
    """The enumerator and hardware id of a device path, without the instance.

    `ACPI\\PNP0303\\4&1e2f3a4b&0` becomes `ACPI\\PNP0303`. The tail is the
    instance path, which says nothing about what the device is and can carry a
    serial number, so it has no business in a file meant to be sent to someone."""
    parts = (ident or '').split('\\')
    return '\\'.join(parts[:2]) if len(parts) > 1 else (ident or '')


# Enumerators a device can appear under and still be a device. Remote desktop
# installs a keyboard and a mouse under TERMINPUT_BUS, the same way a dummy
# monitor tool installs a display adapter under ROOT: reporting those as the
# machine's hardware is the kind of wrong answer that looks right.
REAL_BUSES = ('ACPI', 'USB', 'HID', 'PCI', 'I2C', 'BTHENUM', 'BTHLE')

# Windows binds the 8042 port driver to whatever hangs off the PS/2 controller,
# whatever the vendor called the device. On Linux the same fact is BUS_I8042,
# 0x11 in the kernel's input.h, printed as the bus of each input device.
PS2_DRIVER = 'i8042prt'
PS2_LINUX_BUS = 'Bus=0011'


def ps2_present(raw):
    """Whether anything is on the PS/2 controller, by the driver actually bound.

    Matching PnP ids was wrong: a Toshiba calls its PS/2 keyboard ACPI\\TOS7407
    and its Alps trackpad ACPI\\TTP1000, so a machine with both reported neither
    and got no VoodooPS2 advice."""
    text = (raw.get('peripherals') or '')
    if PS2_DRIVER in text.lower():
        return True
    if PS2_LINUX_BUS in (raw.get('input') or ''):
        return True
    # the standard ids still count, for anything that does use them
    return 'PNP0F13' in text.upper() or 'PNP0303' in text.upper()


def peripherals(text):
    """Cameras, card readers and input devices, with the bus each is on.

    The bus matters for a camera: a USB one is handled by the class driver macOS
    already has, while one that is not on USB is an IPU or MIPI sensor with no
    macOS driver at all. Which specific reader or sensor works is not something
    this repository has data for, so it is not claimed."""
    out = []
    for line in (text or '').splitlines():
        parts = line.split('|')
        if len(parts) < 2:
            continue
        pnp_class, ident = parts[0].strip(), parts[1]
        name = parts[2].strip() if len(parts) > 2 else ident
        driver = parts[3].strip() if len(parts) > 3 else ''
        if not name:
            continue
        bus = ident.split('\\')[0].upper()
        out.append({'kind': PNP_CLASS_KIND.get(pnp_class.lower(), 'other'),
                    'name': name, 'id': hardware_id(ident), 'driver': driver,
                    'usb': bus == 'USB', 'virtual': bus not in REAL_BUSES})
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
        'model': model_name(raw),
        # only a Mac has one, and it is what Apple's support metadata is keyed on
        'board_id': raw.get('board'),
        # {id: role}, where the machine itself said what a device is. Only
        # macOS answers this; everywhere else the kext tables do.
        'machine_roles': raw.get('machine_roles') or {},
        # {id: driver}, from the system that is running while it is asked
        'machine_drivers': raw.get('machine_drivers') or {},
        'multitouch': raw.get('multitouch'),
        'camera_driver': raw.get('camera_driver'),
        'audio_devices': raw.get('audio_devices') or [],
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
        'acpi_ids': acpi_names(raw.get('acpi')),
        # the model beside each id, where the machine printed one. A model name
        # is not a serial number, so it travels in a report like the id does.
        'device_names': {**_names(raw.get('pci'), PCI_PATTERNS),
                         **_names(raw.get('usb'), USB_PATTERNS)},
        'nvme': nvme_drives(raw.get('storage')),
        'peripherals': peripherals(raw.get('peripherals')),
        'ps2': ps2_present(raw),
        'generation': cpu_generation(raw.get('cpu'), bool(laptop)),
    }


# --------------------------------------------------------------------------
# A probe is a plain dictionary of strings, numbers and lists, so it survives a
# round trip through JSON unchanged. That is what makes building for another
# machine possible: run this there, carry the file, build here.

REPORT_VERSION = 1


def describe(hw):
    """One line naming the machine a probe came from, for confirming it."""
    parts = [hw['model']] if hw.get('model') else []
    parts.append(hw.get('cpu') or 'unknown CPU')
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
    ap.add_argument('--acpi', metavar='DIR',
                    help='dump this machine\'s ACPI tables too, which is what '
                         'the SSDTs have to be written against')
    args = ap.parse_args()
    if args.report:
        written = write_report(args.report)
        print(f'  wrote {args.report}')
        print(f'  {describe(written)}')
        print(f'  {len(written["pci_ids"])} PCI, {len(written["usb_ids"])} USB, '
              f'{len(written["hda_ids"])} audio ids')
        tables = None
        if args.acpi:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import acpi
            tables, complaint = acpi.dump('build/acpi-dump', args.acpi)
            print(f'  {"dumped ACPI tables to " + str(tables) if tables else complaint}')
        print(f'\n  Copy it to the machine you build on and run:'
              f'\n      setup.py --machine {args.report}'
              + (f' --acpi-tables {args.acpi}' if tables else ''))
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
