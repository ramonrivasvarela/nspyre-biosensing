import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget

from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox

from special_widgets import unit_widgets

import experiments.WFODMR

import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
    SpinBox: lambda w: w.value() if w.opts.get('suffix', '') != 'm' else w.value()*1e6,
    QSpinBox: lambda w: w.value(),
    QLineEdit: lambda w: w.text(),
    QCheckBox: lambda w: w.isChecked(),
    QComboBox: lambda w: w.currentText(),
}

class WideFieldWidget(ExperimentWidget):
    def __init__(self):

        gain_sb = QSpinBox()
        gain_sb.setMinimum(1)
        gain_sb.setValue(2)
        gain_sb.setMaximum(272)

        repeat_minutes_sb = SpinBox(
            value=0,
            suffix='min',
            siPrefix=False,
            dec=True,
            bounds=(0, 1440),
        )

        rf_amplitude_sb = SpinBox(
            value=-15,
            suffix='dBm',
            siPrefix=False,
            dec=True,
            bounds=(-100, 10),
        )

        mw_duty_sb = SpinBox(
            value=1,
            siPrefix=False,
            dec=True,
            bounds=(0.001, 1),
        )

        mw_rep_sb = SpinBox(
            value=50,
            suffix='Hz',
            siPrefix=True,
            dec=True,
            bounds=(1, 1e6),
        )

        cam_trigger_cb = QComboBox()
        cam_trigger_cb.addItems(['EXTERNAL_EXPOSURE', 'EXTERNAL_FT'])
        cam_trigger_cb.setCurrentText('EXTERNAL_FT')

        optimize_gain_cb = QCheckBox()
        optimize_gain_cb.setChecked(True)

        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setValue(1)

        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setValue(1)

        reps_sb = QSpinBox()
        reps_sb.setMinimum(1)
        reps_sb.setValue(1)

        params_config = {
            'exp_time': {
                'display_text': 'Exposure Time',
                'widget': SpinBox(
                    value=75e-3,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                )
            },
            'cam_trigger': {
                'display_text': 'Camera Trigger',
                'widget': cam_trigger_cb,
            },
            'readout_time': {
                'display_text': 'Readout Time',
                'widget': SpinBox(
                    value=15e-3,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                )
            },
            'gain': {
                'display_text': 'EM Gain',
                'widget': gain_sb,
            },
            'ROI_xyr': {
                'display_text': 'ROI X/Y/R',
                'widget': QLineEdit('[(512,512,16,7)]'),
            },
            'repeat_every_x_minutes': {
                'display_text': 'Repeat Every X Minutes',
                'widget': repeat_minutes_sb,
            },
            'runs_sweeps_reps': {
                'display_text': 'Runs, Sweeps, Reps',
                'widget': QLineEdit('(1,1,1)'),
            },
            'frequency': {
                'display_text': 'Frequency',
                'widget': QLineEdit('(2.85e9, 2.89e9, 30)'),
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb,
            },
            'mw_duty': {
                'display_text': 'MW Duty',
                'widget': mw_duty_sb,
            },
            'mw_rep': {
                'display_text': 'MW Rep',
                'widget': mw_rep_sb,
            },
            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=160e-3,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                )
            },
            'optimize_gain': {
                'display_text': 'Optimize Gain',
                'widget': optimize_gain_cb,
            },
            'trackpy': {
                'display_text': 'Trackpy',
                'widget': QCheckBox(),
            },
            'trackpy_params': {
                'display_text': 'Trackpy Params',
                'widget': QLineEdit("(False, 40, 800)"),
            },
            'sleep_time': {
                'display_text': 'Sleep Time',
                'widget': SpinBox(
                    value=0,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0, 3600),
                )
            },
            'data_path': {
                'display_text': 'Data Path',
                'widget': QLineEdit('Z:\\biosensing_setup\\data\\WFODMR_images_test'),
            },
            'dataset': {
                'display_text': 'Wide Field ODMR',
                'widget': QLineEdit('wfodmr')
            }
        }

        super().__init__(
            params_config,
            experiments.WFODMR,
            'WideFieldODMR',
            'widefield',
            title='Wide Field Imaging', 
            get_param_value_funs=get_param_value_funs
        )

class WFODMRPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('Signal 1',        series='signal_1',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('Background 1',        series='background_1',   scan_i='',     scan_j='',  processing='Average')

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('wfodmr')