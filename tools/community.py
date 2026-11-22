"""The community registry: data/community.toml, read, matched and kept current.

Drivers and add-ons arrive faster than any one table can follow - a Realtek
Wi-Fi driver, AirDrop on it, an RDNA 4 driver, Xe3 graphics, a P-core tweak.
They are somebody else's work, usually experimental by their own account, and
this repository's job is to say that they exist, what they cover in their own
words, and nothing more - until somebody has run one.

    python3 tools/community.py                  # what is recorded, by stage
    python3 tools/community.py --machine r.json # what applies to that machine
    python3 tools/community.py --check          # what moved upstream (network)
    python3 tools/community.py --refresh        # record what moved, by machine
    python3 tools/community.py --discover       # projects not recorded yet

--refresh writes only derived fields - the release, its hash, the ids the kext
declares, the licence GitHub reads - and only where the quoted sentences are
still on the project's page. A changed sentence is reported and left for a
person, because it is a change in what people are told. --discover adds
nothing either: it lists candidates for a person to decide on.
"""
import argparse
import hashlib
import io
import json
import os
import plistlib
import re
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen  # noqa: E402

TABLE = Path('data/community.toml')
SHOWN = ('experimental', 'recommended')
API = 'https://api.github.com/repos/{repo}'
RAW = 'https://raw.githubusercontent.com/{repo}/{sha}/{path}'


# --- reading -----------------------------------------------------------------

def projects():
    if not TABLE.exists():
        return []
    return ocgen.read_toml(TABLE).get('project', [])


def shown():
    """The ones a person is told about: experimental and recommended."""
    return [p for p in projects() if p.get('stage') in SHOWN]


def candidates():
    """Driver projects recorded and not shown - the old candidates table."""
    return [p for p in projects() if p.get('stage') == 'watching'
            and p.get('kind') == 'device']


def graphics():
    """The graphics drivers, in the shape gpu.py reads."""
    return [p for p in shown() if p.get('role') == 'graphics']


def by_device(ident):
    """(project, card row or None) for a device id a shown driver names."""
    ident = (ident or '').lower()
    if not ident:
        return None
    for p in shown():
        if p.get('kind') != 'device':
            continue
        for card in p.get('card', []):
            if card['id'].lower() == ident:
                return p, card
        if ident in [i.lower() for i in p.get('ids', [])]:
            return p, None
    return None


def devices_for(ids):
    """[(project, card, id)] for every id of a machine a shown driver names.

    Every project, not the first: two drivers for one card - AirPort_RTW89 and
    RTLAirLink both claim the RTL8852BE - are two choices, and a person should
    see both rather than whichever this file happens to list first."""
    out, seen = [], set()
    for ident in ids or []:
        ident = ident.lower()
        for p in shown():
            if p.get('kind') != 'device' or (p['name'], ident) in seen:
                continue
            card = next((c for c in p.get('card', []) if c['id'].lower() == ident), None)
            if card is not None or ident in [i.lower() for i in p.get('ids', [])]:
                seen.add((p['name'], ident))
                out.append((p, card, ident))
    return out


def features_for(hw, matched=()):
    """Add-ons whose stated requirement this machine meets.

    A CPU generation for a CPU add-on, a Bluetooth controller from a named
    vendor for a Bluetooth one. What it says it needs, not more."""
    hw = hw or {}
    gen = hw.get('generation') or ''
    usb = [u.lower() for u in hw.get('usb_ids', [])]
    pci = [i.lower() for i in hw.get('pci_ids', [])]
    out = []
    for p in shown():
        if p.get('kind') != 'feature':
            continue
        if p.get('requires_cpu') and gen in p['requires_cpu']:
            out.append(p)
        elif p.get('requires_role') == 'bluetooth' and any(
                i.split(':')[0] in p.get('requires_vendor', []) for i in usb):
            # a Bluetooth controller is a USB device; its vendor is the claim
            out.append(p)
    return out


