import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox

from special_widgets import unit_widgets

import experiments.spatialfb



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

class SpatialFeedbackWidget(ExperimentWidget):
    def __init__(self):
        ctr_ch_le = QLineEdit('Dev1/ctr1')
        initial_position=unit_widgets.PointWidget(1, 0, 0)
        # x_initial_le = unit_widgets.MLineEdit(0)
        # y_initial_le = unit_widgets.MLineEdit(0)
        # z_initial_le = unit_widgets.MLineEdit(0)
        do_z_cb = QCheckBox()
        do_z_cb.setChecked(True)
        sleep_time_le = unit_widgets.SecLineEdit(0.4)
        xyz_step_le = unit_widgets.MLineEdit(0.05)
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