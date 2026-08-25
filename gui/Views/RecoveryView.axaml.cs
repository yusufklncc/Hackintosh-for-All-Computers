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
    bool _read;

    public RecoveryView()
    {
        InitializeComponent();
        Where.Text = _to;
        Target.Text = "The drive, not the EFI folder: OpenCore looks for "
                    + $"{_folder} next to EFI, at the root of the partition.";
        Choose.Click += async (_, _) => await Pick();
        Fetch.Click += async (_, _) => await Get();
        Open.Click += (_, _) => Reveal.Show(Path.Combine(_to, _folder));
    }

    /// <summary>Read the list once, when the pane is first opened.
    ///
    /// The list needs no network: it is macrecovery's own board table, which
    /// travels with the OpenCore release.</summary>
    public async Task Load()
    {
        if (_read) return;
        _read = true;
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
        Provenance.Text = $"{list.Choices.Count} of them, read from macrecovery's own "
                        + "boards.json. The version is the newest Apple offers that "
                        + "board, and the board is what the request is made with.";
    }

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
            : $"{named.Count} recoveries, newest {named[0]}, into {_folder}";
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
