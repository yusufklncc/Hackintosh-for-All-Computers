"""Make sure macOS's own tools can be found by name.

diskutil, hdiutil, ioreg and system_profiler live in /usr/sbin, and every tool
here calls them by name. A program opened from the Finder gets launchd's PATH,
which has /usr/sbin in it, so this never showed - until a shell without it ran
the engine. Then nothing failed loudly: the stick list came back empty, the
machine reported no PCI devices, and both read as "there is nothing here"
rather than "the tool was never run".

Importing this adds the two system directories to PATH when they are missing.
It changes nothing that was already working, and nothing off macOS.
"""
import os
import sys

SYSTEM = ('/usr/sbin', '/sbin', '/usr/bin', '/bin')


def ensure():
    if sys.platform != 'darwin':
        return
    have = os.environ.get('PATH', '').split(os.pathsep)
    missing = [d for d in SYSTEM if d not in have and os.path.isdir(d)]
    if missing:
        os.environ['PATH'] = os.pathsep.join([p for p in have if p] + missing)


ensure()
