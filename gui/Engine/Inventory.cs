// What the repository carries: the kexts, and the standing facts.
//
// Read rather than written down. The sidebar used to claim "OpenCore 1.0.6"
// and "41 kexts" from memory; the tree said 1.0.5 and 42.
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
using System;
using Avalonia;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using System.Threading.Tasks;

namespace Shell.Engine;

public sealed class KextRow
{
    [JsonPropertyName("bundle")] public string Bundle { get; set; } = "";
    [JsonPropertyName("version")] public string? Version { get; set; }
    [JsonPropertyName("upstream")] public string? Upstream { get; set; }
    [JsonPropertyName("url")] public string? Url { get; set; }
    [JsonPropertyName("licence")] public string? Licence { get; set; }
    [JsonPropertyName("shipped")] public bool Shipped { get; set; }
    [JsonPropertyName("roles")] public List<string> Roles { get; set; } = new();
    [JsonPropertyName("label")] public string? Label { get; set; }
    [JsonPropertyName("devices")] public int Devices { get; set; }
}

public sealed class KextList
{
    [JsonPropertyName("kexts")] public List<KextRow> Kexts { get; set; } = new();
}

public sealed class SourceRow
{
    [JsonPropertyName("area")] public string Area { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("file")] public string File { get; set; } = "";
    [JsonPropertyName("source")] public string Source { get; set; } = "";
    [JsonPropertyName("count")] public string Count { get; set; } = "";
    [JsonPropertyName("covers")] public string Covers { get; set; } = "";
    [JsonPropertyName("gap")] public string Gap { get; set; } = "";
}

public sealed class ToolRow
{
    // the lock spells these "upstream" and "license"; reading them as "repo"
    // and "licence" gave nine rows of null and the page quietly showed nothing
    [JsonPropertyName("path")] public string Path { get; set; } = "";
    [JsonPropertyName("upstream")] public string? Upstream { get; set; }
    [JsonPropertyName("license")] public string? Licence { get; set; }
    [JsonPropertyName("version")] public string? Version { get; set; }
    [JsonPropertyName("note")] public string? Note { get; set; }
}

public sealed class About
{
    [JsonPropertyName("opencore")] public string? OpenCore { get; set; }
    [JsonPropertyName("configs")] public int Configs { get; set; }
    [JsonPropertyName("kexts")] public int Kexts { get; set; }
    [JsonPropertyName("shipped")] public int Shipped { get; set; }
    [JsonPropertyName("offline")] public bool Offline { get; set; }
    [JsonPropertyName("network")] public string? Network { get; set; }
    [JsonPropertyName("sources")] public List<SourceRow> Sources { get; set; } = new();
    [JsonPropertyName("tally")] public Dictionary<string, int> Tally { get; set; } = new();
    [JsonPropertyName("tools")] public List<ToolRow> Tools { get; set; } = new();
    [JsonPropertyName("licence")] public string? Licence { get; set; }
    [JsonPropertyName("repo")] public string? Repo { get; set; }
}

public sealed class MacosSpan
{
    [JsonPropertyName("from")] public string? From { get; set; }
    [JsonPropertyName("to")] public string? To { get; set; }
    [JsonPropertyName("oclp")] public string? Oclp { get; set; }
    [JsonPropertyName("oclp_to")] public string? OclpTo { get; set; }
}

public sealed class DeviceRow
{
    [JsonPropertyName("category")] public string Category { get; set; } = "";
    [JsonPropertyName("id")] public string? Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("vendor")] public string? Vendor { get; set; }
    [JsonPropertyName("kext")] public string? Kext { get; set; }
    [JsonPropertyName("note")] public string Note { get; set; } = "";
    [JsonPropertyName("macos")] public MacosSpan? Macos { get; set; }
    [JsonPropertyName("status")] public string Status { get; set; } = "";
}

