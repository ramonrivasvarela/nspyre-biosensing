import numpy as np

from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget
from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
from special_widgets import unit_widgets

import experiments.counts


import experiments.confocalODMR

import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  


class CountsWidget(ExperimentWidget):
    def __init__(self):
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(1)
        
        params_config = {
            'n_points': {
                'display_text': '# Points',
                'widget': n_points_sb,
            },

            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=1,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },
            'clock_time': {
                'display_text': 'Clock Time',
                'widget': SpinBox(
                    value=10e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('counts'),
            },
        }

        super().__init__(params_config, 
                        experiments.counts,
                        'CountsTime',
                        'confocal_counts_time',
                        title='counts vs time')


class CountsPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('counts',        series='counts',   scan_i='',     scan_j='',  processing='Append')


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('counts')