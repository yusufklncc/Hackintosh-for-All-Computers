"""Build data/input.toml from VoodooI2C's own list of supported controllers.

Whether a trackpad is I2C is not something a name reveals, but the I2C
controller it hangs off is a PCI device, and VoodooI2C's README names every
controller it drives. So the presence of one of those is the signal, and the
ids come from the project rather than from anywhere else.

    python3 tools/inputtable.py --out data/input.toml
"""
import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

README = 'https://raw.githubusercontent.com/VoodooI2C/VoodooI2C/master/README.md'

# Dortania's kext list, quoted, because which kext suits which trackpad is
# stated there in prose and nowhere machine-readable.
GUIDE = 'https://dortania.github.io/OpenCore-Install-Guide/ktext.html'
RULES = [
    {'bus': 'i2c', 'label': 'I2C trackpad',
     'kexts': ['VoodooI2C.kext', 'VoodooI2CHID.kext'],
     'quote': 'Attaches to I2C controllers to allow plugins to talk to I2C trackpads. '
              'Must be paired with one or more plugins',
     'note': 'VoodooI2CHID covers I2C-HID devices, which is most of them. ELAN, '
             'Synaptics and FTE trackpads have their own plugin in the same release.'},
    {'bus': 'smbus-synaptics', 'label': 'Synaptics SMBus trackpad',
     'kexts': ['VoodooRMI.kext'],
     'quote': 'For systems with Synaptics SMBus trackpads. Requires macOS 10.11 or '
              'newer for MT2 functions. Depends on Acidanthera\'s VoodooPS2'},
    {'bus': 'smbus-elan', 'label': 'ELAN SMBus trackpad',
     'kexts': ['VoodooSMBus.kext'], 'min_kernel': '18.0.0',
     'quote': 'For systems with ELAN SMBus Trackpads. Supports macOS 10.14 or newer'},
]

KEYBOARD_NOTE = ('Most laptop keyboards are PS2! You will want to grab VoodooPS2 '
                 'even if you have an I2C, USB, or SMBus trackpad.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='data/input.toml')
    a = ap.parse_args()

    with urllib.request.urlopen(README) as r:
        text = r.read().decode('utf-8', 'replace')
    pci = sorted({f'8086:{i.zfill(4)}' for i in re.findall(r'pci8086,([0-9a-f]{2,4})', text)})
    acpi = sorted(set(re.findall(r'`(INT[0-9A-F]{4})`', text)))
    if len(pci) < 20:
        sys.exit(f'only found {len(pci)} controller ids; the README probably changed')

    ocgen.write_toml(Path(a.out),
                     {'controller': {'source': README, 'pci': pci, 'acpi': acpi},
                      'rule': RULES,
                      'keyboard': {'source': GUIDE, 'quote': KEYBOARD_NOTE}},
                     '# Laptop input: which kext a trackpad needs.\n'
                     '#\n'
                     '# The controller ids are read from VoodooI2C\'s README, which names\n'
                     '# every I2C controller it drives - the presence of one is what says a\n'
                     '# trackpad may be I2C, since the trackpad itself does not announce it.\n'
                     '# The kext rules are quoted from Dortania, where they are stated in\n'
                     '# prose and nowhere machine-readable.')
    print(f'  {len(pci)} I2C controllers, {len(acpi)} ACPI ids, {len(RULES)} rules')
    print(f'      {", ".join(pci[:6])} ...')


if __name__ == '__main__':
    main()
