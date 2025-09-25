import numpy as np
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
from pyqtgraph import SpinBox
from special_widgets import unit_widgets
import experiments.temptime
from nspyre import ExperimentWidget
MAXIMUM=2147483647 
class TempTimeWidget(ExperimentWidget):
    def __init__(self):
        # Pre-configured widgets for extra configuration:
        sb_MHz_2fq_cb = QComboBox()
        sb_MHz_2fq_items = [
            '62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
            '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
            '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
            '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
            '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
            '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
            '5.952380952', '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291',
            '5.2631579', '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222',
            '2.84090909', '2.5'
        ]
        sb_MHz_2fq_cb.addItems(sb_MHz_2fq_items)
        sb_MHz_2fq_cb.setCurrentText("10.1010101")

        rf_amplitude_sb = QSpinBox()
        rf_amplitude_sb.setMinimum(-100)
        rf_amplitude_sb.setMaximum(7)
        rf_amplitude_sb.setValue(-20)
        
        quasilinear_slope_sb = QSpinBox()
        quasilinear_slope_sb.setMinimum(0)
        quasilinear_slope_sb.setMaximum(MAXIMUM)
        quasilinear_slope_sb.setValue(0)

        is_center_modulation_qb = QCheckBox()
        is_center_modulation_qb.setChecked(True)


        number_jump_avg_sb = QSpinBox()
        number_jump_avg_sb.setMinimum(1)
        number_jump_avg_sb.setMaximum(100)
        number_jump_avg_sb.setValue(1)

        search_integral_history_sb = QSpinBox()
        search_integral_history_sb.setMinimum(1)
        search_integral_history_sb.setMaximum(100)
        search_integral_history_sb.setValue(1)

        z_cycle_sb = QSpinBox()
        z_cycle_sb.setMinimum(1)
        z_cycle_sb.setMaximum(100)
        z_cycle_sb.setValue(1)

        track_z_cb = QCheckBox()
        track_z_cb.setChecked(True)

        diffusion_constant_sb = SpinBox()
        diffusion_constant_sb.setMinimum(0)
        diffusion_constant_sb.setMaximum(None)
        diffusion_constant_sb.setValue(200)

        integral_history_sb=QSpinBox()
        integral_history_sb.setMinimum(1)
        integral_history_sb.setMaximum(100)
        integral_history_sb.setValue(1)

        params_config = {
            'sampling_rate': {
                'display_text': 'Sampling Rate',
                'widget': unit_widgets.HzLineEdit(50000)
            },
            'timeout': {
                'display_text': 'Timeout',
                'widget': unit_widgets.SecLineEdit(12)
            },
            'time_per_scan': {
                'display_text': 'Time per Scan',
                'widget': unit_widgets.SecLineEdit(0.25)
            },
            'starting_temp': {
                'display_text': 'Starting Temperature',
                'widget': unit_widgets.TemperatureLineEdit(25.0)
            },
            'sb_MHz_2fq': {
                'display_text': 'Sideband MHz (2fq)',
                'widget': sb_MHz_2fq_cb
            },
            'quasilinear_slope': {
                'display_text': 'Quasilinear Slope',
                'widget': quasilinear_slope_sb
            },
            'two_freq': {
                'display_text': 'Two Frequency Modulation',
                'widget': QCheckBox()
            },
            'odmr_frequency': {
                'display_text': 'ODMR Frequency',
                'widget': unit_widgets.HzLineEdit(2.87e9)

            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb
            },
            'clock_time': {
                'display_text': 'Clock Time',
                'widget': unit_widgets.SecLineEdit(10e-9)
            },
            'mwPulseTime': {
                'display_text': 'MW Pulse Time',
                'widget': unit_widgets.SecLineEdit(50e-6)
            },
            'cooling_delay': {
                'display_text': 'Cooling Delay',
                'widget': unit_widgets.SecLineEdit(0.0)
            },
            'is_center_modulation': {
                'display_text': 'Center Modulation',
                'widget': is_center_modulation_qb
            },
            'data_download': {
                'display_text': 'Data Download',
                'widget': QCheckBox()
            },
            'activate_PID': {
                'display_text': 'Activate PID',
                'widget': QCheckBox()
            },
            'activate_PID_no_sg_change': {
                'display_text': 'Activate PID (No SG Change)',
                'widget': QCheckBox()
            },
            'PID': {
                'display_text': 'PID Parameters',
                'widget': QLineEdit("[0.1,0.01,0]")
            },
            'PID_recurrence': {
                'display_text': 'PID Recurrence',
                'widget': QLineEdit("[1,1,0]")
            },
            'integral_history': {
                'display_text': 'Integral History',
                'widget': integral_history_sb
            },
            'threshold_temp_jump': {
                'display_text': 'Threshold Temp Jump',
                'widget': unit_widgets.TemperatureLineEdit(2)
            },
            'number_jump_avg': {
                'display_text': 'Number Jump Average',
                'widget': number_jump_avg_sb
            },
            'searchXYZ': {
                'display_text': 'Search XYZ (um)',
                'widget': QLineEdit("[0.5, 0.5, 0.5]")
            },
            'max_search': {
                'display_text': 'Max Search (um)',
                'widget': QLineEdit("[1, 1, 1]")
            },
            'min_search': {
                'display_text': 'Min Search (um)',
                'widget': QLineEdit("[0.1, 0.1, 0.1]")
            },
            'changing_search': {
                'display_text': 'Changing Search',
                'widget': QCheckBox()
            },
            'search_PID': {
                'display_text': 'Search PID',
                'widget': QLineEdit("[0.5,0.01,0]")
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
            'do_not_run_feedback': {
                'display_text': 'Do Not Run Feedback',
                'widget': QCheckBox()
            },
            'scan_distance': {
                'display_text': 'Scan Distance (um)',
                'widget': QLineEdit("[0.03, 0.03, 0.05]")
            },
            'spot_size': {
                'display_text': 'Spot Size',
                'widget': unit_widgets.MLineEdit(400e-9)
            },
            'advanced_tracking': {
                'display_text': 'Advanced Tracking',
                'widget': QCheckBox()
            },
            'diffusion_constant': {
                'display_text': 'Diffusion Constant',
                'widget': diffusion_constant_sb
            },
            'infrared_on': {
                'display_text': 'Infrared On',
                'widget': QCheckBox()
            },
            'infrared_power': {
                'display_text': 'Infrared Power',
                'widget': unit_widgets.WLineEdit(1e-4)
            },
            'heat_on_off_cycle': {
                'display_text': 'Heat On/Off Cycle',
                'widget': QLineEdit("[True] + [False]*2")
            },
            'warm_and_cool_scans': {
                'display_text': 'Warm and Cool Scans',
                'widget': QLineEdit("[30, 30]")
            },
            'dataset':{
                'display_text': 'Data Source',
                'widget': QLineEdit("temp_time")
            }
        }

        super().__init__(
            params_config,
            experiments.temptime,
            'TemperatureVsTime',
            'temptime',
            title='Temperature vs Time',
            get_param_value_funs={
                unit_widgets.HzLineEdit: lambda w: w.hzvalue,
                unit_widgets.SecLineEdit: lambda w: w.secvalue,
                QSpinBox: lambda w: w.value(),
                QLineEdit: lambda w: w.text(),
                QCheckBox: lambda w: w.isChecked(),
                QComboBox: lambda w: w.currentText(),
                unit_widgets.TemperatureLineEdit: lambda w: w.value,
                unit_widgets.MLineEdit: lambda w: w.umvalue,
                unit_widgets.WLineEdit: lambda w: w.value,
            }
        )