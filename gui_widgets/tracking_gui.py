from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget

class TrackingPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""


    def __init__(self):
        super().__init__(xlabel='Time (s)', title='Tracking')
        # create some default signal plots
        self.add_plot('X_Position',        series='x_pos',   scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)
        self.add_plot('Y_Position',        series='y_pos',   scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)
        self.add_plot('Z_Position',        series='z_pos',   scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)
        self.add_plot('Fluorescence',      series='total_fluor',   scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=False)
        self.add_plot('X_Search',          series='x_search', scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)
        self.add_plot('Y_Search',          series='y_search', scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)
        self.add_plot('Z_Search',          series='z_search', scan_i='',     scan_j='',  processing='Append',  iteration=0,  hidden=True)


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('feedback')