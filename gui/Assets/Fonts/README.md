# The two faces this window is set in

Both are under the SIL Open Font License 1.1, whose text is beside them. That
licence allows redistribution of the font files, and of modified copies under
a different name - which matters, because two of these are modified.

| file | source | how it got here |
|---|---|---|
| `InstrumentSans-Regular.ttf` | google/fonts `ofl/instrumentsans` | one instance of the variable font |
| `InstrumentSans-SemiBold.ttf` | same | same, and renamed so the weight resolves |
| `IBMPlexMono-Regular.ttf` | google/fonts `ofl/ibmplexmono` | as published |
| `IBMPlexMono-Medium.ttf` | same | as published |

Both were taken at google/fonts commit `0b58fb370093f9a9f4ff785d94405710b79de67c`.

## Why the Instrument Sans files are not the published ones

Upstream ships one variable font and no static instances. A variable font
loaded by name renders at its default weight whatever weight is asked for, so
a heading set in SemiBold would come out Regular. These two are cut from it:

    fonttools varLib.instancer InstrumentSans[wdth,wght].ttf wght=400 wdth=100
    fonttools varLib.instancer InstrumentSans[wdth,wght].ttf wght=600 wdth=100

SemiBold is not one of the four styles the legacy name fields can hold, so its
family is `Instrument Sans SemiBold` with typographic names putting it back
under `Instrument Sans`. That is the same arrangement IBM Plex Mono Medium
ships with, and it is what lets `FontWeight="SemiBold"` find it.

Regenerating them needs `fonttools`; nothing in this repository does at build
or run time.
