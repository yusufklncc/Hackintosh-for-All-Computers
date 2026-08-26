// Drive one run of the engine and show it happening.
//
// The transcript is built as controls rather than bound, because a transcript
// is append-only and the tone of each run of text is already decided by the
// time it arrives. The question panel is built the same way: the options are
// different every time, and there is nothing to reuse between them.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Controls.Documents;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Platform.Storage;
using Avalonia.Threading;
using Shell.Engine;

namespace Shell.Views;

public partial class BuilderView : UserControl
{
    Session? _session;
    Question? _open;
    string _out = DefaultFolder();
    TaskCompletionSource<string>? _ended;
    string? _built;

    /// <summary>Start a run without a click, for the screenshot pass.</summary>
    public Task StartForRender() => Run();

    /// <summary>Answer every question the way the machine suggests, until it ends.
    ///
    /// Through the same two methods a click goes through, because a build that
    /// only works when a person is watching is not a build that works. What
    /// comes back is what the pane ends up saying.</summary>
    public async Task<string> DriveToEnd()
    {
        // nothing started, which the standby panel has already explained. An
        // exception here would be a second, worse report of the same thing.
        if (_ended is not { } ended) return "did not start: " + StandbyText.Text;
        // bounded, and it says where it got to. An unattended pass that can
        // hang is a build that hangs, and a build log with nothing in it is
        // the worst way to find that out.
        var deadline = DateTime.UtcNow.AddMinutes(4);
        var last = "";
        while (!ended.Task.IsCompleted)
        {
            if (DateTime.UtcNow > deadline)
            {
                // the last thing the engine said, because a count of lines is
                // not evidence and guessing from one wastes a build each time
                var tail = Transcript.Children.OfType<TextBlock>()
                    .TakeLast(8).Select(t => t.Text ?? string.Join("", t.Inlines!
                        .OfType<Run>().Select(r => r.Text)));
                return "gave up waiting, last state: " + State()
                     + "\n  " + string.Join("\n  ", tail);
            }
            if (State() != last)
            {
                last = State();
                Console.WriteLine("step: " + last);
            }
            if (_open is not null)
            {
                // A question with nothing detected leaves nothing checked, and
                // Send is right to refuse it. This pass has no opinion - so it
                // declines whatever it is offered, and only then falls back to
                // the first row.
                //
                // Declining matters: one of these questions opens USBToolBox,
                // which asks somebody to plug a device into every port. Taking
                // the first row said yes to that on a build runner, and the
                // run sat there until it was killed.
                var rows = Options.Children.OfType<RadioButton>().ToList();
                if (rows.Count > 0 && rows.All(r => r.IsChecked != true))
                {
                    var declining = _open.Options
                        .FirstOrDefault(o => o.Value is "no" or "none");
                    var pick = declining is null ? rows[0]
                        : rows.FirstOrDefault(r => (int)r.Tag! == declining.Number)
                          ?? rows[0];
                    pick.IsChecked = true;
                }
                Send();
            }
            await Task.Delay(150);
        }
        return await ended.Task;
    }

    /// <summary>Follow the last line down, once the layout knows where it is.
    ///
    /// Posting a ScrollToEnd asks the scroller for an end it has not measured
    /// yet, and it stops short: the bottom of a menu stayed out of sight, and
    /// the row hidden there was the one that quits. Waiting for the layout to
    /// settle is the only moment the extent is the real one.</summary>
    void StickToEnd()
    {
        if (_following) return;
        _following = true;
        EventHandler? once = null;
        once = (_, _) =>
        {
            Transcript.LayoutUpdated -= once;
            _following = false;
            Scroll.ScrollToEnd();
        };
        Transcript.LayoutUpdated += once;
        Transcript.InvalidateMeasure();
    }

    bool _following;

    /// <summary>What is on screen, in one line a build log can assert on.</summary>
    public string State() =>
        $"builder: {Transcript.Children.Count} lines, " +
        $"scrolled {Scroll.Offset.Y:0} + {Scroll.Viewport.Height:0} " +
        $"of {Scroll.Extent.Height:0}, " +
        (_open is null ? "no question open"
                       : $"asking \"{_open.Text}\" with {_open.Options.Count} options");

    public BuilderView()
    {
        InitializeComponent();
        OutFolder.Text = _out;
        Begin.Click += async (_, _) => await Run();
        Choose.Click += async (_, _) => await Pick();
        Continue.Click += (_, _) => Send();
        Stop.Click += (_, _) => Halt();
        Open.Click += (_, _) => Reveal.Show(_built ?? _out);
    }

    /// <summary>Beside the program, which is where somebody who double-clicked it is.</summary>
    static string DefaultFolder() =>
        Path.Combine(AppContext.BaseDirectory, "EFI");

