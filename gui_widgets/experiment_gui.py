"""
Example GUI elements.
"""
import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QDoubleSpinBox

from special_widgets import unit_widgets
from special_widgets.experiment_widget import ExperimentWidget

import experiments.counts
import experiments.planescan


class CountsWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'time_per_point': {
                'display_text': 'Time per Point',
                'widget': SpinBox(
                    value=0.1,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmr'),
            },
        }

        super().__init__(params_config, 
                        experiments.counts,
                        'CountsTime',
                        'confocal_counts_time',
                        title='counts vs time')


class FlexLinePlotWidgetWithODMRDefaults(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('counts',        series='counts',   scan_i='',     scan_j='',  processing='Append')


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('counts v time')

class PlaneScanWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
        'point_A':              {'display_text': 'Point A',
                            'widget': unit_widgets.PointWidget(0, 0, 0)},
        'point_B':              {'display_text': 'Point B',
                            'widget': unit_widgets.PointWidget(50, 0, 0)},
        'point_C':              {'display_text': 'Point C',
                            'widget': unit_widgets.PointWidget(50, 0, 60)},
        'line_scan_steps':      {'display_text': 'Line Scan Steps',
                                   'widget': SpinBox(
                                       value=100,
                                   )},
        'extent_steps':         {'display_text': 'Extent Steps',
                                   'widget': SpinBox(
                                       value=100,
                                   )},
        'ctr_ch':               {'display_text': 'Center Channel',
                                   'widget': QLineEdit("Dev1/ctr1")},
        'repetitions':          {'display_text': 'Repetitions',
                                   'widget': SpinBox(
                                       value=1,
                                   )},
        'stack_count':          {'display_text': 'Stack Count',
                                   'widget': SpinBox(
                                        value=1,
                                        minimum=1,
                                   )},
        'stack_stepsize':       {'display_text': 'Stack Stepsize',
                                   'widget': unit_widgets.MLineEdit(1)},
        'stack_pospref':        {'display_text': 'Stack Position Preference',
                                   'widget': QCheckBox()},
        'acq_rate':             {'display_text': 'Acquisition Rate',
                                   'widget': unit_widgets.HzLineEdit(15e3)},
        'pts_per_step':         {'display_text': 'Points Per Step',
                                   'widget': SpinBox(
                                       value=40,
                                       minimum=1,
                                   )},
        'xyz_pos':              {'display_text': 'XYZ Position',
                                   'widget': QCheckBox()},
        'excel':                {'display_text': 'Excel Export',
                                   'widget': QCheckBox()},
        'snake_scan':           {'display_text': 'Snake Scan',
                                   'widget': QCheckBox()},
        'sleep_factor':         {'display_text': 'Sleep Factor',
                                   'widget': SpinBox(
                                       value=1,
                                       minimum=0.001
                                   )},
        'dataset':              {
                                'display_text': 'Data Set',
                                'widget': QtWidgets.QLineEdit('planescan'),
            },
        }
    

        super().__init__(params_config,
                        experiments.planescan,
                        'PlaneScan',
                        'planescan',
                        title='Plane Scan')