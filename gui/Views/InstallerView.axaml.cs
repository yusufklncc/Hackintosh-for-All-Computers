// Build a whole macOS installer image from an installer app.
//
// The engine does all of it - tools/installer.py - and this pane chooses the
// three paths and draws what it says. Two of the steps need root, and this is
// the only place in the program that asks: the pane says what for, and offers
// the script to read, before the password prompt appears.
//
// macOS only, because createinstallmedia is an Apple binary that ships inside
// the app. On Windows and Linux the pane says so rather than half-working.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Shell.Engine;

namespace Shell.Views;

public partial class InstallerView : UserControl
{
    // createinstallmedia copies twelve gigabytes and blesses the result; on a
    // slow stick that is not quick, and a deadline that cuts it off mid-write
    // leaves an image nobody can use.
    static readonly TimeSpan Bound = TimeSpan.FromHours(2);

    string? _app, _efi, _out;
    Task? _read;

    public InstallerView()
    {
        InitializeComponent();
        Pick.Click += async (_, _) => await ChooseApp();
        PickEfi.Click += async (_, _) => await ChooseEfi();
        PickOut.Click += async (_, _) => await ChooseOut();
        Show.Click += async (_, _) => await ShowScript();
        Build.Click += async (_, _) => await Run();
    }

    public Task Load()
    {
        if (_read is { IsFaulted: true }) _read = null;
        return _read ??= Fill();
    }

    Task Fill()
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
        {
            NotHere.IsVisible = true;
            NotHereWhy.Text =
                "Apple's createinstallmedia is the thing that writes an "
                + "installer, it ships inside the installer app, and it runs "
                + "on macOS only. Everything else in this program works here - "
                + "build the EFI, fetch the recovery, write the stick.";
            return Task.CompletedTask;
        }
        Work.IsVisible = true;
        return Task.CompletedTask;
    }

    /// <summary>What the pane says, for the screenshot pass.</summary>
    public async Task<string> StateForRender()
    {
        await Load();
        return NotHere.IsVisible
            ? "installer: not on this system, and says why"
            : $"installer: ready, app={(_app is null ? "none" : "chosen")}, "
              + $"legacy={Legacy.IsChecked}";
    }

    // An .app is a directory on disk and a *package* to the Finder, which is
    // the whole difficulty: a folder picker greys it out, because macOS does
    // not offer a bundle as a folder to descend into. It has to be offered as
    // a file, and named by the type it is.
    static readonly FilePickerFileType Bundle = new("macOS installer")
    {
        Patterns = new[] { "*.app" },
        AppleUniformTypeIdentifiers = new[] { "com.apple.application-bundle" },
    };

    async Task ChooseApp()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Which installer app? Install macOS ….app",
            AllowMultiple = false,
            FileTypeFilter = new[] { Bundle },
        });
        var path = picked.FirstOrDefault()?.TryGetLocalPath();
        if (path is null) return;

        // Whatever came back, end up on the bundle. A panel that treats
        // packages as directories lets somebody wander into
        // Contents/Resources and pick a file there, and the engine would then
        // be handed a path that is not an app at all.
        _app = Bundled(path);
        AppPath.Text = _app;
        await Sized();
    }

    /// <summary>Ask the engine what this app would take, before anything runs.</summary>
    async Task Sized()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null || _app is null) { Say(missing); return; }

        var (said, complaint) = await Inventory.InstallerPlan(engine, _app);
        if (said is null || !said.Available)
        {
            Plan.IsVisible = true;
            PlanTitle.Text = "That is not an installer app";
            PlanText.Text = said?.Why is { Length: > 0 } why ? why
                          : complaint;
            Build.IsEnabled = false;
            return;
        }
        Plan.IsVisible = true;
        PlanTitle.Text = $"{said.Name} {said.Version}".Trim();
        PlanText.Text =
            $"the app is {Gib(said.App)}\n"
          + $"createinstallmedia wants about {Gib(said.Overhead)} more\n"
          + $"so the image will be {said.Gib} GiB";
        Ready();
    }

    /// <summary>The enclosing .app for a path, or the path unchanged.</summary>
    static string Bundled(string path)
    {
        for (var here = new DirectoryInfo(path); here is not null; here = here.Parent)
            if (here.Name.EndsWith(".app", StringComparison.OrdinalIgnoreCase))
                return here.FullName;
        return path;
    }

    static string Gib(long bytes) => $"{bytes / 1024.0 / 1024 / 1024:0.00} GiB";

    async Task ChooseEfi()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Which EFI folder?",
            AllowMultiple = false,
        });
        var path = picked.FirstOrDefault()?.TryGetLocalPath();
        if (path is null) return;
        _efi = path;
        EfiPath.Text = path;
    }

    async Task ChooseOut()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Where should the image go?",
            SuggestedFileName = "macos-installer.raw",
        });
        var path = picked?.TryGetLocalPath();
        if (path is null) return;
        _out = path;
        OutPath.Text = path;
        Ready();
    }

    void Ready() => Build.IsEnabled = _app is not null && _out is not null;

    /// <summary>The privileged half, to read before approving it.</summary>
    async Task ShowScript()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null || _app is null)
        {
            Script.IsVisible = true;
            Script.Text = _app is null ? "Choose an installer app first." : missing;
            return;
        }
        var (text, complaint) = await Inventory.InstallerScript(engine, _app,
                                                               Legacy.IsChecked == true);
        Script.IsVisible = true;
        Script.Text = text is { Length: > 0 } ? text : complaint;
    }

    async Task Run()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null || _app is null || _out is null) { Say(missing); return; }

        Build.IsEnabled = Pick.IsEnabled = PickEfi.IsEnabled = PickOut.IsEnabled = false;
        Result.IsVisible = true;
        Bar.IsVisible = true;
        ResultTitle.Text = "Building the image…";
        ResultNext.IsVisible = false;

        var said = new List<string>();
        var arguments = new List<string> { "--make-installer", _app,
                                           "--installer-out", _out };
        if (_efi is not null) { arguments.Add("--installer-efi"); arguments.Add(_efi); }
        if (Legacy.IsChecked != true) arguments.Add("--no-legacy");

        var (complaint, code) = await Builder.Stream(engine, line =>
        {
            if (line.Trim().Length == 0) return;
            said.Add(line.TrimEnd());
            ResultText.Text = string.Join("\n", said.TakeLast(10));
        }, Bound, arguments.ToArray());

        Bar.IsVisible = false;
        Build.IsEnabled = Pick.IsEnabled = PickEfi.IsEnabled = PickOut.IsEnabled = true;

        if (code != 0 || !File.Exists(_out))
        {
            ResultTitle.Text = "The image was not built";
            if (complaint is { Length: > 0 }) said.Add(complaint);
            ResultText.Text = string.Join("\n", said.TakeLast(10));
            return;
        }

        var size = new FileInfo(_out).Length;
        ResultTitle.Text = $"{Path.GetFileName(_out)} is ready";
        ResultText.Text = $"{_out}\n{size / 1024.0 / 1024 / 1024:0.0} GiB";
        ResultNext.IsVisible = true;
        ResultNext.Text =
            "It is a flat sector image, so balenaEtcher writes it to a stick "
          + "from Windows, Linux or macOS. The stick has to be at least as big "
          + "as the image - which is more gigabytes than the number here, "
          + "because a stick is sold in decimal GB and this is GiB.";
    }

    void Say(string complaint)
    {
        Result.IsVisible = true;
        Bar.IsVisible = false;
        ResultTitle.Text = "No engine";
        ResultText.Text = complaint;
    }
}
