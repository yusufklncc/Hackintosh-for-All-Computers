"""Shared machinery for the profile-based config generator.

A profile is a partial plist tree stored as TOML. Generating a config means
deep-merging Sample.plist from the target OpenCore release with a chain of
profiles. Dicts merge key by key; anything else - including lists - is replaced
wholesale, because an ordered list such as Kernel.Add is a single decision, not
a set of independent ones.

Standard library only.
"""
import datetime
import plistlib
import tomllib

# Written per build by macserial, never stored in a profile.
IDENTITY = (
    'PlatformInfo.Generic.SystemSerialNumber',
    'PlatformInfo.Generic.MLB',
    'PlatformInfo.Generic.SystemUUID',
    'PlatformInfo.Generic.ROM',
)


# --------------------------------------------------------------------------
# TOML cannot hold plist <data> or <date>, so those ride inside tagged strings.

HEX = 'hex:'
DATE = 'date:'


def encode(v):
    if isinstance(v, bytes):
        return HEX + v.hex()
    if isinstance(v, datetime.datetime):
        return DATE + v.isoformat()
    if isinstance(v, dict):
        return {k: encode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [encode(x) for x in v]
    return v


PARAM = _re_param = None  # set below


def expand(v, params):
    """Substitute {name} placeholders in strings using params, e.g. the AMD
    core count that appears as one byte inside a kernel patch."""
    if not params:
        return v
    if isinstance(v, str):
        return v.format(**params) if '{' in v else v
    if isinstance(v, dict):
        return {k: expand(x, params) for k, x in v.items()}
    if isinstance(v, list):
        return [expand(x, params) for x in v]
    return v


def decode(v):
    if isinstance(v, str):
        if v.startswith(HEX):
            return bytes.fromhex(v[len(HEX):])
        if v.startswith(DATE):
            return datetime.datetime.fromisoformat(v[len(DATE):])
        return v
    if isinstance(v, dict):
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v


# --------------------------------------------------------------------------
# Minimal TOML writer. tomllib reads but does not write, and the value space
# here is small enough that a full dependency is not worth it. Every file the
# extractor emits is parsed back and compared before being written.

_BARE = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')


def _key(k):
    return k if k and set(k) <= _BARE else '"' + k.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _scalar(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        s = v.replace('\\', '\\\\').replace('"', '\\"')
        s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{s}"'
    if isinstance(v, list):
        return '[' + ', '.join(_scalar(x) for x in v) + ']'
    raise TypeError(f'cannot serialise {type(v).__name__}: {v!r}')


def _is_table(v):
    return isinstance(v, dict)


def _is_table_array(v):
    return isinstance(v, list) and v and all(isinstance(x, dict) for x in v)


def dumps(tree, header=''):
    """Serialise a dict of scalars, tables and table-arrays, at any depth.

    Table arrays nest: an entry of [[audio]] may itself hold [[audio.layout]].
    The header path is carried down rather than assumed to be one level deep."""
    out = [header] if header else []

    def scalars_of(node):
        return {k: v for k, v in node.items()
                if not _is_table(v) and not _is_table_array(v)}

    def emit(node, path, force_header=False):
        scalars = scalars_of(node)
        head = '.'.join(_key(p) for p in path)
        if path and (scalars or force_header):
            out.append(f'[{head}]')
        for k, v in scalars.items():
            out.append(f'{_key(k)} = {_scalar(v)}')
        if scalars or (path and force_header):
            out.append('')
        for k, v in node.items():
            if _is_table(v):
                emit(v, path + [k], force_header=not v)
            elif _is_table_array(v):
                for entry in v:
                    out.append(f'[[{".".join(_key(p) for p in path + [k])}]]')
                    for ek, ev in scalars_of(entry).items():
                        out.append(f'{_key(ek)} = {_scalar(ev)}')
                    out.append('')
                    for ek, ev in entry.items():
                        if _is_table(ev):
                            emit(ev, path + [k, ek], force_header=not ev)
                        elif _is_table_array(ev):
                            for sub in ev:
                                out.append(f'[[{".".join(_key(p) for p in path + [k, ek])}]]')
                                for sk, sv in scalars_of(sub).items():
                                    out.append(f'{_key(sk)} = {_scalar(sv)}')
                                out.append('')

    emit(tree, [])
    return '\n'.join(out).rstrip() + '\n'


def write_toml(path, tree, header=''):
    """Serialise, parse the result back, and refuse to write if it differs."""
    text = dumps(tree, header)
    if tomllib.loads(text) != tree:
        raise AssertionError(f'TOML round-trip failed for {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def read_toml(path):
    with open(path, 'rb') as fh:
        return tomllib.load(fh)


# --------------------------------------------------------------------------

def merge(base, over):
    """Deep-merge over onto base. Lists and scalars replace; dicts recurse."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = merge(out[k], v) if k in out else v
        return out
    return over


def diff(base, target):
    """Smallest partial tree t such that merge(base, t) == target."""
    if not (isinstance(base, dict) and isinstance(target, dict)):
        return None if base == target else target
    out = {}
    for k, v in target.items():
        if k not in base:
            out[k] = v
        else:
            d = diff(base[k], v)
            if d is not None:
                out[k] = d
    for k in base:
        if k not in target:
            raise ValueError(f'profile layering cannot delete key {k!r}')
    return out or None


def flatten(o, pre=''):
    """{dotted.path: scalar}, array indices included in the path."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f'{pre}{k}.'))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(flatten(v, f'{pre}[{i}].'))
    else:
        out[pre[:-1]] = o
    return out


def prune(o, keep_comments=False, pre=''):
    """Drop generated identity, and Comment strings unless asked to keep them."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            path = f'{pre}{k}'
            if path in IDENTITY:
                continue
            if not keep_comments and k == 'Comment' and isinstance(v, str):
                continue
            out[k] = prune(v, keep_comments, f'{path}.')
        return out
    if isinstance(o, list):
        return [prune(v, keep_comments, pre) for v in o]
    return o


def canonical_bytes(plist, keep_comments=False):
    """Serialise to XML with dict keys sorted, so two trees compare byte for byte.

    Comparing decoded Python values is not enough: True == 1 == 1.0 in Python
    while <true/>, <integer>1</integer> and <real>1</real> are three different
    things to OpenCore, and an empty <array/> is not the same as a missing key.
    Round-tripping through plistlib makes every one of those differences visible
    in the bytes."""
    return plistlib.dumps(prune(plist, keep_comments), fmt=plistlib.FMT_XML,
                          sort_keys=True)


def typed_flatten(o, pre=''):
    """flatten(), but each value carries its type so True and 1 do not collide."""
    return {k: (type(v).__name__, v) for k, v in flatten(o).items()}


def comparable(plist, keep_comments=False):
    """Typed key/value view. Used to report *where* two trees differ; the gate
    itself compares canonical_bytes()."""
    return typed_flatten(prune(plist, keep_comments))


def load_plist(path):
    with open(path, 'rb') as fh:
        return plistlib.load(fh)


# --------------------------------------------------------------------------
# Where a config sits in the layer hierarchy, derived from its path and name.

import os as _os
import re as _re

# The tree this once pointed at is gone; the prefix survives as the naming
# scheme for catalogue entries, which is what resolves per-config residuals.
CONFIG_ROOT = 'EFI/OC/config'
OEM_DIRS = {'HP', 'ASUS', 'MSI', 'DELL', 'SONY', 'DELL - SONY'}
VARIANT_DIRS = {'BIOS (v3006+)'}

# Free-form user data, not schema: a profile owns the whole map, so Sample's own
# entries must not survive into the merge.
EMPTY_MAPS = [('DeviceProperties', 'Add'), ('DeviceProperties', 'Delete'),
              ('NVRAM', 'Add'), ('NVRAM', 'Delete'), ('NVRAM', 'LegacySchema')]


def slug(s):
    return _re.sub(r'[^a-z0-9]+', '-', s.lower().replace('ve ', '').replace('_', '-')).strip('-')


def classify(path):
    parts = _os.path.relpath(path, CONFIG_ROOT).split(_os.sep)
    name, dirs = parts[-1][:-6], parts[:-1]
    platform = dirs[0].lower()
    vendor, i = (dirs[1].lower(), 2) if platform == 'desktop' else (None, 1)
    oem = chipset = variant = None
    for d in dirs[i:]:
        if d in OEM_DIRS:       oem = slug(d)
        elif d in VARIANT_DIRS: variant = slug(d)
        else:                   chipset = slug(d)
    m = _re.match(r'^(\d+)\s*-\s*(?:Desktop|Laptop)\s*-\s*(.+)$', name)
    desc, cores = m.group(2), None
    mc = _re.search(r'\s(\d+)\s+Core$', desc)
    if mc:
        cores, desc = int(mc.group(1)), desc[:mc.start()]
    return dict(path=path, platform=platform, vendor=vendor, cpu=slug(desc),
                chipset=chipset, oem=oem, variant=variant, cores=cores)


def platform_name(row):
    return f"{row['platform']}-{row['vendor']}" if row['vendor'] else row['platform']


def build_params(row):
    return {'cores': row['cores']} if row['cores'] else {}


OVERLAY_ORDER = ('chipset', 'oem', 'variant')


def overlay_tag(row):
    act = [(t, row[t]) for t in OVERLAY_ORDER if row[t]]
    return '+'.join(f'{t}.{n}' for t, n in act) if act else None


def exception_name(row):
    return slug(_os.path.relpath(row['path'], CONFIG_ROOT)[:-6])


def layer_chain(row, profiles):
    """Ordered profile files for one config.

    Single-axis overlays compose: chipset first (what the board needs), then oem
    (vendor firmware workarounds), so a vendor quirk wins over a board default.
    A combo or per-config file may follow, carrying only what composition did not
    already produce."""
    chain = [profiles / 'base.toml',
             profiles / 'platform' / f'{platform_name(row)}.toml',
             profiles / 'cpu' / platform_name(row) / f"{row['cpu']}.toml"]
    if row['cores']:
        chain.append(profiles / 'cpu' / platform_name(row) /
                     f"{row['cpu']}.{row['cores']}core.toml")
    for axis in OVERLAY_ORDER:
        if row[axis]:
            chain.append(profiles / 'overlay' / f'{axis}.{row[axis]}.toml')
    tag = overlay_tag(row)
    if tag:
        chain.append(profiles / 'overlay' / 'combo' / f'{tag}.toml')
        # a per-config residual belongs to one file in EFI/OC/config; a build
        # from bare coordinates has no such file and therefore no residual
        if row.get('path'):
            chain.append(profiles / 'config' / f'{exception_name(row)}.toml')
    return [p for p in chain if p.exists()]


def prepare_sample(sample):
    """Strip Sample.plist documentation keys and blank the free-form maps."""
    s = {k: v for k, v in sample.items() if not k.startswith('#WARNING')}
    for sect, key in EMPTY_MAPS:
        if sect in s and key in s[sect]:
            s[sect] = dict(s[sect])
            s[sect][key] = {}
    return s


def strip_identity(tree):
    t = {k: (dict(v) if isinstance(v, dict) else v) for k, v in tree.items()}
    gen = t.get('PlatformInfo', {}).get('Generic')
    if gen:
        t['PlatformInfo'] = dict(t['PlatformInfo'])
        t['PlatformInfo']['Generic'] = {k: v for k, v in gen.items()
                                        if f'PlatformInfo.Generic.{k}' not in IDENTITY}
    return t


def assemble(sample, chain, params=None):
    """Sample.plist + every profile in the chain, with {placeholders} expanded."""
    tree = strip_identity(prepare_sample(sample))
    for p in chain:
        tree = merge(tree, decode(expand(read_toml(p), params or {})))
    return tree


VENDOR_OC = 'vendor/opencore'


def vendored_versions():
    import pathlib
    return sorted(p.name for p in pathlib.Path(VENDOR_OC).glob('*')
                  if (p / 'Sample.plist').exists())


def vendored_tool(name, version=None):
    """ocvalidate / macserial for the host platform, from the vendored release.

    Returns None when the binary is absent or does not match the host, in which
    case the caller degrades instead of failing: both tools improve a build
    rather than being required for one."""
    import pathlib, platform
    suffix = {'Darwin': '', 'Linux': '.linux', 'Windows': '.exe'}.get(platform.system())
    if suffix is None:
        return None
    versions = [version] if version else list(reversed(vendored_versions()))
    for v in versions:
        p = pathlib.Path(VENDOR_OC) / v / 'Utilities' / name / (name + suffix)
        if p.exists():
            return p
    return None


def vendored_sample(version=None):
    """Path to a Sample.plist shipped in the repository.

    Keeping it vendored is what lets extract/verify/build run on a fresh clone
    with no network. It is 51 KB; the ocvalidate and macserial binaries are not
    vendored because they are 4 MB per OpenCore version and only improve a build
    rather than being required for one."""
    import pathlib
    root = pathlib.Path('vendor/opencore')
    if version:
        p = root / version / 'Sample.plist'
        return p if p.exists() else None
    found = sorted(root.glob('*/Sample.plist'))
    return found[-1] if found else None


SUPPORT = 'support.toml'


def _ver(v):
    return tuple(int(x) for x in v.split('.')) if v else ()


def support_range(profiles, key):
    """(oc_min, oc_max, tested) for a profile, from profiles/support.toml.

    Kept in its own file because extract.py rewrites every profile it generates,
    and a tested version range is knowledge that must outlive regeneration."""
    p = profiles / SUPPORT
    if not p.exists():
        return '', '', []
    d = read_toml(p)
    e = {**d.get('default', {}), **d.get('profile', {}).get(key, {})}
    return e.get('oc_min', ''), e.get('oc_max', ''), e.get('tested', [])


def version_supported(version, oc_min, oc_max):
    v = _ver(version)
    if oc_min and v < _ver(oc_min):
        return f'below the tested minimum {oc_min}'
    if oc_max and v > _ver(oc_max):
        return f'above the tested maximum {oc_max}'
    return ''
