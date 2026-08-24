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
import coverage
import inputdev
import mactable
import netkexts
import ocgen
import ui

PROFILES = Path('profiles')

SUPPORTED, UNSUPPORTED, UNKNOWN, ABSENT = 'supported', 'not supported', 'unknown', '-'
# Only ever said about a Mac, and only about a device the running system has
# handed to a driver. It answers a different question from SUPPORTED: not "does
# a kext here claim it" but "is macOS driving it", asked of a machine that is
# running macOS at the time.
DRIVEN = 'driven by macOS'

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'red', 'reset')

DETAIL = 52

COLOUR = {SUPPORTED: GREEN, DRIVEN: GREEN, UNSUPPORTED: RED,
          UNKNOWN: YELLOW, ABSENT: DIM}

AMD_GENERATIONS = ('ryzen-threadripper', 'bulldozer-jaguar')


def row(part, what, verdict, detail='', kexts=(), ids=(), note=None, driver=None):
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
            # the driver the running system gave the device to. Not a kext:
            # nothing here ships it, and it belongs in its own field so a
            # front end does not draw it as a project it can link to.
            'driver': driver,
            'kexts': list(kexts), 'ids': list(ids)}


def platform_name(hw):
    gen = hw.get('generation')
    if hw.get('laptop'):
        return 'laptop'
    return 'desktop-amd' if gen in AMD_GENERATIONS else 'desktop-intel'


def _apple_silicon(hw):
    return (hw.get('system') == 'Darwin'
            and (hw.get('cpu') or '').startswith('Apple '))


def cpu_row(hw):
    gen, name = hw.get('generation'), hw.get('cpu')
    if not name:
        return row('CPU', 'not readable', UNKNOWN, 'answer the question by hand')
    if _apple_silicon(hw):
        # There is no profile and there never will be: this program builds for
        # Intel and AMD. macOS running on the chip while it is asked is the
        # whole of the answer about it.
        return row('CPU', name, DRIVEN,
                   'Apple silicon, running macOS natively; this program builds '
                   'for Intel and AMD', note='this program builds for Intel and AMD',
                   driver='Apple silicon')
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
    if _apple_silicon(hw):
        return [row('Graphics', hw.get('cpu') or 'Apple graphics', DRIVEN,
                    'part of the Apple silicon package, driven by macOS',
                    note='part of the Apple silicon package',
                    driver='Apple silicon')]
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
    if not ids and hw.get('audio_devices'):
        # Apple silicon has no HD audio codec to read, and AppleALC is about
        # codecs. The devices are named though, and naming them beats "no
        # codec readable" on a machine whose speakers are working.
        return row('Audio', ', '.join(hw['audio_devices']), DRIVEN,
                   "macOS drives these; there is no HD audio codec to match",
                   note='no HD audio codec on this machine',
                   driver='macOS audio')
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
        elif [i for i, r in (hw.get('machine_roles') or {}).items() if r == role]:
            # Nothing here claims it, but the machine said what it is. That is
            # a Mac: no kext claims an Apple chip, and the registry naming the
            # device is the only source there is for what it does.
            for device_id in [i for i, r in hw['machine_roles'].items()
                              if r == role]:
                driver = (hw.get('machine_drivers') or {}).get(device_id)
                out.append(row(label, names.get(device_id) or device_id,
                               DRIVEN if driver else UNKNOWN,
                               f'macOS has it on {driver}' if driver
                               else 'this machine says what the device is; no '
                                    'kext here claims it',
                               ids=[device_id], driver=driver,
                               note='' if driver else 'the machine says what it '
                                    'is; nothing here drives it'))
        elif hw.get('system') == 'Darwin':
            # the registry named every device it has, and none of them is this
            out.append(row(label, 'none', ABSENT, 'this Mac has no such device'))
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
    if not (hw.get('laptop') or i2c or pointing or hw.get('multitouch')):
        return None
    if hw.get('multitouch') and not pointing:
        # a Mac's trackpad is neither PS/2 nor I2C; it is its own device class,
        # and the machine says whether it is there
        return row('Trackpad', 'Apple Multi-Touch', DRIVEN,
                   'macOS drives it', note='', driver='AppleMultitouchDevice')
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
        if hw.get('system') == 'Darwin' and hw.get('camera_driver'):
            out.append(row('Camera', dev['name'], DRIVEN,
                           f"macOS has it on {hw['camera_driver']}",
                           note='', driver=hw['camera_driver']))
            continue
        if hw.get('system') == 'Darwin':
            # on a PC a camera off the USB bus is an IPU or MIPI sensor with no
            # macOS driver. On a Mac it is Apple's own and already working, and
            # saying "not supported" about it would be a claim about the wrong
            # machine.
            out.append(row('Camera', dev['name'], UNKNOWN,
                           "a Mac's own camera, which this repository has no "
                           'data for either way'))
            continue
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
        # `attached`, not `driver`: the name below is the kext this repository
        # would use, and shadowing it made the table's own driver disappear
        attached = (hw.get('machine_drivers') or {}).get(
            f'{own.group(1).lower()}:{own.group(2).lower()}' if own else None)
        if hw.get('system') == 'Darwin' and attached:
            out.append(row('Card reader', dev['name'], DRIVEN,
                           f'macOS has it on {attached}', note='',
                           driver=attached,
                           ids=[found['id']] if found else ()))
            continue
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


