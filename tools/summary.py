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
import functools
import os
import re
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
import ocgen
import ui

PROFILES = Path('profiles')

SUPPORTED, UNSUPPORTED, UNKNOWN, ABSENT = 'supported', 'not supported', 'unknown', '-'

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'red', 'reset')

DETAIL = 52

COLOUR = {SUPPORTED: GREEN, UNSUPPORTED: RED, UNKNOWN: YELLOW, ABSENT: DIM}

AMD_GENERATIONS = ('ryzen-threadripper', 'bulldozer-jaguar')


def row(part, what, verdict, detail='', kexts=(), ids=(), note=None):
    """One line of the summary.

    `detail` is the sentence a person reads on a console that has one column.
    `kexts` and `ids` are the same facts as values, for a front end that draws
    a link rather than printing a name mid-sentence - pulling the kext back out
    of the prose worked, right up until a sentence mentioned two.

    `note` is what is left when the columns have taken their share: a screen
    that shows the kext in its own column and then repeats it in the sentence
    underneath has said the same thing twice. Where nothing is left it is the
    empty string, and where the sentence is all note it defaults to the
    sentence."""
    return {'part': part, 'what': what, 'verdict': verdict, 'detail': detail,
            'note': detail if note is None else note,
            'kexts': list(kexts), 'ids': list(ids)}


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
            # a note is the substance of a family rule - "Kepler was the last
            # supported family" - and must survive. Where it is only the long
            # form of what the family string already says, it is marked as such
            # and the section below prints it instead.
            if entry.get('note') and not entry.get('long_note'):
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
        out.append(row('Graphics', name, state, detail,
                       ids=[device['id']] if device.get('id') else ()))
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
               f'AppleALC, {layouts} layout' + ('s to try' if layouts != 1 else ''),
               kexts=['AppleALC.kext'], ids=ids,
               note=f'{layouts} layout' + ('s to try' if layouts != 1 else ''))


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
                               + (f'  {note}' if note else ''),
                               kexts=[d['kext']], ids=[device_id], note=note))
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
        return row('Storage', ', '.join(third), SUPPORTED, 'NVMeFix',
                   kexts=['NVMeFix.kext'], note='')
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
        return row('Trackpad', name, SUPPORTED, f'VoodooI2C  [{", ".join(i2c)}]',
                   kexts=['VoodooI2C.kext'], ids=i2c, note='')
    # the machine names its own SMBus controller after whatever drives the
    # trackpad, which outranks the PS/2 controller also being there: on these
    # laptops both are, and only one of them is carrying the trackpad
    bus, smbus_id, _ = inputdev.smbus_trackpad(hw.get('device_names'))
    if bus:
        rule = inputdev.smbus_rule(bus)
        return row('Trackpad', name, SUPPORTED,
                   f'{", ".join(rule["kexts"])} for {rule["label"]}  [{smbus_id}]',
                   kexts=rule['kexts'], ids=[smbus_id], note=rule['label'])
    if hw.get('ps2'):
        return row('Trackpad', name, SUPPORTED,
                   'on PS/2; VoodooPS2Controller is in the laptop profile',
                   kexts=['VoodooPS2Controller.kext'], note='on PS/2')
    return row('Trackpad', name, UNKNOWN, 'no I2C controller and nothing on PS/2')


CARDREADER = Path('data/cardreader.toml')


def card_reader(device_id):
    """(entry, driver) for a card reader this repository has data for."""
    if not device_id or not CARDREADER.exists():
        return None, None
    d = ocgen.read_toml(CARDREADER)
    for e in d.get('device', []):
        if e['id'] == device_id.lower():
            return e, d['driver']
    return None, d.get('driver')


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
    ids = {i.lower() for i in (hw.get('pci_ids') or []) + (hw.get('usb_ids') or [])}
    for dev in [d for d in real if d['kind'] == 'card reader']:
        # the peripheral entry carries the reader's own hardware id, which is
        # the right one to look up; the device listing is only the fallback for
        # a report that predates that field
        found = driver = None
        own = re.search(r'VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})', dev.get('id') or '')
        for i in ([f'{own.group(1)}:{own.group(2)}'] if own else []) + sorted(ids):
            found, driver = card_reader(i)
            if found:
                break
        if found and found['supported']:
            # saying "supported" about a kext this repository does not ship would
            # promise something the build cannot deliver
            here = Path('EFI/OC/Kexts') / driver['kext']
            tail = '' if here.exists() else ', not shipped here'
            out.append(row('Card reader', dev['name'], SUPPORTED,
                           f'{driver["kext"]} since {found["since"]}'
                           f'  [{found["id"]}]{tail}',
                           kexts=[driver['kext']] if not tail else (),
                           ids=[found['id']],
                           note=f'since {found["since"]}'
                                + (', not shipped here' if tail else '')))
        elif found:
            out.append(row('Card reader', dev['name'], UNSUPPORTED,
                           f'{driver["kext"]} lists it and does not drive it yet',
                           ids=[found['id']],
                           note=f'{driver["kext"]} lists it and does not drive it yet'))
        else:
            out.append(row('Card reader', dev['name'], UNKNOWN,
                           'not in the one driver this repository has data for'))
    return out


