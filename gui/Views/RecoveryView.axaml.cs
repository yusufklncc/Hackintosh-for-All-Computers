// Fetch Apple's recovery installer onto the stick.
//
// The engine does the whole thing - it drives OpenCore's own macrecovery and
// verifies what lands against Apple's chunklist. This pane chooses which macOS
// and where, and shows the tool's own progress while it runs.
//
// It is the only pane that opens a connection, so it says so, and it does
// nothing until somebody presses the button.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Shell.Engine;

namespace Shell.Views;

public partial class RecoveryView : UserControl
{
    // an hour. A 700 MB image over a slow line is not a hang, and the deadline
    // is here so a stalled one still ends with a sentence rather than a window
    // that waits for ever.
    static readonly TimeSpan Bound = TimeSpan.FromHours(1);

    string _to = AppContext.BaseDirectory;
    string _folder = "com.apple.recovery.boot";
    Task? _read;

    public RecoveryView()
    {
        InitializeComponent();
        Where.Text = _to;
        Target.Text = "The drive, not the EFI folder: OpenCore looks for "
                    + $"{_folder} next to EFI, at the root of the partition.";
        // the row with no version has something to say about itself
        Which.SelectionChanged += (_, _) =>
        {
            var picked = Which.SelectedItem as RecoveryChoice;
            var note = picked?.Note ?? "";
            Chosen.Text = note;
            Chosen.IsVisible = note.Length > 0;
            // the offer to ask belongs to the row that cannot name itself
            // the row is named from data/mac.toml when the pane opens; this
            // offers to check that against Apple rather than to fill a blank
            AskRow.IsVisible = picked is { Version: "latest" };
        };
        Ask.Click += async (_, _) => await AskApple();
        Choose.Click += async (_, _) => await Pick();
        Fetch.Click += async (_, _) => await Get();
        Open.Click += (_, _) => Reveal.Show(Path.Combine(_to, _folder));
    }

    /// <summary>Read the list once, when the pane is first opened.
    ///
    /// The list needs no network: it is macrecovery's own board table, which
    /// travels with the OpenCore release.</summary>
    // One read, and everybody waits for the same one. A bool guard let the
    // second caller past while the first was still awaiting: the nav's own
    // handler starts a Swap of its own, so two arrive together, and the second
    // returned to a pane that had not been filled yet. The screenshot pass
    // caught it on an empty list.
    public Task Load()
    {
        // and a read that threw is not a read: keeping the faulted task would
        // make every later look at this pane raise the same old exception
        if (_read is { IsFaulted: true }) _read = null;
        return _read ??= Fill();
    }

