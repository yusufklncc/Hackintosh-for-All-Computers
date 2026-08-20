"""Which Darwin kernels each config actually covers, measured from the config.

Every injected kext and every kernel patch carries MinKernel/MaxKernel. Taken
together they say where a config is fully armed and where parts of it silently
stop applying. Nothing here is assumed: the numbers come from the configs, and
even the Darwin-to-macOS names are recovered from the repository's own patch
comments rather than from a table someone typed.

    python3 tools/coverage.py            # per-config ceilings
    python3 tools/coverage.py --names    # show the recovered kernel/macOS map
"""
import argparse
import collections
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

INF = (99, 99, 99)


def parse(v, default):
    if not v:
        return default
    parts = (v.split('.') + ['0', '0'])[:3]
    try:
        return tuple(int(x) for x in parts)
    except ValueError:
        return default


def fmt(t):
    return 'unbounded' if t == INF else '.'.join(str(x) for x in t)


VERSION_TAIL = re.compile(
    r'[\s\-/|,]*\b(?:\d{1,2}\.\d{1,2}(?:\.\d+)?|1[0-9]\.\d{1,2})\s*\+?'
    r'(?:[\s\-/|,]*(?:\d{1,2}\.\d{1,2}(?:\.\d+)?)\s*\+?)*[\s\-/|]*$')


def capability(comment):
    """The function a patch performs, independent of who wrote it and of which
    macOS versions this particular entry covers.

    AMD_Vanilla writes comments as "author | function | range", and a successor
    patch for newer kernels often carries a different author. Keying on the
    middle segment is what lets a handover read as one capability instead of two."""
    parts = [p.strip() for p in comment.split('|')]
    if len(parts) >= 3:
        return ' | '.join(parts[1:-1])
    return VERSION_TAIL.sub('', comment).strip(' -/|,')


PROFILES = Path('profiles')


def load_configs():
    """Every published config, generated from the profiles."""
    sample = ocgen.load_plist(ocgen.vendored_sample())
    out = []
    for e in ocgen.read_toml(PROFILES / 'catalogue.toml')['config']:
        row = {'path': f"{ocgen.CONFIG_ROOT}/{e['name']}.plist",
               'platform': e['platform'], 'vendor': e.get('vendor'), 'cpu': e['cpu'],
               'chipset': e.get('chipset'), 'oem': e.get('oem'),
               'variant': e.get('variant'), 'cores': e.get('cores')}
        out.append((e['name'], ocgen.assemble(sample, ocgen.layer_chain(row, PROFILES),
                                              ocgen.build_params(row))))
    return out


def recover_names(configs):
    """Darwin major -> macOS versions, learned from patch comments in this tree.

    A comment like "... 10.13,10.14" on a patch bounded to 17.0.0-18.99.99 pins
    two majors at once. Only mappings that never contradict themselves are kept."""
    votes = collections.defaultdict(collections.Counter)
    for _, cfg in configs:
        for p in cfg['Kernel'].get('Patch', []):
            c = p.get('Comment', '')
            names = re.findall(r'\b(10\.\d{2}|1[1-9]\.\d|1[1-9])\b', c)
            lo, hi = parse(p.get('MinKernel'), None), parse(p.get('MaxKernel'), None)
            if not names or not lo or not hi:
                continue
            majors = list(range(lo[0], hi[0] + 1))
            if len(majors) != len(set(names)):
                continue
            for major, name in zip(majors, sorted(set(names), key=lambda s: [int(x) for x in s.split('.')])):
                votes[major][name] += 1
    return {m: c.most_common(1)[0][0] for m, c in sorted(votes.items()) if len(c) == 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--names', action='store_true')
    a = ap.parse_args()

    configs = load_configs()
    names = recover_names(configs)
    if a.names:
        print('  Darwin major -> macOS, recovered from patch comments in this tree:')
        for k, v in names.items():
            print(f'    {k:3d}  {v}')
        return 0

    def union_ceiling(ranges):
        """Highest kernel still covered by a set of ranges, walking the gaps."""
        ranges = sorted(ranges)
        reach = ranges[0][1]
        for lo, hi in ranges[1:]:
            if lo > _bump(reach):
                break               # a gap: coverage really ends at reach
            reach = max(reach, hi)
        return reach

    def _bump(t):
        return (t[0] + 1, 0, 0) if t != INF else INF

    gaps = collections.defaultdict(list)
    label = {}
    total = 0
    for f, d in configs:
        total += 1
        # a capability is one patch site, or one kext
        caps = collections.defaultdict(list)
        for p in d['Kernel'].get('Patch', []):
            if p.get('Enabled'):
                # Successive patches for the same capability differ in Find as
                # the compiled code shifts between releases, so the byte pattern
                # cannot identify one. The comment minus its version suffix can.
                # Base is part of neither: a successor patch often anchors at a
                # different symbol and capitalises its comment differently while
                # doing the same job.
                site = (p.get('Identifier', ''),
                        capability(p.get('Comment', '')).casefold())
                caps[('patch', site, p.get('Comment', '')[:40])].append(
                    (parse(p.get('MinKernel'), (0, 0, 0)), parse(p.get('MaxKernel'), INF)))
        for k in d['Kernel']['Add']:
            if k.get('Enabled'):
                caps[('kext', k['BundlePath'], '')].append(
                    (parse(k.get('MinKernel'), (0, 0, 0)), parse(k.get('MaxKernel'), INF)))
        # patches on the same site are one capability regardless of comment;
        # the comment is kept only to name it in the report
        bysite = collections.defaultdict(list)
        sitename = {}
        for (kind, site, comment), rs in caps.items():
            bysite[(kind, site)] += rs
            sitename.setdefault((kind, site),
                                site if kind == 'kext' else (capability(comment) or comment))
        for key, rs in bysite.items():
            top = union_ceiling(rs)
            if top != INF:
                # keyed by site, not by display name: two distinct patches can
                # shorten to the same label and must not be counted as one
                gaps[(top, key)].append(f)
                label[key] = sitename[key]

    print(f'  {total} configs. Capabilities that stop being covered above a fixed kernel:\n')
    for (top, key), files in sorted(gaps.items(), key=lambda kv: (kv[0][0], label[kv[0][1]])):
        macos = names.get(top[0], '')
        print(f'  above {fmt(top)}' + (f' (macOS {macos})' if macos else '')
              + f'   {label[key]}   -   {len(files)} configs')
        print(f'      e.g. {files[0]}')
    if not gaps:
        print('  none: every capability is unbounded above')
    return 0


if __name__ == '__main__':
    sys.exit(main())