def rows(hw):
    """Every row, in the order they are worth reading."""
    out = [cpu_row(hw)] + graphics_rows(hw) + [audio_row(hw)]
    out += network_rows(hw) + [storage_row(hw), input_row(hw)]
    return [r for r in out + peripheral_rows(hw) if r]


FRAMEBUFFERS = Path('data/framebuffer.toml')


def _window(lo, hi):
    return (lo or 0, hi if hi else None)


def macos_windows(hw):
    """[(what, min_darwin, max_darwin or None)] for the parts that bound macOS.

    Only the parts a table here actually bounds. The SMBIOS a build picks has a
    ceiling of its own and a discrete card can have one too; neither is recorded
    anywhere in this repository, so neither narrows the answer and the caller
    has to say so rather than presenting this as the machine's true ceiling."""
    out = []
    gen = hw.get('generation')
    if gen and any(gpu.looks_integrated(d.get('name'))
                   for d in hw.get('gpu_devices', [])):
        # an iGPU a field report says does not accelerate bounds nothing: the
        # machine is not going to be run on it either way
        field = gpu.field_igpu(hw.get('cpu'))
        usable = gpu.igpu_verdict(gen)[0] == 'works' and not (
            field and field['status'] != 'works')
        if usable and FRAMEBUFFERS.exists():
            for s in ocgen.read_toml(FRAMEBUFFERS).get('support', []):
                if gen in s.get('profiles', []):
                    out.append(('Intel graphics', *_window(s['min_darwin'],
                                                           s['max_darwin'])))
                    break

    matched = advise.matched_kexts(hw.get('pci_ids') or [], hw.get('usb_ids') or [])
    third_party_nvme = [d for d in hw.get('nvme') or [] if 'apple' not in d.lower()]
    if third_party_nvme:
        matched = set(matched) | {'NVMeFix.kext'}
    for s in netkexts.sets():
        if s['match'] not in matched or s.get('optional'):
            continue
        # a set covers wherever any one of its kexts applies: Broadcom Bluetooth
        # is four kexts in a relay, and the relay has no gap in it
        los = [int((k.get('min_kernel') or '0').split('.')[0]) for k in s['kext']]
        his = [k.get('max_kernel') for k in s['kext']]
        ceiling = None if any(not h for h in his) else max(
            int(h.split('.')[0]) for h in his)
        out.append((s['label'], min(los), ceiling))
    for s in netkexts.variant_sets():
        if s['match'] not in matched:
            continue
        variants = s.get('variant', [])
        if variants:
            out.append((s['label'], min(v['min_darwin'] for v in variants),
                        max(v['max_darwin'] for v in variants)))
    return out


def macos_range(hw):
    """(min_darwin, max_darwin or None, what set each end) across the machine."""
    windows = macos_windows(hw)
    if not windows:
        return None
    floor = max(windows, key=lambda w: w[1])
    ceilings = [w for w in windows if w[2] is not None]
    ceiling = min(ceilings, key=lambda w: w[2]) if ceilings else None
    return floor, ceiling


def name_for(darwin):
    for r in ocgen.read_toml(Path('data/macos.toml'))['release']:
        if r['darwin'] == darwin:
            return f'{r["name"]} {r["version"]}'
    return f'Darwin {darwin}'


LOCK = Path('vendor/kexts.lock')
LICENCES = Path('vendor/licences.toml')
SHIPPED = Path('EFI/OC/Kexts')


