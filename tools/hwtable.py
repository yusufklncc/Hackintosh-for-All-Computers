"""Build data/hardware.toml from the kexts themselves.

The mapping from a PCI or USB id to the kext that drives it is not written by
hand and not copied out of a guide. Every kext already declares exactly which
devices it binds to, in IOPCIPrimaryMatch, IOPCIMatch, IONameMatch or
idVendor/idProduct, so
the table is read straight out of those and carries the kext version it came
from. When a kext is updated the table is regenerated and the diff shows which
devices it gained or lost.

    python3 tools/hwtable.py <directory-of-kexts> [--out data/hardware.toml]
"""
import argparse
import collections
import glob
import os
import plistlib
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

# What each kext is for, in the words a person choosing hardware would use.
ROLES = {
    'IntelMausi': ('ethernet', 'Intel Ethernet'),
    'IntelSnowMausi': ('ethernet', 'Intel Ethernet, Snow Leopard'),
    'RealtekRTL8111': ('ethernet', 'Realtek Gigabit Ethernet'),
    'LucyRTL8125Ethernet': ('ethernet', 'Realtek 2.5G Ethernet'),
    'AtherosE2200Ethernet': ('ethernet', 'Atheros/Killer Ethernet'),
    'AirportItlwm': ('wifi', 'Intel Wi-Fi'),
    'AirportBrcmFixup': ('wifi', 'Broadcom Wi-Fi'),
    'VoodooI2C': ('trackpad', 'I2C controller'),
    'IntelBluetoothFirmware': ('bluetooth', 'Intel Bluetooth'),
    'IntelBluetoothInjector': ('bluetooth', 'Intel Bluetooth, Monterey and older'),
    'BrcmPatchRAM3': ('bluetooth', 'Broadcom Bluetooth, Big Sur and newer'),
    'BrcmPatchRAM2': ('bluetooth', 'Broadcom Bluetooth, Catalina and older'),
    'BrcmBluetoothInjector': ('bluetooth', 'Broadcom Bluetooth injector'),
}


def pci_ids(value):
    """IOPCIPrimaryMatch packs device and vendor into one 0xDDDDVVVV word.

    A term may carry a mask - 0x9d608086&0xFFFCFFFF - which makes the low bits
    of the device id wildcards, so that one term covers 9d60 through 9d63.
    Reading the mask as a second id was the trap here: it would have put
    fffc:ffff in the table the moment a kext that uses one was added."""
    out = set()
    for term in (value or '').split():
        parts = term.split('&')
        m = re.fullmatch(r'0x([0-9a-fA-F]{8})', parts[0].strip())
        if not m:
            continue
        n = int(m.group(1), 16)
        vendor, device = n & 0xffff, n >> 16
        mask = 0xffff
        if len(parts) > 1:
            mm = re.fullmatch(r'0x([0-9a-fA-F]{1,8})', parts[1].strip())
            if mm:
                mask = int(mm.group(1), 16) >> 16
        wildcards = (~mask) & 0xffff
        if bin(wildcards).count('1') > 8:
            # a term that loose is matching a whole class, not a device list,
            # and expanding it would bury the real ids under 256 invented ones
            continue
        span = [0]
        for bit in range(16):
            if wildcards >> bit & 1:
                span = [s | (b << bit) for s in span for b in (0, 1)]
        for extra in span:
            out.add(f'{vendor:04x}:{(device & mask) | extra:04x}')
    return out


def acpi_ids(value):
    """ACPI names in IONameMatch: INT33C2, AMDI0010, PNP0303.

    An I2C controller on a Haswell or Broadwell laptop is enumerated by ACPI and
    has no PCI id at all, so a table of PCI ids alone cannot see it - and AMD's
    controllers are only ever named this way."""
    out = set()
    for name in ([value] if isinstance(value, str) else (value or [])):
        s = str(name).strip()
        if re.fullmatch(r'[A-Za-z]{3,4}[0-9A-Fa-f]{4}', s):
            out.add(s.upper())
    return out


def name_ids(value):
    """IONameMatch names a device the way IOKit does: pci14e4,43a3.

    A Lilu plugin has no IOPCIPrimaryMatch to read, because it does not bind to
    the device itself - it patches the driver that does. Its device list lives
    here instead, and skipping the field meant AirportBrcmFixup contributed
    nothing and every Broadcom Wi-Fi card came out unrecognised."""
    out = set()
    for name in ([value] if isinstance(value, str) else (value or [])):
        m = re.fullmatch(r'pci([0-9a-fA-F]{4}),([0-9a-fA-F]{4})', str(name).strip())
        if m:
            out.add(f'{m.group(1).lower()}:{m.group(2).lower()}')
    return out


def scan(root):
    found = collections.defaultdict(lambda: {'pci': set(), 'usb': set(), 'acpi': set()})
    versions = {}
    for path in sorted(glob.glob(f'{root}/**/*.kext', recursive=True)):
        if '__MACOSX' in path or path.count('.kext') > 1:
            continue
        name = Path(path).stem
        if name not in ROLES:
            continue
        try:
            with open(f'{path}/Contents/Info.plist', 'rb') as fh:
                info = plistlib.load(fh)
        except (OSError, plistlib.InvalidFileException):
            continue
        versions[name] = info.get('CFBundleShortVersionString', '')
        for p in info.get('IOKitPersonalities', {}).values():
            found[name]['pci'] |= pci_ids(p.get('IOPCIPrimaryMatch', ''))
            found[name]['pci'] |= pci_ids(p.get('IOPCIMatch', ''))
            found[name]['pci'] |= name_ids(p.get('IONameMatch'))
            found[name]['acpi'] |= acpi_ids(p.get('IONameMatch'))
            v, d = p.get('idVendor'), p.get('idProduct')
            if isinstance(v, int) and isinstance(d, int):
                found[name]['usb'].add(f'{v:04x}:{d:04x}')
    return found, versions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kexts', help='directory holding the unpacked kexts')
    ap.add_argument('--out', default='data/hardware.toml')
    a = ap.parse_args()

    found, versions = scan(a.kexts)
    if not found:
        sys.exit(f'no known kexts under {a.kexts}')

    entries = []
    for name in sorted(found):
        role, label = ROLES[name]
        for bus in ('pci', 'usb', 'acpi'):
            ids = sorted(found[name][bus])
            if ids:
                entries.append({'kext': f'{name}.kext', 'role': role, 'label': label,
                                'version': versions.get(name, ''), 'bus': bus, 'ids': ids})
    ocgen.write_toml(Path(a.out), {'driver': entries},
                     '# Which kext drives which device.\n'
                     '#\n'
                     '# Generated by tools/hwtable.py from the kexts themselves: every id\n'
                     '# here comes out of that kext\'s own IOPCIPrimaryMatch, IOPCIMatch,\n'
                     '# IONameMatch or idVendor/idProduct, so it says what the driver\n'
                     '# actually binds to rather than what a guide remembers. An ACPI\n'
                     '# row is a device with no PCI id at all, which is how Haswell and\n'
                     '# AMD name their I2C controllers. Regenerate after updating a\n'
                     '# kext; the diff is the list of devices it gained or lost.')
    total = sum(len(e['ids']) for e in entries)
    print(f'  {len(entries)} driver entries, {total} device ids')
    for e in entries:
        print(f'      {e["kext"]:30s} {e["role"]:9s} {e["bus"]} {len(e["ids"]):4d}  v{e["version"]}')


if __name__ == '__main__':
    main()
