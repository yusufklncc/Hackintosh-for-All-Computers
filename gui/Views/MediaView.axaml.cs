// The USB stick: which way macOS gets onto it, which macOS, which stick.
//
// The three panes this replaced still do the work - RecoveryView fetches and
// shows the network verdict, StickView finds and erases sticks, InstallerView
// makes the image - each in an embedded mode with its own heading and buttons
// hidden. What this adds is the order, and the one button that runs a way to
// the end: a recovery downloaded straight onto the stick instead of into a
// folder that then has to be copied there.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

/// <summary>One way of getting macOS onto the stick, as a tile.</summary>
public sealed class Way
{
    public string Key { get; init; } = "";
    public string Title { get; init; } = "";
    public string Cost { get; init; } = "";
    public bool Recommended { get; set; }
    public bool Available { get; init; } = true;
    public double Dim => Available ? 1.0 : 0.5;
}

public partial class MediaView : UserControl
{
    // a full installer is 6 to 19 GB; on a slow line that is hours, not a hang
    static readonly TimeSpan Long = TimeSpan.FromHours(8);

    readonly List<Way> _ways =
    [
        new() { Key = "recovery", Title = "Recovery",
                Cost = "About 700 MB. The rest of macOS downloads during the install, "
                     + "so that machine needs a network card macOS drives." },
        new() { Key = "offline", Title = "No network",
                Cost = "Apple's whole installer, 6 to 19 GB, and UnPlugged to start it. "
                     + "Installs with no connection. 16 GB stick or more." },
        new() { Key = "image", Title = "Installer image",
                Cost = OperatingSystem.IsMacOS()
                    ? "From an Install macOS app, with legacy BIOS boot. Makes an image "
                    + "balenaEtcher writes to any stick."
                    : "Needs a Mac: it runs Apple's createinstallmedia.",
                Available = OperatingSystem.IsMacOS() },
    ];

    Task? _loaded;
    Task? _catalog;

    public MediaView()
    {
        InitializeComponent();
        Recovery.Embed();
        Image.Embed();
        Stick.Embed();
        Ways.ItemsSource = _ways;
        Ways.SelectedIndex = 0;
        Ways.SelectionChanged += async (_, _) => await Switch();
        Recovery.Changed += Ready;
        Stick.Changed += Ready;
        Build.SelectionChanged += (_, _) => { NoteBuild(); Ready(); };
        Go.Click += async (_, _) => await Run();
    }

    string Chosen => (Ways.SelectedItem as Way)?.Key ?? "recovery";

    public Task Load()
    {
        if (_loaded is { IsFaulted: true }) _loaded = null;
        return _loaded ??= Fill();
    }

    async Task Fill()
    {
        await Task.WhenAll(Recovery.Load(), Stick.Load());
        Recommend();
        await Switch();
    }

    /// <summary>The machine the Machine pane shows has changed: judge again.</summary>
    public async Task MachineChanged()
    {
        await Recovery.Reload();
        Recommend();
    }

    /// <summary>Mark the way this machine's network makes sensible.
    ///
    /// The recovery pane always knew whether the machine being installed could
    /// download during the install, and said so under a button that downloads
    /// anyway. The answer belongs before the choice it decides.</summary>
    void Recommend()
    {
        var verdict = Recovery.Verdict;
        foreach (var w in _ways)
            w.Recommended = (w.Key, verdict) switch
            {
                ("recovery", "ready" or "cable") => true,
                ("offline", "no") => true,
                _ => false,
            };
        var at = Ways.SelectedIndex;
        Ways.ItemsSource = null;
        Ways.ItemsSource = _ways;
        // the first look lands on the recommended way; after that, the choice
        // somebody made stands
        Ways.SelectedIndex = _switched ? at
                           : Math.Max(0, _ways.FindIndex(w => w.Recommended));
        WayNote.Text = verdict switch
        {
            "ready" => "This machine has a network card macOS drives, so recovery can finish.",
            "cable" => "Recovery works on this machine over an Ethernet cable: its Wi-Fi has no macOS driver.",
            "no" => "Nothing on this machine connects under macOS, so recovery would boot "
                  + "and then have nothing to download with. The no-network way is the one that finishes.",
            _ => "Whether this machine can download during the install is not known. "
               + "Open its report on the Machine pane to find out.",
        };
    }

    bool _switched;

    async Task Switch()
    {
        var way = Chosen;
        _switched = _loaded is not null;
        Step2.Text = way == "image" ? "2 · FROM WHICH INSTALLER APP" : "2 · WHICH MACOS";
        Recovery.IsVisible = way == "recovery";
        Offline.IsVisible = way == "offline";
        Image.IsVisible = way == "image";
        // the image is a file balenaEtcher writes; it has no stick of its own
        Step3.IsVisible = Stick.IsVisible = GoRow.IsVisible = way != "image";
        Stick.OfflineLayout = way == "offline";
        if (way == "image") await Image.Load();
        if (way == "offline") await LoadCatalog();
        Ready();
    }

