"""Did the transcript follow its last line?

The builder pane prints where it is scrolled every time the render pass looks
at it - `scrolled <offset> + <viewport> of <extent>`. If the offset plus what
is on screen falls short of the extent, something is below the fold, and the
row that ended up there was the one that quits SSDTTime's menu.

    python3 tools/scrollcheck.py render.log

A file of its own rather than a heredoc in the workflow: the same check written
inline was read as shell commands instead of as a script, and passed by
accident while printing nothing.
"""
import argparse
import re
import sys
from pathlib import Path

WHERE = re.compile(r'scrolled (\d+) \+ (\d+) of (\d+)')


def short(text):
    """The lines that were not at the end, with a pixel of slack for rounding."""
    out = []
    for line in text.splitlines():
        found = WHERE.search(line)
        if not found:
            continue
        at, seen, whole = (int(x) for x in found.groups())
        if at + seen < whole - 1:
            out.append(line.strip())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log', help='the render pass output')
    a = ap.parse_args(argv)

    text = Path(a.log).read_text(encoding='utf-8', errors='replace')
    looked = len(WHERE.findall(text))
    if not looked:
        print(f'  {a.log} says nothing about where the transcript is scrolled; '
              f'the pane is meant to report it every time it is looked at')
        return 1

    behind = short(text)
    if behind:
        print('  the transcript did not follow its last line:')
        for said in behind:
            print(f'    {said}')
        return 1
    print(f'  at the end all {looked} times it was looked at')
    return 0


if __name__ == '__main__':
    sys.exit(main())