def profile_window(hw):
    """What the CPU profile itself covers, in Darwin majors, or None.

    The processor is the first thing that bounds macOS and it was the one thing
    not counted here. An AMD machine runs on kernel patches, those patches carry
    their own bounds, and above them it does not boot at all - a harder limit
    than any kext imposes. A Ryzen desktop with no recognised network card
    therefore read as "not bounded here" when its profile said 10.13 to 26."""
    generation = hw.get('generation')
    if not generation:
        return None
    row = {'path': '', 'platform': 'laptop' if hw.get('laptop') else 'desktop',
           'vendor': None if hw.get('laptop') else
                     ('amd' if generation in AMD_GENERATIONS else 'intel'),
           'cpu': generation, 'chipset': None, 'oem': None, 'variant': None,
           'cores': hw.get('cores')}
    try:
        return coverage.window_for(row)
    except (KeyError, ValueError, FileNotFoundError):
        # a core count with no variant, a generation with no profile: the rest
        # of the screen is still worth drawing
        return None


def _darwin_of(version):
    """The Darwin major for a macOS version string, or None.

    "10.13.6" and "11" both appear on the guide's pages; the table here is
    keyed on "10.13" and "11", so the third part is dropped."""
    if not version:
        return None
    parts = version.split('.')
    short = '.'.join(parts[:2]) if version.startswith('10.') else parts[0]
    for release in ocgen.read_toml(Path('data/macos.toml'))['release']:
        if str(release['version']) == short:
            return release['darwin']
    return None


def macos_windows(hw):
    """[(what, min_darwin, max_darwin or None)] for the parts that bound macOS.

    Only the parts a table here actually bounds. The SMBIOS a build picks has a
    ceiling of its own and a discrete card can have one too; neither is recorded
    anywhere in this repository, so neither narrows the answer and the caller
    has to say so rather than presenting this as the machine's true ceiling."""
    out = []
    profile = profile_window(hw)
    if profile:
        out.append(('the kernel patches this CPU needs', profile[0], profile[1]))
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

    # a supported NVIDIA card really does bound macOS, and hard: Kepler ends at
    # Big Sur and Pascal at High Sierra, which is older than anything else here
    # is likely to say
    for device in hw.get('gpu_devices') or []:
        family = gpu.nvidia_family(device)
        if not family or family['status'] != 'works':
            continue
        floor = _darwin_of(family.get('lowest_version'))
        ceiling = _darwin_of(family.get('highest_version'))
        if floor or ceiling:
            out.append((family['name'].split('(')[0].strip(), floor or 0, ceiling))

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


def graphics_advice(hw):
    """What the graphics mean for the macOS range, or None if they mean nothing.

    The range itself comes from the processor and the kexts, because those are
    what the tables bound. Graphics do not narrow it - they decide whether the
    machine has a display at all - so they belong beside the range as a warning
    rather than folded into it, where an unsupported card would silently look
    like a version limit.

    Four cases, and each one ends in what to do about it:

        card unsupported, iGPU works      run on the iGPU
        card unsupported, iGPU does not   replace the card, nothing covers for it
        card unsupported, no iGPU at all  replace the card, there is no fallback
        card unknown                      say so, and say it is not a verdict
    """
    devices = hw.get('gpu_devices') or []
    if not devices:
        return None
    generation = hw.get('generation')

    discrete, integrated = [], []
    for device in devices:
        verdict = gpu.classify(device, generation)[0]
        name = device.get('name') or 'graphics'
        (integrated if gpu.looks_integrated(name) else discrete).append(
            {'name': name, 'verdict': verdict})

    # a field report about this exact processor outranks the generation rule
    field = gpu.field_igpu(hw.get('cpu'))
    for entry in integrated:
        if field:
            entry['verdict'] = field['status']

    bad = [d for d in discrete if d['verdict'] == 'unsupported']
    unclear = [d for d in discrete if d['verdict'] not in ('works', 'works-spoofed',
                                                           'unsupported')]
    if not bad:
        if unclear:
            return {'tone': UNKNOWN,
                    'text': f'{unclear[0]["name"]} is in neither the card table nor '
                            'the family rules, so nothing here can say whether macOS '
                            'drives it. That is not the same as unsupported.'}
        return None

    named = ', '.join(d['name'] for d in bad)
    usable = [d for d in integrated if d['verdict'] in ('works', 'works-spoofed')]
    if usable:
        return {'tone': UNSUPPORTED,
                'text': f'{named} is not supported. macOS would run on '
                        f'{usable[0]["name"]} instead, so the range above still '
                        'holds - but the card gives you nothing and the display '
                        'has to come off the integrated one.'}
    if integrated:
        return {'tone': UNSUPPORTED,
                'text': f'{named} is not supported, and neither is '
                        f'{integrated[0]["name"]}. The card has to be replaced '
                        'with one macOS drives; the integrated graphics cannot '
                        'cover for it.'}
    return {'tone': UNSUPPORTED,
            'text': f'{named} is not supported and there is no integrated graphics '
                    'to fall back on. The card has to be replaced with one macOS '
                    'drives, or this machine has no display under macOS.'}


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


