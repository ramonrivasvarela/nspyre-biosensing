import numpy as np
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
from pyqtgraph import SpinBox
from special_widgets import unit_widgets
import experiments.triple_experiment
from nspyre import ExperimentWidget

MAXIMUM=2147483647 

get_param_value_funs={
    SpinBox: lambda w: w.value() if w.opts.get('suffix', '') != 'm' else w.value()*1e6,
    QSpinBox: lambda w: w.value(),
    QLineEdit: lambda w: w.text(),
    QCheckBox: lambda w: w.isChecked(),
    QComboBox: lambda w: w.currentText(),
}

class TripleExperimentWidget(ExperimentWidget):
    def __init__(self):
        # Pre-configured widgets for extra configuration:
        
        # ODMR Sweeps widget
        odmr_sweeps_sb = QSpinBox()
        odmr_sweeps_sb.setMinimum(1)
        odmr_sweeps_sb.setMaximum(MAXIMUM)
        odmr_sweeps_sb.setValue(10)
        
        # I1I2 Sweeps widget
        i1i2_sweeps_sb = QSpinBox()
        i1i2_sweeps_sb.setMinimum(1)
        i1i2_sweeps_sb.setMaximum(MAXIMUM)
        i1i2_sweeps_sb.setValue(10)
        
        # Sweeps till feedback widget (same as ConfocalODMR)
        sweeps_till_fb_sb = QSpinBox()
        sweeps_till_fb_sb.setMinimum(0)
        sweeps_till_fb_sb.setMaximum(MAXIMUM)
        sweeps_till_fb_sb.setValue(12)
        
        # Search integral history widget (same as other GUIs)
        search_integral_history_sb = QSpinBox()
        search_integral_history_sb.setMinimum(1)
        search_integral_history_sb.setMaximum(100)
        search_integral_history_sb.setValue(5)
        
        # Z cycle widget (same as TempTime)
        z_cycle_sb = QSpinBox()
        z_cycle_sb.setMinimum(1)
        z_cycle_sb.setMaximum(100)
        z_cycle_sb.setValue(1)
        
        # I1I2 continuous tracking checkbox
        i1i2_continuous_tracking_cb = QCheckBox()
        i1i2_continuous_tracking_cb.setChecked(False)
        
        # Changing search checkbox
        changing_search_cb = QCheckBox()
        changing_search_cb.setChecked(False)

        track_z_cb = QCheckBox()
        track_z_cb.setChecked(True)
        

        params_config = {
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': SpinBox(
                    value=-13,
                    suffix='dBm',
                    siPrefix=False,
                    dec=True,
                    bounds=(-100, 10),
                )
            },
            'odmr_sweeps': {
                'display_text': 'ODMR Sweeps',
                'widget': odmr_sweeps_sb
            },
            'i1i2_sweeps': {
                'display_text': 'I1I2 Sweeps', 
                'widget': i1i2_sweeps_sb
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
            'sweeps_till_fb': {
                'display_text': 'Sweeps Till Feedback',
                'widget': sweeps_till_fb_sb
            },
            'time_per_point': {
                'display_text': 'Time Per Point',
                'widget': SpinBox(
                    value=1,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0.001, 1000),
                )
            },
            'odmr_frequency_range': {
                'display_text': 'ODMR Frequencies',
                'widget': QLineEdit("(2.82e9, 2.92e9, 30)")
            },
            'i1i2_frequency_range': {
                'display_text': 'I1I2 Frequencies',
                'widget': QLineEdit("(2.85e9, 2.89e9, 20)")
            },
            'slope_range': {
                'display_text': 'Slope Range',
                'widget': QLineEdit("(2.868e9, 2.871e9)")
            },
            'i1i2_continuous_tracking': {
                'display_text': 'I1I2 Continuous Tracking',
                'widget': i1i2_continuous_tracking_cb
            },
            'searchXYZ': {
                'display_text': 'Search XYZ',
                'widget': QLineEdit("(0.5, 0.5, 0.5)")
            },
            'max_search': {
                'display_text': 'Max Search',
                'widget': QLineEdit("(1, 1, 1)")
            },
            'min_search': {
                'display_text': 'Min Search',
                'widget': QLineEdit("(0.1, 0.1, 0.1)")
            },
            'scan_distance': {
                'display_text': 'Scan Distance',
                'widget': QLineEdit("(0.03, 0.03, 0.05)")
            },
            'changing_search': {
                'display_text': 'Changing Search',
                'widget': changing_search_cb
            },
            'search_PID': {
                'display_text': 'Search PID',
                'widget': QLineEdit("(0.5,0.01,0)")
            },
            'search_integral_history': {
                'display_text': 'Search Integral History',
                'widget': search_integral_history_sb
            },
            'z_cycle': {
                'display_text': 'Z Cycle',
                'widget': z_cycle_sb
            },
            'track_z': {
                'display_text': 'Track Z',
                'widget': track_z_cb
            },
            'odmr_dataset': {
                'display_text': 'ODMR Data Source',
                'widget': QLineEdit("odmr")
            },
            'i1i2_dataset':{
                'display_text': 'I1I2 Data Source',
                'widget': QLineEdit("i1i2"),
            },
            'temptime_dataset': {
                'display_text': 'Temperature Data Source',
                'widget': QLineEdit("temptime")
            }

        }

        super().__init__(
            params_config,
            experiments.triple_experiment,
            'TripleExperiment',
            'main',
            title='Triple Experiment',
            get_param_value_funs=get_param_value_funs
        )