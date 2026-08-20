"""Build data/audio.toml from AppleALC's own codec resources.

Which layout-id a codec needs is not a fact anyone can look up: AppleALC ships
a set of layouts per codec, each contributed for a particular machine, and the
right one is found by trying. So this table records the whole set, with the
comment naming the machine each was made for - which turns "try these numbers"
into "try the one from a Lenovo first, you have a Lenovo".

Every field comes from AppleALC's Resources/<CODEC>/Info.plist, so a codec's
CodecID, its vendor and its layout list are the project's own.

    python3 tools/audiotable.py --out data/audio.toml          # fetch the latest release
    python3 tools/audiotable.py --from <checkout>              # use a tree you have
"""
import argparse
import glob
import io
import json
import os
import plistlib
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

# CodecID is the full HDA id: vendor in the top 16 bits, device in the low 16.
VENDOR_IDS = {'realtek': '10ec', 'idt': '111d', 'conexant': '14f1',
              'analogdevices': '11d4', 'via': '1106', 'cirruslogic': '1013',
              'sigmatel': '8384', 'cmedia': '13f6', 'creative': '1102'}


REPO = 'acidanthera/AppleALC'


def latest_ref():
    with urllib.request.urlopen(f'https://api.github.com/repos/{REPO}/releases/latest') as r:
        return json.load(r)['tag_name']


def fetch(ref, dest):
    """Unpack the source archive for a tag. Pinning to a release rather than
    master means the table records a version somebody can go and look at."""
    url = f'https://codeload.github.com/{REPO}/tar.gz/refs/tags/{ref}'
    with urllib.request.urlopen(url) as r:
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = [m for m in tar.getmembers() if '/Resources/' in m.name
                   and m.name.endswith('Info.plist')]
        tar.extractall(dest, members=members, filter='data')
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='checkout', help='an AppleALC source tree to read instead')
    ap.add_argument('--ref', help='release tag to fetch (default: latest)')
    ap.add_argument('--out', default='data/audio.toml')
    a = ap.parse_args()

    tmp = None
    if a.checkout:
        root, ref = a.checkout, a.ref or 'a local tree'
    else:
        ref = a.ref or latest_ref()
        tmp = tempfile.TemporaryDirectory()
        root = fetch(ref, tmp.name)

    codecs = []
    for info in sorted(glob.glob(f'{root}/**/Resources/*/Info.plist', recursive=True)):
        with open(info, 'rb') as fh:
            d = plistlib.load(fh)
        name, cid = d.get('CodecName'), d.get('CodecID')
        if not name or cid is None:
            continue
        vendor = d.get('Vendor', '')
        # A CodecID under 0x10000 is the device half only; the vendor name then
        # supplies the other half, which is how AppleALC itself stores them.
        if cid > 0xffff:
            hda = f'{cid >> 16:04x}:{cid & 0xffff:04x}'
        else:
            vid = VENDOR_IDS.get(vendor.replace(' ', '').lower())
            hda = f'{vid}:{cid:04x}' if vid else ''
        layouts = []
        for layout in d.get('Files', {}).get('Layouts', []):
            try:
                lid = int(layout.get('Id'))
            except (TypeError, ValueError):
                continue
            e = {'id': lid}
            note = layout.get('Comment') or layout.get('comment')
            if note:
                e['note'] = note
            layouts.append(e)
        if not layouts:
            continue
        layouts.sort(key=lambda x: x['id'])
        codecs.append({'codec': name, 'vendor': vendor, 'hda_id': hda,
                       'codec_id': cid, 'layout': layouts})

    if len(codecs) < 80:
        sys.exit(f'only found {len(codecs)} codecs; is that an AppleALC tree?')
    ocgen.write_toml(Path(a.out), {'source': {'project': REPO, 'ref': ref},
                                   'audio': codecs},
                     '# Audio codecs and the layout-ids AppleALC ships for each.\n'
                     '#\n'
                     '# Read from AppleALC\'s own Resources/<CODEC>/Info.plist by\n'
                     '# tools/audiotable.py. A codec usually has several layouts, each\n'
                     '# contributed for a particular machine and named as such - the right\n'
                     '# one is found by trying, so the whole set is kept rather than a guess.\n'
                     '#\n'
                     '# The ref below is the release it was read from, so a regenerated\n'
                     '# table shows both the version bump and what it changed.')
    if tmp:
        tmp.cleanup()
    total = sum(len(c['layout']) for c in codecs)
    named = sum(1 for c in codecs for l in c['layout'] if l.get('note'))
    print(f'  {REPO} {ref}: {len(codecs)} codecs, {total} layouts, '
          f'{named} of them naming a machine')
    print(f'  with an hda id: {sum(1 for c in codecs if c["hda_id"])}')
    for c in codecs[:3]:
        print(f'      {c["codec"]:10s} {c["hda_id"] or "-":10s} {len(c["layout"])} layouts')


if __name__ == '__main__':
    main()
