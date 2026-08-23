"""What the builder says, and how it asks.

There is one flow through the questions, and there always has to be: a second
one would be a second thing to get wrong, and the two would drift the first
time a question moved. So the flow is unchanged and only its surface is
swapped. The console prints and reads a typed number; the protocol writes one
JSON object per line and reads the answer back the same way, and what it reads
is the same string a person would have typed.

That last part is the point. Everything after the answer - validation, defaults,
what a menu means - runs identically whichever surface is attached, because the
answer arrives in the same form and goes down the same path.

    engine -> ui   {"t":"ask","id":3,"question":...,"options":[...]}
    ui -> engine   {"id":3,"value":"2"}

Text that was printed arrives as {"t":"text","spans":[...]}. The spans carry the
colour the console would have used, because that colour is already how this
codebase marks what a line means: green is a thing that was done, yellow is a
thing to know about, dim is an aside. Reparsing it is cheaper than annotating
190 call sites, and it cannot fall out of step with what the console shows.
"""
import json
import os
import re
import sys

CODES = {
    'bold': '\033[1m', 'dim': '\033[2m', 'green': '\033[32m',
    'yellow': '\033[33m', 'red': '\033[31m', 'reset': '\033[0m',
}
TONES = {v: k for k, v in CODES.items()}
ANSI = re.compile(r'\033\[[0-9;]*m')

# The modules pick their escape codes when they are imported, which is before
# anything has parsed an argument. Reading the flag here is what lets a
# protocol run keep its colour: without it stdout is a pipe, every code comes
# out empty, and the tone of every line is lost on the way to the front end.
PROTOCOL = '--protocol' in sys.argv


def wanted():
    """Whether anything is going to look at colour."""
    if os.environ.get('NO_COLOR'):
        return False
    if PROTOCOL or os.environ.get('FORCE_COLOR'):
        return True
    return sys.stdout.isatty()


def colours(*names):
    """The escape codes for these names, or empty strings when nobody can see them.

    Six modules used to carry a copy of this decision. They agreed, which is
    the only reason nothing was ever wrong about it."""
    on = wanted()
    return tuple(CODES[n] if on else '' for n in names)


def spans(text):
    """A printed line split into runs of one tone each.

    Codes are read left to right and the last one wins, which is how the
    console renders them too: nothing here nests."""
    out, tone, at = [], 'plain', 0
    for m in ANSI.finditer(text):
        chunk = text[at:m.start()]
        if chunk:
            out.append({'tone': tone, 'text': chunk})
        code = m.group(0)
        tone = 'plain' if code == CODES['reset'] else TONES.get(code, tone)
        at = m.end()
    tail = text[at:]
    if tail or not out:
        out.append({'tone': tone, 'text': tail})
    return out


def plain(text):
    return ANSI.sub('', text)


class Console:
    """The surface this has always had: print, and read a line back."""

    protocol = False

    def line(self, text=''):
        print(text)

    def menu(self, event, render):
        """Show a menu and return the typed answer. render() prints it."""
        render()
        return None                      # the caller reads the answer itself

    def done(self, rc, out=None):
        pass

    def fatal(self, message):
        pass


class Protocol:
    """One JSON object per line out, one per line in.

    Anything printed while this is installed becomes a text event, including
    what build.py and the report modules print. They are not aware of this and
    do not need to be: a front end that can render a transcript and a question
    can drive the whole flow the day it is written."""

    protocol = True

    def __init__(self, out=None, inp=None):
        self.out = out or sys.stdout
        self.inp = inp or sys.stdin
        self.pending = ''
        self.counter = 0

    # --- events out -------------------------------------------------------

    def emit(self, **event):
        self.flush_text()
        self._write(event)

    def _write(self, event):
        self.out.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.out.flush()

    def line(self, text=''):
        self.write(text + '\n')

    # --- the stdout this installs ----------------------------------------

    def write(self, s):
        """sys.stdout.write, for as long as this is installed.

        Buffered to a newline so a line printed in pieces - which build.py does
        - arrives as one event rather than three."""
        self.pending += s
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            self._write({'t': 'text', 'spans': spans(line)})
        return len(s)

    def flush_text(self):
        if self.pending:
            rest, self.pending = self.pending, ''
            self._write({'t': 'text', 'spans': spans(rest)})

    def flush(self):
        self.out.flush()

    def isatty(self):
        return False

    @property
    def encoding(self):
        return getattr(self.out, 'encoding', 'utf-8')

    # --- answers in -------------------------------------------------------

    def question(self, **event):
        """Ask, and block until the front end answers this exact question.

        The id is checked rather than trusted. A front end that answers the
        question before last would otherwise put its answer into a menu it was
        never shown, and the build would be wrong in a way nobody could see."""
        self.counter += 1
        mine = self.counter
        self.emit(id=mine, **event)
        while True:
            raw = self.inp.readline()
            if not raw:
                raise SystemExit('the front end closed while a question was open')
            raw = raw.strip()
            if not raw:
                continue
            try:
                reply = json.loads(raw)
            except ValueError:
                self.emit(t='error', message=f'not JSON: {raw[:80]}')
                continue
            if not isinstance(reply, dict) or reply.get('id') != mine:
                self.emit(t='error', message=f'expected an answer to {mine}')
                continue
            return str(reply.get('value', '')).strip()

    def done(self, rc, out=None):
        self.emit(t='done', rc=rc, out=out)

    def fatal(self, message):
        self.emit(t='fatal', message=str(message))


def install(surface):
    """Point stdout at the protocol, and hand back what it was."""
    was = sys.stdout
    sys.stdout = surface
    return was
