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
using System.IO;
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
    [JsonPropertyName("group")] public string Group { get; set; } = "Other";
    [JsonPropertyName("said")] public string Said { get; set; } = "";
    [JsonPropertyName("said_of_project")] public bool SaidOfProject { get; set; }
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
    // which release to draw an icon for, when the row is not named after one
    string _artName = "";
    [JsonPropertyName("art")]
    public string ArtName
    {
        get => _artName;
        set { _artName = value; _looked = false; _art = null; }
    }

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
            // ArtName, not Name: the `latest` row keeps an empty Name so a
            // console `--macos tahoe` cannot match two rows once boards.json
            // grows a real Tahoe. It still knows which release to draw.
            var which = ArtName is { Length: > 0 } ? ArtName : Name;
            if (which is not { Length: > 0 }) return null;
            var file = which.Replace(" ", "");
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

    // the two volumes an offline stick needs, and what is missing if not
    [JsonPropertyName("fat")] public string? Fat { get; set; }
    [JsonPropertyName("exfat")] public string? Exfat { get; set; }
    [JsonPropertyName("offline_why")] public string OfflineWhy { get; set; } = "";

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

/// <summary>A macOS that can go on a stick for an install with no network:
/// Apple's full installer, and which recovery the stick boots.</summary>
public sealed class OfflineChoice
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    [JsonPropertyName("build")] public string Build { get; set; } = "";
    [JsonPropertyName("size")] public long Size { get; set; }
    [JsonPropertyName("boots")] public string Boots { get; set; } = "";
    [JsonPropertyName("steps")] public List<string> Steps { get; set; } = new();
    [JsonPropertyName("newest")] public bool Newest { get; set; }

    public string Titled => $"{Name} {Version} ({Build})";
    public string Detail => (Size > 0 ? $"{Size / 1e9:0.0} GB" : "size unknown")
                          + (Boots.StartsWith("its own") ? " · recovery from the package"
                                                         : $" · boots {Boots}'s recovery")
                          + (Newest ? "" : " · older build");
}

public sealed class OfflineList
{
    [JsonPropertyName("macos")] public List<OfflineChoice> Macos { get; set; } = new();
    [JsonPropertyName("complaint")] public string Complaint { get; set; } = "";
}

/// <summary>One project in the community registry, as the Compatible Hardware
/// pane draws it. Every sentence in it is the project's own.</summary>
public sealed class CommunityProject
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("repo")] public string Repo { get; set; } = "";
    [JsonPropertyName("url")] public string Url { get; set; } = "";
    [JsonPropertyName("role")] public string Role { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("stage")] public string Stage { get; set; } = "";
    [JsonPropertyName("install")] public string Install { get; set; } = "";
    [JsonPropertyName("licence")] public string Licence { get; set; } = "";
    [JsonPropertyName("release")] public string Release { get; set; } = "";
    [JsonPropertyName("macos")] public string Macos { get; set; } = "";
    [JsonPropertyName("said")] public string Said { get; set; } = "";
    [JsonPropertyName("covers")] public string Covers { get; set; } = "";
    [JsonPropertyName("how")] public string How { get; set; } = "";
    [JsonPropertyName("needs")] public string Needs { get; set; } = "";
    [JsonPropertyName("conflicts")] public List<string> Conflicts { get; set; } = new();
    [JsonPropertyName("devices")] public int Devices { get; set; }
    [JsonPropertyName("ids")] public List<string> Ids { get; set; } = new();
    [JsonPropertyName("tested")] public List<string> Tested { get; set; } = new();
    [JsonPropertyName("chips")] public List<string> Chips { get; set; } = new();
    [JsonPropertyName("ai")] public string Ai { get; set; } = "";
    // written, assisted or empty, and the evidence it rests on
    [JsonPropertyName("ai_level")] public string AiLevel { get; set; } = "";
    [JsonPropertyName("ai_why")] public string AiWhy { get; set; } = "";
    // who put the release file there, and whether GitHub attests its build
    [JsonPropertyName("uploaded")] public string Uploaded { get; set; } = "";
    // an issue form filled in with this machine, for saying whether it worked
    [JsonPropertyName("report")] public string Report { get; set; } = "";
    [JsonPropertyName("recipe")] public bool Recipe { get; set; }
    [JsonPropertyName("matches")] public bool Matches { get; set; }
    [JsonPropertyName("requires")] public string Requires { get; set; } = "";
}

/// <summary>One community driver an EFI carries, as OC/Community/record.json says.</summary>
public sealed class AddedDriver
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("release")] public string Release { get; set; } = "";
    [JsonPropertyName("ai_level")] public string AiLevel { get; set; } = "";
    [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
}

/// <summary>What a written EFI holds, read back from the folder.</summary>
public sealed class EfiFacts
{
    [JsonPropertyName("complaint")] public string? Complaint { get; set; }
    [JsonPropertyName("smbios")] public string Smbios { get; set; } = "";
    [JsonPropertyName("kexts")] public List<string> Kexts { get; set; } = new();
    [JsonPropertyName("boot_args")] public string BootArgs { get; set; } = "";
    [JsonPropertyName("alcid")] public string? Alcid { get; set; }
    [JsonPropertyName("secure_boot_model")] public string? SecureBootModel { get; set; }
    [JsonPropertyName("community")] public List<string> Community { get; set; } = new();
    [JsonPropertyName("next")] public List<string> Next { get; set; } = new();
    [JsonPropertyName("next_file")] public string NextFile { get; set; } = "";
}

