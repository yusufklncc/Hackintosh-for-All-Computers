"""Which AAPL,ig-platform-id to start from for an Intel iGPU.

Like the audio layout, this is a short list rather than an answer. Dortania
gives several per generation with a reason attached - default, recommended,
headless, "1366x768 screens" - and which one suits a machine depends on its
panel and its ports. So the most likely goes into the config and the rest are
written down.

What this deliberately does not do is write framebuffer connector patches. A
working laptop config often carries twenty more properties - con0/con1 patches,
stolenmem, fbmem - and those are tuned per machine by trying. Producing them
from a guess would look like configuration and behave like noise.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

TABLE = Path('data/gpu.toml')
FRAMEBUFFERS = Path('data/framebuffer.toml')
IGPU_PATH = 'PciRoot(0x0)/Pci(0x2,0x0)'

# The label says why you would choose it, so it also says what to try first.
PREFERENCE = ('recommended', 'default', '')

# An id no framebuffer kext claims means none attaches, and macOS falls back to
# a picture with no graphics acceleration. Yusuf uses that deliberately to get a
# first boot on a machine whose framebuffer is not worked out yet. It is not in
# anyone's documentation, which is why it says whose testing it rests on.
NO_ACCELERATION = {'value': '0x12345678', 'data': '78563412',
                   'label': 'boots without graphics acceleration',
                   'note': "not a real framebuffer: nothing claims it, so none "
                           "attaches. Reported by this repository's maintainer as a "
                           "way to get a first boot before the right id is known."}


def guide_candidates(generation, laptop):
    """The one or two Dortania names, which carry a reason to prefer them."""
    if not generation or not TABLE.exists():
        return []
    where = 'laptop_platform_id' if laptop else 'desktop_platform_id'
    for g in ocgen.read_toml(TABLE).get('igpu', []):
        if generation in g.get('profiles', []) and g.get(where):
            def rank(c):
                label = c['label'].lower()
                for i, want in enumerate(PREFERENCE):
                    if want and want in label:
                        return i
                # headless means no display out, so never the one to start with
                return len(PREFERENCE) + (1 if 'headless' in label else 0)
            return sorted(g[where], key=rank)
    return []


def documented(generation, laptop):
    """Every framebuffer WhateverGreen lists for this generation and form factor."""
    if not generation or not FRAMEBUFFERS.exists():
        return []
    want = 'mobile' if laptop else 'desktop'
    return [e for e in ocgen.read_toml(FRAMEBUFFERS).get('framebuffer', [])
            if generation in e.get('profiles', []) and e['type'] == want]


def candidates(generation, laptop):
    """Dortania's pick first, then the rest of WhateverGreen's list.

    Two sources rather than one because they answer different questions: the
    guide says which to start with and why, the kext's own manual says what else
    exists. Every id the guide names is in the manual's list too, which is the
    check that neither parser has drifted."""
    out, seen = [], set()
    for c in guide_candidates(generation, laptop):
        out.append(dict(c))
        seen.add(c['value'].lower())
    for e in documented(generation, laptop):
        if e['value'].lower() in seen:
            continue
        seen.add(e['value'].lower())
        label = f'{e["connectors"]} connectors, {e["stolen"]}'
        if not e['connectors']:
            label = f'headless, {e["stolen"]}'
        out.append({'value': e['value'], 'data': e['data'], 'label': label,
                    'connectors': e['connectors']})
    # headless last however it was described: no display output is never where
    # somebody wants to begin
    return sorted(out, key=lambda c: 'headless' in c['label'].lower())


def props_for(candidate):
    """DeviceProperties for one framebuffer.

    None asks for the key to be removed rather than merely not written: the
    profiles ship a placeholder, so not writing one would leave that behind and
    call it a choice."""
    if not candidate:
        return {IGPU_PATH: {'AAPL,ig-platform-id': None}}
    return {IGPU_PATH: {'AAPL,ig-platform-id': 'hex:' + candidate['data']}}


def report(generation, laptop, supported):
    """(lines, device properties to add, notes). Nothing when the iGPU is not
    supported - a platform id will not rescue a generation macOS has no driver
    for."""
    if not supported:
        return [], {}, ''
    cands = candidates(generation, laptop)
    if not cands:
        return [], {}, ''

    first = cands[0]
    lines = [f'  {len(cands)} framebuffer id{"s" if len(cands) > 1 else ""} for this '
             f'generation, starting with {first["value"]}'
             + (f'  ({first["label"]})' if first['label'] else '')]
    for c in cands[1:3]:
        lines.append(f'      {c["value"]}  {c["label"] or "alternative"}')
    if len(cands) > 3:
        lines.append(f'      and {len(cands) - 3} more, in NEXT-STEPS.txt')
    lines.append(f'      {NO_ACCELERATION["value"]}  {NO_ACCELERATION["label"]}')

    props = {IGPU_PATH: {'AAPL,ig-platform-id': 'hex:' + first['data']}}

    steps = ['Intel graphics', '',
             '  The framebuffer id decides which ports light up and how much',
             f'  memory the iGPU gets. {first["value"]} went in. If the screen stays',
             '  black, or an HDMI or DisplayPort output does nothing, try the next:', '']
    for c in cands:
        steps.append(f'    {c["value"]}   data {c["data"]}   {c["label"]}')
    steps += ['',
              f'  {NO_ACCELERATION["value"]}   data {NO_ACCELERATION["data"]}   '
              f'{NO_ACCELERATION["label"]}',
              f'      {NO_ACCELERATION["note"]}',
              '',
              '  Leaving the key out entirely is the other option: WhateverGreen',
              '  then injects the default framebuffer for the generation.',
              '']
    steps += ['',
              '  Change it under DeviceProperties in config.plist, at',
              f'  {IGPU_PATH}, key AAPL,ig-platform-id. The data value is the',
              '  byte-swapped form shown above.',
              '',
              '  Beyond this id, laptops often need connector patches tuned by hand.',
              '  This builder does not write those:',
              '  https://dortania.github.io/OpenCore-Install-Guide/', '']
    return lines, props, '\n'.join(steps)


if __name__ == '__main__':
    for gen, laptop in (('kaby-lake', True), ('kaby-lake', False), ('ivy-bridge', True),
                        ('coffe-lake', False), ('alder-lake', False)):
        lines, props, _ = report(gen, laptop, supported=gen != 'alder-lake')
        print(f'\n=== {gen} laptop={laptop} ===')
        print('\n'.join(lines) if lines else '  nothing to offer')
        if props:
            print(f'  -> {props[IGPU_PATH]}')
