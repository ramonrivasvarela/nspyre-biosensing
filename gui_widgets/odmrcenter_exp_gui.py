import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QComboBox
from special_widgets import unit_widgets
from nspyre import DataSink

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
        rf_amplitude_sb.setValue(-15)

        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'AM'])
        mode_cb.setCurrentText('QAM')

        n_steps_sb = QSpinBox()
        n_steps_sb.setMinimum(1)
        n_steps_sb.setMaximum(MAXIMUM)
        n_steps_sb.setValue(20)

        sb_every_sb = QSpinBox()
        sb_every_sb.setMinimum(1)
        sb_every_sb.setMaximum(MAXIMUM)
        sb_every_sb.setValue(50)

        factor_sb = SpinBox()
        factor_sb.setMinimum(0)
        factor_sb.setMaximum(1)
        factor_sb.setValue(0.9)
        
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
                'widget': QLineEdit("(100000000, 30000, 0.0)"),
            
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
            'sb_every': {
                'display_text': 'Spatial Feedback Every N Runs',
                'widget': sb_every_sb
            },
            'factor': {
                'display_text': 'Multiply integrant by',
                'widget': factor_sb
            }
        }

        super().__init__(params_config, 
                        experiments.odmrcenterFM,
                        'ODMRCenter',
                        'main',
                        title='odmr center', get_param_value_funs=get_param_value_funs)


def process_ODMR_data(sink: DataSink):
    """Subtract the signal from background trace and add it as a new 'diff' dataset."""
    # FIX: Use separate lists for left and right
    left_div_sweeps = []
    for s, _ in enumerate(sink.datasets['left_sg']):
        freqs = sink.datasets['left_sg'][s][0]
        sig = sink.datasets['left_sg'][s][1]
        bg = sink.datasets['left_bg'][s][1]
        left_div_sweeps.append(np.stack([freqs, sig / bg]))
    sink.datasets['left_div'] = left_div_sweeps
    
    right_div_sweeps = []
    for s, _ in enumerate(sink.datasets['right_sg']):
        freqs = sink.datasets['right_sg'][s][0]
        sig = sink.datasets['right_sg'][s][1]
        bg = sink.datasets['right_bg'][s][1]
        right_div_sweeps.append(np.stack([freqs, sig / bg]))
    sink.datasets['right_div'] = right_div_sweeps

    

class ODMRCenterPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_ODMR_data)
        # create some default signal plots
        self.add_plot('left_sig_avg',        series='left_sg',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('left_sig_latest',     series='left_sg',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default background plots
        self.add_plot('left_bg_avg',         series='left_bg',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('left_bg_latest',      series='left_bg',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default diff plots
        self.add_plot('left_div_avg',       series='left_div',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('left_div_latest',    series='left_div',  scan_i='-1',    scan_j='',  processing='Average')

        self.add_plot('right_sig_avg',        series='right_sg',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('right_sig_latest',     series='right_sg',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default background plots
        self.add_plot('right_bg_avg',         series='right_bg',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('right_bg_latest',      series='right_bg',   scan_i='-1',   scan_j='',  processing='Average')


        # create some default diff plots
        self.add_plot('right_div_avg',       series='right_div',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('right_div_latest',    series='right_div',  scan_i='-1',    scan_j='',  processing='Average')
 
        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmrcenter')

class ODMRCenterTrackPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('left_contrast',        series='left_contrast',   scan_i='',     scan_j='',  processing='Append')
        self.add_plot('right_contrast',       series='right_contrast',  scan_i='',     scan_j='',  processing='Append')
        self.add_plot('frequency',            series='frequency',       scan_i='',     scan_j='',  processing='Append')

 
        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('tracking_odmr_center')