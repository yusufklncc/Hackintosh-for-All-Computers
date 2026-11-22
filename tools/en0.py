"""Is en0 built-in, and if not, where does built-in = 01 go.

Dortania's iServices page, quoted in data/iservices.toml: check whether en0 is
marked built-in, and only if it is not, add `built-in` under its PciRoot path.
Both halves need macOS running on the machine - IOBuiltin is something macOS
decides at boot - so this reads ioreg and answers nothing anywhere else.

The path is read off the registry, not guessed: the PCI devices between the
root bridge and en0, each `name@dev,func`, which is what gfxutil and Hackintool
print. Anything that does not read cleanly declines with the reason instead of
writing a path - a built-in on the wrong device fixes nothing and looks as
though it did:

  * en0 behind USB: the nearest PCI device is the USB controller
  * a root bridge with no _UID to number PciRoot by
  * a PCI device in the chain with no location

    python3 tools/en0.py        # what this machine says
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sysenv  # noqa: F401,E402  ioreg is in /usr/sbin
import ocgen  # noqa: E402

TABLE = Path('data/iservices.toml')

NODE = re.compile(r'^(?P<indent>[ |]*)\+-o (?P<name>\S+)\s+<class (?P<cls>[^,>]+)')
PROP = re.compile(r'^[ |]*"(?P<key>[^"]+)" = (?P<value>.*)$')


def rules():
    return ocgen.read_toml(TABLE)


def chain(text):
    """[(name, class, {property: raw value})] from Root down to the last node.

    `ioreg -t -r -n en0 -d 1` prints the ancestors of en0 one level deeper each
    time, and properties only for en0 itself; -t is what puts the ancestors in."""
    nodes = []
    for line in text.splitlines():
        m = NODE.match(line)
        if m:
            nodes.append((m['name'], m['cls'].strip(), {}))
            continue
        p = PROP.match(line)
        if p and nodes:
            nodes[-1][2][p['key']] = p['value'].strip()
    return nodes


def _pci(location):
    """`1f,6` -> Pci(0x1f,0x6); `1c` -> Pci(0x1c,0x0)."""
    dev, _, func = location.partition(',')
    try:
        return f'Pci(0x{int(dev, 16):x},0x{int(func or "0", 16):x})'
    except ValueError:
        return None


def path_of(nodes, uid_of):
    """(PciRoot path, None) or (None, why not) for the PCI device under en0.

    uid_of(name) answers the root bridge's _UID, or None."""
    if not nodes:
        return None, 'ioreg printed nothing for en0'
    above = nodes[:-1]
    pci = [i for i, (_, cls, _) in enumerate(above) if cls == 'IOPCIDevice']
    if not pci:
        return None, 'en0 is not on a PCI device'
    # what sits between en0 and its PCI device: a USB adapter hangs off the
    # USB controller, and that is the device a naive walk would mark
    between = above[pci[-1] + 1:]
    if any('USB' in cls for _, cls, _ in between):
        return None, 'en0 is a USB adapter; built-in on the USB controller would be the wrong device'
    roots = [name for name, cls, _ in above[:pci[0]] if cls == 'IOACPIPlatformDevice']
    if not roots:
        # Apple silicon, for one: its PCIe hangs off arm-io, not ACPI
        return None, 'no ACPI root bridge above en0, so there is no PciRoot to name'
    root = roots[-1]
    uid = uid_of(root.split('@')[0])
    if uid is None:
        return None, f'{root} reports no _UID to number PciRoot by'
    parts = [f'PciRoot(0x{uid:x})']
    for i in pci:
        name = above[i][0]
        if '@' not in name:
            return None, f'{name} has no location in the registry'
        piece = _pci(name.split('@', 1)[1])
        if not piece:
            return None, f'{name}: location does not read as dev,func'
        parts.append(piece)
    return '/'.join(parts), None


def _uid_from(text):
    m = re.search(r'"_UID" = "?(\w+)"?', text)
    if not m:
        return None
    raw = m.group(1)
    try:
        return int(raw, 16) if raw.lower().startswith('0x') else int(raw)
    except ValueError:
        return None


def read(run=None):
    """{'builtin': bool, 'path': str|None, 'why': str|None}, or None.

    None means there was no en0 to ask about, which is not the same as en0 not
    being built-in: the first says nothing, the second is the case to fix."""
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True,
                                             timeout=20).stdout)
    try:
        text = run(['ioreg', '-t', '-r', '-n', 'en0', '-d', '1'])
    except Exception:
        return None
    nodes = chain(text or '')
    if not nodes or nodes[-1][0] != 'en0':
        return None
    flag = nodes[-1][2].get('IOBuiltin')
    if flag not in ('Yes', 'No'):
        return None
    if flag == 'Yes':
        return {'builtin': True, 'path': None, 'why': None}

    def uid_of(name):
        try:
            return _uid_from(run(['ioreg', '-r', '-n', name, '-d', '1']) or '')
        except Exception:
            return None
    path, why = path_of(nodes, uid_of)
    return {'builtin': False, 'path': path, 'why': why}


def advice(state):
    """(lines, device properties) for one en0 reading. Nothing when all is well."""
    if not state or state.get('builtin') is not False:
        return [], {}
    r = rules()
    lines = [f'en0 is not marked built-in, so Messages, FaceTime and the App Store '
             f'may refuse to sign in. Dortania: "{r["fix"]}"']
    if state.get('path'):
        lines.append(f'built-in = 01 goes in under {state["path"]}')
        return lines, {state['path']: {'built-in': 'hex:01'}}
    lines.append(f'Nothing written: {state.get("why") or "the path could not be read"}. '
                 f'The steps are at {r["page"]}')
    return lines, {}


if __name__ == '__main__':
    s = read()
    if s is None:
        print('  no en0 here to ask about')
    elif s['builtin']:
        print('  en0 is built-in; nothing to do')
    else:
        print('\n'.join(f'  {x}' for x in advice(s)[0]))
