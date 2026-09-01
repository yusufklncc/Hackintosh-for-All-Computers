---
title: When your system blocks it
---

# When your system blocks it

Signing an application means paying Microsoft or Apple every year for a
certificate. This project does not, so the first run is refused on both.

Nothing below weakens anything permanently, and none of it is specific to this
program - it is what every unsigned open-source download needs.

## Windows

If **Smart App Control** is on, the program will not start and Windows will say
very little about why. Microsoft's own page is plain about the rule:

> If the app is unsigned, or the signature is invalid, Smart App Control will
> consider it untrusted and block it for your protection.
>
> — [What is Smart App Control?](https://support.microsoft.com/en-us/topic/what-is-smart-app-control-285ea03d-fa88-4d56-882e-6698afdb7003)

There is no *run anyway* on that dialog. The switch is the only way past it.

1. Open **Windows Security**.
2. Go to **App & browser control** → **Smart App Control**.
3. Set it to **Off**.
4. Run the program.

!!! question "Can I turn it back on afterwards?"
    Yes. Microsoft's page answers the question everybody asks before touching
    that switch: *"Recent Windows updates allow Smart App Control to be
    re-enabled without requiring a clean installation."* Turning it back on was
    tested here on Windows 11 and worked from the same switch.

### That is not the dialog I got

A blue box headed **Windows protected your PC** is SmartScreen, not Smart App
Control. That one you can pass without changing any setting:

1. Click **More info**.
2. Click **Run anyway**.

## macOS

The app is signed ad-hoc - enough that macOS will run it at all on Apple silicon
- but it is not notarised, so Gatekeeper refuses the first open.

!!! tip "Move it before you open it"
    Unzip the download and **move the app in Finder** before opening it -
    anywhere will do; Applications is only the habit.

    macOS runs a quarantined app from a read-only copy somewhere else on the
    disk when it is launched from where it was unarchived. That is App
    Translocation, and it is why an app can be allowed and still behave as
    though it were not. Moving it in Finder ends it.

    If you would rather not move it, clearing the quarantine flag does the same
    thing and leaves the app where it is:

    ```
    xattr -dr com.apple.quarantine "Hackintosh EFI Builder.app"
    ```

The way through is to try once and then allow it, in that order:

1. Double-click `HackintoshEFIBuilder.app`. **It will be refused.** That refusal
   is what creates the entry in the next step.
2. Open **System Settings** → **Privacy & Security**, scroll down to
   **Security**, and click **Open Anyway** next to the app's name.
3. Enter your login password.

Apple notes that this *"button is available for about an hour after you try to
open the app"* ([Open a Mac app from an unknown
developer](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac)).
If it is not there, try to open the app again and go back.

macOS remembers the exception, and it opens normally from then on.

## Linux

Nothing blocks it. The AppImage only needs the executable bit.

```
chmod +x HackintoshEFIBuilder-linux-x64.AppImage
./HackintoshEFIBuilder-linux-x64.AppImage
```

## None of this worked

The builder also runs without the window, in a terminal, from a package that
has no graphical part at all - see [Without the window](terminal.md). It asks
the same questions and writes the same EFI folder.

On Windows, note that Smart App Control blocks that one for the same reason it
blocks the app; the console package is not a way around that setting.
