import numpy as np

from nspyre import FlexLinePlotWidget
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

get_param_value_funs={
            unit_widgets.PointWidget: lambda w: w.get_point(),
            unit_widgets.MLineEdit:   lambda w: w.umvalue,
            unit_widgets.HzLineEdit:  lambda w: w.hzvalue,
            unit_widgets.SecLineEdit:  lambda w: w.secvalue,
            unit_widgets.NSLineEdit:  lambda w: w.nsvalue,
            unit_widgets.HzIntervalWidget: lambda w: w.get_range(),
            unit_widgets.ThreeValueWidget: lambda w: w.get_values(),
            QSpinBox: lambda w: w.value(),
        }

class CountsWidget(ExperimentWidget):
    def __init__(self):
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(10)
        
        params_config = {
            'n_points': {
                'display_text': '# Points',
                'widget': n_points_sb,
            },

            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=0.1,
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
                        title='counts vs time', get_param_value_funs=get_param_value_funs)


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