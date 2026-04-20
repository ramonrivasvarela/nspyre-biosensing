import numpy as np
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
from pyqtgraph import SpinBox
import experiments.temptime
from nspyre import ExperimentWidget
from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget

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

        quasilinear_slope_sb = SpinBox()
        quasilinear_slope_sb.setMinimum(0)
        quasilinear_slope_sb.setMaximum(MAXIMUM)
        quasilinear_slope_sb.setValue(1e-9)

        is_center_modulation_qb = QCheckBox()
        is_center_modulation_qb.setChecked(True)

        number_jump_avg_sb = QSpinBox()
        number_jump_avg_sb.setMinimum(1)
        number_jump_avg_sb.setMaximum(100)
        number_jump_avg_sb.setValue(1)

        search_integral_history_sb = QSpinBox()
        search_integral_history_sb.setMinimum(1)
        search_integral_history_sb.setMaximum(100)
        search_integral_history_sb.setValue(5)

        z_cycle_sb = QSpinBox()
        z_cycle_sb.setMinimum(1)
        z_cycle_sb.setMaximum(100)
        z_cycle_sb.setValue(1)

        track_z_cb = QCheckBox()
        track_z_cb.setChecked(True)

        integral_history_sb=QSpinBox()
        integral_history_sb.setMinimum(1)
        integral_history_sb.setMaximum(100)
        integral_history_sb.setValue(1)

        changing_search_cb = QCheckBox()
        changing_search_cb.setChecked(True)

        two_freq_cb = QCheckBox()
        two_freq_cb.setChecked(True)
        params_config = {
            'sampling_rate': {
                'display_text': 'Sampling Rate',
                'widget': SpinBox(
                    value=50000,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                    bounds=(1, 1e9),
                )
            },
            'timeout': {
                'display_text': 'Timeout',
                'widget': SpinBox(
                    value=12,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0.1, 1000),
                )
            },
            'time_per_scan': {
                'display_text': 'Time per Scan',
                'widget': SpinBox(
                    value=0.25,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                )
            },
            'starting_temp': {
                'display_text': 'Starting Temperature',
                'widget': SpinBox(
                    value=25.0,
                    suffix='°C',
                    siPrefix=False,
                    dec=True,
                    bounds=(-273, 1000),
                )
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
                'widget': two_freq_cb
            },
            'odmr_frequency': {
                'display_text': 'ODMR Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e6, 1e12),
                )
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': SpinBox(
                    value=-15,
                    suffix='dBm',
                    siPrefix=False,
                    dec=True,
                    bounds=(-100, 10),
                )
            },
            'clock_time': {
                'display_text': 'Clock Time',
                'widget': SpinBox(
                    value=10e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1),
                )
            },
            'mwPulseTime': {
                'display_text': 'MW Pulse Time',
                'widget': SpinBox(
                    value=50e-6,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-9, 1),
                )
            },
            'cooling_delay': {
                'display_text': 'Cooling Delay',
                'widget': SpinBox(
                    value=0.400,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0, 1000),
                )
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
                'widget': QLineEdit("[0.01,0.0025,0.0065]")
            },
            'PID_recurrence': {
                'display_text': 'PID Recurrence',
                'widget': QLineEdit("[1,1,1]")
            },
            'integral_history': {
                'display_text': 'Integral History',
                'widget': integral_history_sb
            },
            'threshold_temp_jump': {
                'display_text': 'Threshold Temp Jump',
                'widget': SpinBox(
                    value=2,
                    suffix='°C',
                    siPrefix=False,
                    dec=True,
                    bounds=(-273, 1000),
                )
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
                'widget': changing_search_cb 
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
                'widget': SpinBox(
                    value=400e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1e-3),
                )
            },
            'advanced_tracking': {
                'display_text': 'Advanced Tracking',
                'widget': QCheckBox()
            },
            'diffusion_constant': {
                'display_text': 'Diffusion Constant',
                'widget': SpinBox(
                    value=200,
                    siPrefix=False,
                    dec=True,
                    bounds=(0.1, 10000),
                )
            },
            'infrared_on': {
                'display_text': 'Infrared On',
                'widget': QCheckBox()
            },
            'infrared_power': {
                'display_text': 'Infrared Power',
                'widget': SpinBox(
                    value=1e-4,
                    suffix='W',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-9, 1000),
                )
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
            title='Temperature vs Time'
        )

class TempTimePlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        
        
                
        super().__init__() 
        self.add_plot('I1',        series='I1',   scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('I2',        series='I2',   scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('x_pos',      series='x_pos', scan_i='',     scan_j='',  processing='Append', hidden=True)
        
        self.add_plot('y_pos',      series='y_pos', scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('z_pos',      series='z_pos', scan_i='',     scan_j='',  processing='Append', hidden=True)
        self.add_plot('odmr_freq',      series='odmr_freq', scan_i='',     scan_j='',  processing='Append')
        self.add_plot('total_fluor',      series='total_fluor', scan_i='',     scan_j='',  processing='Append', hidden=True)

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('temp_time')