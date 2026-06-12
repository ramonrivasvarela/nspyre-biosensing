import numpy as np

from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox

import experiments.line_scan_fb



import pyqtgraph as pg


cmap = pg.colormap.get('viridis')  


class LineScanFBWidget(ExperimentWidget):
    def __init__(self):
        n_points_sb = QSpinBox()
        n_points_sb.setMinimum(1)
        n_points_sb.setMaximum(1000)
        n_points_sb.setValue(40)

        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        runs_sb.setMaximum(100)
        runs_sb.setValue(30)

        n_steps_sb = QSpinBox()
        n_steps_sb.setMinimum(1)
        n_steps_sb.setMaximum(1000)
        n_steps_sb.setValue(100)
        
        params_config = {
            'runs': {
                'display_text': 'Runs',
                'widget': runs_sb,
            },
            'points_per_step': {
                'display_text': 'Points per Step',
                'widget': n_points_sb,
            },
            'n_steps': {
                'display_text': 'Number of Steps',
                'widget': n_steps_sb,
            },
            'scan_distance': {
                'display_text': 'Scan Distance',
                'widget': QLineEdit("(3, 3, 3)"),  # Default to 10 units
            },
            

            'time_per_point': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=0.1,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                ),
            },
            'spot_size': {
                'display_text': 'Spot Size (for fitting)',
                'widget': SpinBox(
                    value=400e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                ),
            },
            'convergence_threshold': {
                'display_text': 'Convergence Threshold',
                'widget': SpinBox(
                    value=50e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                ),
            },

            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('line_scan_fb'),
            },
        }

        super().__init__(params_config, 
                        experiments.line_scan_fb,
                        'LineScanFB',
                        'main',
                        title='testing axis')