    async Task Pick()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;
        var picked = await top.StorageProvider.OpenFolderPickerAsync(
            new FolderPickerOpenOptions { Title = "Where should the EFI go?", AllowMultiple = false });
        if (picked.Count == 0) return;
        var path = picked[0].TryGetLocalPath();
        if (path is null)
        {
            // a folder the picker can name but the filesystem cannot - a phone,
            // a network location the engine has no path for
            Say(new[] { new TextSpan("warn", "That folder has no path this can write to.") });
            return;
        }
        _out = Path.Combine(path, "EFI");
        OutFolder.Text = _out;
    }

    async Task Run()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null)
        {
            Standby.IsVisible = true;
            StandbyTitle.Text = "No engine";
            StandbyText.Text = missing;
            return;
        }

        Transcript.Children.Clear();
        Standby.IsVisible = false;
        Begin.IsEnabled = false;
        _ended = new TaskCompletionSource<string>();

        var session = Session.Start(engine, _out);
        _session = session;
        session.Said += spans => Dispatcher.UIThread.Post(() => Say(spans));
        session.Asked += question => Dispatcher.UIThread.Post(() => Show(question));
        session.Finished += (code, built) => Dispatcher.UIThread.Post(() => Done(code, built));
        try
        {
            await session.Read();
        }
        catch (IOException e)
        {
            Say(new[] { new TextSpan("bad", "the engine stopped talking: " + e.Message) });
            Done(1, null);
        }
    }

    void Halt()
    {
        _session?.Stop();
        _session = null;
        Prompt.IsVisible = false;
        // the panel below changes how tall the transcript is, and an
        // offset that was at the bottom is not any more
        StickToEnd();
        Standby.IsVisible = true;
        Begin.IsEnabled = true;
        StandbyTitle.Text = "Stopped";
        StandbyText.Text = "Nothing was written. Starting again asks from the top.";
    }

    // ---- what it said ----------------------------------------------------

    static readonly Dictionary<string, string> Tones = new()
    {
        ["bold"] = "Ink", ["dim"] = "Faint", ["green"] = "Ok",
        ["yellow"] = "Warn", ["red"] = "Bad", ["plain"] = "Muted",
        // the session's own words, for the things the engine never said
        ["warn"] = "Warn", ["bad"] = "Bad",
    };

    void Say(IReadOnlyList<TextSpan> spans)
    {
        var line = new TextBlock
        {
            FontFamily = this.TryFindResource("Mono", out var mono)
                ? (FontFamily)mono! : FontFamily.Default,
            FontSize = 12,
        };
        foreach (var span in spans)
        {
            var run = new Run(span.Text);
            if (this.TryFindResource(Tones.GetValueOrDefault(span.Tone, "Muted"), out var brush))
                run.Foreground = (IBrush?)brush;
            if (span.Tone == "bold") run.FontWeight = FontWeight.SemiBold;
            line.Inlines!.Add(run);
        }
        Transcript.Children.Add(line);
        StickToEnd();
    }

    // ---- what it asked ---------------------------------------------------

    void Show(Question question)
    {
        _open = question;
        Prompt.IsVisible = true;
        // the panel below changes how tall the transcript is, and an
        // offset that was at the bottom is not any more
        StickToEnd();
        Standby.IsVisible = false;
        QuestionText.Text = question.Text;
        Step.Text = question.Note?.ToUpperInvariant();
        Step.IsVisible = question.Note is not null;
        Hint.IsVisible = false;

        Options.Children.Clear();
        FreeText.IsVisible = question.FreeText;
        if (question.FreeText)
        {
            FreeText.Text = "";
            if (question.Note is not null)
            {
                Hint.Text = question.Note;
                Hint.IsVisible = true;
                Step.IsVisible = false;
            }
            FreeText.Focus();
            return;
        }

        foreach (var option in question.Options)
        {
            var row = new RadioButton
            {
                GroupName = "answer",
                Tag = option.Number,
                IsChecked = option.Detected,
                Content = option.Detected
                    ? new StackPanel
                    {
                        Orientation = Orientation.Horizontal,
                        Spacing = 8,
                        Children =
                        {
                            new TextBlock { Text = option.Label, VerticalAlignment = VerticalAlignment.Center },
                            Pill("detected"),
                        },
                    }
                    : option.Label,
            };
            Options.Children.Add(row);
        }
        // nothing detected means nothing preselected: the first row is not an
        // answer, it is only the first row
        if (!question.Options.Any(o => o.Detected) && Options.Children.Count > 0)
            ((RadioButton)Options.Children[0]).IsChecked = false;
    }

    Control Pill(string text)
    {
        var pill = new Border { Classes = { "pill", "ok" }, VerticalAlignment = VerticalAlignment.Center };
        pill.Child = new TextBlock { Text = text };
        return pill;
    }

    void Send()
    {
        if (_open is null || _session is null) return;
        string answer;
        if (_open.FreeText)
        {
            answer = FreeText.Text ?? "";
        }
        else
        {
            var chosen = Options.Children.OfType<RadioButton>()
                .FirstOrDefault(r => r.IsChecked == true);
            if (chosen is null)
            {
                Hint.Text = "Pick one of these first.";
                Hint.IsVisible = true;
                return;
            }
            answer = chosen.Tag!.ToString()!;
        }
        var id = _open.Id;
        _open = null;
        Prompt.IsVisible = false;
        // the panel below changes how tall the transcript is, and an
        // offset that was at the bottom is not any more
        StickToEnd();
        _session.Answer(id, answer);
    }

    void Done(int code, string? built)
    {
        _session = null;
        Prompt.IsVisible = false;
        // the panel below changes how tall the transcript is, and an
        // offset that was at the bottom is not any more
        StickToEnd();
        Standby.IsVisible = true;
        Begin.IsEnabled = true;
        Begin.Content = "Build again";
        _built = built;
        Open.IsVisible = code == 0 && built is not null;
        if (code == 0 && built is not null)
        {
            StandbyTitle.Text = "Written";
            StandbyText.Text = $"The EFI folder is at {built}. Copy it to the EFI " +
                               "partition of your USB drive.";
        }
        else if (code == 0)
        {
            StandbyTitle.Text = "Finished";
            StandbyText.Text = "It ended without writing an EFI. The transcript says why.";
        }
        else
        {
            StandbyTitle.Text = "Stopped with an error";
            StandbyText.Text = $"The engine exited {code}. The transcript says why.";
        }
        _ended?.TrySetResult($"rc={code} {StandbyTitle.Text}: {built ?? "nothing written"}");
    }
}
