import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox

from special_widgets import unit_widgets

import experiments.spatialfb



import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            SpinBox: lambda w: w.value() if w.opts.get('suffix', '') != 'm' else w.value()*1e6,
            QSpinBox: lambda w: w.value(),
            QLineEdit: lambda w: w.text(),
            QCheckBox: lambda w: w.isChecked(),
            QComboBox: lambda w: w.currentText(),
            unit_widgets.PointWidget: lambda w: w.get_point(),
        }

class SpatialFeedbackWidget(ExperimentWidget):
    def __init__(self):
        do_z_cb = QCheckBox()
        do_z_cb.setChecked(True)
        
        shrink_every_x_iter_sb = QSpinBox()
        shrink_every_x_iter_sb.setMinimum(1)
        shrink_every_x_iter_sb.setValue(1)
        
        starting_point_cb = QComboBox()
        starting_point_cb.addItems(['user_input', 'current_position (ignore input)'])
        starting_point_cb.setCurrentText('current_position (ignore input)')
        
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(10)

        params_config = {
            'initial_position': {
                'display_text': 'Initial position',
                'widget': unit_widgets.PointWidget(0, 0, 10),
            },
            'do_z': {
                'display_text': 'Do Z',
                'widget': do_z_cb,
            },
            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=0.4,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                ),
            },
            'n_points': {
                'display_text': 'Number of Points',
                'widget': n_points_sb,
            },
            'xyz_step': {
                'display_text': 'XYZ Step',
                'widget': SpinBox(
                    value=0.05e-6,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1e-3),
                ),
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