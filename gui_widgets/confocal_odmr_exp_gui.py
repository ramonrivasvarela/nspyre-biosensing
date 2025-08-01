import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
import experiments.counts_new
from special_widgets import unit_widgets
from pyqtgraph import SpinBox

import experiments.confocalODMR
import sys

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
            unit_widgets.FlexiblePointWidget: lambda w: w.get_points(),
        }

MAXIMUM=2147483647
class ConfocalODMRWidget(ExperimentWidget):
    def __init__(self):
        from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox

        # Define widgets that require extra configuration outside of params:
        channel1_cb = QComboBox()
        channel1_cb.addItems(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none'])
        channel1_cb.setCurrentText('ctr1')
        
        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        
        runs_sb.setMaximum(MAXIMUM)
        runs_sb.setValue(1000)
        
        timeout_sb = QSpinBox()
        timeout_sb.setMinimum(0)
        timeout_sb.setValue(30)
        
        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setMaximum(MAXIMUM)
        sweeps_sb.setValue(10)


        
        repetitions_sb = QSpinBox()
        repetitions_sb.setMinimum(1)
        repetitions_sb.setValue(1)

        sequence_cb = QComboBox()
        sequence_cb.addItems(['odmr_heat_wait', 'odmr_no_wait'])
        sequence_cb.setCurrentText('odmr_no_wait')
        
        sweeps_til_fb_sb = QSpinBox()
        sweeps_til_fb_sb.setMinimum(1)
        sweeps_til_fb_sb.setMaximum(MAXIMUM)
        sweeps_til_fb_sb.setValue(6)
        
        starting_point_cb = QComboBox()
        starting_point_cb.addItems(['user_input', 'current_position (ignore input)'])
        starting_point_cb.setCurrentText('current_position (ignore input)')
        
        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'AM'])
        mode_cb.setCurrentText('QAM')

        sampling_rate_sb=unit_widgets.HzLineEdit(50000)

        repeat_minutes_sb = SpinBox()
        repeat_minutes_sb.setValue(0)
        repeat_minutes_sb.setMinimum(0)
        repeat_minutes_sb.setMaximum(None)
        repeat_minutes_sb.setDecimals(3)

        rf_amplitude_sb = QSpinBox()
        rf_amplitude_sb.setMinimum(-100)
        rf_amplitude_sb.setMaximum(7)
        rf_amplitude_sb.setValue(-20)

        feedback_cb=QCheckBox()
        feedback_cb.setChecked(True)

        dozfb_cb=QCheckBox()
        dozfb_cb.setChecked(True)

        count_step_shrink_sb=QSpinBox()
        count_step_shrink_sb.setMinimum(1)

        
        # Build the parameter configuration dictionary using only display_text and widget.
        # Widgets that require extra config have been defined above.
        params_config = {
            'device': {
                'display_text': 'Device',
                'widget': QLineEdit("Dev1")
            },
            'channel1': {
                'display_text': 'Channel1',
                'widget': channel1_cb
            },
            'PS_clk_channel': {
                'display_text': 'PS Clock Channel',
                'widget': QLineEdit("PFI0")
            },
            'sampling_rate': {
                'display_text': 'Sampling Rate',
                'widget': sampling_rate_sb
            },
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
            'repeat_every_x_minutes': {
                'display_text': 'Repeat Every X Minutes',
                'widget': repeat_minutes_sb
            },
            'repetitions': {
                'display_text': 'Repetitions',
                'widget': repetitions_sb
            },
            'frequency': {
                'display_text': 'Frequency',
                'widget': QLineEdit("(2.84e9, 2.90e9, 30)")
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb
            },
            'probe_time': {
                'display_text': 'Probe Time',
                'widget': unit_widgets.SecLineEdit(100e-6)
            },
            'clock_duration': {
                'display_text': 'Clock Duration',
                'widget': unit_widgets.SecLineEdit(10e-9)
            },
            'laser_lag': {
                'display_text': 'Laser Lag',
                'widget': unit_widgets.SecLineEdit(80e-9)
            },
            'cooldown_time': {
                'display_text': 'Cooldown Time',
                'widget': unit_widgets.SecLineEdit(5e-6)
            },
            'sequence': {
                'display_text': 'Sequence',
                'widget': sequence_cb
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
            # 'initial_position': {
            #     'display_text': 'Initial Position',
            #     'widget': unit_widgets.PointWidget(0.0, 0.0, 0.0)
            # },
            
            'xyz_step': {
                'display_text': 'XYZ Step',
                'widget': unit_widgets.MLineEdit(45e-9)
            },
            'count_step_shrink': {
                'display_text': 'Count Step Shrink',
                'widget': count_step_shrink_sb
            },
            'starting_point': {
                'display_text': 'Starting Point',
                'widget': starting_point_cb
            },
            'data_download': {
                'display_text': 'Data Download',
                'widget': QCheckBox()
            },
            'mode': {
                'display_text': 'Mode',
                'widget': mode_cb
            },
            'dataset':{
                'display_text':'Data Set',
                'widget':QLineEdit('odmr')
            }
        }
        
        super().__init__(
            params_config,
            experiments.confocalODMR,  # Ensure that experiments.ConfocalODMR exists in your experiments folder
            'ConfocalODMR',
            'confocal_odmr',
            title='Confocal ODMR',
            get_param_value_funs=get_param_value_funs
        )

class ConfocalODMRPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('Series',        series='series',   scan_i='',     scan_j='',  processing='Append')
        self.add_plot('Background',        series='background',   scan_i='',     scan_j='',  processing='Append')


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmr')