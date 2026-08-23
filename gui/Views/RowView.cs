// One hardware row, ready to draw.
//
// The verdict arrives as a word and leaves as a class name, because the colour
// of a pill is a styling question and belongs in the stylesheet with the rest
// of them - not baked in here, where it would stop following the theme.
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Avalonia.Media;
using Shell.Engine;

namespace Shell.Views;

public sealed partial class RowView
{
    // the id is already in the device name, and it is a column of its own
    [GeneratedRegex(@"\s*\[[0-9a-fA-F:]+\]\s*$")]
    private static partial Regex TrailingId();

    public RowView(Row row)
    {
        Part = row.Part;
        What = TrailingId().Replace(row.What, "");
        // the sentence is written for a console with one column; here the
        // kext and the id have columns of their own, and repeating them
        // underneath says the same thing twice
        Note = row.Note;
        HasNote = row.Note.Length > 0;
        Ids = string.Join("\n", row.Ids);
        // the view model, not the payload: binding the payload straight
        // through drew the type name in the column
        Kexts = row.Kexts.Select(k => new KextView(k)).ToList();
        HasKexts = row.Kexts.Count > 0;
        Icon = Icons.For(row.Part);

        (Label, IsOk, IsBad, IsUnknown) = row.Verdict switch
        {
            "supported" => ("supported", true, false, false),
            // only ever said about a Mac, and it answers a different question:
            // not "does a kext here claim it" but "is macOS driving it"
            "driven by macOS" => ("driven by macOS", true, false, false),
            "not supported" => ("not supported", false, true, false),
            "unknown" => ("unknown", false, false, true),
            "-" => ("not present", false, false, false),
            _ => (row.Verdict, false, false, false),
        };
    }

    public string Part { get; }
    public string What { get; }
    public string Note { get; }
    public bool HasNote { get; }
    public string Ids { get; }
    public string Label { get; }
    public bool IsOk { get; }
    public bool IsBad { get; }
    public bool IsUnknown { get; }
    public bool HasKexts { get; }
    public Geometry? Icon { get; }
    public IReadOnlyList<KextView> Kexts { get; }
}

public sealed class KextView
{
    public KextView(KextFacts facts)
    {
        Bundle = facts.Bundle;
        Version = facts.Version ?? "";
        Url = facts.Url ?? "";
        HasUrl = !string.IsNullOrEmpty(facts.Url);
        // "not shipped here" is the more useful half when both are true: a kext
        // this repository does not carry cannot be added whatever its licence
        Aside = facts.Shipped ? facts.Licence ?? "licence unread"
                              : "not shipped here";
    }

    public string Bundle { get; }
    public string Version { get; }
    public string Url { get; }
    public bool HasUrl { get; }
    public string Aside { get; }
}

public sealed class BoundView
{
    public BoundView(Bound bound)
    {
        What = bound.What;
        Span = $"{bound.From?.ToString() ?? "any"} → {bound.To?.ToString() ?? "current"}";
    }

    public string What { get; }
    public string Span { get; }
}

public static class Icons
{
    // Drawn rather than photographed: a product photograph would need a source
    // and a licence, and this program does not reach the network.
    static readonly Dictionary<string, string> Paths = new()
    {
        ["CPU"] = "M4,4 H12 V12 H4 Z M6.2,1.6 V4 M9.8,1.6 V4 M6.2,12 V14.4 M9.8,12 V14.4 M1.6,6.2 H4 M1.6,9.8 H4 M12,6.2 H14.4 M12,9.8 H14.4",
        ["Graphics"] = "M1.8,3 H14.2 V11 H1.8 Z M5.5,13.4 H10.5",
        ["Audio"] = "M8.8,3.2 L5.6,5.9 H3.2 V10.1 H5.6 L8.8,12.8 Z M11.2,6 A3.2,3.2 0 0 1 11.2,10",
        ["Ethernet"] = "M4.4,2.2 H11.6 V7.2 H4.4 Z M8,7.2 V10.2 M3,13.8 V11.6 H13 V13.8",
        ["Wi-Fi"] = "M2,6.2 A8.6,8.6 0 0 1 14,6.2 M4.4,8.8 A5.2,5.2 0 0 1 11.6,8.8 M6.8,11.9 A1.2,1.2 0 1 0 9.2,11.9 A1.2,1.2 0 1 0 6.8,11.9",
        ["Bluetooth"] = "M6,4.6 L10.2,8 L8,9.8 V3.2 L10.2,5 L6,11.4",
        ["Storage"] = "M2.2,4.6 H13.8 V11.4 H2.2 Z M4.4,6.6 H7.8 M10.1,8 A1.1,1.1 0 1 0 12.3,8 A1.1,1.1 0 1 0 10.1,8",
        ["Trackpad"] = "M2.2,3.4 H13.8 V12.6 H2.2 Z M8,3.4 V7.8 M2.2,7.8 H13.8",
        ["Camera"] = "M1.8,5.4 H4.4 L5.5,3.8 H10.4 L11.5,5.4 H14.2 V12.6 H1.8 Z M5,8.4 A3,3 0 1 0 11,8.4 A3,3 0 1 0 5,8.4",
        ["Card reader"] = "M2,3.6 H14 V12.4 H2 Z M5,3.6 V6.8 M7.2,3.6 V6.8 M9.4,3.6 V6.8",
    };

    public static Geometry? For(string part) =>
        Paths.TryGetValue(part, out var data) ? Geometry.Parse(data) : null;

    public static IEnumerable<string> Known => Paths.Keys;
}
