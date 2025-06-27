"""
Example GUI elements.
"""
import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QDoubleSpinBox, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from nspyre.gui.widgets import HeatMapWidget
from special_widgets import unit_widgets
from special_widgets.experiment_widget import ExperimentWidget

import experiments.counts
import experiments.planescan
import experiments.widefield

class CountsWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'n_points': {
                'display_text': '# Points',
                'widget': SpinBox(
                    value=1,
                    dec = False,
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

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('counts'),
            },
        }

        super().__init__(params_config, 
                        experiments.counts,
                        'CountsTime',
                        'confocal_counts_time',
                        title='counts vs time')


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
        line_scan_steps_sb = SpinBox(value=100)
        line_scan_steps_sb.setMinimum(1)
        extent_steps_sb = SpinBox(value=100)
        extent_steps_sb.setMinimum(1)
        repetitions_sb = SpinBox(value=1)
        repetitions_sb.setMinimum(1)
        stack_count_sb = SpinBox(value=1)
        stack_count_sb.setMinimum(1)
        pts_per_step_sb = SpinBox(value=40)
        pts_per_step_sb.setMinimum(1)
        sleep_factor_sb = SpinBox(value=1)
        sleep_factor_sb.setMinimum(1)

        params_config = {
            'point_A': {'display_text': 'Point A',
                        'widget': unit_widgets.PointWidget(0, 0, 0)},
            'point_B': {'display_text': 'Point B',
                        'widget': unit_widgets.PointWidget(50, 0, 0)},
            'point_C': {'display_text': 'Point C',
                        'widget': unit_widgets.PointWidget(50, 0, 60)},
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
            'excel': {'display_text': 'Excel Export',
                      'widget': QCheckBox()},
            'snake_scan': {'display_text': 'Snake Scan',
                           'widget': QCheckBox()},
            'sleep_factor': {'display_text': 'Sleep Factor',
                             'widget': sleep_factor_sb},
            'dataset': {
                'display_text': 'Data Set',
                'widget': HeatMapWidget('planescan'),
            },
        }

        super().__init__(params_config,
                         experiments.planescan,
                         'PlaneScan',
                         'planescan',
                         title='Plane Scan')

# class PlaneScanWidgetWithFlexLinePlot(HeatMapWidget):
#     def __init__(self):
#         super().__init__()
#         # create some default signal plots
#         self.set_data(xs=,
#                       ys=,
#                       data=
#                       )


#         # retrieve legend object
#         legend = self.line_plot.plot_widget.addLegend()
#         # set the legend location
#         legend.setOffset((-10, -50))

#         self.datasource_lineedit.setText('counts v time')
        
class WideFieldWidget(ExperimentWidget):
    def __init__(self):


        gain_sb = SpinBox(value=2)
        gain_sb.setMinimum(1)
        gain_sb.setMaximum(272)

        repeat_minutes_sb = SpinBox(value=0)
        repeat_minutes_sb.setMinimum(0)
        repeat_minutes_sb.setDecimals(3)

        rf_amplitude_sb = SpinBox(value=-15)
        rf_amplitude_sb.setDecimals(2)

        mw_duty_sb = SpinBox(value=1)
        mw_duty_sb.setDecimals(3)

        mw_rep_sb = SpinBox(value=50)
        mw_rep_sb.setMinimum(1)


        cam_trigger_cb = QtWidgets.QComboBox()
        cam_trigger_cb.addItems(['EXTERNAL_EXPOSURE', 'EXTERNAL_FT'])
        cam_trigger_cb.setCurrentText('EXTERNAL_FT')

        optimize_gain_cb = QCheckBox()
        optimize_gain_cb.setChecked(True)

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
            'repeat_every_x_minutes': {
                'display_text': 'Repeat Every X Minutes',
                'widget': repeat_minutes_sb,
            },
            'runs_sweeps_reps': {
                'display_text': 'Runs, Sweeps, Reps',
                'widget': QLineEdit('[1,1,1]'),
            },
            'frequency': {
                'display_text': 'Frequency',
                'widget': QLineEdit('[2.85e9, 2.89e9, 30]'),
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
                'widget': 5
            }
        }

        super().__init__(
            params_config,
            experiments.widefield,
            'WideFieldODMR',
            'run_widefield_experiment',
            title='Wide Field Imaging'
        )