public sealed class DeviceList
{
    [JsonPropertyName("devices")] public List<DeviceRow> Devices { get; set; } = new();
    [JsonPropertyName("categories")] public List<string> Categories { get; set; } = new();
    [JsonPropertyName("vendors")] public List<string> Vendors { get; set; } = new();
    [JsonPropertyName("statuses")] public List<string> Statuses { get; set; } = new();
}

public sealed class RecoveryChoice
{
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    // Setting this has to drop the cached lookup below. The `latest` row
    // starts with no name, draws its mark, and is renamed once Apple has been
    // asked - and a cache that remembered "there was no icon" would keep the
    // placeholder on a row that now knows it is Tahoe.
    string _name = "";
    [JsonPropertyName("name")]
    public string Name
    {
        get => _name;
        set { _name = value; _looked = false; _art = null; }
    }
    // what to call the row. The engine decides it, because one of these has no
    // version to print and a window inventing its own wording for that is how
    // two surfaces come to say different things about the same thing.
    [JsonPropertyName("label")] public string Label { get; set; } = "";
    [JsonPropertyName("note")] public string Note { get; set; } = "";
    [JsonPropertyName("board")] public string Board { get; set; } = "";
    [JsonPropertyName("boards")] public int Boards { get; set; }
    // drawn by this window, decided by the engine: two surfaces colouring the
    // same release differently is the same failure as wording it differently
    [JsonPropertyName("mark")] public RecoveryMark? Mark { get; set; }

    /// <summary>Apple's own icon for this release, when there is one.
    ///
    /// Nothing here draws a placeholder in its place: a release with no file
    /// falls back to the mark below, because the offer list grows out of
    /// macrecovery's board table and a pane that needed a file per release
    /// would show a hole the day Apple served something new.
    ///
    /// Looked up once. AssetLoader.Open throws on a missing resource, and
    /// doing that per redraw for eight tiles is eight exceptions a frame.</summary>
    Bitmap? _art;
    bool _looked;
    public Bitmap? Art
    {
        get
        {
            if (_looked) return _art;
            _looked = true;
            if (Name is not { Length: > 0 }) return null;
            var file = Name.Replace(" ", "");
            var where = new Uri($"avares://HackintoshEFIBuilder/Assets/macOS/{file}.png");
            try
            {
                if (AssetLoader.Exists(where)) _art = new Bitmap(AssetLoader.Open(where));
            }
            catch (Exception)
            {
                // a file that is there and is not a picture is the packager's
                // problem, not something to take the window down over
                _art = null;
            }
            return _art;
        }
    }
    public bool Drawn => Art is null;

    public IBrush Tile => Mark is null
        ? new SolidColorBrush(Color.Parse("#3e3ba8"))
        : new LinearGradientBrush
          {
              StartPoint = new RelativePoint(0, 0, RelativeUnit.Relative),
              EndPoint = new RelativePoint(1, 1, RelativeUnit.Relative),
              GradientStops =
              {
                  new GradientStop(Color.Parse(Mark.From), 0),
                  new GradientStop(Color.Parse(Mark.To), 1),
              },
          };
    public string Letter => Mark?.Letter ?? "?";

    public string Titled => Label is { Length: > 0 } said ? said
                                                          : $"{Name} {Version}".Trim();
    public bool Explained => Note.Length > 0;
}

public sealed class RecoveryMark
{
    [JsonPropertyName("letter")] public string Letter { get; set; } = "?";
    [JsonPropertyName("from")] public string From { get; set; } = "#3e3ba8";
    [JsonPropertyName("to")] public string To { get; set; } = "#6f6ad6";
    // "chosen" or "derived" - a release the table never heard of still gets a
    // mark, and the About pane is where that distinction is spelled out
    [JsonPropertyName("source")] public string Source { get; set; } = "";
}

