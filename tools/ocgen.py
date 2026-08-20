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
    out = [header] if header else []

    def emit(node, path):
        scalars = {k: v for k, v in node.items() if not _is_table(v) and not _is_table_array(v)}
        if scalars:
            if path:
                out.append(f'[{".".join(_key(p) for p in path)}]')
            for k, v in scalars.items():
                out.append(f'{_key(k)} = {_scalar(v)}')
            out.append('')
        for k, v in node.items():
            if _is_table(v):
                if not v:
                    out.append(f'[{".".join(_key(p) for p in path + [k])}]')
                    out.append('')
                else:
                    emit(v, path + [k])
            elif _is_table_array(v):
                for entry in v:
                    out.append(f'[[{".".join(_key(p) for p in path + [k])}]]')
                    for ek, ev in entry.items():
                        out.append(f'{_key(ek)} = {_scalar(ev)}')
                    out.append('')

    # a table with only sub-tables must still print its own header first
    if any(not _is_table(v) and not _is_table_array(v) for v in tree.values()):
        emit(tree, [])
    else:
        for k, v in tree.items():
            if _is_table(v):
                emit(v, [k]) if v else out.extend([f'[{_key(k)}]', ''])
            elif _is_table_array(v):
                for entry in v:
                    out.append(f'[[{_key(k)}]]')
                    for ek, ev in entry.items():
                        out.append(f'{_key(ek)} = {_scalar(ev)}')
                    out.append('')
            else:
                out.append(f'{_key(k)} = {_scalar(v)}')
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


def comparable(plist, keep_comments=False):
    """Key/value view used by the equivalence gate: generated identity dropped,
    Comment strings dropped unless explicitly requested."""
    return {
        k: v for k, v in flatten(plist).items()
        if k not in IDENTITY and (keep_comments or not k.endswith('.Comment'))
    }


def load_plist(path):
    with open(path, 'rb') as fh:
        return plistlib.load(fh)


# --------------------------------------------------------------------------
# Where a config sits in the layer hierarchy, derived from its path and name.

import os as _os
import re as _re

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


def cpu_name(row):
    return row['cpu'] + (f"-{row['cores']}core" if row['cores'] else '')


def overlay_tag(row):
    act = [(t, row[t]) for t in ('oem', 'chipset', 'variant') if row[t]]
    return '+'.join(f'{t}.{n}' for t, n in act) if act else None


def exception_name(row):
    return slug(_os.path.relpath(row['path'], CONFIG_ROOT)[:-6])


def layer_chain(row, profiles):
    """Ordered profile files for one config. Missing optional layers are skipped;
    a per-config exception file replaces the shared overlay when present."""
    chain = [profiles / 'base.toml',
             profiles / 'platform' / f'{platform_name(row)}.toml',
             profiles / 'cpu' / platform_name(row) / f'{cpu_name(row)}.toml']
    tag = overlay_tag(row)
    if tag:
        exc = profiles / 'config' / f'{exception_name(row)}.toml'
        chain.append(exc if exc.exists()
                     else profiles / 'overlay' / (tag.replace('+', '/') + '.toml'))
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


def assemble(sample, chain):
    """Sample.plist + every profile in the chain."""
    tree = strip_identity(prepare_sample(sample))
    for p in chain:
        tree = merge(tree, decode(read_toml(p)))
    return tree
