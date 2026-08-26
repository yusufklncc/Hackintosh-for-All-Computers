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
        {
            var want = (Which.SelectedItem as Stick)?.Device ?? "";
            var typed = Typed.Text?.Trim() ?? "";
            Erase.IsEnabled = _erasable && want.Length > 0 && typed == want;
            // and say what is wrong, rather than leaving a grey button
            TypedHint.Text = typed.Length == 0 || Erase.IsEnabled ? ""
                           : $"that is not {want}";
        };
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
        // the one that is ready, if any: a person with two sticks in wants the
        // one they do not have to erase
        var ready = list.Sticks.FindIndex(s => s.Ready);
        Which.SelectedIndex = list.Sticks.Count == 0 ? -1 : ready >= 0 ? ready : 0;
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

    /// <summary>What the pane found, for the screenshot pass.
    ///
    /// And then what it draws for a stick that is not there. A build machine
    /// has no USB in it, so a real run only ever exercises the empty list -
    /// and the path that draws a disk is the one that took the whole program
    /// down when a resource lookup handed back UnsetValue.</summary>
    public async Task<string> ListForRender()
    {
        await Load();
        var sticks = Which.ItemsSource as IEnumerable<Stick>;
        var all = sticks?.ToList() ?? new List<Stick>();
        var ready = all.Count(s => s.Ready);
        var drawn = Rehearse();
        return $"{all.Count} sticks, {ready} ready, erasable={_erasable}, "
             + $"into {_folder}, drew {drawn}";
    }

    /// <summary>Select a made-up stick of each kind, and put it back.</summary>
    string Rehearse()
    {
        var was = Which.ItemsSource;
        var wasIndex = Which.SelectedIndex;
        var pretend = new List<Stick>
        {
            new() { Device = "disk404", Name = "a stick that is not here",
                    Size = "8.0 GB", Ready = true, WriteTo = "/nowhere",
                    Why = "FAT32 under GPT: ready as it is, nothing to erase." },
            new() { Device = "disk405", Name = "another that is not here",
                    Size = "16.0 GB", Ready = false,
                    Why = "this holds APFS, and OpenCore boots from a FAT32 "
                        + "partition. It has to be erased and formatted first." },
        };
        var seen = 0;
        try
        {
            Which.ItemsSource = pretend;
            foreach (var _ in pretend)
            {
                Which.SelectedIndex = seen;          // SelectionChanged -> Describe
                seen++;
            }
        }
        finally
        {
            Which.ItemsSource = was;
            Which.SelectedIndex = wasIndex;
        }
        return $"{seen} verdicts";
    }

    void Describe()
    {
        if (Which.SelectedItem is not Stick stick)
        {
            EraseBox.IsVisible = VerdictBox.IsVisible = false;
            Open.IsVisible = false;
            Copy.IsEnabled = false;
            return;
        }

        // the question a stick raises is "do I have to format this?", so that
        // is answered before anything else on the pane
        VerdictBox.IsVisible = true;
        VerdictBox.Classes.Set("ok", stick.Ready);
        VerdictBox.Classes.Set("warn", !stick.Ready);
        VerdictWhat.Text = stick.Ready
            ? $"Ready. Writes to {stick.WriteTo}"
            : "This one has to be formatted first";
        VerdictWhy.Text = stick.Why;

        Copy.IsEnabled = stick.Ready;
        // and when it does need formatting, the way to do that is open rather
        // than folded away behind a heading nobody clicks
        EraseBox.IsExpanded = !stick.Ready;
        EraseBox.IsVisible = true;
        Open.IsVisible = stick.Where.Length > 0;
        EraseWhat.Text = $"This erases everything on {stick.Name}, {stick.Size} "
                       + $"({stick.Device})"
                       + (stick.Where.Length > 0 ? $", mounted at {stick.Where}." : ".")
                       + " There is no undoing it.";
        // the word to type, spelled out. "the disk name" was read as the
        // volume's name - USB, RUFUS_BOOT - and the button stayed grey with
        // nothing saying why
        EraseHow.Text = _erasable
            ? $"It becomes one FAT32 partition under GPT, which is what OpenCore "
            + $"boots from. Type {stick.Device} below to turn the button on."
            : "This system cannot do it from here - it needs a root or "
            + "administrator the engine does not have. Press it anyway and the "
            + "exact commands to run yourself are printed below.";
        Typed.Watermark = $"type {stick.Device}";
        EraseAsk.IsVisible = true;
        Erase.IsEnabled = false;
        Typed.Text = "";
        TypedHint.Text = "";
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
