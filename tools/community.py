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
        if p.get('requires_cpu_name'):
            # the processor the project names, not the generation it belongs
            # to: "verified on an i5-12450HX" is not "for Alder Lake", and
            # widening it was a claim the project never made
            if any(re.search(pat, hw.get('cpu') or '', re.I) for pat in p['requires_cpu_name']):
                out.append(p)
        elif p.get('requires_cpu') and gen in p['requires_cpu']:
            out.append(p)
        elif p.get('requires_role') == 'bluetooth' and any(
                i.split(':')[0] in p.get('requires_vendor', []) for i in usb):
            # a Bluetooth controller is a USB device; its vendor is the claim
            out.append(p)
        elif p.get('requires_role') == 'wifi' and any(
                i in p.get('requires_ids', []) for i in pci):
            out.append(p)
    return out


def line(p, card=None):
    """One sentence for a front end: what it is, how far, in whose words."""
    tested = ''
    if card is not None and 'tested' in card:
        tested = ', run on this card' if card['tested'] else ', not yet run on this card'
    where = ('Installed after macOS boots' if p.get('install') == 'system'
             else 'A kext for the EFI, offered when the EFI is built and never added unasked'
             if p.get('recipe') else
             f"Its own installer edits the EFI ({p.get('how', '')}); nothing here adds it")
    said = (p.get('macos') or '').strip().rstrip('.')
    level = {'written': ', AI-written', 'assisted': ', AI-assisted'}.get(ai_level(p)[0], '')
    return f"{p['name']} ({p['stage']}{tested}{level}) - {said}. {where}. {p['repo']}"


def for_machine(hw):
    """Everything in the registry that applies to one machine, shown ones only."""
    ids = list((hw or {}).get('pci_ids', [])) + list((hw or {}).get('usb_ids', []))
    for d in (hw or {}).get('gpu_devices', []) or []:
        if d.get('id'):
            ids.append(d['id'])
    devices = devices_for(ids)
    return devices, features_for(hw, [p['name'] for p, _, _ in devices])


ROLE = {'graphics': 'Graphics', 'wifi': 'Wi-Fi', 'bluetooth': 'Bluetooth',
        'ethernet': 'Ethernet', 'cpu': 'CPU', 'card reader': 'Card reader'}


