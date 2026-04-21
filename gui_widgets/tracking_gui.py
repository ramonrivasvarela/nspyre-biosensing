from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget

class CountsPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def data_processing_func(self, sink):
        sink.title="Tracking"
        sink.ylabel="Counts"
        sink.xlabel="Time (s)"

    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('X_Position',        series='x_pos',   scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('Y_Position',        series='y_pos',   scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('Z_Position',        series='z_pos',   scan_i='',     scan_j='',  processing='Append', hidden=True)


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('')