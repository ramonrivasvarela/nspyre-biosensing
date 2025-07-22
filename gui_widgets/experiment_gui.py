"""
Example GUI elements.
"""
import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
import experiments.counts_new
from special_widgets import unit_widgets
from nspyre import InstrumentManager
#from special_widgets.experiment_widget import ExperimentWidget
from nspyre import DataSource
import experiments.counts
import experiments.planescan
import experiments.WFODMR
import experiments.spatialfb
import experiments.counts_new
import experiments.picture
import experiments.WFTracking

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

class CountsWidget(ExperimentWidget):
    def __init__(self):
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(10)
        
        params_config = {
            'n_points': {
                'display_text': '# Points',
                'widget': n_points_sb,
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

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('counts'),
            },
        }

        super().__init__(params_config, 
                        experiments.counts,
                        'CountsTime',
                        'confocal_counts_time',
                        title='counts vs time', get_param_value_funs=get_param_value_funs)


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

        self.datasource_lineedit.setText('counts v time')

class PlaneScanWidget(ExperimentWidget):
    def __init__(self):
        # Create SpinBoxes and set minimums
        line_scan_steps_sb = QSpinBox()
        line_scan_steps_sb.setMaximum(1000)
        line_scan_steps_sb.setValue(100)
        line_scan_steps_sb.setMinimum(1)
        
        extent_steps_sb = QSpinBox()
        extent_steps_sb.setMaximum(1000)
        extent_steps_sb.setValue(100)
        extent_steps_sb.setMinimum(1)
    
        repetitions_sb = QSpinBox(value=1)
        repetitions_sb.setMinimum(1)
        stack_count_sb = QSpinBox(value=1)
        stack_count_sb.setMinimum(1)
        pts_per_step_sb = QSpinBox(value=40)
        pts_per_step_sb.setMinimum(1)
        sleep_factor_sb = SpinBox(value=1)
        sleep_factor_sb.setMinimum(1)

        params_config = {
            'point_A': {'display_text': 'Point A',
                        'widget': unit_widgets.PointWidget(-50, 0, 50)},
            'point_B': {'display_text': 'Point B',
                        'widget': unit_widgets.PointWidget(50, 0, 50)},
            'point_C': {'display_text': 'Point C',
                        'widget': unit_widgets.PointWidget(50, 0, 80)},
            'line_scan_steps': {'display_text': 'Line Scan Steps',
                                'widget': line_scan_steps_sb},
            'extent_steps': {'display_text': 'Extent Steps',
                             'widget': extent_steps_sb},
            'ctr_ch': {'display_text': 'Center Channel',
                       'widget': QLineEdit("Dev1/ctr1")},
            'repetitions': {'display_text': 'Repetitions',
                            'widget': repetitions_sb},
            'stack_count': {'display_text': 'Stack Count',
                            'widget': stack_count_sb},
            'stack_stepsize': {'display_text': 'Stack Stepsize',
                               'widget': unit_widgets.MLineEdit(1)},
            'stack_pospref': {'display_text': 'Stack Position Pref',
                              'widget': QCheckBox()},
            'acq_rate': {'display_text': 'Acquisition Rate',
                         'widget': unit_widgets.HzLineEdit(15e3)},
            'pts_per_step': {'display_text': 'Points Per Step',
                             'widget': pts_per_step_sb},
            'xyz_pos': {'display_text': 'XYZ Position',
                        'widget': QCheckBox()},

            'snake_scan': {'display_text': 'Snake Scan',
                           'widget': QCheckBox()},
            'sleep_factor': {'display_text': 'Sleep Factor',
                             'widget': sleep_factor_sb},
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('planescan'),
            },
        
        }

        super().__init__(params_config, 
                         experiments.planescan,
                         'PlaneScan',
                         'planescan',
                         title='Plane Scan', get_param_value_funs=get_param_value_funs)

    

