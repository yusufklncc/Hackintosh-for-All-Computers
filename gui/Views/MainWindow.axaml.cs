using Avalonia.Controls;

namespace Shell.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        // what the program carries, said once and not repeated on every pane
        Standing.Text = "179 configs\n41 kexts vendored\nno network needed";

        ToMachine.IsCheckedChanged += (_, _) => Swap();
        ToBuilder.IsCheckedChanged += (_, _) => Swap();
    }

    /// <summary>Switch to the builder and start one, for the screenshot pass.</summary>
    public async System.Threading.Tasks.Task ShowBuilder()
    {
        ToBuilder.IsChecked = true;
        await BuilderPane.StartForRender();
    }

    public string BuilderState() => BuilderPane.State();

    void Swap()
    {
        MachinePane.IsVisible = ToMachine.IsChecked == true;
        BuilderPane.IsVisible = ToBuilder.IsChecked == true;
    }
}
