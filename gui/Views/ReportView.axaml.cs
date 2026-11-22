// Write this machine's hardware report, for building somewhere else.
//
// The engine already does this from the command line; this pane is a place to
// put the file and a sentence saying what to do with it.
using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Shell.Engine;

namespace Shell.Views;

public partial class ReportView : UserControl
{
    string _to = Path.Combine(Places.Work, "machine.json");

    public ReportView()
    {
        InitializeComponent();
        Where.Text = _to;
        Choose.Click += async (_, _) => await Pick();
        Take.Click += async (_, _) => await Take_();
        Open.Click += (_, _) => Reveal.Show(_to);
        OpenReport.Click += async (_, _) => await OpenOne();
        Back.Click += (_, _) => Showing_(null);
        Showing_(Program.MachineFile, quiet: true);
    }

    /// <summary>Raised with the report now being shown, or null for this machine.</summary>
    public event Action<string?>? Switched;

    async Task OpenOne()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Which hardware report?",
            AllowMultiple = false,
            FileTypeFilter = new[] { new FilePickerFileType("Hardware report") { Patterns = new[] { "*.json" } } },
        });
        var path = picked.FirstOrDefault()?.TryGetLocalPath();
        if (path is null) return;
        Showing_(path);
    }

    void Showing_(string? report, bool quiet = false)
    {
        Program.MachineFile = report;
        Showing.Text = report is null ? "Showing this machine."
                                      : $"Showing the machine in {Path.GetFileName(report)}.";
        Back.IsVisible = report is not null;
        if (!quiet) Switched?.Invoke(report);
    }

    /// <summary>Take one without a click, and say what came of it.
    ///
    /// A pane with a button nobody has pressed is a pane nobody has tested.</summary>
    public async Task<string> TakeForRender()
    {
        await Take_();
        return $"{ResultTitle.Text} -> {_to}";
    }

    async Task Pick()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.SaveFilePickerAsync(new FilePickerSaveOptions
        {
            Title = "Where should the report go?",
            SuggestedFileName = "machine.json",
            DefaultExtension = "json",
        });
        var path = picked?.TryGetLocalPath();
        if (path is null) return;
        _to = path;
        Where.Text = _to;
    }

    async Task Take_()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Show("No engine", missing, null); return; }

        Take.IsEnabled = false;
        Show("Reading this machine…", "", null);
        var (output, error, code) = await Builder.Run(engine, "--report", _to);
        Take.IsEnabled = true;

        if (code != 0 || !File.Exists(_to))
        {
            Open.IsVisible = false;
            Show("Nothing was written",
                 error.Trim() is { Length: > 0 } said ? said : output.Trim(), null);
            return;
        }
        Open.IsVisible = true;
        // the engine prints what it read and where the tables went; that is the
        // useful part and it is already written for a person
        Show("Written", output.Trim(),
             $"Copy {Path.GetFileName(_to)} to the machine you build on and " +
             "open it there with Open a report.");
    }

    void Show(string title, string body, string? next)
    {
        Result.IsVisible = true;
        ResultTitle.Text = title;
        // a title that ends in "…" is a thing still happening
        Working.Say(title.EndsWith('…') ? "" : null);
        ResultText.Text = body;
        ResultNext.Text = next ?? "";
        ResultNext.IsVisible = next is not null;
    }
}
