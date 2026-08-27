"""Does the guide link to pages and headings that exist?

`mkdocs build --strict` catches a link to a page that is not there. It does not
catch a link to a *heading* that is not there - the fragment after the `#` is
never resolved, so `usb.md#with-an-image` and `usb.md#nothing-of-the-sort` are
equally fine by it, and the second one silently scrolls nowhere.

That gap is not theoretical here. The Turkish headings slug differently from
the English ones, and the first draft linked to
`#hangi-macos-...-yalnizca-...-olmadigi` while the page had built
`#hangi-macos-...-yalnızca-...-olmadığı`: every non-ASCII letter had been
dropped by the default slugify rather than kept. Nothing said so.

    python3 tools/guidecheck.py _site

It reads the built site rather than the sources, because what a reader clicks
is the built HTML: the anchors are whatever the slugify in `mkdocs.yml`
actually produced, not what a Markdown file appeared to promise.
"""
import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urldefrag

# href="..." on an anchor, and id="..." anywhere. Attribute order is the
# generator's business, so both are matched loosely rather than by tag shape.
HREF = re.compile(r'<a\b[^>]*?href="([^"]+)"', re.I)
ID = re.compile(r'\bid="([^"]+)"')
# the version banner and other generated chrome carry hrefs nobody wrote
SKIP = ('mailto:', 'tel:', 'javascript:', 'data:')


def anchors(text):
    """Every id on the page, plus the name= a few generators still emit."""
    found = set(ID.findall(text))
    found.update(re.findall(r'\bname="([^"]+)"', text))
    return {html.unescape(a) for a in found}


def pages(root):
    """Every built page, by the path a link would reach it at."""
    # keyed by the resolved path, because that is what resolve() hands back:
    # a relative key and an absolute lookup never match, and the first draft
    # of this reported every link in the site as broken.
    out = {}
    for page in sorted(root.rglob('*.html')):
        text = page.read_text(encoding='utf-8', errors='replace')
        out[page.resolve()] = anchors(text)
    return out


def resolve(page, href, root):
    """Where a link on `page` lands, as a file, or None if it leaves the site."""
    target, _ = urldefrag(href)
    if not target:
        return page                       # a bare #fragment stays on this page
    where = (page.parent / unquote(target)).resolve()
    try:
        where.relative_to(root.resolve())
    except ValueError:
        return None                       # climbed out of the site
    if where.is_dir():
        where = where / 'index.html'
    return where


def check(root):
    """Returns the list of complaints, each a line ready to print."""
    known = pages(root)
    if not known:
        return [f'{root} holds no built pages; nothing was checked']

    bad = []
    for page in sorted(known):
        text = page.read_text(encoding='utf-8', errors='replace')
        here = page.relative_to(root.resolve())
        for href in HREF.findall(text):
            href = html.unescape(href)
            if href.startswith(('http://', 'https://', '//')) or href.startswith(SKIP):
                continue                  # off-site, and not this tool's job
            landed = resolve(page, href, root)
            if landed is None:
                continue
            if landed not in known:
                bad.append(f'{here}: "{href}" -> no such page')
                continue
            _, fragment = urldefrag(href)
            if fragment and unquote(fragment) not in known[landed]:
                bad.append(f'{here}: "{href}" -> the page is there, '
                           f'the heading is not')
    return bad


def parity(guide):
    """Every page in one language has to exist in the other.

    A guide that quietly ships a page in English only reads, to somebody on the
    Turkish side, as a guide with a hole in it - and nothing in the build says
    a word about it."""
    english = {p.stem for p in guide.glob('*.md') if not p.stem.endswith('.tr')}
    turkish = {p.stem[:-3] for p in guide.glob('*.tr.md')}
    out = []
    for missing in sorted(english - turkish):
        out.append(f'{missing}.md has no {missing}.tr.md beside it')
    for orphan in sorted(turkish - english):
        out.append(f'{orphan}.tr.md has no English {orphan}.md beside it')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('site', nargs='?', default='_site',
                    help='the built site (default: _site)')
    ap.add_argument('--guide', default='guide',
                    help='the sources, for the language-parity check')
    a = ap.parse_args(argv)

    complaints = parity(Path(a.guide))
    if complaints:
        print('  the two languages do not hold the same pages:')
        for said in complaints:
            print(f'    {said}')
        return 1
    print(f'  every page exists in both languages')

    root = Path(a.site)
    if not root.is_dir():
        print(f'  {root} is not there; run `mkdocs build` first')
        return 1
    complaints = check(root)
    if complaints:
        print('  links that go nowhere:')
        for said in complaints:
            print(f'    {said}')
        return 1
    counted = sum(len(HREF.findall(p.read_text(encoding='utf-8', errors='replace')))
                  for p in root.rglob('*.html'))
    print(f'  {counted} links across the built site, every internal one lands')
    return 0


if __name__ == '__main__':
    sys.exit(main())
