// The USB stick: what to write, and where.
//
// The engine finds the disks and does the writing. This pane is the picking
// and the asking - and the asking matters, because erasing is the only thing
// this program does that cannot be undone.
//
// What actually stops the wrong disk is not the question in front of it: the
// engine refuses any device its own list did not offer, checked again at the
// moment it runs. The question is here so nobody is surprised.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Shell.Engine;

namespace Shell.Views;

public partial class StickView : UserControl
{
    // copying 900 MB to a slow stick is not a hang
    static readonly TimeSpan Bound = TimeSpan.FromMinutes(30);

    string _efi = Path.Combine(AppContext.BaseDirectory, "EFI");
    string _recovery = AppContext.BaseDirectory;
    string _folder = "com.apple.recovery.boot";
    bool _erasable;
    Task? _loaded;

    public StickView()
    {
        InitializeComponent();
        EfiFrom.Text = _efi;
        RecoveryFrom.Text = _recovery;
        Again.Click += async (_, _) => { _loaded = null; await Load(); };
        PickEfi.Click += async (_, _) => await Pick(true);
        PickRecovery.Click += async (_, _) => await Pick(false);
        Copy.Click += async (_, _) => await CopyOn();
        Erase.Click += async (_, _) => await EraseIt();
        Which.SelectionChanged += (_, _) => Describe();
        // the button turns on only when what is typed is the disk that is
        // selected. A checkbox would be a habit; this has to be read.
        Typed.TextChanged += (_, _) =>
            Erase.IsEnabled = _erasable
                && Which.SelectedItem is Stick s
                && Typed.Text?.Trim() == s.Device;
        Open.Click += (_, _) =>
        {
            if (Which.SelectedItem is Stick s && s.Where.Length > 0) Reveal.Show(s.Where);
        };
    }

    public Task Load()
    {
        if (_loaded is { IsFaulted: true }) _loaded = null;
        return _loaded ??= Fill();
    }

    async Task Fill()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Found.Text = missing; Copy.IsEnabled = false; return; }

        var (list, complaint) = await Inventory.Sticks(engine);
        if (list is null)
        {
            Found.Text = complaint;
            Copy.IsEnabled = false;
            return;
        }
        _folder = list.Recovery;
        _erasable = list.Erasable;
        Which.ItemsSource = list.Sticks;
        Which.SelectedIndex = list.Sticks.Count > 0 ? 0 : -1;
        Copy.IsEnabled = list.Sticks.Count > 0;
        Found.Text = list.Sticks.Count switch
        {
            0 => "No removable disk is plugged in. This only ever lists removable, "
               + "external, physical disks, and never the one this computer booted "
               + $"from{(list.Booted is { } b ? $" ({b})" : "")}.",
            1 => "One, and it is not the disk this computer booted from.",
            var n => $"{n} of them. The disk this computer booted from is not among "
                   + "them and cannot be.",
        };
        Describe();
    }

    /// <summary>What the pane found, for the screenshot pass.</summary>
    public async Task<string> ListForRender()
    {
        await Load();
        var sticks = Which.ItemsSource as IEnumerable<Stick>;
        var count = sticks?.Count() ?? 0;
        return $"{count} sticks, erasable={_erasable}, into {_folder}";
    }

    void Describe()
    {
        if (Which.SelectedItem is not Stick stick)
        {
            EraseBox.IsVisible = false;
            Open.IsVisible = false;
            return;
        }
        EraseBox.IsVisible = true;
        Open.IsVisible = stick.Where.Length > 0;
        EraseWhat.Text = $"This erases everything on {stick.Name}, {stick.Size} "
                       + $"({stick.Device})"
                       + (stick.Where.Length > 0 ? $", mounted at {stick.Where}." : ".")
                       + " There is no undoing it.";
        EraseHow.Text = _erasable
            ? "It becomes one FAT32 partition under GPT, which is what OpenCore "
            + "boots from. Type the disk name to turn the button on."
            : "This system cannot do it from here - it needs a root or "
            + "administrator the engine does not have. Press it anyway and the "
            + "exact commands to run yourself are printed below.";
        EraseAsk.IsVisible = true;
        Erase.IsEnabled = false;
        Typed.Text = "";
        if (!_erasable) Erase.IsEnabled = true;
    }

    async Task Pick(bool efi)
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = efi ? "Which EFI folder?"
                        : $"Which folder holds {_folder}?",
            AllowMultiple = false,
        });
        var path = picked.FirstOrDefault()?.TryGetLocalPath();
        if (path is null) return;
        if (efi) { _efi = path; EfiFrom.Text = path; }
        else { _recovery = path; RecoveryFrom.Text = path; }
    }

    async Task CopyOn()
    {
        if (Which.SelectedItem is not Stick stick) return;
        if (stick.Where.Length == 0)
        {
            Show("That stick is not mounted",
                 $"{stick.Device} has no mounted volume, so there is nowhere to "
                 + "copy to. Format it first, or mount it.", null);
            return;
        }
        var engine = Builder.Find(out var missing);
        if (engine is null) { Show("No engine", missing, null); return; }

        Copy.IsEnabled = false;
        Show($"Copying onto {stick.Name}…", "", null);
        var said = new List<string>();
        var (complaint, code) = await Builder.Stream(engine, line =>
        {
            if (line.Trim().Length == 0) return;
            said.Add(line.TrimEnd());
            ResultText.Text = string.Join("\n", said.TakeLast(8));
        }, Bound, "--usb-place", stick.Where, "--out", _efi,
           "--recovery-from", _recovery);
        Copy.IsEnabled = true;

        if (code != 0)
        {
            Show("Nothing was copied",
                 complaint is { Length: > 0 } ? complaint : string.Join("\n", said), null);
            return;
        }
        Show($"{stick.Name} is ready", string.Join("\n", said),
             $"Boot the machine from it. OpenCore's picker lists macOS Base System "
             + "if the installer is on there; the rest of macOS comes down during "
             + "the install, so that machine needs Ethernet or a card macOS drives.");
    }

    async Task EraseIt()
    {
        if (Which.SelectedItem is not Stick stick) return;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Show("No engine", missing, null); return; }

        Erase.IsEnabled = false;
        Show($"Erasing {stick.Name}…", "", null);
        var said = new List<string>();
        var (complaint, code) = await Builder.Stream(engine, line =>
        {
            if (line.Trim().Length == 0) return;
            said.Add(line.TrimEnd());
            ResultText.Text = string.Join("\n", said.TakeLast(8));
        }, Bound, "--usb-prepare", stick.Device);

        if (code != 0)
        {
            Show("It was not erased",
                 complaint is { Length: > 0 } ? complaint : string.Join("\n", said),
                 null);
            Typed.Text = "";
            return;
        }
        Show($"{stick.Name} is formatted", string.Join("\n", said),
             "Now copy the EFI and the installer onto it.");
        Typed.Text = "";
        _loaded = null;
        await Load();                      // it has a new mount point now
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
