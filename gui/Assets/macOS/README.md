# Release icons

One PNG per macOS release, drawn on the tiles in the Recovery pane. Named after
the release with the spaces taken out, so `data/macos.toml`'s "Big Sur" is
`BigSur.png`:

    Tahoe.png  Sequoia.png  Sonoma.png  Ventura.png  Monterey.png
    BigSur.png  Catalina.png  Mojave.png  HighSierra.png  Sierra.png
    ElCapitan.png  Yosemite.png

Square, 256×256 or larger, with transparency.

**A release with no file here is not a fault.** The pane falls back to the drawn
mark in `data/macosmark.toml` - a gradient in that release's colour with its
initial on it. The list of releases comes from macrecovery's board table and
grows on its own the day Apple serves something new, so a pane that needed a
file per release would arrive with a hole in it that day.

## Whose these are

Apple's. They are reproduced here to identify which macOS a tile stands for,
which is the only thing they are used for and the only reason they are here.

Everything else in this repository is either its own work or a vendored project
under its own licence, and the About pane says which is which. This folder is
the exception, and it is named as one there rather than left to be discovered.

Nothing of Apple's **software** is redistributed here - no installer, no
BaseSystem, no image. The Recovery pane fetches those from Apple, over Apple's
own protocol, when somebody presses the button.
