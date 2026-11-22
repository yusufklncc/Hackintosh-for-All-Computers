// A turning ring and a sentence: the one way this window says "working on it".
using Avalonia.Controls;

namespace Shell.Views;

public partial class Busy : UserControl
{
    public Busy() => InitializeComponent();

    /// <summary>What is being waited for, in a few words.</summary>
    public string Text
    {
        get => Said.Text ?? "";
        set => Said.Text = value;
    }

    /// <summary>Show it saying this, or hide it with null.</summary>
    public void Say(string? text)
    {
        IsVisible = text is not null;
        if (text is not null) Said.Text = text;
    }
}