def line(p, card=None):
    """One sentence for a front end: what it is, how far, in whose words."""
    tested = ''
    if card is not None and 'tested' in card:
        tested = ', run on this card' if card['tested'] else ', not yet run on this card'
    where = ('Installed after macOS boots' if p.get('install') == 'system'
             else 'A kext for the EFI, offered and never added unasked')
    said = (p.get('macos') or '').strip().rstrip('.')
    return f"{p['name']} ({p['stage']}{tested}) - {said}. {where}. {p['repo']}"


def for_machine(hw):
    """Everything in the registry that applies to one machine, shown ones only."""
    ids = list((hw or {}).get('pci_ids', [])) + list((hw or {}).get('usb_ids', []))
    for d in (hw or {}).get('gpu_devices', []) or []:
        if d.get('id'):
            ids.append(d['id'])
    devices = devices_for(ids)
    return devices, features_for(hw, [p['name'] for p, _, _ in devices])


# --- upstream ----------------------------------------------------------------

def _get(url, accept=None):
    headers = {'User-Agent': 'hackintosh-community'}
    if accept:
        headers['Accept'] = accept
    token = os.environ.get('GITHUB_TOKEN')
    if token and 'api.github.com' in url:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def kext_ids(blob):
    """The device ids every kext in a release zip declares, from its Info.plist."""
    import hwtable
    ids = set()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(tmp)
        for info in Path(tmp).rglob('Contents/Info.plist'):
            if not info.parent.parent.name.endswith('.kext') or '__MACOSX' in str(info):
                continue
            with open(info, 'rb') as fh:
                plist = plistlib.load(fh)
            for per in (plist.get('IOKitPersonalities') or {}).values():
                ids |= hwtable.pci_ids(per.get('IOPCIPrimaryMatch', ''))
                ids |= hwtable.pci_ids(per.get('IOPCIMatch', ''))
                ids |= hwtable.name_ids(per.get('IONameMatch'))
                v, d = per.get('idVendor'), per.get('idProduct')
                if isinstance(v, int) and isinstance(d, int):
                    ids.add(f'{v:04x}:{d:04x}')
    # a vendor-wide mask matches a whole vendor's class of devices and names
    # none of them; it is not an id list, and reading it as one would claim
    # every Intel display device for whatever kext carries it
    return sorted(i for i in ids if not i.endswith(':ffff') and ':' in i)


def _flat(text):
    return re.sub(r'\s+', ' ', text)


def check(p, get=_get):
    """[(what changed, derived update or None)] for one project, against upstream."""
    out = []
    repo = p['repo']
    info = json.loads(get(API.format(repo=repo)))
    if info.get('archived') and not p.get('archived'):
        out.append(('the repository is archived now', {'archived': True}))
    lic = ((info.get('license') or {}).get('spdx_id')) or 'none stated'
    # NOASSERTION is GitHub saying it could not tell; the licence recorded was
    # then read from the file by a person, and GitHub has nothing to add
    if lic != 'NOASSERTION' and lic != p.get('licence'):
        out.append((f'licence reads {lic} now', {'licence': lic}))
    head = json.loads(get(API.format(repo=repo) + '/commits/HEAD'))['sha']
    if p.get('source') and (p.get('quote') or p.get('macos')):
        page = _flat(get(RAW.format(repo=repo, sha=head, path=p['source'])).decode('utf-8', 'replace'))
        # only what is recorded as the project's own words: the two GPU drivers
        # carried over keep a summary in `macos`, and a summary is never on
        # the page it summarises
        for key in p.get('quoted', ['quote']):
            if p.get(key) and p[key] not in page:
                out.append((f'the {key} sentence is no longer on {p["source"]}', None))
    if p.get('ids_from') == 'rules' and p.get('card'):
        # the driver's own rule file: the ids its EFI tool and kext act on
        rules = json.loads(get(RAW.format(repo=repo, sha=head, path=p['source'])))
        ids = {f"{rules['cards']['vendor_id']}:{i}".lower() for i in rules['cards']['device_ids']}
        have = {c['id'].lower() for c in p['card']}
        for added in sorted(ids - have):
            out.append((f'now matches {added}', None))
        for gone in sorted(have - ids):
            out.append((f'no longer matches {gone}', None))
    if p.get('release') is not None and p.get('ids_from') in ('kext', 'quoted', None) \
            and not p.get('unreleased'):
        try:
            rel = json.loads(get(API.format(repo=repo) + '/releases?per_page=1'))
        except urllib.error.HTTPError:
            rel = []
        if rel and rel[0].get('tag_name') != p.get('release'):
            tag = rel[0]['tag_name']
            update = {'release': tag}
            zips = [a for a in rel[0].get('assets', []) if a['name'].lower().endswith('.zip')
                    and 'debug' not in a['name'].lower() and 'source' not in a['name'].lower()
                    and 'tools' not in a['name'].lower()]
            if zips:
                blob = get(zips[0]['browser_download_url'])
                update.update(asset=zips[0]['name'], sha256=hashlib.sha256(blob).hexdigest())
                if p.get('ids_from') == 'kext':
                    update['ids'] = kext_ids(blob)
            out.append((f'released {tag}', update))
    if not out and head != p.get('commit') and p.get('commit'):
        out.append((f'moved to {head[:12]}, nothing recorded here changed', {'commit': head}))
    return out


