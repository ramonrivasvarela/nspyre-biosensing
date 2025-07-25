import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget

from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox

from special_widgets import unit_widgets

import experiments.WFODMR



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

class WFODMRPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__()
        # create some default signal plots
        self.add_plot('Signal 1',        series='signal_1',   scan_i='',     scan_j='',  processing='Append')
        self.add_plot('Background 1',        series='background_1',   scan_i='',     scan_j='',  processing='Append')


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('wfodmr')