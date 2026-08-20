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
IGPU_PATH = 'PciRoot(0x0)/Pci(0x2,0x0)'

# The label says why you would choose it, so it also says what to try first.
PREFERENCE = ('recommended', 'default', '')


def candidates(generation, laptop):
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

    props = {IGPU_PATH: {'AAPL,ig-platform-id': 'hex:' + first['data']}}

    steps = ['Intel graphics', '',
             '  The framebuffer id decides which ports light up and how much',
             f'  memory the iGPU gets. {first["value"]} went in. If the screen stays',
             '  black, or an HDMI or DisplayPort output does nothing, try the next:', '']
    for c in cands:
        steps.append(f'    {c["value"]}   data {c["data"]}   {c["label"]}')
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
