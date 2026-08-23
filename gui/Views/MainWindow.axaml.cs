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

    void Swap()
    {
        MachinePane.IsVisible = ToMachine.IsChecked == true;
        BuilderPane.IsVisible = ToBuilder.IsChecked == true;
    }
}
