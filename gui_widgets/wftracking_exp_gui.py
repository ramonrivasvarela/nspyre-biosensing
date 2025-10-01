import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox
from special_widgets import unit_widgets

import experiments.WFTracking

import experiments.confocalODMR

import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
    SpinBox: lambda w: w.value() if w.suffix() != 'm' else w.value()*1e6,
    QSpinBox: lambda w: w.value(),
    QLineEdit: lambda w: w.text(),
    QCheckBox: lambda w: w.isChecked(),
    QComboBox: lambda w: w.currentText(),
}

class WFTrackingWidget(ExperimentWidget):
    def __init__(self):
        # Widgets that need extra configuration are created separately
        # cam_trigger_cb requires adding items and setting default text
        cam_trigger_cb = QComboBox()
        cam_trigger_cb.addItems(["EXTERNAL_EXPOSURE", "EXTERNAL_FT"])
        cam_trigger_cb.setCurrentText("EXTERNAL_FT")
        
        # gain_sb needs min, max and value set
        gain_sb = QSpinBox()
        gain_sb.setMinimum(1)
        gain_sb.setMaximum(272)
        gain_sb.setValue(2)
        
        # rf_amplitude_sb: although a QSpinBox, we want to set its value explicitly
        rf_amplitude_sb = QSpinBox()
        rf_amplitude_sb.setValue(-15)
        rf_amplitude_sb.setMinimum(-100)
        rf_amplitude_sb.setMaximum(10)
        
        # mode_cb requires extra steps
        mode_cb = QComboBox()
        mode_cb.addItems(["AM", "SWITCH"])
        mode_cb.setCurrentText("AM")
        
        params_config = {
            'device': {
                'display_text': 'Device',
                'widget': QLineEdit("Dev1"),
            },
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
            'cam_trigger': {
                'display_text': 'Camera Trigger',
                'widget': cam_trigger_cb,
            },
            'gain': {
                'display_text': 'EM Gain',
                'widget': gain_sb,
            },
            'cooler': {
                'display_text': 'Cooler',
                'widget': QLineEdit("(False, 20)"),
            },
            'routine': {
                'display_text': 'Routine',
                'widget': QLineEdit("[2,3,100,0,-1]"),
            },
            'wait_interval': {
                'display_text': 'Wait Interval',
                'widget': QLineEdit("(0,10)"),
            },
            'end_ODMR': {
                'display_text': 'End ODMR',
                'widget': QCheckBox(),
            },
            'frequency': {
                'display_text': 'Frequency',
                'widget': QLineEdit("[2.84e9, 2.90e9, 30]"),
            },
            'label': {
                'display_text': 'Label',
                'widget': QLineEdit("[t, 1, 0, 2, 0, 1, 0, 2, 0]"),
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb,
            },
            'mode': {
                'display_text': 'Mode',
                'widget': mode_cb,
            },
            'ROI_xy': {
                'display_text': 'ROI xy',
                'widget': QLineEdit("[(512,512)]"),
            },
            'ZFS': {
                'display_text': 'ZFS',
                'widget': QLineEdit("2.868780e9"),
            },
            'sideband': {
                'display_text': 'Sideband',
                'widget': QLineEdit("12e6"),
            },
            'QLS': {
                'display_text': 'QLS',
                'widget': QLineEdit("[-5e-9]"),
            },
            'alt_label': {
                'display_text': 'Alternate Label',
                'widget': QCheckBox(),
            },
            'PID': {
                'display_text': 'PID Parameters',
                'widget': QLineEdit("{'Kp':0.03, 'Ki': 0.005, 'Kd':0.01, 'Mem': 15, 'Mem_decay': 2.0}"),
            },
            'data_path': {
                'display_text': 'Data Path',
                'widget': QLineEdit("Z:\\biosensing_setup\\data\\WFODMR_images_test"),
            },
            'save_image': {
                'display_text': 'Save Image',
                'widget': QCheckBox(),
            },
            'data_download': {
                'display_text': 'Data Download',
                'widget': QCheckBox(),
            },
            'window': {
                'display_text': 'Window',
                'widget': QCheckBox(),  # Set default state in code after if needed.
            },
            'trackpy': {
                'display_text': 'Trackpy',
                'widget': QCheckBox(),
            },
            'trackpy_params': {
                'display_text': 'Trackpy Params',
                'widget': QLineEdit("(False, 40, 800)"),
            },
            'shutdown': {
                'display_text': 'Shutdown',
                'widget': QCheckBox(),  # Set default state in code if necessary.
            },
            'data_source': {
                'display_text': 'Data Source',
                'widget': QLineEdit('wftrack'),
            },
            'Misc': {
                'display_text': 'Miscellaneous',
                'widget': QLineEdit("{'DEBUG':False}"),
            },
        }
        
        super().__init__(
            params_config,
            experiments.WFTracking,
            'WFTracking',
            'wftracking',
            title='Wide Field Tracking',
            get_param_value_funs=get_param_value_funs
        )
