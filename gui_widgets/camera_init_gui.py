import numpy as np

from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox

import experiments.initializecamera

get_param_value_funs = {
    QSpinBox: lambda w: w.value(),
    QLineEdit: lambda w: w.text(),
    QCheckBox: lambda w: w.isChecked(),
    SpinBox: lambda w: w.value(),
    QComboBox: lambda w: w.currentText(),
}

class CameraInitWidget(ExperimentWidget):
    def __init__(self):
        gain_sb = QSpinBox()
        gain_sb.setMinimum(1)
        gain_sb.setMaximum(255)
        gain_sb.setValue(1)

        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setMaximum(100)
        runs_sb.setValue(1)

        ns_probe_time_sb = SpinBox(value=1e8, suffix='ns', siPrefix=True, dec=True)
        ns_exp_time_sb = SpinBox(value=1e8, suffix='ns', siPrefix=True, dec=True)
        ns_readout_time_sb = SpinBox(value=0.05e9, suffix='ns', siPrefix=True, dec=True)
        ns_laser_lag_sb = SpinBox(value=0.02e9, suffix='ns', siPrefix=True, dec=True)

        optimize_gain_cb = QCheckBox()
        optimize_gain_cb.setChecked(True)

        cam_trigger_cb = QComboBox()
        cam_trigger_cb.addItems(['EXTERNAL_EXPOSURE', 'EXTERNAL_FT'])
        cam_trigger_cb.setCurrentText('EXTERNAL_EXPOSURE')
        
        mode_le = QLineEdit('AM')

        params_config = {
            'optimize_gain': {
                'display_text': 'Optimize Gain',
                'widget': optimize_gain_cb,
            },
            'cam_trigger': {
                'display_text': 'Camera Trigger',
                'widget': cam_trigger_cb,
            },
            'ns_probe_time': {
                'display_text': 'Probe Time (ns)',
                'widget': ns_probe_time_sb,
            },
            'ns_exp_time': {
                'display_text': 'Exposure Time (ns)',
                'widget': ns_exp_time_sb,
            },
            'ns_readout_time': {
                'display_text': 'Readout Time (ns)',
                'widget': ns_readout_time_sb,
            },
            'ns_laser_lag': {
                'display_text': 'Laser Lag (ns)',
                'widget': ns_laser_lag_sb,
            },
            'gain': {
                'display_text': 'EMCCD Gain',
                'widget': gain_sb,
            },
            'mode': {
                'display_text': 'Mode',
                'widget': mode_le,
            },
            'runs': {
                'display_text': 'Runs',
                'widget': runs_sb,
            },
        }

        super().__init__(
            params_config,
            experiments.initializecamera,
            'CameraInitialization',
            'initialize_camera',
            title='Camera Initialization',
            get_param_value_funs=get_param_value_funs
        )
