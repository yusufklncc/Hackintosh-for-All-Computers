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
using Avalonia;
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

    /// <summary>An answer given: to which question, what was sent, what it
    /// said, and whether the pane took it rather than the person.</summary>
    sealed record Given(string Question, string Sent, string Label, bool Auto);

    // every answer of this run, in order: the trail above, and what going
    // back replays
    readonly List<Given> _given = new();
    // the answers to give again, without asking, after going back
    Queue<Given>? _replay;
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

    /// <summary>Go back to question <paramref name="number"/> (from 1) and wait
    /// until it is the one asked: what clicking its chip does, checked by the
    /// screenshot pass rather than trusted.</summary>
    public async Task<string> BackForRender(int number)
    {
        var before = _given.Take(number - 1).Select(g => g.Label).ToList();
        var asked = _given.Count >= number ? _given[number - 1].Question : null;
        if (asked is null) return $"no question {number} to go back to";
        var going = GoBack(number - 1);
        var deadline = DateTime.UtcNow.AddMinutes(2);
        while (_open?.Text != asked && DateTime.UtcNow < deadline) await Task.Delay(150);
        var again = _given.Select(g => g.Label).ToList();
        return _open?.Text == asked && again.SequenceEqual(before)
            ? $"back at question {number}, \"{asked}\", with {again.Count} answers given again"
            : $"did not get back to \"{asked}\": {State()}";
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
        // the answers may use up to two fifths of the pane and scroll past
        // that, so the transcript and the buttons always keep their room
        SizeChanged += (_, e) => OptionsScroll.MaxHeight = Math.Max(160, e.NewSize.Height * 0.4);
        Begin.Click += async (_, _) => await Run();
        Choose.Click += async (_, _) => await Pick();
        Continue.Click += (_, _) => Send();
        Stop.Click += (_, _) => Halt();
        Open.Click += (_, _) => Reveal.Show(_built ?? _out);
        ToStick.Click += (_, _) => StickRequested?.Invoke();
        Back.Click += async (_, _) => await GoBack(_given.Count - 1);
        // folded unless asked for - or unless this is the screenshot pass,
        // whose checks read where the transcript is scrolled to
        DetailsToggle.IsCheckedChanged += (_, _) =>
        {
            Details.IsVisible = DetailsToggle.IsChecked == true;
            DetailsToggle.Content = Details.IsVisible ? "Hide details" : "Show details";
            if (Details.IsVisible) StickToEnd();
        };
        DetailsToggle.IsChecked = Program.RenderTo is not null;
    }

    /// <summary>Back to answer number <paramref name="index"/> (from 0): the
    /// engine starts again and is given every answer before it, unasked, so
    /// the first question it puts to the person is that one.
    ///
    /// Again rather than undone, because the engine is a program asking in
    /// order: what a later question offers can depend on an earlier answer,
    /// and only running it again gets that right.</summary>
    async Task GoBack(int index)
    {
        if (index < 0 || index >= _given.Count) return;
        var keep = _given.Take(index).ToList();
        StopQuietly();
        _replay = new Queue<Given>(keep);
        await Run(going: index + 1);
    }

    /// <summary>Beside the program, which is where somebody who double-clicked it is.</summary>
    static string DefaultFolder() =>
        Path.Combine(Places.Work, "EFI");

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

    async Task Run(int going = 0)
    {
        if (going == 0) _replay = null;
        var engine = Builder.Find(out var missing);
        if (engine is null)
        {
            Standby.IsVisible = true;
            StandbyTitle.Text = "No engine";
            StandbyText.Text = missing;
            return;
        }

        Transcript.Children.Clear();
        ToStick.IsVisible = false;
        Begin.Classes.Set("accent", true);
        Trail.Children.Clear();
        Trail.IsVisible = false;
        _given.Clear();
        HwSummary.Children.Clear();
        Standby.IsVisible = false;
        Waiting.Say(going > 0 ? $"Going back to question {going}…"
                    : Program.MachineFile is null ? "Starting, and reading this machine…"
                                                  : "Starting, and reading the report…");
        Begin.IsEnabled = false;
        _ended = new TaskCompletionSource<string>();

        var session = Session.Start(engine, _out);
        _session = session;
        // only the run on screen speaks: one stopped to go back still has a
        // last line or two in its pipe, and its "done" would end the new one
        bool Mine() => ReferenceEquals(_session, session);
        session.Said += spans => Dispatcher.UIThread.Post(() => { if (Mine()) Say(spans); });
        session.Asked += question => Dispatcher.UIThread.Post(() => { if (Mine()) Show(question); });
        session.Hardware += (source, rows) => Dispatcher.UIThread.Post(() => { if (Mine()) Table(source, rows); });
        session.Finished += (code, built) => Dispatcher.UIThread.Post(() => { if (Mine()) Done(code, built); });
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

    /// <summary>Stop the engine without saying so: going back starts another.</summary>
    void StopQuietly()
    {
        var old = _session;
        _session = null;
        _open = null;
        old?.Stop();
        Prompt.IsVisible = false;
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
            if (Brush(Tones.GetValueOrDefault(span.Tone, "Muted")) is { } brush)
                run.Foreground = brush;
            if (span.Tone == "bold") run.FontWeight = FontWeight.SemiBold;
            line.Inlines!.Add(run);
        }
        Transcript.Children.Add(line);
        StickToEnd();
    }

    /// <summary>The hardware summary as the Machine pane draws it: columns that
    /// wrap, a verdict in colour, rather than text lined up in spaces.</summary>
    void Table(string source, IReadOnlyList<HardwareRow> rows)
    {
        var box = new StackPanel { Spacing = 0, Margin = new Thickness(0, 6, 0, 8), MaxWidth = 860,
                                   HorizontalAlignment = HorizontalAlignment.Left };
        box.Children.Add(new TextBlock
        {
            Text = $"HARDWARE FOR MACOS  ·  FROM {source.ToUpperInvariant()}",
            Classes = { "eyebrow" }, Margin = new Thickness(0, 0, 0, 6),
        });
        foreach (var r in rows)
        {
            var grid = new Grid
            {
                ColumnDefinitions = new ColumnDefinitions("100,*,150"),
                ColumnSpacing = 12, Margin = new Thickness(0, 0, 0, 0),
            };
            grid.Children.Add(new TextBlock
            {
                Text = r.Part, FontSize = 12.5, FontWeight = FontWeight.SemiBold, Foreground = Brush("Ink"),
            });
            var what = new StackPanel { Spacing = 1 };
            what.Children.Add(new TextBlock { Text = r.What, FontSize = 12.5, Foreground = Brush("Ink"),
                                              TextWrapping = TextWrapping.Wrap });
            if (r.Detail.Length > 0)
                what.Children.Add(new TextBlock { Text = r.Detail, FontSize = 11.5, Foreground = Brush("Muted"),
                                                  TextWrapping = TextWrapping.Wrap });
            Grid.SetColumn(what, 1);
            grid.Children.Add(what);
            var tone = r.Verdict switch
            {
                "supported" or "driven by macOS" => "ok",
                "unsupported" or "not supported" => "bad",
                "third-party driver" or "unknown" => "warn",
                _ => "",
            };
            var pill = new Border { Classes = { "pill" }, VerticalAlignment = VerticalAlignment.Top,
                                    Child = new TextBlock { Text = r.Verdict == "-" ? "not present" : r.Verdict } };
            if (tone.Length > 0) pill.Classes.Add(tone);
            Grid.SetColumn(pill, 2);
            grid.Children.Add(pill);
            box.Children.Add(new Border
            {
                Child = grid, Padding = new Thickness(0, 6), BorderThickness = new Thickness(0, 0, 0, 1),
                BorderBrush = Brush("Line"),
            });
        }
        Transcript.Children.Add(box);
        StickToEnd();

        // and in a line at the top, the way the Machine pane counts them: the
        // whole table is in the details, and on the Machine pane
        HwSummary.Children.Clear();
        HwSummary.Children.Add(new TextBlock
        {
            Text = "HARDWARE", Classes = { "eyebrow" }, VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 10, 0),
        });
        foreach (var g in rows.Where(r => r.Verdict != "-").GroupBy(r => r.Verdict))
        {
            var tone = g.Key switch
            {
                "supported" or "driven by macOS" => "ok",
                "not supported" => "bad",
                "third-party driver" or "unknown" => "warn",
                _ => "",
            };
            var pill = new Border { Classes = { "pill" }, Margin = new Thickness(0, 0, 6, 0),
                                    Child = new TextBlock { Text = $"{g.Count()} {g.Key}" } };
            if (tone.Length > 0) pill.Classes.Add(tone);
            ToolTip.SetTip(pill, string.Join("\n", g.Select(r => $"{r.Part}: {r.What}")));
            HwSummary.Children.Add(pill);
        }
    }

    /// <summary>A colour of the current theme, from code.
    ///
    /// With the theme named. The colours live in the theme dictionaries, and a
    /// lookup that does not say which theme finds nothing: the transcript's
    /// tones had been falling back to the default all along, and a table built
    /// this way drew its text in no colour at all.</summary>
    IBrush? Brush(string key) =>
        this.TryFindResource(key, ActualThemeVariant, out var b) ? b as IBrush : null;

    // ---- what it asked ---------------------------------------------------

    void Show(Question question)
    {
        // going back: the answers before the one being changed are given
        // again, as long as the engine asks what it asked before
        if (_replay is { Count: > 0 } && _replay.Peek().Question == question.Text
            && (question.FreeText || question.Options.Any(o => o.Number.ToString() == _replay.Peek().Sent
                                                             && o.Label == _replay.Peek().Label)))
        {
            var again = _replay.Dequeue();
            Give(question, again.Sent, again.Label, again.Auto);
            return;
        }
        _replay = null;
        // an expert question with an answer ready is answered with it, and
        // shown above like any other, unless Advanced asks for all of them
        if (question.Expert && AskAll.IsChecked != true && !question.FreeText)
        {
            var ready = question.Options.FirstOrDefault(o => o.Detected)
                        ?? question.Options.FirstOrDefault(o => o.Value is "no");
            if (ready is not null)
            {
                Give(question, ready.Number.ToString(), ready.Label, auto: true);
                return;
            }
        }
        _open = question;
        Back.IsEnabled = _given.Count > 0;
        Waiting.Say(null);
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
        OptionsScroll.Offset = default;
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
        // a detected answer far down the list is no use behind the fold
        if (Options.Children.OfType<RadioButton>().FirstOrDefault(r => r.IsChecked == true) is { } picked)
            Dispatcher.UIThread.Post(() => picked.BringIntoView(), DispatcherPriority.Loaded);
    }

    /// <summary>Send an answer and put it on the trail.</summary>
    void Give(Question question, string sent, string label, bool auto)
    {
        if (_session is null) return;
        _given.Add(new Given(question.Text, sent, label, auto));
        Answered(question.Text, label, auto, _given.Count - 1);
        _open = null;
        Prompt.IsVisible = false;
        Waiting.Say("Working…");
        StickToEnd();
        _session.Answer(question.Id, sent);
    }

    void Answered(string question, string answer, bool auto, int index)
    {
        var n = index + 1;
        var shown = answer.Length > 34 ? answer[..33] + "\u2026" : answer;
        if (answer.Length == 0) shown = "(left empty)";
        var chip = new Border
        {
            CornerRadius = new CornerRadius(11), Padding = new Thickness(9, 3, 10, 4),
            Margin = new Thickness(0, 0, 6, 6), BorderThickness = new Thickness(1),
            BorderBrush = Brush("Line"), Background = Brush("Surface2"),
            Child = new TextBlock
            {
                FontSize = 11.5, Foreground = Brush("Muted"),
                Inlines = { new Run($"{n}  ") { Foreground = Brush("Accent"), FontWeight = FontWeight.SemiBold },
                            new Run(shown) { Foreground = Brush("Ink") } },
            },
        };
        if (auto)
        {
            // taken by the pane: said so, in the chip and its tip
            ((TextBlock)chip.Child!).Inlines!.Add(new Run("  detected") { Foreground = Brush("Ok"), FontSize = 10.5 });
        }
        ToolTip.SetTip(chip, $"{question}\n{answer}"
                           + (auto ? "\nTaken as detected; Advanced asks it." : "")
                           + "\nClick to go back to this question.");
        chip.Cursor = new Avalonia.Input.Cursor(Avalonia.Input.StandardCursorType.Hand);
        chip.PointerPressed += async (_, _) => await GoBack(index);
        Trail.Children.Add(chip);
        Trail.IsVisible = true;
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
        var label = "";
        if (_open.FreeText)
        {
            answer = FreeText.Text ?? "";
            label = answer;
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
            // the answer joins the trail above, so what has been settled stays
            // on screen after its question is gone
            label = _open.Options.FirstOrDefault(o => o.Number.ToString() == answer)?.Label ?? answer;
        }
        // until the next question or the end: an SSDT pass or a build can take
        // a while, and an empty space under the question says nothing. The
        // panel going changes how tall the transcript is, so it follows its
        // end again (StickToEnd();, in Give).
        Give(_open, answer, label, auto: false);
    }

    /// <summary>Raised by the button that goes on to the USB stick pane.</summary>
    public event Action? StickRequested;

    /// <summary>Raised when a build wrote an EFI, for the sidebar's tick.</summary>
    public event Action? Built;

    void Done(int code, string? built)
    {
        Waiting.Say(null);
        _session = null;
        Prompt.IsVisible = false;
        // the panel below changes how tall the transcript is, and an
        // offset that was at the bottom is not any more
        StickToEnd();
        Standby.IsVisible = true;
        Begin.IsEnabled = true;
        Begin.Content = "Build again";
        // a run that failed says why in the transcript: open it
        if (code != 0) DetailsToggle.IsChecked = true;
        _built = built;
        Open.IsVisible = code == 0 && built is not null;
        // one filled button: the next step when there is one, starting again
        // when there is not
        ToStick.IsVisible = Open.IsVisible;
        Begin.Classes.Set("accent", !ToStick.IsVisible);
        if (ToStick.IsVisible) Built?.Invoke();
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
        ShowAdded(code == 0 ? built : null);
        _ = ShowFacts(code == 0 ? built : null);
        _ended?.TrySetResult($"rc={code} {StandbyTitle.Text}: {built ?? "nothing written"}");
    }

    /// <summary>The written EFI in a few cards: identity, kexts, audio, security,
    /// and what is left to do by hand.</summary>
    async Task ShowFacts(string? efi)
    {
        Facts.Children.Clear();
        LeftRows.Children.Clear();
        Facts.IsVisible = LeftToDo.IsVisible = false;
        if (efi is null || Builder.Find(out _) is not { } engine) return;
        var (facts, _) = await Inventory.Efi(engine, efi);
        if (facts is null) return;

        void Card(string label, string value, string? detail = null)
        {
            var body = new StackPanel { Spacing = 2 };
            body.Children.Add(new TextBlock { Text = label.ToUpperInvariant(), Classes = { "eyebrow" } });
            body.Children.Add(new TextBlock
            {
                Text = value, FontSize = 15, FontWeight = FontWeight.SemiBold,
                [!TextBlock.ForegroundProperty] = this.GetResourceObservable("Ink").ToBinding(),
            });
            if (detail is { Length: > 0 })
                body.Children.Add(new TextBlock
                {
                    Text = detail, FontSize = 11.5, TextWrapping = TextWrapping.Wrap, MaxWidth = 200,
                    [!TextBlock.ForegroundProperty] = this.GetResourceObservable("Muted").ToBinding(),
                });
            Facts.Children.Add(new Border
            {
                Child = body, Padding = new Avalonia.Thickness(12, 9), Margin = new Avalonia.Thickness(0, 0, 8, 8),
                CornerRadius = new Avalonia.CornerRadius(8), BorderThickness = new Avalonia.Thickness(1),
                MinWidth = 150,
                [!Border.BorderBrushProperty] = this.GetResourceObservable("Line").ToBinding(),
                [!Border.BackgroundProperty] = this.GetResourceObservable("Surface2").ToBinding(),
            });
        }

        if (facts.Smbios.Length > 0) Card("Identity", facts.Smbios, "the Mac model it presents as");
        Card("Kexts", facts.Kexts.Count.ToString(),
             string.Join(", ", facts.Kexts.Take(4).Select(k => k.Replace(".kext", "")))
             + (facts.Kexts.Count > 4 ? $" and {facts.Kexts.Count - 4} more" : ""));
        if (facts.Alcid is { } alcid) Card("Audio", $"layout {alcid}", "alcid in boot-args; try the next one in NEXT-STEPS.txt if there is no sound");
        if (facts.SecureBootModel is { } sbm) Card("Secure boot", sbm, "Misc → Security → SecureBootModel");
        if (facts.Community.Count > 0) Card("Community", facts.Community.Count.ToString(),
                                            string.Join(", ", facts.Community));
        Facts.IsVisible = Facts.Children.Count > 0;

        foreach (var step in facts.Next)
            LeftRows.Children.Add(new TextBlock
            {
                Text = "\u2192  " + step, FontSize = 13,
                [!TextBlock.ForegroundProperty] = this.GetResourceObservable("Ink").ToBinding(),
            });
        if (facts.NextFile.Length > 0)
        {
            var open = new Button { Content = "Open NEXT-STEPS.txt", Margin = new Avalonia.Thickness(0, 6, 0, 0) };
            var file = facts.NextFile;
            open.Click += (_, _) => Reveal.Show(file);
            LeftRows.Children.Add(open);
        }
        LeftToDo.IsVisible = facts.Next.Count > 0;
    }

    /// <summary>The community drivers the EFI carries, each with a way out.</summary>
    void ShowAdded(string? efi)
    {
        AddedRows.Children.Clear();
        var added = efi is null ? new List<AddedDriver>() : Inventory.Added(efi);
        Added.IsVisible = added.Count > 0;
        if (efi is null || added.Count == 0) return;
        AddedNote.Text = "Experimental, and somebody else's. Taking one out puts back "
                       + "what it changed. Without this program: in OC, rename "
                       + "config-without-community.plist to config.plist.";
        foreach (var d in added)
        {
            var ai = d.AiLevel switch { "written" => "  ·  AI-written", "assisted" => "  ·  AI-assisted", _ => "" };
            var row = new Grid { ColumnDefinitions = new ColumnDefinitions("*,Auto"), ColumnSpacing = 10 };
            row.Children.Add(new TextBlock
            {
                Text = $"{d.Name}  {d.Release}{ai}", FontSize = 13,
                VerticalAlignment = VerticalAlignment.Center,
            });
            var take = new Button { Content = "Take out", Tag = d.Name };
            Grid.SetColumn(take, 1);
            take.Click += async (_, _) => await TakeOut(efi, d.Name, take);
            row.Children.Add(take);
            AddedRows.Children.Add(row);
        }
    }

    async Task TakeOut(string efi, string name, Button button)
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { AddedNote.Text = missing; return; }
        button.IsEnabled = false;
        var (said, code) = await Inventory.TakeOut(engine, efi, name);
        foreach (var line in said.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            Say(new[] { new TextSpan(code == 0 ? "dim" : "warn", line.TrimEnd()) });
        StickToEnd();
        ShowAdded(efi);
        if (code != 0) AddedNote.Text = said.Trim();
    }
}