public sealed class RecoveryList
{
    [JsonPropertyName("folder")] public string Folder { get; set; } = "";
    [JsonPropertyName("available")] public bool Available { get; set; }
    [JsonPropertyName("choices")] public List<RecoveryChoice> Choices { get; set; } = new();
    // whether the machine being installed can reach the network at all, which
    // is the question this pane never asked and several issues turned on
    [JsonPropertyName("network")] public string Network { get; set; } = "";
    [JsonPropertyName("network_note")] public string NetworkNote { get; set; } = "";
}

public sealed class Stick
{
    [JsonPropertyName("device")] public string Device { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("size")] public string Size { get; set; } = "";
    [JsonPropertyName("bus")] public string Bus { get; set; } = "";
    [JsonPropertyName("mounted")] public List<string> Mounted { get; set; } = new();
    [JsonPropertyName("scheme")] public string Scheme { get; set; } = "";
    // whether it can be copied to as it stands, where to, and why. The engine
    // decides: "is this a USB stick" is not the question, "is this FAT32" is.
    [JsonPropertyName("ready")] public bool Ready { get; set; }
    [JsonPropertyName("write_to")] public string WriteTo { get; set; } = "";
    [JsonPropertyName("why")] public string Why { get; set; } = "";

    public string Titled => $"{Name} · {Size}".Trim();
    public string Where => WriteTo.Length > 0 ? WriteTo
                         : Mounted.Count > 0 ? Mounted[0] : "";
    public string State => Ready ? "ready" : "needs formatting";
}

public sealed class StickList
{
    [JsonPropertyName("platform")] public string Platform { get; set; } = "";
    [JsonPropertyName("booted")] public string? Booted { get; set; }
    [JsonPropertyName("erasable")] public bool Erasable { get; set; }
    // an empty list is "none plugged in"; this is "could not ask"
    [JsonPropertyName("asked")] public bool Asked { get; set; }
    [JsonPropertyName("trouble")] public string Trouble { get; set; } = "";
    [JsonPropertyName("recovery")] public string Recovery { get; set; } = "";
    [JsonPropertyName("sticks")] public List<Stick> Sticks { get; set; } = new();
}

[JsonSerializable(typeof(Newest))]
[JsonSerializable(typeof(StickList))]
[JsonSerializable(typeof(RecoveryList))]
[JsonSerializable(typeof(DeviceList))]
[JsonSerializable(typeof(KextList))]
[JsonSerializable(typeof(About))]
public partial class Carried : JsonSerializerContext
{
}

/// <summary>What Apple says it is serving right now.
///
/// The `latest` rows in the board table are the Macs Apple still updates, so
/// they fetch whatever is newest - and nothing in a binary built months ago
/// can name what that is. This is the answer, asked of Apple at the moment
/// somebody presses for it.</summary>
public sealed class Newest
{
    [JsonPropertyName("newest")] public RecoveryChoice? Choice { get; set; }
    [JsonPropertyName("complaint")] public string Complaint { get; set; } = "";
}

public static class Inventory
{
    /// <summary>Asks Apple. Opens a connection, so only a button calls it.</summary>
    public static async Task<(RecoveryChoice? said, string complaint)> Newest(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--recovery-newest");
        try
        {
            var got = JsonSerializer.Deserialize(output, Carried.Default.Newest);
            if (got?.Choice is { } choice) return (choice, "");
            return (null, got?.Complaint is { Length: > 0 } said ? said
                        : Said(error, code));
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(KextList? list, string complaint)> Kexts(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--inventory", "kexts");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.KextList), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(DeviceList? list, string complaint)> Devices(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--inventory", "devices");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.DeviceList), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(RecoveryList? list, string complaint)> Recoveries(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--inventory", "recovery");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.RecoveryList), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(StickList? list, string complaint)> Sticks(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--usb-list");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.StickList), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(About? about, string complaint)> Facts(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--inventory", "about");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.About), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    static string Said(string error, int code) =>
        error.Trim() is { Length: > 0 } said ? said : $"the engine exited {code}";
}
