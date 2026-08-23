// One run of the engine, driven the way a person drives it.
//
// The engine writes one JSON object per line and reads answers back the same
// way. Nothing here decides anything: an ask arrives with its options already
// worked out, and what goes back is the number a person would have typed.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace Shell.Engine;

// TextSpan rather than Span: Avalonia.Controls.Documents has one of its own,
// and the transcript uses both.
public sealed record TextSpan(string Tone, string Text);

public sealed record Option(int Number, string Label, bool Detected);

public sealed record Question(
    int Id, string Text, IReadOnlyList<Option> Options, string? Note, bool FreeText);

public sealed class Session
{
    readonly Process _process;

    Session(Process process) => _process = process;

    public event Action<IReadOnlyList<TextSpan>>? Said;
    public event Action<Question>? Asked;
    public event Action<int, string?>? Finished;

    /// <summary>Start a build and read it until it ends.</summary>
    public static Session Start(Located engine, string outFolder)
    {
        var info = new ProcessStartInfo
        {
            FileName = engine.Program,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            WorkingDirectory = engine.Prefix.Count > 0
                ? Directory.GetParent(Path.GetDirectoryName(engine.Prefix[0])!)!.FullName
                : Path.GetDirectoryName(engine.Program)!,
        };
        foreach (var a in engine.Prefix) info.ArgumentList.Add(a);
        info.ArgumentList.Add("--protocol");
        info.ArgumentList.Add("--out");
        info.ArgumentList.Add(outFolder);

        var process = new Process { StartInfo = info };
        process.Start();
        return new Session(process);
    }

    /// <summary>Read events until the engine stops. Raises on the calling thread's context.</summary>
    public async Task Read()
    {
        string? built = null;
        while (await _process.StandardOutput.ReadLineAsync() is { } line)
        {
            if (line.Length == 0) continue;
            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(line);
            }
            catch (JsonException)
            {
                // not ours: an engine that crashed writes a traceback, and the
                // person reading the transcript should see it
                Said?.Invoke(new[] { new TextSpan("warn", line) });
                continue;
            }

            using (document)
            {
                var root = document.RootElement;
                switch (Text(root, "t"))
                {
                    case "text":
                        Said?.Invoke(Spans(root));
                        break;
                    case "ask":
                        Asked?.Invoke(Menu(root));
                        break;
                    case "prompt":
                        Asked?.Invoke(new Question(
                            root.GetProperty("id").GetInt32(), Text(root, "question") ?? "",
                            Array.Empty<Option>(), Text(root, "note"), true));
                        break;
                    case "built":
                        built = Text(root, "out");
                        break;
                    case "fatal":
                        Said?.Invoke(new[] { new TextSpan("bad", Text(root, "message") ?? "") });
                        break;
                    case "done":
                        Finished?.Invoke(root.GetProperty("rc").GetInt32(), built);
                        break;
                }
            }
        }
        await _process.WaitForExitAsync();
    }

    /// <summary>Answer the question that is open, with what a person would have typed.
    ///
    /// A typed record, not a dictionary of object. Reflection is off in the
    /// published build, so serialising a boxed value throws at runtime - and
    /// the throw landed in an unobserved task, which is why the first version
    /// of this did not fail, it hung.</summary>
    public void Answer(int id, string value)
    {
        _process.StandardInput.WriteLine(
            JsonSerializer.Serialize(new Reply(id, value), Replies.Default.Reply));
        _process.StandardInput.Flush();
    }

    public void Stop()
    {
        try
        {
            if (!_process.HasExited) _process.Kill(entireProcessTree: true);
        }
        catch (InvalidOperationException) { }
    }

    static string? Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() : null;

    static IReadOnlyList<TextSpan> Spans(JsonElement root)
    {
        var out_ = new List<TextSpan>();
        if (root.TryGetProperty("spans", out var spans))
            foreach (var span in spans.EnumerateArray())
                out_.Add(new TextSpan(Text(span, "tone") ?? "plain", Text(span, "text") ?? ""));
        return out_;
    }

    static Question Menu(JsonElement root)
    {
        var options = new List<Option>();
        foreach (var option in root.GetProperty("options").EnumerateArray())
            options.Add(new Option(option.GetProperty("n").GetInt32(),
                                   Text(option, "label") ?? "",
                                   option.GetProperty("detected").GetBoolean()));
        // the skip row is a row like any other once it is drawn
        if (root.TryGetProperty("skip", out var skip))
            options.Add(new Option(skip.GetProperty("n").GetInt32(),
                                   Text(skip, "label") ?? "none of these", false));
        var step = root.TryGetProperty("step", out var s) && s.ValueKind == JsonValueKind.Number
            ? s.GetInt32() : (int?)null;
        var total = root.TryGetProperty("total", out var t) && t.ValueKind == JsonValueKind.Number
            ? t.GetInt32() : (int?)null;
        var note = step is null ? null
            : total is null ? $"question {step}" : $"question {step} of {total}";
        return new Question(root.GetProperty("id").GetInt32(),
                            Text(root, "question") ?? "", options, note, false);
    }
}

public sealed record Reply(int id, string value);

[System.Text.Json.Serialization.JsonSerializable(typeof(Reply))]
public partial class Replies : System.Text.Json.Serialization.JsonSerializerContext
{
}