def _by_version(major):
    """The release whose version string is this major, or None."""
    if not major:
        return None
    for r in ocgen.read_toml(Path('data/macos.toml'))['release']:
        if str(r['version']) == str(major):
            return {'darwin': r['darwin'], 'name': r['name'],
                    'version': str(r['version'])}
    return {'darwin': None, 'name': None, 'version': str(major)}


def genuine_mac(hw):
    """What Apple says about this Mac, or None if it is not one.

    A different question from the rest of this file. Everywhere else the answer
    comes from what a kext claims; here it comes from Apple's own list of which
    machines each macOS line still runs on, because on a real Mac that is the
    only question worth asking."""
    # both, not either: a probe from a report carries whatever the machine it
    # came from had, and only a Mac's board means anything to Apple's list
    if hw.get('system') != 'Darwin':
        return None
    board = hw.get('board_id')
    if not board:
        return None
    found = mactable.window(board)
    if not found:
        # a Mac too new or too old for the lines Apple still serves
        return {'board': board, 'from': None, 'to': None, 'listed': False}
    floor, ceiling = found
    return {'board': board, 'from': _by_version(floor), 'to': _by_version(ceiling),
            'listed': True}


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
                    'model': hw.get('model'),
                    # a front end says something different about a Mac, and
                    # only the probe knows what it ran on
                    'system': hw.get('system')},
        'rows': parts,
        # how much was read, which is not the same as how much was recognised:
        # a row says "nothing recognised" and carries no id, and counting the
        # rows' ids then says nothing was readable when five devices were
        'read': {kind: len(hw.get(kind + '_ids') or [])
                 for kind in ('pci', 'usb', 'hda', 'acpi')},
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
        # a real Mac answers the macOS question from Apple rather than from the
        # kexts, which claim none of its hardware
        'mac': genuine_mac(hw),
        # what the graphics mean for that range: not a bound on it, but the
        # difference between a machine that boots to a display and one that does not
        'graphics_advice': graphics_advice(hw),
    }


def worth_showing(hw):
    """Whether a summary of this machine would say anything.

    A table of nothing but `unknown` is not a report, it is noise - and it is
    what a Mac produces, since it reports its own hardware and this reads none
    of it. One line saying so beats ten saying nothing."""
    return any(r['verdict'] in (SUPPORTED, DRIVEN, UNSUPPORTED) for r in rows(hw))


def _fit(text, width):
    return text if len(text) <= width else text[:width - 1] + '\u2026'


def render(hw, source='this machine'):
    """The whole screen as lines."""
    table = rows(hw)
    width = max(len(r['what']) for r in table)
    width = min(max(width, 24), 44)
    # measured, not fixed at 14: "driven by macOS" is fifteen characters and ran
    # straight into the sentence after it
    verdict_width = max(14, max(len(r['verdict']) for r in table)) + 1
    lines = [f'{BOLD}Hardware for macOS{RESET}  {DIM}from {source}{RESET}', '']
    for r in table:
        what = _fit(r['what'], width)
        colour = COLOUR[r['verdict']]
        # a detail that does not fit wraps rather than being cut. The part that
        # would be lost is where the caveats live - "Kepler was the last
        # supported family" - and half a sentence is worse than two lines.
        body = textwrap.wrap(r['detail'], DETAIL) or ['']
        lines.append(f'  {r["part"]:<12s} {what:<{width}s}  '
                     f'{colour}{r["verdict"]:<{verdict_width}s}{RESET}'
                     f'{DIM}{body[0]}{RESET}'.rstrip())
        pad = ' ' * (2 + 12 + 1 + width + 2 + verdict_width)
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
