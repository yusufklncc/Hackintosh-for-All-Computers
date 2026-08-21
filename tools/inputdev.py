"""What the trackpad needs, if an I2C controller says it might be one.

A trackpad does not announce how it is wired, but the controller it hangs off
does: VoodooI2C names every I2C controller it drives, so finding one on the PCI
bus is the signal. Nothing here decides the trackpad *is* I2C - plenty of
machines have an I2C controller and a PS/2 trackpad - so the kexts are offered,
with what to check, rather than assumed.

The keyboard is left alone. Dortania is blunt that most laptop keyboards are PS2
regardless of the trackpad, and the profiles in this repository already decide
that per machine.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

TABLE = Path('data/input.toml')
HARDWARE = Path('data/hardware.toml')


def load():
    if not TABLE.exists():
        sys.exit(f'{TABLE} missing')
    return ocgen.read_toml(TABLE)


def known_controllers():
    """(pci ids, acpi names) VoodooI2C declares, from the generated table."""
    pci, acpi = set(), set()
    for d in ocgen.read_toml(HARDWARE)['driver']:
        if d['role'] != 'trackpad':
            continue
        (pci if d['bus'] == 'pci' else acpi if d['bus'] == 'acpi' else set()).update(d['ids'])
    return pci, acpi


def controllers(pci_ids, acpi_ids=None):
    """The I2C controllers present, named as the machine reported them.

    An I2C controller on Haswell or Broadwell is enumerated by ACPI and has no
    PCI id at all, and AMD's are only ever named that way, so a machine with one
    of those used to look as though it had no I2C at all."""
    pci, acpi = known_controllers()
    found = [i for i in pci_ids or [] if i in pci]
    found += [a for a in acpi_ids or [] if a.upper() in acpi]
    return found


def entries(pci_ids, ps2_present, acpi_ids=None):
    """(lines, kext entries) - kexts only for what was actually found."""
    d = load()
    found = controllers(pci_ids, acpi_ids)
    lines, kexts = [], []
    if not found:
        return lines, kexts

    rule = next(r for r in d['rule'] if r['bus'] == 'i2c')
    lines.append(f'  an I2C controller is present  [{", ".join(found)}]')
    lines.append(f'      "{rule["quote"]}"')
    lines.append(f'      {rule["note"]}')
    for bundle in rule['kexts']:
        kexts.append({'Arch': 'x86_64', 'BundlePath': bundle, 'Comment': rule['label'],
                      'Enabled': True, 'ExecutablePath': '', 'MaxKernel': '',
                      'MinKernel': '', 'PlistPath': 'Contents/Info.plist'})
    if ps2_present:
        lines.append('      a PS/2 device is present too, so the trackpad may well be '
                     'PS/2 and this unnecessary')
    lines.append(f'      {d["keyboard"]["quote"]}')
    return lines, kexts


def smbus_notes():
    """The other two paths, for a machine with no I2C controller.

    Reached on a PS/2 laptop, which used to be told nothing at all: the notes
    only ran when an I2C controller was found, so the machines most likely to
    have an SMBus trackpad were the ones that never heard of one."""
    d = load()
    out = ['Trackpad', '',
           '  No I2C controller was found, so nothing was added for the trackpad.',
           '  A laptop keyboard is almost always PS/2 and VoodooPS2 is already in',
           '  the profile, which usually brings the trackpad with it.', '',
           '  If the trackpad still does nothing, it may be on SMBus instead:', '']
    for rule in d['rule']:
        if rule['bus'].startswith('smbus'):
            out.append(f'    {rule["label"]}: ' + ', '.join(rule['kexts']))
            out.append(f'      {rule["quote"]}')
    out += ['',
            '  Neither kext is added automatically: nothing this reads says which',
            '  bus a trackpad is on, and adding the wrong one is not harmless.', '']
    return '\n'.join(out)


def notes(pci_ids, acpi_ids=None):
    d = load()
    if not controllers(pci_ids, acpi_ids):
        return smbus_notes()
    out = ['Trackpad', '',
           '  An I2C controller was found, so VoodooI2C and VoodooI2CHID went in.',
           '  VoodooI2CHID covers I2C-HID trackpads, which is most of them. If the',
           '  trackpad still does nothing, the release carries a plugin per family:', '']
    for k in ('VoodooI2CELAN', 'VoodooI2CSynaptics', 'VoodooI2CFTE'):
        out.append(f'    {k}.kext')
    out += ['',
            '  If it is not I2C at all, these are the other two paths:', '']
    for rule in d['rule']:
        if rule['bus'].startswith('smbus'):
            out.append(f'    {rule["label"]}: ' + ', '.join(rule['kexts']))
            out.append(f'      {rule["quote"]}')
    out += ['',
            '  Some trackpads also need an SSDT before macOS will see them at all.',
            '  That is machine-specific and not something this builder can write:',
            '  https://voodooi2c.github.io/ has the procedure.', '']
    return '\n'.join(out)


if __name__ == '__main__':
    for ids, ps2 in ((['8086:9d60'], False), (['8086:a368'], True), (['8086:15b8'], False)):
        lines, kexts = entries(ids, ps2)
        print(f'\n=== {ids} ps2={ps2} ===')
        print('\n'.join(lines) if lines else '  no I2C controller here')
        if kexts:
            print(f'  -> {[k["BundlePath"] for k in kexts]}')