def refresh(rows, get=_get, say=print):
    """Apply the derived updates. Returns (rows, changed, left for a person)."""
    changed, left = 0, []
    for p in rows:
        try:
            found = check(p, get=get)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            say(f'  {p["name"]}: could not be read ({exc})')
            continue
        quotes_moved = any(u is None for _, u in found)
        for what, update in found:
            say(f'  {p["name"]}: {what}')
            if update is None:
                left.append((p['name'], what))
            elif not quotes_moved:
                p.update(update)
                changed += 1
        if quotes_moved:
            say(f'  {p["name"]}: left for a person - what it says has changed')
    return rows, changed, left


# --- discovery ---------------------------------------------------------------

SEARCH = ('https://api.github.com/search/repositories?q={q}'
          '&sort=updated&order=desc&per_page=50')
FLAIRS = ('release', 'dev', 'info/guide', 'success')
KEXTISH = re.compile(r'\b(kext|driver|airdrop|handoff|wi-?fi|bluetooth|igpu|gpu|rdna|xe\d?)\b', re.I)
DRIVERISH = re.compile(r'\b(kext|driver|lilu plugin|plugin|airdrop|handoff|awdl)\b', re.I)
NOT_A_DRIVER = re.compile(r'\bEFI\b|efi[-_ ]|config|guide|hotpatch|installer iso|'
                          r'kext-free|apple silicon|driverkit|windows|'
                          r'\b(thinkpad|latitude|probook|zenbook|legion|vivobook|'
                          r'optiplex|elitebook|esprimo)\b', re.I)
REPO_LINK = re.compile(r'github\.com/([\w.-]+/[\w.-]+)', re.I)


