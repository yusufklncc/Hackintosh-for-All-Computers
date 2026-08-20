"""Derive the layered profile set from the existing configs under EFI/OC/config.

Nothing here is hand-authored: every profile is computed from the tree that is
already in the repository, so the result reproduces it by construction. The
equivalence gate in verify.py is what proves it.

    python3 tools/extract.py <path-to-Sample.plist> [--out profiles]
"""
import argparse
import collections
import glob
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

ROOT = ocgen.CONFIG_ROOT
slug = ocgen.slug
classify = ocgen.classify
prepare_sample = ocgen.prepare_sample
strip_identity = ocgen.strip_identity


def intersect(trees):
    """Largest partial tree shared by every input tree."""
    if not trees:
        return {}
    out = {}
    for k, v in trees[0].items():
        if any(k not in t for t in trees[1:]):
            continue
        others = [t[k] for t in trees[1:]]
        if isinstance(v, dict) and all(isinstance(o, dict) for o in others):
            sub = intersect([v] + others)
            if sub:
                out[k] = sub
        elif all(o == v for o in others):
            out[k] = v
    return out


def common_diff(ref, targets):
    return intersect([ocgen.diff(ref, t) or {} for t in targets])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sample')
    ap.add_argument('--out', default='profiles')
    a = ap.parse_args()

    out = Path(a.out)
    sample = strip_identity(prepare_sample(ocgen.load_plist(a.sample)))
    rows = [classify(p) for p in sorted(glob.glob(f'{ROOT}/**/*.plist', recursive=True))]
    tree = {r['path']: strip_identity(ocgen.load_plist(r['path'])) for r in rows}
    written = collections.Counter()

    def emit(rel, data, note):
        if data:
            ocgen.write_toml(out / rel, ocgen.encode(data), f'# {note}\n')
            written[rel.split('/')[0]] += 1

    # ---- level 0: what every config changes about Sample.plist
    base = common_diff(sample, list(tree.values()))
    emit('base.toml', base, 'Applies to every generated config.')
    lvl0 = ocgen.merge(sample, base)

    # ---- level 1: platform / vendor
    canon = [r for r in rows if not (r['chipset'] or r['oem'] or r['variant'])]
    groups = collections.defaultdict(list)
    for r in canon:
        groups[(r['platform'], r['vendor'])].append(r)
    lvl1 = {}
    for (plat, vend), rs in groups.items():
        name = f'{plat}-{vend}' if vend else plat
        layer = common_diff(lvl0, [tree[r['path']] for r in rs])
        emit(f'platform/{name}.toml', layer, f'{len(rs)} cpu profiles build on this.')
        lvl1[(plat, vend)] = ocgen.merge(lvl0, layer)

    # ---- level 2: one profile per cpu generation (per core count for AMD)
    cpu_ref = {}
    for r in canon:
        key = (r['platform'], r['vendor'], r['cpu'], r['cores'])
        name = r['cpu'] + (f'-{r["cores"]}core' if r['cores'] else '')
        plat = f'{r["platform"]}-{r["vendor"]}' if r['vendor'] else r['platform']
        prof = ocgen.diff(lvl1[(r['platform'], r['vendor'])], tree[r['path']]) or {}
        emit(f'cpu/{plat}/{name}.toml', prof, f'Derived from {r["path"]}')
        cpu_ref[key] = ocgen.merge(lvl1[(r['platform'], r['vendor'])], prof)

    # ---- level 3: overlays, only where every member agrees
    by_tag = collections.defaultdict(list)
    for r in rows:
        act = [(t, r[t]) for t in ('oem', 'chipset', 'variant') if r[t]]
        if act:
            by_tag['+'.join(f'{t}.{n}' for t, n in act)].append(r)
    shared, leaves = 0, []
    for tag, rs in sorted(by_tag.items()):
        deltas = {}
        for r in rs:
            d = ocgen.diff(cpu_ref[(r['platform'], r['vendor'], r['cpu'], r['cores'])],
                           tree[r['path']]) or {}
            deltas.setdefault(repr(ocgen.encode(d)), []).append((r, d))
        if len(deltas) == 1:
            _, pairs = next(iter(deltas.items()))
            emit(f'overlay/{tag.replace("+", "/")}.toml', pairs[0][1],
                 f'{len(pairs)} configs, identical delta.')
            shared += 1
        else:
            for r, d in [p for v in deltas.values() for p in v]:
                rel = os.path.relpath(r['path'], ROOT)[:-6]
                emit(f'config/{slug(rel)}.toml', d, f'Exception: {r["path"]}')
                leaves.append(r['path'])

    print(f'  base              1')
    for k in ('platform', 'cpu', 'overlay', 'config'):
        print(f'  {k:16s} {written[k]:3d}')
    print(f'\n  shared overlays: {shared}   per-config exceptions: {len(leaves)}')
    for p in leaves:
        print(f'      {p}')
    print(f'\n  total profile files: {sum(written.values()) + (1 if base else 0) - written["base.toml"] if False else sum(written.values())}')


if __name__ == '__main__':
    main()