def document(hw=None):
    """The registry as the Compatible Hardware pane draws it: one card each.

    With a machine, each card also says whether that machine matches it - by a
    device id the project names, or by the requirement an add-on states."""
    mine = set()
    if hw:
        devices, features = for_machine(hw)
        mine = {p['name'] for p, _, _ in devices} | {p['name'] for p in features}
    out = []
    for p in projects():
        ids = [c['id'] for c in p.get('card', [])] or list(p.get('ids', []))
        out.append({
            'name': p['name'], 'repo': p['repo'], 'url': f"https://github.com/{p['repo']}",
            'role': ROLE.get(p.get('role'), (p.get('role') or '').title()),
            'kind': p.get('kind', ''), 'stage': p.get('stage', ''),
            'install': p.get('install', ''), 'licence': p.get('licence', ''),
            'release': p.get('release') or '', 'macos': p.get('macos', ''),
            'said': p.get('quote') or p.get('caveat') or '',
            'covers': p.get('covers', ''), 'how': p.get('how', ''),
            'needs': p.get('needs', ''), 'conflicts': p.get('conflicts', []),
            'devices': len(ids), 'ids': ids[:8],
            'tested': [c['name'] for c in p.get('card', []) if c.get('tested')],
            'ai': p.get('ai', ''),
            'ai_level': ai_level(p)[0],
            'ai_why': ai_level(p)[1],
            'ai_files': p.get('ai_files', []),
            'ai_commits': p.get('ai_commits', [0, 0]),
            'ai_tools': p.get('ai_tools', []),
            'recipe': bool(p.get('recipe')),
            'matches': p['name'] in mine,
            'chips': p.get('chips', []),
            'requires': (p['requires_cpu_said'] if p.get('requires_cpu_said')
                         else ', '.join(p.get('requires_cpu', [])) if p.get('requires_cpu')
                         else 'a Realtek or Intel Bluetooth controller'
                         if p.get('requires_role') == 'bluetooth'
                         else 'a Broadcom BCM4360-class Wi-Fi card'
                         if p.get('requires_role') == 'wifi' else ''),
        })
    order = {'recommended': 0, 'experimental': 1, 'vendored': 2, 'watching': 3}
    out.sort(key=lambda r: (order.get(r['stage'], 9), r['role'], r['name'].lower()))
    return {'projects': out}


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
        # a project with no README still describes itself in one line on
        # GitHub, and that line is as much its own words
        # the sentences may live in another file than the ids do: the Arc
        # driver's ids are in its rule file and its own words in its README
        where = p.get('quote_source') or p['source']
        page = (_flat(info.get('description') or '') if where == '@description' else
                _flat(get(RAW.format(repo=repo, sha=head, path=where)).decode('utf-8', 'replace')))
        # only what is recorded as the project's own words: the two GPU drivers
        # carried over keep a summary in `macos`, and a summary is never on
        # the page it summarises
        for key in p.get('quoted', ['quote']):
            if p.get(key) and p[key] not in page:
                out.append((f'the {key} sentence is no longer on {where}', None))
    if p.get('ai') and p.get('ai_source'):
        page = _flat(get(RAW.format(repo=repo, sha=head, path=p['ai_source'])).decode('utf-8', 'replace'))
        if p['ai'] not in page:
            out.append((f'the ai sentence is no longer on {p["ai_source"]}', None))
    if p.get('ids_from') == 'rules' and p.get('card'):
        # the driver's own rule file: the ids its EFI tool and kext act on
        rules = json.loads(get(RAW.format(repo=repo, sha=head, path=p['source'])))
        ids = {f"{rules['cards']['vendor_id']}:{i}".lower() for i in rules['cards']['device_ids']}
        have = {c['id'].lower() for c in p['card']}
        for added in sorted(ids - have):
            out.append((f'now matches {added}', None))
        for gone in sorted(have - ids):
            out.append((f'no longer matches {gone}', None))
    if p.get('release') and p.get('ids_from') in ('rules', 'chips'):
        # installed by its own app, so only the release it is on is followed
        try:
            rel = json.loads(get(API.format(repo=repo) + '/releases?per_page=1'))
        except urllib.error.HTTPError:
            rel = []
        if isinstance(rel, list) and rel and rel[0].get('tag_name') != p['release']:
            out.append((f'released {rel[0]["tag_name"]}', {'release': rel[0]['tag_name']}))
    if p.get('release') is not None and p.get('ids_from') in ('kext', 'quoted', None) \
            and not p.get('unreleased'):
        try:
            rel = json.loads(get(API.format(repo=repo) + '/releases?per_page=1'))
        except urllib.error.HTTPError:
            rel = []
        if isinstance(rel, list) and rel and rel[0].get('tag_name') != p.get('release'):
            tag = rel[0]['tag_name']
            update = {'release': tag}
            zips = [a for a in rel[0].get('assets', []) if a['name'].lower().endswith('.zip')
                    and 'debug' not in a['name'].lower() and 'source' not in a['name'].lower()
                    and 'tools' not in a['name'].lower()
                    and (p.get('asset_match') or '').lower() in a['name'].lower()]
            if zips:
                blob = get(zips[0]['browser_download_url'])
                update.update(asset=zips[0]['name'], sha256=hashlib.sha256(blob).hexdigest())
                if p.get('ids_from') == 'kext':
                    update['ids'] = kext_ids(blob)
            out.append((f'released {tag}', update))
    seen_ai = ai_evidence(repo, head, get=get)
    now = {'ai_files': seen_ai['files'], 'ai_commits': seen_ai['commits'],
           'ai_tools': seen_ai['tools']}
    if any(p.get(k) != v for k, v in now.items()):
        out.append(('what its repository shows about AI tools changed', now))
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


