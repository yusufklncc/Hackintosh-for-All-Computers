"""update.json: what a release is, for the window's updater.

A release keeps its number while its packages are rebuilt, so the window
cannot tell a newer build from a number. This names the commit the packages
were built from, when, a few lines of what changed, and the SHA-256 of every
file - and the window installs nothing whose hash is not listed here.

    python3 tools/updateinfo.py --tag v1.0.8 --commit <sha> --dist dist \\
        --notes docs/releases/v1.0.8.md
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path


def summary(notes, limit=8):
    """The first sentence of each bullet in the notes, plain text."""
    out = []
    for line in Path(notes).read_text(encoding='utf-8').splitlines():
        if not line.startswith('- '):
            continue
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line[2:])   # links -> their words
        text = text.replace('**', '').replace('`', '')
        first = re.split(r'(?<=[.!?])\s', text, maxsplit=1)[0].strip()
        out.append(first[:160])
        if len(out) == limit:
            break
    return out


def build(tag, commit, dist, notes, now=None):
    files = sorted(p for p in Path(dist).iterdir()
                   if p.is_file() and p.name != 'update.json')
    return {
        'tag': tag,
        'commit': commit,
        'built': (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(),
        'summary': summary(notes) if notes and Path(notes).exists() else [],
        'assets': [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                    'size': p.stat().st_size} for p in files],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--dist', required=True)
    ap.add_argument('--notes')
    a = ap.parse_args(argv)
    doc = build(a.tag, a.commit, a.dist, a.notes)
    (Path(a.dist) / 'update.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(f"  update.json: {a.tag} {a.commit[:7]}, {len(doc['assets'])} files")
    return 0


if __name__ == '__main__':
    sys.exit(main())
