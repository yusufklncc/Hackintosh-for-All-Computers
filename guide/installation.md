---
title: macOS installation steps
---

# macOS installation steps

Boot from the USB and choose **Install macOS "Sonoma"** - or whichever release
you are installing.

![The OpenCore picker](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/opencore-install-macos.png)
![Verbose boot beginning](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/verbose-start.png)
![Verbose boot continuing](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/middle-verbose.png)

Select your language.

![Choosing the installer language](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-language.png)

!!! tip "Check the network before you go further"
    On Ethernet, double-click Safari and see whether a page loads. On Wi-Fi,
    click the Wi-Fi icon top right, join your network, then test it in Safari.

    On the recovery route this is not optional: the installer downloads macOS
    from here.

## Prepare the disk

Open **Disk Utility**.

![Opening Disk Utility](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-disk-utility.png)

Choose **Show All Devices** from the *View* button.

![Show All Devices](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/show-all-devices.png)

Select the disk you are installing to from the left, and click **Erase**.

![Selecting the disk to erase](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-main-disk-name-erase.png)

Give the disk a name, set **Format** to APFS and **Scheme** to GUID Partition
Map. Click **Erase**.

![Name, format and scheme](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-format-scheme.png)

=== "Installing alongside Windows"

    Create a partition in HFS+ first — [video
    guide](https://vk.com/video749455540_456239018).

    Then right-click the volume you created in Disk Utility's sidebar and choose
    **Convert to APFS**. You can select it on the installer screen and go on.

=== "Adding a volume to an existing macOS disk"

    Select the **Container**, then click the **+** button top right.

    ![Adding an APFS volume](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/add-apfs-volume.png)

    Give the volume a name, set Format to APFS, and click Erase.

    ![Naming the new volume](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-new-volume.png)

When the erase finishes, click **Done**.

![Erase complete](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/erase-done.png)

## Run the installer

Close Disk Utility and open **Install macOS "Sonoma"**.

![Opening the installer](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-instal-macos.png)

Click **Continue**, then **Agree**, then **Agree**.

![Installer step one](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-1.png)
![Installer step two](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-2.png)
![Installer step three](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-3.png)

Select the disk you erased, and click **Continue**.

![Selecting the target disk](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-disk.png)
![Installation starting](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-start.png)
![Installation running](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-middle.png)

At around **12 minutes remaining** the computer restarts into verbose mode.

![The first restart](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart.png)

!!! warning "Which entry to boot after each restart"
    OpenCore creates a boot entry called **OpenCore**, and the machine will use
    it on every restart from now on. Some firmware refuses custom entries - if
    you have another operating system on this computer, select the USB from the
    boot menu at every restart instead.

After the first restart, choose **macOS Installer** in the OpenCore menu.

![Choosing macOS Installer](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart-macos-installer.png)

You get the Apple logo and a time bar, and then another restart.

![The second stage](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-installation.png)
![The second restart](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-restart.png)

Keep choosing **macOS Installer** until that option disappears. On the last
reboot you will see the name you gave the disk - select that.

![Selecting the installed disk](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/last-select-disk.png)

## Set macOS up

Choose your country.

![Selecting a country](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-country.png)

Here the guide clicks **Customize Settings**, because the machine is used in
English while the keyboard and native language are not. If the defaults suit
you, click Continue.

![Language](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-language.png)
![Input source](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input.png)
![Input source, continued](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input-2.png)
![Dictation](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-dictation.png)

Skip accessibility with **Not Now**.

![Accessibility](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/accessibility.png)

!!! danger "Choose *My computer does not connect to the internet*"
    Even if you have a working connection. The serial number, MLB and ROM in
    your config still have to be made your own before this machine talks to
    Apple - see [Post installation](post-installation.md).

![Network setup](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type.png)
![Network setup, continued](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type-2.png)

Click **Continue**.

![Data and privacy](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/data-privacy.png)

Migration Assistant can bring data from another machine. Assuming this is a
first install, click **Not Now**.

![Migration Assistant](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/migration-assistant.png)

Click **Agree**, then **Agree**.

![Terms and conditions](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions.png)
![Terms and conditions, continued](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions-2.png)

Create an account with a name, username and password.

![Creating the account](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/create-account.png)

Location Services, analytics, Screen Time and Siri are all yours to choose.
The guide turns analytics off.

![Location services](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-location.png)
![Analytics](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/analytics.png)
![Screen Time](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/screen-time.png)
![Siri](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-siri.png)
![Siri language](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-language.png)
![Siri voice](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-voice.png)
![Improve Siri and dictation](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/improve-siri-dictation.png)

Pick a theme, and the installation is done.

![Selecting a theme](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-theme.png)

You may get the keyboard setup assistant afterwards. Work through it.

![Keyboard Setup Assistant](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/keyboard-setup-assistant.png)
![Identifying the keyboard](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/identifying-keyboard.png)
![Selecting the keyboard type](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-keyboard-type.png)

And there is the desktop.

![The desktop](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/desktop-2.png)
![The lock screen](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/lock-screen.png)

!!! bug "System Settings or About This Mac crashes when opened"
    Open Terminal and run `sudo purge`.

    ![The crash](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings-crash.png)
    ![Terminal in Spotlight](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/spotlight-terminal.png)
    ![sudo purge](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge.png)
    ![sudo purge, finishing](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge-2.png)
    ![About This Mac](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/about-this-mac.png)
    ![System Settings](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings.png)

[Post installation :material-arrow-right:](post-installation.md){ .md-button .md-button--primary }
