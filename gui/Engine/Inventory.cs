// What the repository carries: the kexts, and the standing facts.
//
// Read rather than written down. The sidebar used to claim "OpenCore 1.0.6"
// and "41 kexts" from memory; the tree said 1.0.5 and 42.
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
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
    [JsonPropertyName("path")] public string Path { get; set; } = "";
    [JsonPropertyName("repo")] public string? Repo { get; set; }
    [JsonPropertyName("licence")] public string? Licence { get; set; }
    [JsonPropertyName("version")] public string? Version { get; set; }
}

public sealed class About
{
    [JsonPropertyName("opencore")] public string? OpenCore { get; set; }
    [JsonPropertyName("configs")] public int Configs { get; set; }
    [JsonPropertyName("kexts")] public int Kexts { get; set; }
    [JsonPropertyName("shipped")] public int Shipped { get; set; }
    [JsonPropertyName("offline")] public bool Offline { get; set; }
    [JsonPropertyName("sources")] public List<SourceRow> Sources { get; set; } = new();
    [JsonPropertyName("tally")] public Dictionary<string, int> Tally { get; set; } = new();
    [JsonPropertyName("tools")] public List<ToolRow> Tools { get; set; } = new();
}

public sealed class MacosSpan
{
    [JsonPropertyName("from")] public string? From { get; set; }
    [JsonPropertyName("to")] public string? To { get; set; }
    [JsonPropertyName("oclp")] public string? Oclp { get; set; }
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

[JsonSerializable(typeof(DeviceList))]
[JsonSerializable(typeof(KextList))]
[JsonSerializable(typeof(About))]
public partial class Carried : JsonSerializerContext
{
}

public static class Inventory
{
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
