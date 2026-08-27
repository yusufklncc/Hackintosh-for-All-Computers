---
title: Working on this repository
---

# Working on this repository

The 179 configs in `configs.zip` are **generated from a small set of profiles**
rather than stored one by one. The tooling that does it - the builder, the
hardware tables, and the equivalence gate that proves a profile change did not
alter what anyone downloads - is documented in
[tools/README.md](https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/tools/README.md).

```
python3 tools/selftest.py                          everything, including this site
python3 tools/build.py --catalogue                 every published config
python3 tools/build.py --name "Laptop/HP/009 - Laptop - Kaby Lake"
```

## What a change has to survive

Nothing here is accepted on the grounds that it looks right. Every table names
where it came from, and the **About** pane in the program says so out loud:
derived, measured, quoted, reported - or no source at all, said plainly.

- A device claimed as supported names the kext that drives it, read out of that
  kext's own `Info.plist`.
- A sentence about hardware behaviour that no upstream document states goes in
  `data/field.toml`, with the name of whoever observed it and exactly what they
  saw. *"Does not work"* is not an entry; *"installs, but graphics acceleration
  cannot be made to work"* is.
- A config change has to pass the equivalence gate, which rebuilds every
  published config and compares it against a hash catalogue.

## Editing this guide

Each page has a pencil icon at the top right that opens it on GitHub.

The site lives in `guide/`, and every page exists twice: `bios.md` in English
and `bios.tr.md` in Turkish. The selftest fails if one of the pair is missing,
so a page added in one language cannot quietly ship without the other.

```
pip install -r guide/requirements.txt
mkdocs serve                                       preview at localhost:8000
```

## The release version

The tag mirrors the **OpenCore version** vendored in the repository - `v1.0.7`
means OpenCore 1.0.7. It is never bumped for features. When OpenCore has not
moved and a fix has to go out, the release is republished on the same tag; see
[docs/RELEASING.md](https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/docs/RELEASING.md).
