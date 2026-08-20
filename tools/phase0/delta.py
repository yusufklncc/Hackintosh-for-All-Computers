"""Phase 0 / step 2: derive layer deltas and check that each layer is consistent."""
import plistlib, json, sys, collections

def flat(o, pre=''):
    """Flatten a plist into {dotted.path: scalar}. Arrays keep index in the path."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, f'{pre}{k}.'))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(flat(v, f'{pre}[{i}].'))
    else:
        out[pre[:-1]] = o
    return out

def delta(a, b):
    """What must be applied to a to obtain b."""
    fa, fb = flat(a), flat(b)
    d = {}
    for k in fb.keys() | fa.keys():
        if k not in fa:      d[k] = ('add', fb[k])
        elif k not in fb:    d[k] = ('del', None)
        elif fa[k] != fb[k]: d[k] = ('set', fb[k])
    return d

def show(v):
    if isinstance(v, bytes): return f'<data {len(v)}B>'
    s = str(v)
    return s if len(s) <= 44 else s[:41] + '...'

def key(d):
    return tuple(sorted((k, op, show(v)) for k, (op, v) in d.items()))

rows = json.load(open(sys.argv[1]))
plists = {r['path']: plistlib.load(open(r['path'], 'rb')) for r in rows}

# canonical = same (platform, vendor, cpu, cores), no chipset/oem/variant
canon = {}
for r in rows:
    if not (r['chipset'] or r['oem'] or r['variant']):
        canon[(r['platform'], r['vendor'], r['cpu'], r['cores'])] = r['path']

by_layer = collections.defaultdict(lambda: collections.defaultdict(list))
orphans = []
for r in rows:
    layers = [('oem', r['oem']), ('chipset', r['chipset']), ('variant', r['variant'])]
    active = [(t, n) for t, n in layers if n]
    if not active:
        continue
    base = canon.get((r['platform'], r['vendor'], r['cpu'], r['cores']))
    if not base:
        orphans.append(r); continue
    d = delta(plists[base], plists[r['path']])
    tag = '+'.join(f'{t}:{n}' for t, n in active)
    by_layer[tag][key(d)].append(r['path'])

print(f'{len(rows)} configs, {len(canon)} canonical (no overlay)\n')
print('=== overlay consistency ===')
clean = messy = 0
for tag in sorted(by_layer):
    variants = by_layer[tag]
    n = sum(len(v) for v in variants.values())
    if len(variants) == 1:
        clean += 1
        d = next(iter(variants))
        body = ', '.join(f'{k}={v}' for k, op, v in d) if d else '(identical to base)'
        print(f'  OK    {tag:34s} {n:3d} configs -> {body}')
    else:
        messy += 1
        print(f'  SPLIT {tag:34s} {n:3d} configs -> {len(variants)} different deltas')
        for d, files in sorted(variants.items(), key=lambda x: -len(x[1])):
            body = ', '.join(f'{k}={v}' for k, op, v in d) if d else '(identical to base)'
            print(f'          {len(files):3d}x {body}')
            if len(files) <= 3:
                for f in files: print(f'               {f}')
print(f'\n  consistent overlays: {clean}   inconsistent: {messy}')
if orphans:
    print(f'\n=== no canonical parent ({len(orphans)}) ===')
    for r in orphans: print('   ', r['path'])
