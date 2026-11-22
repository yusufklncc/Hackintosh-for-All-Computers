"""Keep data/gpudriver.toml in step with the drivers it quotes.

The table says which cards a third-party driver runs, and both halves move
upstream: intel-gpu-macos-driver adds ids to its rule file as it matches new
cards, and NullMoth could narrow or widen the sentence the NVIDIA row is built
on. Either change is a change in what people are told about their card, so the
weekly refresh runs this and the pull request it opens is the diff.

    python3 tools/gpudrivers.py              # report drift, change nothing
    python3 tools/gpudrivers.py --refresh    # record the new commits and ids

What it will not do is write a card or a sentence. A newly matched Arc id is
reported and left for a person: "matched" and "runs" are different claims, and
only the driver's own documentation can say which one applies. It records a new
commit only where nothing this table says has changed.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

TABLE = Path('data/gpudriver.toml')
API = 'https://api.github.com/repos/{repo}/commits/{ref}'
RAW = 'https://raw.githubusercontent.com/{repo}/{sha}/{path}'


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'hackintosh-gpudrivers'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')


def _repo(url):
    return url.rstrip('/').split('github.com/')[1]


def head(repo):
    return json.loads(_get(API.format(repo=repo, ref='HEAD')))['sha']


def check(fetch=_get, newest=head):
    """[(driver, what changed)] against each driver's current main."""
    table = ocgen.read_toml(TABLE)
    out = []
    for d in table['driver']:
        repo = _repo(d['url'])
        sha = newest(repo)
        text = fetch(RAW.format(repo=repo, sha=sha, path=d['source']))
        if d.get('card'):
            ids = {f"{json.loads(text)['cards']['vendor_id']}:{i}".lower()
                   for i in json.loads(text)['cards']['device_ids']}
            have = {c['id'].lower() for c in d['card']}
            for added in sorted(ids - have):
                out.append((d['name'], f'now matches {added}', sha, added))
            for gone in sorted(have - ids):
                out.append((d['name'], f'no longer matches {gone}', sha, gone))
        if d.get('quote'):
            flat = re.sub(r'\s+', ' ', text)
            if d['quote'] not in flat:
                out.append((d['name'], 'the quoted sentence is no longer on its page', sha, None))
        if not out or out[-1][0] != d['name']:
            if sha != d['commit']:
                out.append((d['name'], f'moved to {sha[:12]} with nothing that matters here changed', sha, None))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--refresh', action='store_true',
                    help='write the new commits and any newly matched ids')
    a = ap.parse_args(argv)

    found = check()
    if not found:
        print('  every driver row matches its source')
        return 0
    for name, what, _, _ in found:
        print(f'  {name}: {what}')
    if not a.refresh:
        return 1

    text = TABLE.read_text(encoding='utf-8')
    for name, what, sha, ident in found:
        if what.startswith(('the quoted sentence', 'now matches', 'no longer matches')):
            # A sentence is not something to rewrite by machine, and neither is
            # a card: its name, and whether it has run, are the driver's own
            # documentation's to say. Appending a row was also wrong in a
            # simpler way - a [[driver.card]] at the end of the file belongs to
            # whichever driver is last, which is the wrong one.
            print(f'  {name}: left for a person - {what}')
    for name, what, sha, _ in found:
        if not what.startswith('moved to'):
            continue
        block = text.split(f'name = "{name}"', 1)
        if len(block) == 2:
            block[1] = re.sub(r'commit = "[0-9a-f]{40}"', f'commit = "{sha}"', block[1], count=1)
            text = f'name = "{name}"'.join(block)
    TABLE.write_text(text, encoding='utf-8')
    print(f'  wrote {TABLE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