    Task LoadCatalog() => _catalog is { IsFaulted: false } ? _catalog : _catalog = FillCatalog();

    async Task FillCatalog()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { BuildNote.Text = missing; return; }
        BuildNote.Text = "Reading Apple's catalog…";
        var (list, complaint) = await Inventory.Offline(engine);
        if (list is null) { BuildNote.Text = complaint; _catalog = null; return; }
        Build.ItemsSource = list.Macos;
        Build.SelectedIndex = list.Macos.Count > 0 ? 0 : -1;
        NoteBuild();
    }

    void NoteBuild()
    {
        BuildNote.Text = Build.SelectedItem is OfflineChoice c
            ? $"{c.Detail}. Every build Apple still serves for Intel Macs is listed."
            : "";
    }

    /// <summary>Whether the button can do its job, and if not, why not.</summary>
    void Ready()
    {
        var stick = Stick.Selected;
        (bool ok, string why) = Chosen switch
        {
            "recovery" when Recovery.Selected is null => (false, "Pick a macOS above."),
            "recovery" when stick is null => (false, "Plug in a stick and pick it."),
            "recovery" when !stick.Ready => (false, "That stick has to be erased first - below its name."),
            "recovery" => (true, $"Downloads {Recovery.Selected!.Titled} straight onto "
                               + $"{stick.Where} and copies the EFI beside it."),
            "offline" when Build.SelectedItem is null => (false, "Pick a macOS above."),
            "offline" when stick is null => (false, "Plug in a stick and pick it."),
            "offline" when stick.Fat is not { Length: > 0 } || stick.Exfat is not { Length: > 0 }
                => (false, $"{stick.OfflineWhy}."),
            "offline" => (true, $"OpenCore and the recovery go on {stick.Fat}; the installer "
                              + $"and UnPlugged.command on {stick.Exfat}."),
            _ => (false, ""),
        };
        Go.IsEnabled = ok;
        GoNote.Text = why;
    }

    async Task Run()
    {
        var stick = Stick.Selected;
        if (stick is null) return;
        Go.IsEnabled = false;
        try
        {
            if (Chosen == "recovery") await RunRecovery(stick);
            else if (Chosen == "offline") await RunOffline(stick);
        }
        finally
        {
            Ready();
        }
    }

    async Task RunRecovery(Stick stick)
    {
        // the recovery pane draws its own progress; it is visible above
        if (!await Recovery.FetchTo(stick.Where)) return;
        if (!await Stick.PlaceEfi()) return;
        Stick.Say($"{stick.Name} is ready",
                  $"{Recovery.Selected!.Titled} and the EFI are on {stick.Where}.",
                  "Boot the machine from it and pick the recovery entry. The rest of "
                  + "macOS downloads during the install.");
    }

    async Task RunOffline(Stick stick)
    {
        if (Build.SelectedItem is not OfflineChoice choice) return;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Stick.Say("No engine", missing, null); return; }
        Stick.Say($"Putting {choice.Titled} on {stick.Name}…", "", null);
        var said = new List<string>();
        var (complaint, code) = await Builder.Stream(engine, line =>
        {
            if (line.Trim().Length == 0) return;
            said.Add(line.TrimEnd());
            Stick.Say($"Putting {choice.Titled} on {stick.Name}…",
                      string.Join("\n", said.TakeLast(8)), null);
        }, Long, "--usb-offline", choice.Build, "--usb-fat", stick.Fat!,
           "--usb-exfat", stick.Exfat!, "--out", Stick.Efi);
        if (code != 0)
        {
            Stick.Say("The stick is not finished",
                      complaint is { Length: > 0 } ? complaint : string.Join("\n", said.TakeLast(12)),
                      "Press the button again: what was downloaded is kept and it carries on.");
            return;
        }
        Stick.Say($"{stick.Name} installs {choice.Name} with no network",
                  string.Join("\n", said.TakeLast(6)),
                  string.Join("\n", choice.Steps.Select((s, i) => $"{i + 1}. {s}")));
    }

    // --- for the screenshot pass -------------------------------------------

    public Task<string> ListRecoveries() => Show("recovery", Recovery.ListForRender);
    public Task<string> InstallerState() => Show("image", Image.StateForRender);
    public Task<string> ListSticks() => Show("recovery", Stick.ListForRender);

    async Task<string> Show(string way, Func<Task<string>> then)
    {
        await Load();
        Ways.SelectedIndex = _ways.FindIndex(w => w.Key == way);
        await Switch();
        return await then();
    }
}
