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


# --- install.sh: UnPlugged with its questions answered -----------------------
#
# UnPlugged asks five things, from its own stdin, and takes only numbers for
# two of them: which way to build the app, and which volume - the volume by
# its place in a listing of /Volumes made at that moment. A wrong answer is
# asked again, so a list of fixed answers piped in can slide out of step and,
# once the input runs out, ask for ever. This works each answer out in
# recovery, with the commands UnPlugged itself uses, at the commit pinned in
# data/unplugged.toml (whose hash fetch() checks, so the two cannot drift),
# asks the person one thing, and falls back to UnPlugged as it is whenever
# anything is not what it expects. Bash 3.2: recovery has nothing newer.

INSTALLER = 'install.sh'
CONF = 'install.conf'

SCRIPT = r"""#!/bin/bash
# Hackintosh EFI Builder: UnPlugged.command, with its questions answered.
#
#   bash /Volumes/UNPLUGGED/install.sh
#
# Erase the target disk in Disk Utility first. This asks which volume and
# whether to go on, then runs UnPlugged.command beside it with the answers it
# would have asked for. Anything unexpected and it starts UnPlugged as it is.
here="$(cd -- "$(dirname "$0")" >/dev/null 2>&1; pwd -P)"
volumes="${UNPLUGGED_VOLUMES:-/Volumes}"     # a test points these elsewhere
root="${UNPLUGGED_ROOT:-/}"
pkgutil_bin="${UNPLUGGED_PKGUTIL:-/usr/sbin/pkgutil}"
script="$here/UnPlugged.command"
[ -f "$script" ] || { echo "UnPlugged.command is not beside this script."; exit 1; }
NAME="macOS"; VERSION=""; WANT=""
[ -f "$here/install.conf" ] && . "$here/install.conf"

by_hand () {
    echo
    echo "$1"
    echo "Starting UnPlugged as it is: answer its questions yourself (the guide lists them)."
    echo
    cd "$here" && exec bash "$script"
}

answers=()

# 0. Whether pkgutil can read the package here. When it cannot, UnPlugged
#    stops once to ask whether to go on - "Some recovery environments have odd
#    issues (macOS 13, for instance)" - and its answer is yes "as long as the
#    .pkg copy process completed correctly", which the stick was checked for
unread=""
if [ -e "$here/InstallAssistant.pkg" ]; then
    app_temp="$(pkgutil --payload-files "$here/InstallAssistant.pkg" 2>/dev/null | grep -iE "(?i)^.*/Install[^/]+\.app$")"
    if [ "$?" != "0" ] || [ -z "$app_temp" ]; then
        unread=1
        answers+=("y")
    fi
fi

# 1. How UnPlugged will build the app (UnPlugged.command, hasAll and the
#    approaches it lists, in its order)
if [ -e "$here/InstallAssistant.pkg" ]; then
    count=0; pick=0
    cat "$pkgutil_bin" 2>/dev/null | grep -i "expand-full" >/dev/null 2>&1 && can_expand=1 || can_expand=0
    if [ "$can_expand" = "1" ]; then
        count=$((count+1)); [ "$WANT" = "expand" ] && pick=$count
    fi
    if [ -e "$here/BaseSystem.dmg" ] || [ -e "$here/RecoveryImage.dmg" ]; then
        count=$((count+1)); [ "$WANT" = "extract" ] && pick=$count
    fi
    apps="$(find "$root" -name "Install*.app" -type d -maxdepth 3 2>/dev/null)"
    [ -n "$apps" ] && count=$((count+1))
    if [ "$count" -gt 1 ]; then
        [ "$pick" -gt 0 ] || by_hand "The way to build the installer this stick is for is not one UnPlugged offers here."
        answers+=("$pick")
    elif [ "$count" -eq 1 ]; then
        [ "$pick" -eq 1 ] || by_hand "UnPlugged offers one way here, and not the one this stick is for."
    else
        by_hand "UnPlugged has no way to build the installer here."
    fi
fi

# 2. Which volume: the place in UnPlugged's own listing, found by name
listing="$(cd "$volumes/" && ls -1 | grep "^[^.]")"
mine="$(basename "$here")"
candidates=()
while IFS= read -r v; do
    [ -z "$v" ] && continue
    case "$v" in
        "$mine"|EFI|OPENCORE|"macOS Base System"|"OS X Base System"|"Image Volume"|Recovery|Preboot|VM|Update) continue;;
    esac
    candidates+=("$v")
done <<< "$listing"
if [ "${#candidates[@]}" -eq 0 ]; then
    by_hand "No volume to install to. Erase the target disk in Disk Utility first (APFS, GUID Partition Map)."
fi
target="${candidates[0]}"
if [ "${#candidates[@]}" -gt 1 ]; then
    echo; echo "Install $NAME $VERSION onto which volume?"; echo
    i=0
    for v in "${candidates[@]}"; do i=$((i+1)); echo "  $i. $v"; done
    echo
    read -r -p "Number: " n
    case "$n" in ''|*[!0-9]*) by_hand "Not a number from the list.";; esac
    [ "$n" -ge 1 ] && [ "$n" -le "${#candidates[@]}" ] || by_hand "Not a number from the list."
    target="${candidates[$((n-1))]}"
fi
place=0; i=0
while IFS= read -r v; do
    [ -z "$v" ] && continue
    i=$((i+1)); [ "$v" = "$target" ] && place=$i
done <<< "$listing"
[ "$place" -gt 0 ] || by_hand "$target is not in the volume list any more."
answers+=("$place")

# 3. An earlier attempt on that volume is removed, and said so before
earlier="$(find "$volumes/$target" -name "macOS-Installer-*" -type d -maxdepth 1 2>/dev/null)"
[ -n "$earlier" ] && answers+=("y")

# 4. Copy rather than symlink: UnPlugged's own words, "More reliable"
answers+=("2")

echo
echo "Install $NAME $VERSION onto "$target"."
[ -n "$earlier" ] && echo "The earlier attempt on it is removed first."
[ -n "$unread" ] && echo "pkgutil cannot read the installer package in this recovery, which UnPlugged says some do; it was checked when the stick was made, and UnPlugged goes on."
echo "The installer is put together on that volume and started. Leave Terminal open."
echo
read -r -p "Go on? [y/n]: " go
case "$go" in [Yy]*) ;; *) echo "Nothing was done."; exit 0;; esac

# 5. And UnPlugged's own last question
answers+=("${UNPLUGGED_FINAL:-y}")

if [ "${1:-}" = "--answers" ]; then printf '%s\n' "${answers[@]}"; exit 0; fi
# q after the answers: a question asked again, because something was not as
# expected, ends UnPlugged instead of waiting on input that will never come
cd "$here" && { printf '%s\n' "${answers[@]}" q q q q; } | bash "$script"
"""


def write_installer(into, plan):
    """install.sh and the facts it reads, beside UnPlugged.command."""
    into = Path(into)
    want = ('' if plan.get('recovery_from_package') else
            'extract' if plan.get('basesystem_on_exfat') else 'expand')
    row = plan['macos']
    (into / INSTALLER).write_text(SCRIPT, encoding='utf-8', newline='\n')
    (into / CONF).write_text(
        f'NAME="{row["name"]}"\nVERSION="{row.get("version", "")}"\nWANT="{want}"\n',
        encoding='utf-8', newline='\n')
    try:
        (into / INSTALLER).chmod(0o755)
    except OSError:
        pass
    return into / INSTALLER


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
