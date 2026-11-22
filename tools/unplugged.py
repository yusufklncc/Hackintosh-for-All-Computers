"""corpnewt's UnPlugged.command, fetched rather than shipped.

UnPlugged is a script run in the recovery environment: it builds
`Install macOS.app` from the InstallAssistant.pkg on the stick and starts it,
so the install never needs the network. Its repository states no licence, and
code with no licence is not ours to redistribute, so it is not in this
repository or in any package made from it. The builder downloads it from
corpnewt's GitHub at the commit recorded in data/unplugged.toml and refuses a
file whose hash is not the one recorded - so what lands on a stick is exactly
the script that was read, and it reaches the person from its author.

A licence has been asked for (corpnewt/UnPlugged#17). If one arrives, this can
become an ordinary vendored tool.

    python3 tools/unplugged.py --out /Volumes/UNPLUGGED
"""
import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen  # noqa: E402

TABLE = Path('data/unplugged.toml')
NAME = 'UnPlugged.command'


def pin():
    return ocgen.read_toml(TABLE)['script']


def url(p=None):
    p = p or pin()
    return f"https://raw.githubusercontent.com/{p['upstream']}/{p['commit']}/{NAME}"


def _get(address):
    req = urllib.request.Request(address, headers={'User-Agent': 'hackintosh-unplugged'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch(into, get=_get):
    """Write UnPlugged.command into <into>. Returns (path, complaint)."""
    p = pin()
    try:
        data = get(url(p))
    except OSError as exc:
        return None, f'{NAME} could not be downloaded from {p["upstream"]}: {exc}'
    got = hashlib.sha256(data).hexdigest()
    if got != p['sha256']:
        return None, (f'{NAME} from {p["upstream"]} is not the file that was checked '
                      f'(expected {p["sha256"][:12]}, got {got[:12]}); nothing written')
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    target = into / NAME
    target.write_bytes(data)
    try:
        target.chmod(0o755)   # ExFAT keeps no mode; the recovery steps say `bash` too
    except OSError:
        pass
    return target, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='.')
    a = ap.parse_args(argv)
    path, complaint = fetch(a.out)
    print(f'  {complaint}' if complaint else f'  {path}')
    return 1 if complaint else 0


if __name__ == '__main__':
    sys.exit(main())
