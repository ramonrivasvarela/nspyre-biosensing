import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
from special_widgets import unit_widgets

import experiments.testing_axis



import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
        }

class TestingAxisWidget(ExperimentWidget):
    def __init__(self):
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(10)

        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setMaximum(100)
        runs_sb.setValue(1)

        n_steps_sb = QSpinBox()
        n_steps_sb.setMinimum(1)
        n_steps_sb.setMaximum(1000)
        n_steps_sb.setValue(100)
        
        params_config = {
            'runs': {
                'display_text': 'Runs',
                'widget': runs_sb,
            },
            'points_per_step': {
                'display_text': 'Points per Step',
                'widget': n_points_sb,
            },
            'n_steps': {
                'display_text': 'Number of Steps',
                'widget': n_steps_sb,
            },
            'starting_point': {
                'display_text': 'Starting Point',
                'widget': QLineEdit("(0, 0, 50)"),  # Default to 10 units
            },
            'scan_distance': {
                'display_text': 'Scan Distance',
                'widget': QLineEdit("(0.5, 0.5, 0.5)"),  # Default to 10 units
            },

            'time_per_point': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=0.1,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('testing_axis'),
            },
        }

        super().__init__(params_config, 
                        experiments.testing_axis,
                        'TestingAxis',
                        'main',
                        title='testing axis', get_param_value_funs=get_param_value_funs)

class TestingAxisPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('counts')