# --- into an EFI, when somebody picks one -------------------------------------
#
# Each recipe is the project's own manual steps, quoted in data/community.toml
# and applied here as they read. Nothing is shipped: the project's release and
# any kext it says to fetch from elsewhere are downloaded at the moment they
# are picked, from the address recorded, and refused unless the hash matches.

CACHE = Path(os.environ.get('COMMUNITY_CACHE', '.community-cache'))
BOOT_GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'


def offered(hw):
    """The shown projects with a recipe for the EFI that this machine matches."""
    devices, features = for_machine(hw)
    out, seen = [], set()
    for p in [d for d, _, _ in devices] + features:
        if p['name'] in seen or not p.get('recipe') or p.get('install') != 'efi':
            continue
        seen.add(p['name'])
        out.append(p)
    return out


def _unzip_kexts(blob, into):
    """Extract a zip and return {bundle name: path} for its top-level kexts."""
    import shutil
    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            # nothing outside the folder it is being unpacked into
            if member.startswith('/') or '..' in Path(member).parts:
                raise ValueError(f'{member}: a path outside the archive')
        z.extractall(into)
    found = {}
    for kext in sorted(into.rglob('*.kext')):
        if '__MACOSX' in kext.parts or '.kext' in str(kext.parent):
            continue
        found.setdefault(kext.name, kext)
    return found


def fetch(p, cache=None, get=_get):
    """({bundle name: local path}, complaint) for everything a recipe adds."""
    cache = Path(cache or CACHE) / re.sub(r'[^\w.-]', '_', p['name'])
    url = f"https://github.com/{p['repo']}/releases/download/{p['release']}/{p['asset']}"
    sources = [(url, p['sha256'], 'release')]
    sources += [(e['url'], e['sha256'], e['name']) for e in p['recipe'].get('extra', [])]
    found = {}
    for i, (address, want, what) in enumerate(sources):
        try:
            blob = get(address)
        except (urllib.error.URLError, OSError) as exc:
            return {}, f'{p["name"]}: {what} could not be downloaded ({exc})'
        got = hashlib.sha256(blob).hexdigest()
        if got != want:
            return {}, (f'{p["name"]}: {what} is not the file that was recorded '
                        f'(expected {want[:12]}, got {got[:12]}); nothing was added')
        try:
            found.update(_unzip_kexts(blob, cache / str(i)))
        except (zipfile.BadZipFile, ValueError) as exc:
            return {}, f'{p["name"]}: {what} is not a zip this can read ({exc})'
    tops = {a.split('/')[0] for a in p['recipe']['add']}
    missing = sorted(tops - set(found))
    if missing:
        return {}, f'{p["name"]}: {", ".join(missing)} is not in what was downloaded'
    return found, None


def _executable(kext):
    info = kext / 'Contents' / 'Info.plist'
    try:
        with open(info, 'rb') as fh:
            name = plistlib.load(fh).get('CFBundleExecutable')
    except (OSError, plistlib.InvalidFileException):
        return ''
    return f'Contents/MacOS/{name}' if name and (kext / 'Contents' / 'MacOS' / name).exists() else ''


