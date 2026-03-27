import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox
from pyqtgraph import SpinBox

import experiments.confocalODMR
import sys

import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  



MAXIMUM=2147483647 # There has to be a better way...
class ConfocalFMODMRWidget(ExperimentWidget):
    def __init__(self):

        # Define widgets that require extra configuration outside of params:
        
        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setMaximum(MAXIMUM)
        runs_sb.setValue(10)
        
        timeout_sb = QSpinBox()
        timeout_sb.setMinimum(0)
        timeout_sb.setValue(30)
        
        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setMaximum(MAXIMUM)
        sweeps_sb.setValue(100)

        sweeps_til_fb_sb = QSpinBox()
        sweeps_til_fb_sb.setMinimum(1)
        sweeps_til_fb_sb.setMaximum(MAXIMUM)
        sweeps_til_fb_sb.setValue(6)
        
        starting_point_cb = QComboBox()
        starting_point_cb.addItems(['user_input', 'current_position (ignore input)'])
        starting_point_cb.setCurrentText('current_position (ignore input)')

        rf_amplitude_sb = SpinBox(
            value=-20,
            suffix='dBm',
            siPrefix=False,
            dec=True,
            bounds=(-100, 10),
        )

        feedback_cb=QCheckBox()
        feedback_cb.setChecked(True)

        dozfb_cb=QCheckBox()
        dozfb_cb.setChecked(True)

        count_step_shrink_sb=QSpinBox()
        count_step_shrink_sb.setMinimum(1)

        
        # Build the parameter configuration dictionary using only display_text and widget.
        # Widgets that require extra config have been defined above.
        params_config = {
            'runs': {
                'display_text': 'Runs',
                'widget': runs_sb
            },
            'timeout': {
                'display_text': 'Timeout',
                'widget': timeout_sb
            },
            'sweeps': {
                'display_text': 'Sweeps',
                'widget': sweeps_sb
            },

            'frequencies': {
                'display_text': 'Frequencies',
                'widget': QLineEdit("(2.84e9, 2.90e9, 30)")
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb
            },
            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=100e-6,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-9, 1),
                )
            },
            'clock_duration': {
                'display_text': 'Clock Duration',
                'widget': SpinBox(
                    value=10e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1),
                )
            },
            'laser_lag': {
                'display_text': 'Laser Lag',
                'widget': SpinBox(
                    value=80e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1),
                )
            },
            'cooldown_time': {
                'display_text': 'Cooldown Time',
                'widget': SpinBox(
                    value=0,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0, 1000),
                )
            },

            'feedback': {
                'display_text': 'Feedback',
                'widget': feedback_cb
            },
            'dozfb': {
                'display_text': 'Z Feedback',
                'widget': dozfb_cb
            },
            'sweeps_til_fb': {
                'display_text': 'Sweeps Till Feedback',
                'widget': sweeps_til_fb_sb
            },
        
            'xyz_step': {
                'display_text': 'XYZ Step',
                'widget': SpinBox(
                    value=45e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1e-3),
                )
            },
            'count_step_shrink': {
                'display_text': 'Count Step Shrink',
                'widget': count_step_shrink_sb
            },
            'starting_point': {
                'display_text': 'Starting Point',
                'widget': starting_point_cb
            },
            'dataset':{
                'display_text':'Data Set',
                'widget':QLineEdit('odmr')
            }
        }
        
        super().__init__(
            params_config,
            experiments.confocalODMR,  # Ensure that experiments.ConfocalODMR exists in your experiments folder
            'ConfocalFMODMR',
            'confocal_fmodmr',
            title='Confocal FMODMR'
        )

def process_ODMR_data(sink: DataSink):
    """Subtract the signal from background trace and add it as a new 'diff' dataset."""
    div_sweeps = []
    for s,_ in enumerate(sink.datasets['signal']):
        freqs = sink.datasets['signal'][s][0]
        sig = sink.datasets['signal'][s][1]
        bg = sink.datasets['background'][s][1]
        div_sweeps.append(np.stack([freqs, sig / bg]))
    sink.datasets['div'] = div_sweeps


class ConfocalODMRPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_ODMR_data)
        # create some default signal plots
        self.add_plot('sig_avg',        series='signal',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('sig_latest',     series='signal',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default background plots
        self.add_plot('bg_avg',         series='background',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('bg_latest',      series='background',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default diff plots
        self.add_plot('div_avg',       series='div',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('div_latest',    series='div',  scan_i='-1',    scan_j='',  processing='Average') #what does append do in this case? Test it some day...


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmr')