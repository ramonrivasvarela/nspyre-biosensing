import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QComboBox
from special_widgets import unit_widgets

import experiments.odmrcenterFM


import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  
MAXIMUM=2147483647

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
            SpinBox: lambda w: w.value() if w.opts.get('suffix', '') != 'm' else w.value()*1e6,
        }

class ODMRCenterWidget(ExperimentWidget):
    def __init__(self):


        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setMaximum(MAXIMUM)
        runs_sb.setValue(1)

        rf_amplitude_sb = QSpinBox()
        rf_amplitude_sb.setMinimum(-100)
        rf_amplitude_sb.setMaximum(7)
        rf_amplitude_sb.setValue(-20)

        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'AM'])
        mode_cb.setCurrentText('QAM')

        n_steps_sb = QSpinBox()
        n_steps_sb.setMinimum(1)
        n_steps_sb.setMaximum(MAXIMUM)
        n_steps_sb.setValue(100)
        
        params_config = {
            'runs': {
                'display_text': '# Runs',
                'widget': runs_sb,
            },
            'n_steps': {
                'display_text': "# Steps",
                'widget': n_steps_sb,
            },
            'initial_odmr': {
                'display_text': 'Initial ODMR Freq',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                ),
            },
            'odmr_span': {
                'display_text': 'ODMR Span',
                'widget': SpinBox(
                    value=20e6,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                ),
            },
            'sweep_time': { 
                'display_text': 'Sweep Time',
                'widget': SpinBox(
                    value=1.0,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
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
            'laser_pause': {
                'display_text': 'Laser Pause',
                'widget': SpinBox(
                    value=0.0,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },

            'timeout_counter': {
                'display_text': 'Timeout Counter',
                'widget': SpinBox(
                    value=100,
                    siPrefix=False,
                    dec=True,
                ),
            },
            'PID': {
                'display_text': 'PID (kp, ki, kd)',
                'widget': QLineEdit("(1.0, 0.0, 0.0)"),
            
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb
            },
            # 'mode': {
            #     'display_text': 'Modulation Mode',
            #     'widget': mode_cb
            # },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmrcenter'),
            },
        }

        super().__init__(params_config, 
                        experiments.odmrcenterFM,
                        'ODMRCenter',
                        'main',
                        title='odmr center', get_param_value_funs=get_param_value_funs)


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