def apply(efi, picks, darwin=None, say=print, get=_get, cache=None):
    """Apply each picked recipe to a built EFI folder. Returns a complaint or None.

    The config is read, changed as the recipes say, and written once, after
    every download has checked out - a recipe that fails halfway leaves the
    EFI as it was built."""
    import shutil
    efi = Path(efi)
    cfg_path = efi / 'OC' / 'config.plist'
    with open(cfg_path, 'rb') as fh:
        config = plistlib.load(fh)
    kexts_dir = efi / 'OC' / 'Kexts'
    names = {p['name'] for p in picks}
    staged = []
    for p in picks:
        clash = [c for c in p.get('conflicts', []) if c in names]
        if clash:
            return f'{p["name"]} cannot go in beside {", ".join(clash)}: pick one'
        got, complaint = fetch(p, cache=cache, get=get)
        if complaint:
            return complaint
        staged.append((p, got))

    add = config['Kernel']['Add']
    # what to say is kept until the config is written: a line that cannot be
    # printed must not be the thing that leaves an EFI half changed
    told = []
    say, tell = told.append, say
    for p, got in staged:
        r = p['recipe']
        note = f"{p['name']} {p.get('release', '')}, community, experimental"
        for top in sorted({a.split('/')[0] for a in r['add']}):
            target = kexts_dir / top
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(got[top], target)
        for rel in r.get('remove', []):
            if (kexts_dir / rel).exists():
                shutil.rmtree(kexts_dir / rel)
        for bundle in r['add']:
            entry = {'Arch': 'x86_64', 'BundlePath': bundle, 'Comment': note,
                     'Enabled': True, 'ExecutablePath': _executable(kexts_dir / bundle),
                     'MaxKernel': r.get('max_kernel', ''),
                     'MinKernel': r.get('min_kernel', ''),
                     'PlistPath': 'Contents/Info.plist'}
            add[:] = [e for e in add if e.get('BundlePath') != bundle] + [entry]
        for name in r.get('disable', []) + [c for c in p.get('conflicts', [])
                                            if c.endswith('.kext')]:
            for e in add:
                if e.get('BundlePath') == name and e.get('Enabled'):
                    e['Enabled'] = False
                    say(f'      {name} turned off: {p["name"]} says so')
        for b in r.get('block', []):
            blocks = config['Kernel'].setdefault('Block', [])
            blocks[:] = [x for x in blocks if x.get('Identifier') != b['identifier']]
            blocks.append({'Arch': 'x86_64', 'Comment': note, 'Enabled': True,
                           'Identifier': b['identifier'], 'MaxKernel': '',
                           'MinKernel': b.get('min_kernel', ''),
                           'Strategy': b.get('strategy', 'Exclude')})
        if r.get('secure_boot_model'):
            config['Misc']['Security']['SecureBootModel'] = r['secure_boot_model']
        nv = config['NVRAM']['Add'].setdefault(BOOT_GUID, {})
        for b in r.get('boot_args', []):
            if darwin is not None and darwin < b.get('from_darwin', 0):
                continue
            args = (nv.get('boot-args') or '').split()
            if b['arg'] not in args:
                nv['boot-args'] = ' '.join(args + [b['arg']])
        say(f'      {p["name"]} {p.get("release", "")} added, as its README says:')
        for step in r.get('steps', []):
            say(f'        "{step}"')

    with open(cfg_path, 'wb') as fh:
        plistlib.dump(config, fh, sort_keys=False)
    for line in told:
        tell(line)
    return None


def validate(efi):
    """'clean', 'ISSUES: ...' or 'skipped' - the vendored ocvalidate on the result."""
    import subprocess
    tool = ocgen.vendored_tool('ocvalidate')
    if not tool:
        return 'skipped'
    r = subprocess.run([str(tool), str(Path(efi) / 'OC' / 'config.plist')],
                       capture_output=True, text=True)
    if 'No issues found' in r.stdout:
        return 'clean'
    return 'ISSUES: ' + ' '.join(line.strip() for line in r.stdout.splitlines()
                                 if 'OCS:' in line or 'OCK:' in line or 'Kernel' in line)[:400]


# --- how it was written, where that can be shown ------------------------------
#
# Whether a project was written with an AI is not something this can know from
# the outside. Three things can be shown, and each is labelled for what it is:
# the project saying so (a sentence, quoted); files in the repository that only
# exist to instruct an AI coding tool; and commits whose message credits one as
# a co-author. Absence of all three is "not stated", never "written by hand".

