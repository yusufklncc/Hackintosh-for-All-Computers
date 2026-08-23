// The shape of what `setup.py --describe` writes.
//
// Deserialised through a generated context rather than by reflection: the
// published build is trimmed, and a trimmed reflection-based reader returns a
// document with every field null - a window that comes up empty and says
// nothing about why.
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Shell.Engine;

public sealed class Release
{
    [JsonPropertyName("darwin")] public int Darwin { get; set; }
    [JsonPropertyName("name")] public string? Name { get; set; }
    [JsonPropertyName("version")] public string? Version { get; set; }

    public override string ToString() =>
        Name is null ? $"Darwin {Darwin}" : $"{Name} {Version}";
}

public sealed class KextFacts
{
    [JsonPropertyName("bundle")] public string Bundle { get; set; } = "";
    [JsonPropertyName("version")] public string? Version { get; set; }
    [JsonPropertyName("upstream")] public string? Upstream { get; set; }
    [JsonPropertyName("url")] public string? Url { get; set; }
    [JsonPropertyName("licence")] public string? Licence { get; set; }
    [JsonPropertyName("shipped")] public bool Shipped { get; set; }
}

public sealed class Row
{
    [JsonPropertyName("part")] public string Part { get; set; } = "";
    [JsonPropertyName("what")] public string What { get; set; } = "";
    [JsonPropertyName("verdict")] public string Verdict { get; set; } = "";
    [JsonPropertyName("detail")] public string Detail { get; set; } = "";
    [JsonPropertyName("note")] public string Note { get; set; } = "";
    [JsonPropertyName("kexts")] public List<KextFacts> Kexts { get; set; } = new();
    [JsonPropertyName("ids")] public List<string> Ids { get; set; } = new();
}

public sealed class Profile
{
    [JsonPropertyName("cpu")] public string? Cpu { get; set; }
    [JsonPropertyName("model")] public string? Model { get; set; }
    [JsonPropertyName("system")] public string? System { get; set; }
    [JsonPropertyName("generation")] public string? Generation { get; set; }
    [JsonPropertyName("oem")] public string? Oem { get; set; }
    [JsonPropertyName("cores")] public int? Cores { get; set; }
}

public sealed class Bound
{
    [JsonPropertyName("what")] public string What { get; set; } = "";
    [JsonPropertyName("from")] public Release? From { get; set; }
    [JsonPropertyName("to")] public Release? To { get; set; }
}

public sealed class MacosWindow
{
    [JsonPropertyName("from")] public Release? From { get; set; }
    [JsonPropertyName("from_because")] public string? FromBecause { get; set; }
    [JsonPropertyName("to")] public Release? To { get; set; }
    [JsonPropertyName("to_because")] public string? ToBecause { get; set; }
    [JsonPropertyName("parts")] public List<Bound> Parts { get; set; } = new();
}

public sealed class MacSupport
{
    [JsonPropertyName("board")] public string Board { get; set; } = "";
    [JsonPropertyName("from")] public Release? From { get; set; }
    [JsonPropertyName("to")] public Release? To { get; set; }
    [JsonPropertyName("listed")] public bool Listed { get; set; }
}

public sealed class MachineDocument
{
    [JsonPropertyName("source")] public string Source { get; set; } = "";
    [JsonPropertyName("platform")] public string? Platform { get; set; }
    [JsonPropertyName("profile")] public Profile Profile { get; set; } = new();
    [JsonPropertyName("rows")] public List<Row> Rows { get; set; } = new();
    [JsonPropertyName("macos")] public MacosWindow Macos { get; set; } = new();
    [JsonPropertyName("worth_showing")] public bool WorthShowing { get; set; }
    [JsonPropertyName("read")] public Dictionary<string, int> Read { get; set; } = new();
    [JsonPropertyName("mac")] public MacSupport? Mac { get; set; }
}

[JsonSerializable(typeof(MachineDocument))]
[JsonSourceGenerationOptions(PropertyNameCaseInsensitive = false)]
public partial class Payload : JsonSerializerContext
{
}
