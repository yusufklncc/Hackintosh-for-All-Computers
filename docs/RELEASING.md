# Moving to a new OpenCore, and publishing it

Two things, in that order. Neither is automatic on purpose: a new OpenCore
changes what every machine boots with, and a release is what people download.

## 1. The OpenCore bump

Everything an EFI rests on comes out of one release — the boot files, the
drivers, the tools, the `Sample.plist` every config is layered onto, and the
`ocvalidate` that checks the result. Updating any of them separately is how a
config drifts from the OpenCore it will run under, so one tool does all of it:

```
python3 tools/opencore.py 1.0.8            # what would change
python3 tools/opencore.py 1.0.8 --write    # change it
```

The dry run prints every binary it would replace with the before and after
hash, and names anything it will leave alone. `HfsPlus.efi` is left alone every
time: it is acidanthera's OcBinaryData and ships on its own schedule, so an
OpenCore bump has nothing to say about it.

`--write` replaces the binaries, vendors the new `Sample.plist`, the two
Utilities and `macrecovery` under `vendor/opencore/1.0.8/`, removes the version
before it — one vendored version, so nobody has to know which sorts last — and
rehashes `profiles/catalogue.toml`.

`macrecovery` travels with its `boards.json`, which is where the Recovery tab's
list of macOS versions comes from. A new OpenCore usually brings a newer board
list, so that list moves with the bump rather than on its own; if a macOS
appears or disappears from the Recovery tab after an update, this is why.

Whether any hash moves depends on the new sample. Going from 1.0.5 to 1.0.7
moved none of the 179, because nothing the profiles layer onto had changed. If
some do move, that is the diff to read: it is every published config changing.

### Then check it

```
python3 tools/verify.py --comments     # 179/179 configs match their hash
python3 tools/selftest.py              # everything else
python3 tools/build.py --platform laptop --cpu kaby-lake --out /tmp/oc
```

The last one has to end in `ocvalidate  clean`. If it stops with nothing
printed, look at the executable bit before anything else — the release zip
ships the Linux builds of `ocvalidate` and `macserial` unexecutable, and a
build that shells out to one of those stops dead with no output at all.
`tools/opencore.py` sets the bit, `tools/fetch_oc.py` sets it in the cache, and
`selftest.py` refuses a tree where git has recorded any of them as `100644`.
All three exist because this happened.

### Record what it was tested against

`profiles/support.toml` is measured, not asserted. To add the new version to
the tested list:

```
OC_CACHE=.oc-cache python3 tools/matrix.py 1.0.7 1.0.8
```

It validates every profile against each version named and rewrites the range.
Nothing here decides that a version works; the run does.

## 2. The release

Tag it. The workflow does the rest:

```
git tag v1.4.0 && git push origin v1.4.0
```

`release.yml` then:

1. verifies the kext lock and all 179 configs before building anything,
2. builds `EFI-base.zip` and `configs.zip`,
3. builds the console `HackintoshEFIBuilder.exe`,
4. builds the window and its engine for Windows, Linux and macOS, and zips each
   as `HackintoshEFIBuilder-<system>.zip`,
5. publishes them all under the tag.

It can also be started by hand from the Actions tab with a tag as input, which
is the way to re-publish without moving a tag.

### What the packages are

Each `HackintoshEFIBuilder-<system>.zip` holds two programs:

| file | what it is |
|---|---|
| `HackintoshEFIBuilder` | the window |
| `EFIBuilderEngine` | the builder, which the window runs |

Both are needed. The window reimplements none of the engine: it asks it for
everything and draws the answers. CI proves the packaged pair is the one being
used — the render step fails unless the window reports `engine: beside this
window`, which it can only do when the engine is the one shipped beside it and
not a clone lying around.

Neither is signed. Windows SmartScreen will warn on first run and macOS will
refuse a downloaded copy until it is allowed in System Settings. Signing costs
money and is a decision nobody has taken yet.

## The other refresh, which is not this

`refresh.yml` runs weekly and regenerates the tables that describe other
people's work — the GPU guide, AppleALC's layouts, the kexts' own device lists,
Apple's Mac support metadata, OCLP's patch list. It opens a pull request and
never merges: a change there is a change to what people are told about their
hardware, and that is worth reading.

An OpenCore bump is not part of it, and should not be. A table going stale
misinforms; the wrong OpenCore does not boot.