public sealed class AddedRecord
{
    [JsonPropertyName("added")] public List<AddedDriver> Added { get; set; } = new();
}

public sealed class CommunityList
{
    [JsonPropertyName("projects")] public List<CommunityProject> Projects { get; set; } = new();
}

[JsonSerializable(typeof(CommunityList))]
[JsonSerializable(typeof(AddedRecord))]
[JsonSerializable(typeof(EfiFacts))]
[JsonSerializable(typeof(OfflineList))]
[JsonSerializable(typeof(InstallerPlan))]
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

/// <summary>What building an installer image from one app would take.
///
/// Asked before anything is created, so the size is known while it can still
/// be changed rather than after a twenty minute copy refuses.</summary>
public sealed class InstallerPlan
{
    [JsonPropertyName("available")] public bool Available { get; set; }
    [JsonPropertyName("why")] public string Why { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    [JsonPropertyName("app")] public long App { get; set; }
    [JsonPropertyName("overhead")] public long Overhead { get; set; }
    [JsonPropertyName("gib")] public int Gib { get; set; }
}

public static class Inventory
{
    /// <summary>Sizes for one installer app. Reads nothing and writes nothing.</summary>
    public static async Task<(InstallerPlan? said, string complaint)> InstallerPlan(
        Located engine, string app)
    {
        var (output, error, code) = await Builder.Run(engine, "--installer-plan", app);
        try
        {
            var got = JsonSerializer.Deserialize(output, Carried.Default.InstallerPlan);
            if (got is not null) return (got, "");
            return (null, Said(error, code));
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    /// <summary>The privileged half as text, so it can be read before it runs.</summary>
    public static async Task<(string text, string complaint)> InstallerScript(
        Located engine, string app, bool legacy)
    {
        var arguments = new List<string> { "--make-installer", app,
                                           "--installer-script" };
        if (!legacy) arguments.Add("--no-legacy");
        var (output, error, code) = await Builder.Run(engine, arguments.ToArray());
        return code == 0 ? (output, "") : ("", Said(error, code));
    }

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

    public static async Task<(CommunityList? list, string complaint)> Community(Located engine)
    {
        var (output, error, code) = Program.MachineFile is { Length: > 0 } report
            ? await Builder.Run(engine, "--inventory", "community", "--machine", report)
            : await Builder.Run(engine, "--inventory", "community");
        if (code != 0) return (null, Said(error, code));
        try
        {
            return (JsonSerializer.Deserialize(output, Carried.Default.CommunityList), "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    public static async Task<(RecoveryList? list, string complaint)> Recoveries(Located engine)
    {
        // judged for the machine being installed: the one the Machine pane shows
        var (output, error, code) = Program.MachineFile is { Length: > 0 } report
            ? await Builder.Run(engine, "--inventory", "recovery", "--machine", report)
            : await Builder.Run(engine, "--inventory", "recovery");
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

    public static async Task<(OfflineList? list, string complaint)> Offline(Located engine)
    {
        var (output, error, code) = await Builder.Run(engine, "--offline-list");
        if (code != 0) return (null, Said(error, code));
        try
        {
            var list = JsonSerializer.Deserialize(output, Carried.Default.OfflineList);
            return list is { Complaint.Length: > 0 } ? (null, list.Complaint) : (list, "");
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

    /// <summary>The community drivers in a built EFI; empty when it has none
    /// or its record cannot be read. Read from the folder, not asked of the
    /// engine: it is one small file the engine wrote.</summary>
    public static List<AddedDriver> Added(string efi)
    {
        try
        {
            var text = File.ReadAllText(Path.Combine(efi, "OC", "Community", "record.json"));
            return JsonSerializer.Deserialize(text, Carried.Default.AddedRecord)?.Added ?? new();
        }
        catch (Exception) { return new(); }
    }

    /// <summary>What a built EFI holds, as the engine reads it back.</summary>
    public static async Task<(EfiFacts? facts, string complaint)> Efi(Located engine, string efi)
    {
        var (output, error, code) = await Builder.Run(engine, "--inventory", "efi", "--out", efi);
        if (code != 0) return (null, Said(error, code));
        try
        {
            var facts = JsonSerializer.Deserialize(output, Carried.Default.EfiFacts);
            return facts is { Complaint.Length: > 0 } ? (null, facts.Complaint) : (facts, "");
        }
        catch (JsonException e) { return (null, e.Message); }
    }

    /// <summary>Take community drivers out of a built EFI.</summary>
    public static async Task<(string said, int code)> TakeOut(Located engine, string efi, string name)
    {
        var (output, error, code) = await Builder.Run(engine, "--community-remove", name, "--out", efi);
        return (code == 0 ? output : Said(error, code), code);
    }

    static string Said(string error, int code) =>
        error.Trim() is { Length: > 0 } said ? said : $"the engine exited {code}";
}