@functools.lru_cache(maxsize=1)
def _lock():
    return ocgen.read_toml(LOCK)['kext'] if LOCK.exists() else {}


@functools.lru_cache(maxsize=1)
def _licences():
    if not LICENCES.exists():
        return {}
    return {u['repo']: u['licence']
            for u in ocgen.read_toml(LICENCES).get('upstream', [])}


def kext_facts(bundle):
    """Everything this repository knows about one kext, by name.

    The lock is written from the tree by tools/kexts.py, so the version and the
    upstream are the ones actually vendored rather than the ones a table
    remembers. A kext with no row is not an error: the profiles ship a few this
    repository has never had to look up."""
    entry = _lock().get(bundle) or {}
    upstream = entry.get('upstream')
    licence = _licences().get(upstream) if upstream else None
    return {
        'bundle': bundle,
        'version': entry.get('version'),
        'upstream': upstream,
        'url': f'https://github.com/{upstream}' if upstream else None,
        'licence': licence,
        'shipped': (SHIPPED / bundle).exists(),
    }


def _release(darwin):
    if darwin is None:
        return None
    for r in ocgen.read_toml(Path('data/macos.toml'))['release']:
        if r['darwin'] == darwin:
            return {'darwin': darwin, 'name': r['name'], 'version': r['version']}
    return {'darwin': darwin, 'name': None, 'version': None}


def document(hw, source='this machine'):
    """The whole summary as values, for a front end to draw.

    The same functions the printed table is built from, with the kexts resolved
    against the lock. Nothing here is computed a second way: a screen that
    disagreed with the text would be a second answer to the same question."""
    parts = []
    for r in rows(hw):
        parts.append(dict(r, kexts=[kext_facts(k) for k in r['kexts']]))
    windows = [{'what': w[0], 'from': _release(w[1] or None), 'to': _release(w[2])}
               for w in macos_windows(hw)]
    span = macos_range(hw)
    return {
        't': 'machine',
        'source': source,
        'platform': ('laptop' if hw.get('laptop') else
                     'desktop' if hw.get('laptop') is False else None),
        'profile': {'cpu': hw.get('cpu'), 'generation': hw.get('generation'),
                    'oem': hw.get('oem'), 'cores': hw.get('cores'),
                    # what the machine calls itself, where it calls itself
                    # anything: a name a person recognises beats a processor
                    'model': hw.get('model')},
        'rows': parts,
        'macos': {
            # the floor is whichever part needs the newest macOS, the ceiling
            # whichever stops first; both name the part, because "10.12 or
            # newer" without saying what decided it cannot be argued with
            'from': _release(span[0][1]) if span and span[0][1] else None,
            'from_because': span[0][0] if span else None,
            'to': _release(span[1][2]) if span and span[1] else None,
            'to_because': span[1][0] if span and span[1] else None,
            'parts': windows,
        },
        # a table of nothing but unknown is not a report; a front end should
        # say so rather than draw eight empty rows
        'worth_showing': worth_showing(hw),
    }


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
        lines.append(f'  {DIM}For a card in a slot, replacing it is usually the '
                     f'answer. For one soldered on,\n  it is something to live '
                     f'without. Either way this does not stop the build, and the\n'
                     f'  sections below say more.{RESET}')
    else:
        lines.append(f'  {GREEN}Nothing here is known to be unsupported.{RESET}')
    if unknown:
        lines.append(f'  {DIM}{len(unknown)} left as unknown, where no table here has '
                     f'anything to say.{RESET}')

    window = macos_range(hw)
    if window:
        floor, ceiling = window
        span = f'{name_for(floor[1])} or newer'
        if ceiling:
            span = f'{name_for(floor[1])} to {name_for(ceiling[2])}'
        lines.append('')
        lines.append(f'  {BOLD}macOS{RESET}  {span}')
        lines.append(f'      {DIM}{floor[0]} sets the oldest'
                     + (f', {ceiling[0]} the newest' if ceiling else '') + f'{RESET}')
        # the honest caveat: this is as far as these tables reach, and two of the
        # things that really do cap a machine are not in any of them
        lines.append(f'      {DIM}from the parts these tables bound. The SMBIOS a build '
                     f'picks has a ceiling\n      of its own, and so can a discrete '
                     f'card; neither is recorded here.{RESET}')
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