class PlaneScanHeatMapWidget(HeatMapPlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
                # open in read-only mode; adjust dataset name if needed

        self.datasource_lineedit.setText('planescan')
        

class WideFieldWidget(ExperimentWidget):
    def __init__(self):


        gain_sb = QSpinBox()
        gain_sb.setMinimum(1)
        gain_sb.setValue(2)
        gain_sb.setMaximum(272)

        repeat_minutes_sb = SpinBox()
        repeat_minutes_sb.setValue(0)
        repeat_minutes_sb.setMinimum(0)
        repeat_minutes_sb.setDecimals(3)

        rf_amplitude_sb = SpinBox()
        rf_amplitude_sb.setValue(-15)
        rf_amplitude_sb.setDecimals(2)

        mw_duty_sb = SpinBox()
        mw_duty_sb.setValue(1)
        mw_duty_sb.setDecimals(3)

        mw_rep_sb = SpinBox()
        mw_rep_sb.setValue(50)
        mw_rep_sb.setMinimum(1)


        cam_trigger_cb = QtWidgets.QComboBox()
        cam_trigger_cb.addItems(['EXTERNAL_EXPOSURE', 'EXTERNAL_FT'])
        cam_trigger_cb.setCurrentText('EXTERNAL_FT')

        optimize_gain_cb = QCheckBox()
        optimize_gain_cb.setChecked(True)

        runs_sb= QSpinBox()
        runs_sb.setMinimum(1)

        sweeps_sb= QSpinBox()
        sweeps_sb.setMinimum(1)

        reps_sb=QSpinBox()
        reps_sb.setMinimum(1)

        # number_nds=QSpinBox()
        # number_nds.setMinimum(1)
        # number_nds.setMaximum(10)
        # number_nds.setValue(1)
        # number_nds.editingFinished.connect(lambda: nds.change_number(number_nds.value()))

        # nds= unit_widgets.FlexiblePointWidget(number_nds.value())
        # nds.change_number(number_nds.value())

        params_config = {

            'exp_time': {
                'display_text': 'Exposure Time',
                'widget': unit_widgets.SecLineEdit(75e-3),
            },
            'cam_trigger': {
                'display_text': 'Camera Trigger',
                'widget': cam_trigger_cb,
            },
            'readout_time': {
                'display_text': 'Readout Time',
                'widget': unit_widgets.SecLineEdit(15e-3),
            },
            'gain': {
                'display_text': 'EM Gain',
                'widget': gain_sb,
            },
            'ROI_xyr': {
                'display_text': 'ROI X/Y/R',
                'widget': QLineEdit('[(512,512,16,7)]'),  # Example default value
            },
            'repeat_every_x_minutes': {
                'display_text': 'Repeat Every X Minutes',
                'widget': repeat_minutes_sb,
            },
            'runs_sweeps_reps': {
                'display_text': 'Runs, Sweeps, Reps',
                'widget': QLineEdit('(1,1,1)'),  # Example default value
            },
            'frequency': {
                'display_text': 'Frequency',
                'widget': QLineEdit('(2.85e9, 2.89e9, 30)'),  # Example default value
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
                'widget': unit_widgets.SecLineEdit(160e-3),
            },
            'laser_lag': {
                'display_text': 'Laser Lag',
                'widget': unit_widgets.SecLineEdit(0.07),
            },
            'optimize_gain': {
                'display_text': 'Optimize Gain',
                'widget': optimize_gain_cb,
            },

            'trackpy':{

                'display_text': 'Trackpy',
                'widget': QCheckBox(),
            },
            'trackpy_params': {
                'display_text': 'Trackpy Params',
                'widget': QLineEdit("(False, 40, 800)"),  # Example default value
            },
            'sleep_time': {
                'display_text': 'Sleep Time',
                'widget': unit_widgets.SecLineEdit(0),
            },
            'data_path': {
                'display_text': 'Data Path',
                'widget': QLineEdit('Z:\\biosensing_setup\\data\\WFODMR_images_test'),
            },
            'dataset': {
                'display_text': 'Wide Field ODMR',
                'widget': QtWidgets.QLineEdit('wfodmr')
            }
        }

        super().__init__(
            params_config,
            experiments.WFODMR,
            'WideFieldODMR',
            'widefield',
            title='Wide Field Imaging', get_param_value_funs=get_param_value_funs
        )

class SpatialFeedbackWidget(ExperimentWidget):
    def __init__(self):
        ctr_ch_le = QLineEdit('Dev1/ctr1')
        initial_position=unit_widgets.PointWidget(0, 0, 0)
        # x_initial_le = unit_widgets.MLineEdit(0)
        # y_initial_le = unit_widgets.MLineEdit(0)
        # z_initial_le = unit_widgets.MLineEdit(0)
        do_z_cb = QCheckBox()
        do_z_cb.setChecked(True)
        sleep_time_le = unit_widgets.SecLineEdit(0.4)
        xyz_step_le = unit_widgets.MLineEdit(0.5e-7)
        shrink_every_x_iter_sb = QSpinBox()
        shrink_every_x_iter_sb.setMinimum(1)
        shrink_every_x_iter_sb.setValue(1)
        starting_point_cb = QtWidgets.QComboBox()
        starting_point_cb.addItems(['user_input', 'current_position (ignore input)'])
        starting_point_cb.setCurrentText('current_position (ignore input)')

        params_config = {
            'ctr_ch': {
                'display_text': 'Center Channel',
                'widget': ctr_ch_le,
            },
            'initial_position': {
                'display_text': 'Initial position',
                'widget': initial_position,
            },
            'do_z': {
                'display_text': 'Do Z',
                'widget': do_z_cb,
            },
            'sleep_time': {
                'display_text': 'Sleep Time',
                'widget': sleep_time_le,
            },
            'xyz_step': {
                'display_text': 'XYZ Step',
                'widget': xyz_step_le,
            },
            'shrink_every_x_iter': {
                'display_text': 'Shrink Every X Iterations',
                'widget': shrink_every_x_iter_sb,
            },
            'starting_point': {
                'display_text': 'Starting Point',
                'widget': starting_point_cb,
            },
        }

        super().__init__(
            params_config,
            experiments.spatialfb,
            'SpatialFeedback',
            'spatial_feedback',
            title='Spatial Feedback', get_param_value_funs=get_param_value_funs
        )

class PicturesWidget(ExperimentWidget):
    def __init__(self):
        params_config={
            'picture': {
                'display_text': 'Data Series',
                'widget': QtWidgets.QLineEdit('picture')
            }
        }

        super().__init__(
            params_config,
            experiments.picture,
            'Pictures',
            'take_picture',
            title='Pictures', get_param_value_funs=get_param_value_funs
        )

class WFTrackingWidget(ExperimentWidget):
    def __init__(self):
        # Widgets that need extra configuration are created separately
        # cam_trigger_cb requires adding items and setting default text
        cam_trigger_cb = QtWidgets.QComboBox()
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
        
        # mode_cb requires extra steps
        mode_cb = QtWidgets.QComboBox()
        mode_cb.addItems(["AM", "SWITCH"])
        mode_cb.setCurrentText("AM")
        
        params_config = {
            'device': {
                'display_text': 'Device',
                'widget': QLineEdit("Dev1"),
            },
            'exp_time': {
                'display_text': 'Exposure Time',
                'widget': unit_widgets.SecLineEdit(75e-3),
            },
            'readout_time': {
                'display_text': 'Readout Time',
                'widget': unit_widgets.SecLineEdit(15e-3),
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