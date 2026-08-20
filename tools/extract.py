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


def templatize(ref, variants):
    """Turn byte leaves that encode the core count into {cores:02x} placeholders.

    A leaf qualifies only if every variant's bytes are identical to the
    reference except at positions holding that variant's own core count. Bytes
    that differ for any other reason are left alone and land in a per-core
    override, so nothing is normalised away."""
    def walk(node, others):
        if isinstance(node, dict):
            return {k: walk(v, [o[k] for o in others]) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, [o[i] for o in others]) for i, v in enumerate(node)]
        if not isinstance(node, bytes) or all(o == node for _, o in
                                              zip(range(len(others)), others)):
            return node
        vals = [(c, o) for (c, _), o in zip(variants, others)]
        if any(not isinstance(o, bytes) or len(o) != len(node) for _, o in vals):
            return node
        # template a position only where every variant holds its own core count;
        # positions that differ for any other reason stay at the reference value
        # and the variants that disagree get an override of their own
        pos = [i for i in range(len(node))
               if all(o[i] == c for c, o in vals) and any(o[i] != node[i] for _, o in vals)]
        if not pos:
            return node
        out = ocgen.HEX + node.hex()
        for i in sorted(pos, reverse=True):
            out = out[:len(ocgen.HEX) + 2 * i] + '{cores:02x}' + out[len(ocgen.HEX) + 2 * i + 2:]
        return out
    return walk(ref, [t for _, t in variants])


def key_of(r):
    return (r['platform'], r['vendor'], r['cpu'], r['cores'])


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

    # ---- level 2: one profile per cpu generation. Core-count variants of the
    #      same generation collapse into a single templated profile.
    cpu_ref = {}
    fams = collections.defaultdict(list)
    for r in canon:
        fams[(r['platform'], r['vendor'], r['cpu'])].append(r)
    for (plat, vend, cpu), rs in sorted(fams.items()):
        pname = f'{plat}-{vend}' if vend else plat
        profs = {r['cores']: (ocgen.diff(lvl1[(plat, vend)], tree[r['path']]) or {}) for r in rs}
        rs.sort(key=lambda r: r['cores'] or 0)
        tpl = profs[rs[0]['cores']]
        if len(rs) > 1:
            # try every variant as the template source and keep the one that
            # needs the fewest overrides, so an outlier stays an outlier instead
            # of becoming the norm every sibling has to correct
            def overrides_for(cand):
                t = templatize(profs[cand], sorted(profs.items()))
                n = 0
                for r in rs:
                    exp = ocgen.decode(ocgen.expand(ocgen.encode(t), ocgen.build_params(r)))
                    if ocgen.diff(ocgen.merge(lvl1[(plat, vend)], exp), tree[r['path']]):
                        n += 1
                return n, t
            _, tpl = min((overrides_for(r['cores']) for r in rs), key=lambda x: x[0])
        emit(f'cpu/{pname}/{cpu}.toml',
             tpl, f'{len(rs)} config' + (f', {len(rs)} core counts' if len(rs) > 1 else ''))
        for r in rs:
            params = ocgen.build_params(r)
            expanded = ocgen.decode(ocgen.expand(ocgen.encode(tpl), params))
            built = ocgen.merge(lvl1[(plat, vend)], expanded)
            over = ocgen.diff(built, tree[r['path']])
            if over:
                emit(f'cpu/{pname}/{cpu}.{r["cores"]}core.toml', over,
                     f'{r["cores"]}-core deviates from the templated profile.')
                built = ocgen.merge(built, over)
            cpu_ref[key_of(r)] = built

    # ---- level 3a: single-axis overlays, learned from configs where that axis
    #      is the only one active, so a combination cannot contaminate them.
    solo = collections.defaultdict(list)
    for r in rows:
        act = [(ax, r[ax]) for ax in ocgen.OVERLAY_ORDER if r[ax]]
        if len(act) == 1:
            solo[act[0]].append(r)
    overlays = {}
    for (axis, name), rs in sorted(solo.items()):
        # each config is diffed against its own cpu reference, then intersected;
        # the group spans several cpu generations, so one shared reference is wrong
        d = intersect([ocgen.diff(cpu_ref[key_of(r)], tree[r['path']]) or {} for r in rs])
        if d:
            emit(f'overlay/{axis}.{name}.toml', d, f'{len(rs)} configs use this alone.')
            overlays[(axis, name)] = d

    # ---- level 3b: whatever composing those overlays does not already produce
    def composed(r):
        t = cpu_ref[key_of(r)]
        for ax in ocgen.OVERLAY_ORDER:
            if r[ax] and (ax, r[ax]) in overlays:
                t = ocgen.merge(t, overlays[(ax, r[ax])])
        return t

    by_tag = collections.defaultdict(list)
    for r in rows:
        if ocgen.overlay_tag(r):
            by_tag[ocgen.overlay_tag(r)].append(r)
    combos, leaves = 0, []
    for tag, rs in sorted(by_tag.items()):
        res = {r['path']: (ocgen.diff(composed(r), tree[r['path']]) or {}) for r in rs}
        if not any(res.values()):
            continue
        uniq = {repr(ocgen.encode(d)) for d in res.values()}
        if len(uniq) == 1:
            emit(f'overlay/combo/{tag}.toml', next(iter(res.values())),
                 f'{len(rs)} configs; residual after composing the single-axis overlays.')
            combos += 1
        else:
            for r in rs:
                if res[r['path']]:
                    emit(f'config/{ocgen.exception_name(r)}.toml', res[r['path']],
                         f'Residual specific to {r["path"]}')
                    leaves.append(r['path'])

    print(f'  base              1')
    for k in ('platform', 'cpu', 'overlay', 'config'):
        print(f'  {k:16s} {written[k]:3d}')
    print(f'\n  single-axis overlays: {len(overlays)}   combo residuals: {combos}'
          f'   per-config residuals: {len(leaves)}')
    for p in leaves:
        print(f'      {p}')
    print(f'\n  total profile files: {sum(written.values()) + (1 if base else 0) - written["base.toml"] if False else sum(written.values())}')


if __name__ == '__main__':
    main()
