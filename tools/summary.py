"""What a machine's hardware means for macOS, one line each, before anything else.

Every verdict here is composed from a table that already backs a decision
elsewhere in these tools - the AMD card list, AppleALC's layouts, the device ids
read out of the kexts - so this screen cannot say something the build would
then contradict. Where a table has nothing to say, the row says `unknown` and
names why. That is the whole point: a blank is a fact, and inventing a verdict
for a card reader nobody has data for would be worse than admitting to it.

Nothing here stops a build. It is a report, and the decision stays with whoever
is reading it.

    python3 tools/summary.py                       # this machine
    python3 tools/summary.py --machine report.json
"""
import argparse
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise
import audio
import detect
import gpu
import inputdev
import netkexts

PROFILES = Path('profiles')

SUPPORTED, UNSUPPORTED, UNKNOWN, ABSENT = 'supported', 'not supported', 'unknown', '-'

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[31m', '\033[0m')
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RED = RESET = ''

DETAIL = 52

COLOUR = {SUPPORTED: GREEN, UNSUPPORTED: RED, UNKNOWN: YELLOW, ABSENT: DIM}

AMD_GENERATIONS = ('ryzen-threadripper', 'bulldozer-jaguar')


def row(part, what, verdict, detail=''):
    return {'part': part, 'what': what, 'verdict': verdict, 'detail': detail}


def platform_name(hw):
    gen = hw.get('generation')
    if hw.get('laptop'):
        return 'laptop'
    return 'desktop-amd' if gen in AMD_GENERATIONS else 'desktop-intel'


def cpu_row(hw):
    gen, name = hw.get('generation'), hw.get('cpu')
    if not name:
        return row('CPU', 'not readable', UNKNOWN, 'answer the question by hand')
    if not gen:
        # the decoder returns nothing rather than a guess for Xeon, Pentium,
        # first generation Core and anything newer than it knows
        return row('CPU', name, UNKNOWN,
                   'this generation is not one the decoder recognises')
    pname = platform_name(hw)
    profile = PROFILES / 'cpu' / pname / f'{gen}.toml'
    if profile.exists():
        return row('CPU', name, SUPPORTED, f'{gen}, {pname} profile')
    return row('CPU', name, UNSUPPORTED, f'no {pname} profile for {gen}')


def graphics_rows(hw):
    out = []
    field = gpu.field_igpu(hw.get('cpu'))
    for device in hw.get('gpu_devices', []):
        verdict, entry = gpu.classify(device, hw.get('generation'))
        if field and gpu.looks_integrated(device.get('name')):
            # somebody ran this exact processor. That outranks a rule written
            # for its generation, and says so rather than quietly disagreeing.
            verdict = field['status']
            entry = {'family': f'{field["observed"]}, reported by '
                               f'{field["observed_by"]}'}
        detail = ''
        if entry:
            detail = entry.get('family') or entry.get('name') or ''
            if entry.get('note'):
                detail = f'{detail}, {entry["note"]}' if detail else entry['note']
        state = {'works': SUPPORTED, 'works-spoofed': SUPPORTED,
                 'unsupported': UNSUPPORTED}.get(verdict, UNKNOWN)
        if verdict == 'works-spoofed':
            detail = (detail + ', with a spoof') if detail else 'with a spoof'
        if state is UNKNOWN and not detail:
            detail = 'not in the card table or the iGPU list'
        name = device.get('name') or 'graphics'
        if device.get('id'):
            name = f'{name}  [{device["id"]}]'
        out.append(row('Graphics', name, state, detail))
    if not out:
        out.append(row('Graphics', 'none readable', UNKNOWN,
                       'nothing was reported on the graphics bus'))
    return out


def audio_row(hw):
    ids = hw.get('hda_ids') or []
    if not ids:
        return row('Audio', 'no codec readable', UNKNOWN, '')
    found = audio.find(ids)
    if not found:
        return row('Audio', ', '.join(ids), UNSUPPORTED,
                   'no AppleALC layout names this codec')
    codec = found[0]
    layouts = len(codec['layout'])
    return row('Audio', f"{codec['vendor']} {codec['codec']}", SUPPORTED,
               f'AppleALC, {layouts} layout' + ('s to try' if layouts != 1 else ''))


def _kext_note(match):
    """What else the driver set for a kext brings, from data/network.toml."""
    for s in netkexts.sets():
        if s['match'] == match:
            extra = len(s['kext']) - 1
            return f'+{extra} by macOS version' if extra else ''
    for s in netkexts.variant_sets():
        if s['match'] == match:
            # one build per release, which is why setup.py asks which macOS
            return 'one build per macOS'
    return ''


def _driver_sets():
    """The kexts data/network.toml keys a set on.

    Several kexts can claim one device - a Broadcom Bluetooth adapter matches
    BrcmPatchRAM3, BrcmPatchRAM2 and BrcmBluetoothInjector - and only one of
    them is what the build will key on. Naming any other one here would show a
    kext that is not the one being added."""
    return {s['match'] for s in netkexts.sets() + netkexts.variant_sets()}


def network_rows(hw):
    index = advise.load_table()
    names = hw.get('device_names') or {}
    keyed = _driver_sets()
    seen, order = {}, []
    for bus, ids in (('pci', hw.get('pci_ids') or []), ('usb', hw.get('usb_ids') or [])):
        for i in ids:
            for d in sorted(index.get((bus, i), []),
                            key=lambda x: x['kext'] not in keyed):
                # keyed on the device, not the role: a machine with both an Intel
                # and a Realtek NIC has two of them, and hiding one is a lie by
                # omission about the card the person is looking for
                key = (d['role'], i)
                if key in seen:
                    continue
                seen[key] = d
                order.append(key)
    out = []
    for role, label in (('ethernet', 'Ethernet'), ('wifi', 'Wi-Fi'),
                        ('bluetooth', 'Bluetooth')):
        hits = [(i, seen[(r, i)]) for r, i in order if r == role]
        if hits:
            for device_id, d in hits:
                # the id goes right after the kext so a long note cannot push
                # the most useful part of the line off the end
                note = _kext_note(d['kext'])
                out.append(row(label, names.get(device_id) or d['label'], SUPPORTED,
                               f'{d["kext"]}  [{device_id}]'
                               + (f'  {note}' if note else '')))
        elif hw.get('pci_ids') or hw.get('usb_ids'):
            # the devices were read and none of them matched, which is a fact
            # worth stating: either macOS needs no kext, or the card has to go
            out.append(row(label, 'nothing recognised', UNKNOWN,
                           'no kext here claims a device on this machine'))
        else:
            out.append(row(label, 'no devices readable', UNKNOWN, ''))
    return out


def storage_row(hw):
    drives = hw.get('nvme') or []
    if not drives:
        return row('Storage', 'no NVMe', ABSENT, 'nothing to add')
    third = [d for d in drives if 'apple' not in d.lower()]
    if third:
        return row('Storage', ', '.join(third), SUPPORTED, 'NVMeFix')
    return row('Storage', ', '.join(drives), SUPPORTED,
               'Apple NVMe, which is the case NVMeFix is not for')


def input_row(hw):
    """The trackpad row, or nothing on a machine that has no trackpad to speak of."""
    i2c = inputdev.controllers(hw.get('pci_ids') or [])
    pointing = [d for d in hw.get('peripherals', [])
                if d.get('kind') == 'pointing device' and not d.get('virtual')]
    if not (hw.get('laptop') or i2c or pointing):
        return None
    name = pointing[0]['name'] if pointing else ('I2C trackpad' if i2c else 'not readable')
    if i2c:
        return row('Trackpad', name, SUPPORTED, f'VoodooI2C  [{", ".join(i2c)}]')
    if hw.get('ps2'):
        return row('Trackpad', name, SUPPORTED,
                   'on PS/2; VoodooPS2 is in the laptop profile')
    return row('Trackpad', name, UNKNOWN, 'no I2C controller and nothing on PS/2')


def peripheral_rows(hw):
    out = []
    real = [d for d in hw.get('peripherals', []) if not d.get('virtual')]
    for dev in [d for d in real if d['kind'] == 'camera']:
        if dev['usb']:
            out.append(row('Camera', dev['name'], SUPPORTED,
                           'USB, so the class driver macOS has handles it'))
        else:
            out.append(row('Camera', dev['name'], UNSUPPORTED,
                           'not on USB, so an IPU or MIPI sensor'))
    for dev in [d for d in real if d['kind'] == 'card reader']:
        out.append(row('Card reader', dev['name'], UNKNOWN,
                       'no support data for card readers here'))
    return out


def rows(hw):
    """Every row, in the order they are worth reading."""
    out = [cpu_row(hw)] + graphics_rows(hw) + [audio_row(hw)]
    out += network_rows(hw) + [storage_row(hw), input_row(hw)]
    return [r for r in out + peripheral_rows(hw) if r]


def worth_showing(hw):
    """Whether a summary of this machine would say anything.

    A table of nothing but `unknown` is not a report, it is noise - and it is
    what a Mac produces, since it reports its own hardware and this reads none
    of it. One line saying so beats ten saying nothing."""
    return any(r['verdict'] in (SUPPORTED, UNSUPPORTED) for r in rows(hw))


def _fit(text, width):
    return text if len(text) <= width else text[:width - 1] + '\u2026'


def render(hw, source='this machine'):
    """The whole screen as lines."""
    table = rows(hw)
    width = max(len(r['what']) for r in table)
    width = min(max(width, 24), 44)
    lines = [f'{BOLD}Hardware for macOS{RESET}  {DIM}from {source}{RESET}', '']
    for r in table:
        what = _fit(r['what'], width)
        colour = COLOUR[r['verdict']]
        # a detail that does not fit wraps rather than being cut. The part that
        # would be lost is where the caveats live - "Kepler was the last
        # supported family" - and half a sentence is worse than two lines.
        body = textwrap.wrap(r['detail'], DETAIL) or ['']
        lines.append(f'  {r["part"]:<12s} {what:<{width}s}  '
                     f'{colour}{r["verdict"]:<14s}{RESET}{DIM}{body[0]}{RESET}'.rstrip())
        pad = ' ' * (2 + 12 + 1 + width + 2 + 14)
        for extra in body[1:]:
            lines.append(f'{pad}{DIM}{extra}{RESET}')
    bad = [r for r in table if r['verdict'] == UNSUPPORTED]
    unknown = [r for r in table if r['verdict'] == UNKNOWN]
    lines.append('')
    if bad:
        parts = list(dict.fromkeys(r['part'] for r in bad))   # Graphics once, not twice
        lines.append(f'  {RED}macOS does not support {len(bad)} of these: '
                     f'{", ".join(parts)}.{RESET}')
        lines.append(f'  {DIM}Replacing the part is usually the answer. This does not '
                     f'stop the build, and the sections below say more.{RESET}')
    else:
        lines.append(f'  {GREEN}Nothing here is known to be unsupported.{RESET}')
    if unknown:
        lines.append(f'  {DIM}{len(unknown)} left as unknown, where no table here has '
                     f'anything to say.{RESET}')
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', metavar='FILE', help='read a hardware report instead')
    a = ap.parse_args(argv)
    if a.machine:
        hw, complaint = detect.read_report(a.machine)
        if complaint:
            sys.exit(complaint)
        source = f'report {Path(a.machine).name}'
    else:
        hw, source = detect.probe(), 'this machine'
    print('\n'.join(render(hw, source)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