def reddit_posts():
    """r/hackintosh's newest posts, or [] when Reddit will not answer.

    Reddit refuses anonymous reads from scripts (403), so this needs an app of
    its own: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET, a "script" app made at
    reddit.com/prefs/apps, read with the client-credentials grant. Without
    them the GitHub half still runs, and the issue says which half did."""
    cid, secret = os.environ.get('REDDIT_CLIENT_ID'), os.environ.get('REDDIT_CLIENT_SECRET')
    if not (cid and secret):
        return []
    import base64
    ua = 'hackintosh-community/1.0 (weekly review list)'
    try:
        req = urllib.request.Request(
            'https://www.reddit.com/api/v1/access_token',
            data=b'grant_type=client_credentials',
            headers={'User-Agent': ua, 'Authorization': 'Basic ' + base64.b64encode(
                f'{cid}:{secret}'.encode()).decode()})
        with urllib.request.urlopen(req, timeout=30) as r:
            token = json.load(r)['access_token']
        req = urllib.request.Request('https://oauth.reddit.com/r/hackintosh/new?limit=100',
                                     headers={'User-Agent': ua,
                                              'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)['data']['children']
    except Exception:                                   # noqa: BLE001
        return []


def discover(get=_get, known=None):
    """[(repo, where it was seen, title)] for projects the registry lacks."""
    known = {p['repo'].lower() for p in (known if known is not None else projects())}
    vendored = set()
    lock = Path('vendor/kexts.lock')
    if lock.exists():
        vendored = {(e.get('upstream') or '').lower()
                    for e in ocgen.read_toml(lock).get('kext', {}).values()}
    seen = {}
    posts = reddit_posts()
    for post in posts:
        d = post.get('data', {})
        flair = (d.get('link_flair_text') or '').lower()
        text = f"{d.get('title', '')} {d.get('selftext', '')} {d.get('url', '')}"
        if flair not in FLAIRS and not KEXTISH.search(d.get('title', '')):
            continue
        for repo in REPO_LINK.findall(text):
            repo = repo.rstrip('.').removesuffix('.git')
            if repo.lower() not in known | vendored:
                seen.setdefault(repo, (f"reddit: https://reddit.com{d.get('permalink', '')}",
                                       d.get('title', '')))
    import datetime
    since = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    for q in (f'kext in:name,description pushed:>{since}',
              f'hackintosh in:name,description,topics pushed:>{since}'):
        try:
            items = json.loads(get(SEARCH.format(q=urllib.request.quote(q))))['items']
        except Exception:                               # noqa: BLE001
            items = []
        for item in items:
            repo = item['full_name']
            if repo.lower() in known | vendored or item.get('fork'):
                continue
            about = f"{item['name']} {item.get('description') or ''}"
            # a machine's EFI folder is somebody's config, not a driver: those
            # are most of what a search for "hackintosh" finds
            if NOT_A_DRIVER.search(about) or not DRIVERISH.search(about):
                continue
            seen.setdefault(repo, ('github search', item.get('description') or ''))
    return sorted((repo, where, title) for repo, (where, title) in seen.items())


def digest(found):
    """The body of the weekly issue: a checklist, newest sightings first."""
    if not found:
        return 'Nothing new this week: every project seen is already in data/community.toml.'
    lines = ['Projects seen this week that data/community.toml does not have. '
             'Nothing is added automatically; tick one off by adding it to the '
             'registry, or leave it.', '']
    if not os.environ.get('REDDIT_CLIENT_ID'):
        lines += ['_r/hackintosh was not read: set the REDDIT_CLIENT_ID and '
                  'REDDIT_CLIENT_SECRET secrets to include it._', '']
    for repo, where, title in found:
        lines.append(f'- [ ] [{repo}](https://github.com/{repo}) - {title[:120]} ({where})')
    return '\n'.join(lines)


# --- console -----------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--machine', help='a hardware report: what applies to it')
    ap.add_argument('--check', action='store_true', help='what moved upstream')
    ap.add_argument('--refresh', action='store_true', help='record what moved')
    ap.add_argument('--discover', action='store_true', help='projects not recorded yet')
    ap.add_argument('--digest', metavar='FILE', help='with --discover: write the issue body')
    a = ap.parse_args(argv)

    if a.discover:
        found = discover()
        for repo, where, title in found:
            print(f'  {repo:45} {where}  {title[:60]}')
        if a.digest:
            Path(a.digest).write_text(digest(found), encoding='utf-8')
        return 0
    if a.check or a.refresh:
        rows = projects()
        rows, changed, left = refresh(rows)
        if a.refresh and changed:
            head = TABLE.read_text(encoding='utf-8').split('[[project]]')[0].rstrip('\n')
            ocgen.write_toml(TABLE, {'project': rows}, head)
            print(f'  wrote {TABLE}')
        return 1 if (left and not a.refresh) else 0
    if a.machine:
        import detect
        hw, complaint = detect.read_report(a.machine)
        if not hw:
            print(f'  {complaint}')
            return 1
        devices, features = for_machine(hw)
        for p, card, ident in devices:
            print(f'  {ident}  {line(p, card)}')
        for p in features:
            print(f'  {p["role"]:9}  {line(p)}')
        if not devices and not features:
            print('  nothing in the registry applies to this machine')
        return 0
    for stage in ('vendored', 'recommended', 'experimental', 'watching'):
        rows = [p for p in projects() if p.get('stage') == stage]
        if rows:
            print(f'{stage}')
            for p in rows:
                print(f"  {p['name']:28} {p.get('role', ''):10} {p.get('release') or '-':14} "
                      f"{p.get('licence', '')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
