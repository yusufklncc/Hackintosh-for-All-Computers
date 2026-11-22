// What the program is, counted from the tree rather than remembered.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed record CountItem(string Name, string Value);

public sealed class ToolItem
{
    public ToolItem(ToolRow row)
    {
        Path = row.Path;
        Upstream = row.Upstream ?? "no upstream recorded";
        Licence = row.Licence ?? "unread";
        Note = row.Note ?? "";
        HasNote = Note.Length > 0;
    }

    public string Path { get; }
    public string Upstream { get; }
    public string Licence { get; }
    public string Note { get; }
    public bool HasNote { get; }
}

public sealed class SourceItem
{
    public SourceItem(SourceRow row)
    {
        Area = row.Area;
        Kind = row.Kind;
        Source = row.Source;
        Covers = $"{row.Count} · {row.Covers}";
        Gap = row.Gap;
        HasGap = row.Gap.Length > 0;
        // derived beats quoted beats reported, and "none" is the one worth
        // colouring like a problem, because it is one
        IsDerived = row.Kind is "derived" or "measured";
        IsWeak = row.Kind is "quoted" or "reported";
        IsNone = row.Kind == "none";
    }

    public string Area { get; }
    public string Kind { get; }
    public string Source { get; }
    public string Covers { get; }
    public string Gap { get; }
    public bool HasGap { get; }
    public bool IsDerived { get; }
    public bool IsWeak { get; }
    public bool IsNone { get; }
}

public partial class AboutView : UserControl
{
    Task? _loaded;

    public AboutView()
    {
        InitializeComponent();
        BuildLine.Text = Updater.Describe();
        CheckAtStart.IsChecked = Updater.Settings.CheckAtStart;
        CheckAtStart.IsCheckedChanged += (_, _) =>
            Updater.Settings = new UpdateSettings { CheckAtStart = CheckAtStart.IsChecked == true };
        CheckNow.Click += async (_, _) => await CheckForUpdate(quiet: false);
        InstallUpdate.Click += async (_, _) => await Install();
        OpenReleases.Click += async (_, _) =>
        {
            if (Avalonia.Controls.TopLevel.GetTopLevel(this) is { } top)
                try { await top.Launcher.LaunchUriAsync(new Uri(Updater.ReleasePage)); }
                catch (Exception) { }
        };
    }

    UpdateInfo? _newer;

    /// <summary>Raised when a newer build is found, for the sidebar.</summary>
    public event Action? UpdateFound;

    /// <summary>Ask the release whether it has a newer build. Quiet is the
    /// check at start: it says nothing unless there is something to say.</summary>
    public async Task CheckForUpdate(bool quiet)
    {
        if (!quiet) UpdateBusy.Say("Asking GitHub for the newest build…");
        var (newer, said) = await Updater.Check();
        UpdateBusy.Say(null);
        _newer = newer;
        if (newer is not null || !quiet) UpdateSaid.Text = newer is null ? said
            : $"{said} What changed:\n" + string.Join("\n", newer.Summary.Take(8).Select(s => "  " + s));
        InstallUpdate.IsVisible = newer is not null && Updater.Plan().asset is not null;
        if (newer is not null) UpdateFound?.Invoke();
    }

    async Task Install()
    {
        if (_newer is null) return;
        InstallUpdate.IsEnabled = CheckNow.IsEnabled = false;
        UpdateBar.IsVisible = true;
        UpdateBusy.Say($"Downloading {_newer.Tag}…");
        var (script, complaint) = await Updater.Stage(_newer, (done, total) =>
            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
            {
                UpdateBar.Value = total > 0 ? done * 100.0 / total : 0;
                UpdateSaid.Text = $"{done / 1e6:0.0} of {total / 1e6:0.0} MB";
            }));
        UpdateBusy.Say(null);
        UpdateBar.IsVisible = false;
        InstallUpdate.IsEnabled = CheckNow.IsEnabled = true;
        if (script is null)
        {
            UpdateSaid.Text = complaint;
            return;
        }
        UpdateSaid.Text = "Checked against the release. The program closes, swaps itself and opens again.";
        if (!Updater.Launch(script))
        {
            UpdateSaid.Text = "The swap could not be started. The release page has the new package.";
            return;
        }
        await Task.Delay(600);
        if (Avalonia.Application.Current?.ApplicationLifetime is
            Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
            desktop.Shutdown();
    }

    // One read, and everybody waits for the same one. A bool guard let the
    // second caller past while the first was still awaiting: the nav's own
    // handler starts a Swap of its own, so two arrive together, and the second
    // returned to a pane that had not been filled yet. The screenshot pass
    // caught it on an empty list.
    public Task Load()
    {
        // and a read that threw is not a read: keeping the faulted task would
        // make every later look at this pane raise the same old exception
        if (_loaded is { IsFaulted: true }) _loaded = null;
        return _loaded ??= Fill();
    }

    async Task Fill()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Tally.Text = missing; return; }

        Reading.Say("Reading where every answer comes from…");
        var (about, complaint) = await Inventory.Facts(engine);
        Reading.Say(null);
        if (about is null) { Tally.Text = complaint; return; }

        Counts.ItemsSource = new List<CountItem>
        {
            new("OPENCORE", about.OpenCore ?? "unknown"),
            new("CONFIGS", about.Configs.ToString()),
            new("KEXTS", about.Kexts.ToString()),
            new("SOURCES", about.Sources.Count.ToString()),
            new("NETWORK", about.Network is null ? "never" : "when asked"),
        };

        // counted, not asserted. It used to say "both ACPI tools" while nine
        // programs travelled in the package.
        Offline.Text = "Nothing here reaches the network while it runs. The machine "
                     + "an EFI is prepared on is usually the machine about to be "
                     + $"replaced, and it is often not online - so {about.Kexts} kexts, "
                     + $"{about.Configs} configs and {about.Tools.Count} whole programs "
                     + "travel inside it. The tables below were fetched once, by the "
                     + "tool named beside each, and committed."
                     + (about.Network is { } once
                        ? $" The one thing that does open a connection is {once}."
                        : "");
        Licence.Text = (about.Licence is { } licence ? licence + ". " : "")
                     + (about.Repo ?? "");
        Tools.ItemsSource = about.Tools.Select(t => new ToolItem(t)).ToList();

        // the order is the order of how much a claim is worth
        var order = new[] { "derived", "measured", "quoted", "reported", "none" };
        var said = order.Where(k => about.Tally.ContainsKey(k))
                        .Select(k => $"{about.Tally[k]} {k}");
        Tally.Text = $"{string.Join(", ", said)}. Derived means it was read out of the "
                   + "thing itself - a kext's own matching rules, the profile tree. "
                   + "Quoted means a sentence from a document. Reported means somebody "
                   + "ran it and said what happened. None means this repository has no "
                   + "source for it and says so rather than guessing.";
        // weakest first. A page whose subject is where the answers come from
        // should open on the ones that came from nowhere, not bury them at
        // twenty-two of twenty-six.
        var weight = new Dictionary<string, int>
        {
            ["none"] = 0, ["reported"] = 1, ["quoted"] = 2,
            ["measured"] = 3, ["derived"] = 4,
        };
        Sources.ItemsSource = about.Sources
            .OrderBy(s => weight.GetValueOrDefault(s.Kind, 9))
            .ThenBy(s => s.Area, StringComparer.OrdinalIgnoreCase)
            .Select(s => new SourceItem(s)).ToList();
    }
}