    async Task Fill()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Provenance.Text = missing; Fetch.IsEnabled = false; return; }

        var (list, complaint) = await Inventory.Recoveries(engine);
        if (list is null || !list.Available)
        {
            Provenance.Text = complaint is { Length: > 0 } said ? said
                            : "no macrecovery is vendored, so there is nothing to drive";
            Fetch.IsEnabled = false;
            return;
        }
        _folder = list.Folder;
        Which.ItemsSource = list.Choices;
        Which.SelectedIndex = 0;
        SayNetwork(list);
        Provenance.Text = $"{list.Choices.Count} of them, read from macrecovery's own "
                        + "boards.json, which records the newest macOS Apple offers "
                        + "each board. The board is what the request is made with.";
    }

    /// <summary>Whether the machine being installed can finish this at all.
    ///
    /// The engine reads it off the hardware report; this only draws it. A
    /// verdict of "cable" is the one worth the space - Wi-Fi with no driver
    /// and Ethernet with one is a common laptop, recovery works on it, and the
    /// only thing missing is knowing to plug the cable in first.</summary>
    void SayNetwork(RecoveryList list)
    {
        if (list.Network is not { Length: > 0 } verdict) return;
        var (word, style) = verdict switch
        {
            "ready"   => ("This machine can download during the install", "ok"),
            "cable"   => ("Use an Ethernet cable for the install", "warn"),
            "no"      => ("Recovery cannot finish on this machine", "bad"),
            _         => ("Not known for this machine", "warn"),
        };
        NetworkState.Text = word;
        NetworkNote.Text = list.NetworkNote;
        Network.Classes.Set("ok", style == "ok");
        Network.Classes.Set("warn", style == "warn");
        Network.Classes.Set("bad", style == "bad");
        Network.IsVisible = true;
        // a machine that cannot download is not stopped from fetching - the
        // stick may be for a different computer than the one making it
        _blocked = verdict == "no";
    }

    bool _blocked;

    /// <summary>What the pane says, for the screenshot pass.
    ///
    /// The pass lists and stops. Pressing this button would put 700 MB of
    /// somebody else's bandwidth through a build machine on every run, and
    /// what it would prove is that Apple was up.</summary>
    public async Task<string> ListForRender()
    {
        await Load();
        var choices = Which.ItemsSource as IEnumerable<RecoveryChoice>;
        var named = choices?.Select(c => c.Titled).ToList() ?? new List<string>();
        return named.Count == 0
            ? $"no recoveries listed: {Provenance.Text}"
            : $"{named.Count} recoveries, newest {named[0]}, into {_folder}"
              + $", network {(Network.IsVisible ? NetworkState.Text : "not said")}"
              + $", marks {named.Count(_ => true)}";
    }

    /// <summary>Name the unnamed row, from Apple.
    ///
    /// The board table records those boards as `latest` and stops there, so
    /// the row reads "Whatever Apple serves now" and everybody asks the same
    /// question about it. Apple's own device-management metadata answers it.
    /// Nothing calls this on its own: it opens a connection.</summary>
    async Task AskApple()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Answered.Text = missing; return; }

        Ask.IsEnabled = false;
        Answered.Text = "asking Apple…";
        var (said, complaint) = await Inventory.Newest(engine);
        Ask.IsEnabled = true;

        if (said is null)
        {
            Answered.Text = complaint is { Length: > 0 } ? complaint
                          : "Apple did not answer";
            return;
        }

        // relabel the row in place. The version stays `latest` - that is what
        // the download is asked for, and what Apple serves it may have moved
        // on by the time the button is pressed again.
        if (Which.ItemsSource is List<RecoveryChoice> rows)
        {
            var row = rows.FirstOrDefault(r => r.Version == "latest");
            if (row is not null)
            {
                row.ArtName = said.Name;
                row.Label = said.Name is { Length: > 0 }
                          ? $"{said.Name} {said.Version}" : said.Version;
                row.Mark = said.Mark;
                var at = Which.SelectedIndex;
                Which.ItemsSource = null;
                Which.ItemsSource = rows;
                Which.SelectedIndex = at;
            }
        }
        Answered.Text = $"Apple is serving {said.Name} {said.Version} today. "
                      + "The row still asks for whatever is newest when you "
                      + "press download, not for this number.";
    }

    async Task Pick()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Which drive? Pick the root of it, not the EFI folder.",
            AllowMultiple = false,
        });
        var path = picked.FirstOrDefault()?.TryGetLocalPath();
        if (path is null) return;
        _to = path;
        Where.Text = _to;
    }

    async Task Get()
    {
        if (Which.SelectedItem is not RecoveryChoice choice) return;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Show("No engine", missing, null); return; }

        Fetch.IsEnabled = Choose.IsEnabled = false;
        Open.IsVisible = false;
        Show($"Fetching {choice.Titled} from Apple…", "", null);

        var said = new List<string>();
        var (complaint, code) = await Builder.Stream(engine, line =>
        {
            if (line.Trim().Length == 0) return;
            said.Add(line.TrimEnd());
            // the tool redraws one progress line; the last few are what
            // somebody watching wants, not all seven hundred
            ResultText.Text = string.Join("\n", said.TakeLast(6));
        }, Bound, "--recovery", choice.Version, "--recovery-to", _to);
        Fetch.IsEnabled = Choose.IsEnabled = true;

        var landed = Path.Combine(_to, _folder);
        var files = Directory.Exists(landed)
            ? new DirectoryInfo(landed).GetFiles().OrderBy(f => f.Name).ToList()
            : new List<FileInfo>();
        if (code != 0 || files.Count == 0)
        {
            Show("Nothing was fetched",
                 complaint is { Length: > 0 } ? complaint : string.Join("\n", said.TakeLast(8)),
                 null);
            return;
        }
        Open.IsVisible = true;
        Show($"{choice.Titled} is on the stick",
             string.Join("\n", files.Select(f => $"{f.Name}  {f.Length / 1024.0 / 1024:0.0} MB")),
             $"It sits in {_folder} at the root of {_to}. OpenCore lists it at the "
             + "boot menu. The rest of macOS comes down during the install, so that "
             + "machine needs Ethernet or a card macOS already drives.");
    }

    void Show(string title, string body, string? next)
    {
        Result.IsVisible = true;
        ResultTitle.Text = title;
        ResultText.Text = body;
        ResultNext.Text = next ?? "";
        ResultNext.IsVisible = next is not null;
    }
}
