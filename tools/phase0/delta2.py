"""Phase 0 / step 2b: same analysis, with generated identity + cosmetic noise excluded."""
import plistlib, json, sys, collections, re

IDENTITY = {'PlatformInfo.Generic.SystemSerialNumber', 'PlatformInfo.Generic.MLB',
            'PlatformInfo.Generic.SystemUUID', 'PlatformInfo.Generic.ROM'}
COSMETIC = re.compile(r'\.Comment$')

def flat(o, pre=''):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items(): out.update(flat(v, f'{pre}{k}.'))
    elif isinstance(o, list):
        for i, v in enumerate(o): out.update(flat(v, f'{pre}[{i}].'))
    else: out[pre[:-1]] = o
    return out

def keep(k, drop_cosmetic):
    if k in IDENTITY: return False
    if drop_cosmetic and COSMETIC.search(k): return False
    return True

def delta(a, b, drop_cosmetic):
    fa = {k: v for k, v in flat(a).items() if keep(k, drop_cosmetic)}
    fb = {k: v for k, v in flat(b).items() if keep(k, drop_cosmetic)}
    d = {}
    for k in fb.keys() | fa.keys():
        if k not in fa: d[k] = ('add', fb[k])
        elif k not in fb: d[k] = ('del', None)
        elif fa[k] != fb[k]: d[k] = ('set', fb[k])
    return d

def show(v):
    if isinstance(v, bytes): return f'<data:{v.hex()[:12]}>'
    s = str(v); return s if len(s) <= 40 else s[:37] + '...'

def key(d): return tuple(sorted((k, op, show(v)) for k, (op, v) in d.items()))

rows = json.load(open(sys.argv[1]))
drop_cosmetic = '--strict' not in sys.argv
plists = {r['path']: plistlib.load(open(r['path'], 'rb')) for r in rows}
canon = {(r['platform'], r['vendor'], r['cpu'], r['cores']): r['path']
         for r in rows if not (r['chipset'] or r['oem'] or r['variant'])}

by_layer = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    active = [(t, r[t]) for t in ('oem', 'chipset', 'variant') if r[t]]
    if not active: continue
    base = canon[(r['platform'], r['vendor'], r['cpu'], r['cores'])]
    by_layer['+'.join(f'{t}:{n}' for t, n in active)][key(delta(plists[base], plists[r['path']], drop_cosmetic))].append(r['path'])

print(f'cosmetic Comment fields {"IGNORED" if drop_cosmetic else "INCLUDED"}\n')
clean = messy = 0
for tag in sorted(by_layer):
    v = by_layer[tag]; n = sum(len(x) for x in v.values())
    if len(v) == 1:
        clean += 1
        d = next(iter(v))
        print(f'  OK    {tag:52s} {n:3d}x  {len(d)} key')
    else:
        messy += 1
        print(f'  SPLIT {tag:52s} {n:3d}x  -> {len(v)} farkli delta')
        for d, files in sorted(v.items(), key=lambda x: -len(x[1])):
            diff = set(d) ^ set(next(iter(v)))
            print(f'          {len(files):3d}x {len(d)} key   ayrisan: {sorted(k for k,_,_ in diff)[:6]}')
print(f'\n  tutarli: {clean}   tutarsiz: {messy}')

# how big is each canonical CPU profile relative to the most common baseline?
print('\n=== kanonik config sayisi ve ortak taban ===')
base_candidates = collections.defaultdict(collections.Counter)
for p in canon.values():
    for k, v in flat(plists[p]).items():
        if keep(k, drop_cosmetic): base_candidates[k][show(v)] += 1
N = len(canon)
universal = [k for k, c in base_candidates.items() if len(c) == 1 and sum(c.values()) == N]
print(f'  {N} kanonik config, toplam {len(base_candidates)} anahtar yolu')
print(f'  hepsinde ayni olan (saf taban)      : {len(universal)}')
print(f'  profile gore degisen (katman icerigi): {len(base_candidates)-len(universal)}')
