import numpy as np
from scipy import optimize

from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget
from nspyre import ExperimentWidget # Gets this from nspyre/src/nspyre/__init__.py
# from special_widgets.custom_experiment import ExperimentWidget
from nspyre import DataSink
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox
from pyqtgraph import SpinBox

import sys

import pyqtgraph as pg

cmap = pg.colormap.get('viridis')  

import experiments.blast_experiment
class BlastExperimentWidget(ExperimentWidget):
    def __init__(self):
        from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox

        # Define widgets that require extra configuration outside of params:
        first_fb_combo = QComboBox()

        # Build the parameter configuration dictionary using only display_text and widget.
        # Widgets that require extra config have been defined above.
        params_config = {
            'feedback_params_path':{
                'display_text': 'Feedback Params Path',
                'widget': QLineEdit(r'C:\Users\Lab\biosensing\instrumentation\nspyre\experiment_params\feedback_params.pkl')
            },
            'I1I2_params_path':{
                'display_text': 'I1I2 Params Path',
                'widget': QLineEdit(r'C:\Users\Lab\biosensing\instrumentation\nspyre\experiment_params\I1I2_params.pkl')
            },
            'ODMR_params_path':{
                'display_text': 'ODMR Params Path',
                'widget': QLineEdit(r'C:\Users\Lab\biosensing\instrumentation\nspyre\experiment_params\ODMR_params.pkl')
            },
            'autosave_folder':{
                'display_text': 'Autosave Folder',
                'widget': QLineEdit(r'Z:\biosensing_setup\data\Misc\Autosave')
            },
            'autosave_labels':{
                'display_text': 'Autosave Labels',
                'widget': QLineEdit("['baseline']")
            },
            'iters':{
                'display_text': 'Iterations',
                'widget': QSpinBox(), 'display_text': 'Iterations', 'default': 3, 'min': 1, 'max': 100
            },
            'first_fb':{
                            'display_text': 'First Feedback',
                            'widget': first_fb_combo, 'display_text': 'First Feedback', 'default': 'skip', 'options': ['skip', 'run', 'special']
                        },
            'rf_override':{
                'display_text': 'RF Override',
                'widget': SpinBox(
                                    value=-18,
                                    suffix='dBm',
                                    siPrefix=False,
                                    dec=True,
                                    bounds=(-50, 10),
                                )
            },
            'laser_base_power':{
                'display_text': 'Laser Base Power',
                'widget': QSpinBox(), 'display_text': 'Laser Base Power', 'default': 2, 'min': 0, 'max': 100
            },
            'laser_blast_power':{
                'display_text': 'Laser Blast Power',
                'widget': QSpinBox(), 'display_text': 'Laser Blast Power', 'default': 100, 'min': 0, 'max': 100
            },
            'duration':{
                'display_Text': 'Blast Duration (s)',
                'widget': SpinBox(
                                    value=2.0,
                                    suffix='s',
                                    siPrefix=False,
                                    dec=True,
                                    bounds=(0.01, 100.0),
                                )
            },
            
        }
        super().__init__(
            params_config,
            experiments.blast_experiment,  # Ensure that experiments.BlastExperiment exists in your experiments folder
            'BlastExperiment',
            'blast_experiment',
            title='Blast Experiment',
        )



