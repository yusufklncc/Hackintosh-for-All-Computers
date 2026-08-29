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
using Avalonia.Input;
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
    List<string> _found = new();
    Task? _read;

    public InstallerView()
    {
        InitializeComponent();
        Pick.Click += async (_, _) => await ChooseApp();
        Found.SelectionChanged += async (_, _) =>
        {
            var at = Found.SelectedIndex;
            if (at < 0 || at >= _found.Count) return;
            Several.IsVisible = false;
            await Chosen(_found[at]);
        };

        // Dropped, which the note under the box promises and a TextBox does
        // not do on its own. It is also the way that never argues with a file
        // panel about what a package is.
        DragDrop.SetAllowDrop(this, true);
        AddHandler(DragDrop.DragOverEvent, (_, e) =>
        {
            e.DragEffects = e.Data.Contains(DataFormats.Files)
                ? DragDropEffects.Copy : DragDropEffects.None;
        });
        AddHandler(DragDrop.DropEvent, async (_, e) =>
        {
            var dropped = e.Data.GetFiles()?.FirstOrDefault();
            if (dropped is null) return;
            var path = Local(dropped);
            if (path is not null) await Chosen(Bundled(path));
        });
        // a typed or dragged path counts the moment it points at something
        AppPath.LostFocus += async (_, _) => await Typed();
        AppPath.KeyDown += async (_, e) =>
        {
            if (e.Key == Avalonia.Input.Key.Enter) await Typed();
        };
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

    /// <summary>A local path for a picked item, however it can be had.
    ///
    /// TryGetLocalPath is the documented way and returns null for some
    /// providers; the Uri behind it still carries the path, so that is the
    /// second try rather than giving up on it.</summary>
    static string? Local(IStorageItem item)
    {
        var said = item.TryGetLocalPath();
        if (said is { Length: > 0 }) return said;
        try
        {
            var uri = item.Path;
            if (uri is not null && uri.IsFile && uri.LocalPath.Length > 0)
                return uri.LocalPath;
        }
        catch (Exception) { }
        return null;
    }

    async Task Typed()
    {
        var said = (AppPath.Text ?? "").Trim().Trim('\'', '"');
        if (said.Length == 0 || said == _app) return;
        if (!Directory.Exists(said) && !File.Exists(said)) return;
        await Chosen(Bundled(said));
    }

    async Task ChooseApp()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;

        // Not a file picker. An .app is a package, and macOS will not let one
        // be confirmed in a panel that is choosing files - the Open button
        // stays grey however the type filter is written. It will happily
        // choose the folder the app is *in*, so that is what is asked for and
        // the bundle is found here.
        var picked = await top.StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Which folder is the installer in? Applications, say",
            AllowMultiple = false,
        });
        var item = picked.FirstOrDefault();
        if (item is null) return;                 // cancelled, which is fine

        var where = Local(item);
        if (where is null)
        {
            Trouble("That could not be read as a path",
                    $"macOS handed back {item.Name} with no usable location. "
                    + "Drag the app onto this pane, or type its path above.");
            return;
        }

        // the folder itself may be the bundle, if the panel allowed it
        if (where.EndsWith(".app", StringComparison.OrdinalIgnoreCase))
        {
            await Chosen(where);
            return;
        }

        var found = Installers(where);
        if (found.Count == 0)
        {
            Trouble("No installer app in there",
                    $"{where} holds no Install macOS ….app. The app is usually "
                    + "in /Applications, or wherever Mist or softwareupdate "
                    + "left it. You can also drag it onto this pane.");
            return;
        }
        if (found.Count == 1)
        {
            await Chosen(found[0]);
            return;
        }
        // more than one: offer them, because naming them and stopping is a
        // dead end - somebody has to be able to say which
        Offer(found);
    }

    /// <summary>Put the ones found in front of somebody to choose from.</summary>
    void Offer(List<string> found)
    {
        // the paths are kept here rather than closed over: subscribing inside
        // this method stacks a handler every time a folder is chosen, and the
        // second choice would then fire the first one's list too
        _found = found;
        Several.IsVisible = true;
        Found.ItemsSource = found.Select(Path.GetFileName).ToList();
        Found.SelectedIndex = -1;
        Plan.IsVisible = true;
        PlanTitle.Text = $"{found.Count} installers in that folder";
        PlanText.Text = "Pick the one to build from.";
        Build.IsEnabled = false;
    }

    /// <summary>The installer apps directly inside a folder.
    ///
    /// By what makes one - a createinstallmedia inside it - rather than by the
    /// name, which is localised and has the version stuck on the end.</summary>
    static List<string> Installers(string folder)
    {
        var out_ = new List<string>();
        try
        {
            foreach (var entry in Directory.EnumerateDirectories(folder, "*.app"))
                if (File.Exists(Path.Combine(entry, "Contents", "Resources",
                                             "createinstallmedia")))
                    out_.Add(entry);
        }
        catch (Exception) { }
        out_.Sort(StringComparer.OrdinalIgnoreCase);
        return out_;
    }

    void Trouble(string title, string body)
    {
        Plan.IsVisible = true;
        PlanTitle.Text = title;
        PlanText.Text = body;
        Build.IsEnabled = false;
    }

    /// <summary>Ask the engine what this app would take, before anything runs.</summary>
    async Task Sized()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null || _app is null) { Say(missing); return; }

        var (said, complaint) = await Inventory.InstallerPlan(engine, _app);
        if (said is null)
        {
            // The app may be perfectly good and the answer unreadable, and
            // saying "that is not an installer app" about a JSON fault sends
            // somebody looking at the wrong thing. It did.
            Trouble("The engine's answer could not be read", complaint);
            return;
        }
        if (!said.Available)
        {
            Trouble("That is not an installer app",
                    said.Why is { Length: > 0 } why ? why : complaint);
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

    /// <summary>Take a path, from the picker, a drop or typed, and read it.</summary>
    async Task Chosen(string path)
    {
        Several.IsVisible = false;
        _app = path;
        AppPath.Text = path;
        await Sized();
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
