// Everything the tables know, in one list a person can search.
//
// The rows are read once and filtered in memory. Six hundred of them is not a
// number worth asking the engine about again on every keystroke, and a
// catalogue that lags behind the typing is a catalogue nobody uses.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed class DeviceItem
{
    public DeviceItem(DeviceRow row)
    {
        Category = row.Category;
        Name = row.Name;
        Vendor = row.Vendor ?? "";
        Id = row.Id ?? "";
        Kext = row.Kext ?? "";
        Note = row.Macos is { From: { } from }
            ? $"{row.Note} · macOS {from}" + (row.Macos.To is { } to ? $"–{to}" : " and newer")
            : row.Note;
        // one string to match against, lower-cased once rather than per keystroke
        Haystack = $"{Category} {Name} {Vendor} {Id} {Kext} {Note}".ToLowerInvariant();
    }

    public string Category { get; }
    public string Name { get; }
    public string Vendor { get; }
    public string Id { get; }
    public string Kext { get; }
    public string Note { get; }
    public string Haystack { get; }
}

public partial class DevicesView : UserControl
{
    const string Everything = "All";
    List<DeviceItem> _all = new();
    bool _loaded;
    // which column orders the list, and which way. One at a time: two keys
    // would need a second arrow and nobody would read it.
    string _sortBy = "category";
    bool _ascending = true;

    public DevicesView()
    {
        InitializeComponent();
        Search.TextChanged += (_, _) => Draw();
        Category.SelectionChanged += (_, _) => Draw();
        Vendor.SelectionChanged += (_, _) => Draw();
        SortCategory.Click += (_, _) => SortOn("category");
        SortName.Click += (_, _) => SortOn("name");
    }

    /// <summary>Order by this column, or turn it round if it already is.</summary>
    void SortOn(string column)
    {
        if (_sortBy == column) _ascending = !_ascending;
        else { _sortBy = column; _ascending = true; }
        Draw();
    }

    public async Task Load()
    {
        if (_loaded) return;
        _loaded = true;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Blurb.Text = missing; return; }

        var (list, complaint) = await Inventory.Devices(engine);
        if (list is null) { Blurb.Text = complaint; return; }

        _all = list.Devices.Select(d => new DeviceItem(d)).ToList();
        Blurb.Text = $"{_all.Count} devices across {list.Categories.Count} categories, "
                   + "read out of the same tables a build reads. A device being here "
                   + "means something in this repository claims it - not that every "
                   + "machine it sits in will work.";
        Category.ItemsSource = new[] { Everything }.Concat(list.Categories).ToList();
        Vendor.ItemsSource = new[] { Everything }.Concat(list.Vendors).ToList();
        Category.SelectedIndex = 0;
        Vendor.SelectedIndex = 0;
        Draw();
    }

    void Draw()
    {
        var needle = (Search.Text ?? "").Trim().ToLowerInvariant();
        var category = Category.SelectedItem as string ?? Everything;
        var vendor = Vendor.SelectedItem as string ?? Everything;

        var matching = _all.Where(d =>
            (category == Everything || d.Category == category) &&
            (vendor == Everything || d.Vendor == vendor) &&
            (needle.Length == 0 || d.Haystack.Contains(needle, StringComparison.Ordinal)));

        // ordinal-ignore-case, so "BCM4311" and "bcm4311" sort together and a
        // list of hex ids does not depend on anybody's locale
        var by = _sortBy == "name"
            ? (Func<DeviceItem, string>)(d => d.Name)
            : d => d.Category + " " + d.Name;
        matching = _ascending
            ? matching.OrderBy(by, StringComparer.OrdinalIgnoreCase)
            : matching.OrderByDescending(by, StringComparer.OrdinalIgnoreCase);
        var shown = matching.ToList();

        // the arrow goes on the column doing the ordering, and only that one
        var arrow = _ascending ? "  \u2191" : "  \u2193";
        SortCategoryLabel.Text = "CATEGORY" + (_sortBy == "category" ? arrow : "");
        SortNameLabel.Text = "DEVICE" + (_sortBy == "name" ? arrow : "");

        Rows.ItemsSource = shown;
        Count.Text = shown.Count == _all.Count
            ? $"{shown.Count} devices"
            : $"{shown.Count} of {_all.Count} devices";
    }
}