AI_SAYS = re.compile(r'([^.\n]*\b(built with ai|ai[- ]assist\w*|written (with|by) (an? )?(ai|llm)|'
                     r'claude|chatgpt|openai codex|github copilot|gemini|cursor ai|'
                     r'large language model|llm)\b[^.\n]*[.\n])', re.I)
AI_NOT = re.compile(r'radeon ai|ai pro|ai max|\bai\b engine|npu', re.I)
AI_FILES = ('CLAUDE.md', 'AGENTS.md', 'GEMINI.md', '.cursorrules', '.windsurfrules',
            '.github/copilot-instructions.md')
AI_DIRS = ('.claude/', '.cursor/', '.codex/', '.gemini/', '.kiro/')
AI_COAUTHOR = re.compile(r'co-authored-by:\s*(claude|copilot|chatgpt|codex|gemini|cursor|'
                         r'openhands|devin|aider)', re.I)


WRITTEN_SAYS = re.compile(r'\b(most|all|the code|code in this repository|written by|'
                          r'developed with ai)\b', re.I)


def ai_level(p):
    """('written' | 'assisted' | '', why) - from what can be shown, never guessed.

    written   the project says its code was written with or by an AI, or at
              least half of its recent commits credit an AI as co-author
    assisted  some commits credit one, or the repository carries files that
              only exist to instruct an AI coding tool
    ''        none of that: not stated, which is not the same as "by hand"
    """
    credited, seen = (p.get('ai_commits') or [0, 0])[:2]
    tools = ', '.join(p.get('ai_tools') or []) or 'an AI'
    parts = []
    if p.get('ai'):
        parts.append(f'it says so: "{p["ai"].replace("**", "").strip()}"')
    if credited:
        parts.append(f'{credited} of its last {seen} commits credit {tools} as co-author')
    if p.get('ai_files'):
        parts.append(f'{", ".join(p["ai_files"])} in the repository')
    why = '; '.join(parts)
    if (p.get('ai') and WRITTEN_SAYS.search(p['ai'])) or (seen and credited * 2 >= seen):
        return 'written', why
    if parts:
        return 'assisted', why
    return '', ''


def ai_evidence(repo, head, get=_get):
    """{'said': sentence or '', 'files': [...], 'commits': (n of m)} for one repo."""
    said = ''
    try:
        readme = json.loads(get(API.format(repo=repo) + '/readme'))
        import base64
        text = base64.b64decode(readme.get('content', '')).decode('utf-8', 'replace')
        for m in AI_SAYS.finditer(text):
            sentence = _flat(m.group(1)).strip(' >*-#')
            if not AI_NOT.search(sentence):
                said = sentence[:240]
                break
    except Exception:                                   # noqa: BLE001
        pass
    files = []
    try:
        tree = json.loads(get(API.format(repo=repo) + f'/git/trees/{head}?recursive=1'))
        paths = [x['path'] for x in tree.get('tree', [])]
        files = sorted({f for f in AI_FILES if f in paths}
                       | {d.rstrip('/') for d in AI_DIRS
                          if any(x == d.rstrip('/') or x.startswith(d) for x in paths)})
    except Exception:                                   # noqa: BLE001
        pass
    credited, seen, tools = 0, 0, []
    try:
        commits = json.loads(get(API.format(repo=repo) + '/commits?per_page=100'))
        seen = len(commits)
        named = [AI_COAUTHOR.search(c.get('commit', {}).get('message', '')) for c in commits]
        credited = sum(1 for m in named if m)
        tools = sorted({m.group(1).title() for m in named if m})
    except Exception:                                   # noqa: BLE001
        tools = []
    return {'said': said, 'files': files, 'commits': [credited, seen], 'tools': tools}


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
