// Write this machine's hardware report, for building somewhere else.
//
// The engine already does this from the command line; this pane is a place to
// put the file and a sentence saying what to do with it.
using System;
using System.IO;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Shell.Engine;

namespace Shell.Views;

public partial class ReportView : UserControl
{
    string _to = Path.Combine(AppContext.BaseDirectory, "machine.json");

    public ReportView()
    {
        InitializeComponent();
        Where.Text = _to;
        Choose.Click += async (_, _) => await Pick();
        Take.Click += async (_, _) => await Take_();
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
            Show("Nothing was written",
                 error.Trim() is { Length: > 0 } said ? said : output.Trim(), null);
            return;
        }
        // the engine prints what it read and where the tables went; that is the
        // useful part and it is already written for a person
        Show("Written", output.Trim(),
             $"Copy {Path.GetFileName(_to)} to the machine you build on, open the " +
             "Builder there, and answer “Another machine, and I have its " +
             "hardware report”.");
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
