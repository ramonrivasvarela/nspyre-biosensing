import numpy as np
from scipy import optimize

from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox
from pyqtgraph import SpinBox

import sys

import pyqtgraph as pg

cmap = pg.colormap.get('viridis')

import experiments.multi_blast
class MultiBlastWidget(ExperimentWidget):
    def __init__(self):
        from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
        
        # Define widgets that require extra configuration outside of params:

        params_config = {
            'locations': {'widget': QLineEdit(), 'display_text': 'Locations (x,y) list', 'default': '[]'},
            'blast_power': {'widget': QSpinBox(), 'display_text': 'Blast Power (%)', 'default': 100, 'min': 1, 'max': 100},
            'duration': {'widget': QSpinBox(), 'display_text': 'Duration (s)', 'default': 1, 'min': 0, 'max': 100},
            'feedback': {'widget': QCheckBox(), 'display_text': 'Feedback', 'default': True},
            'do_z': {'widget': QCheckBox(), 'display_text': 'Do Z', 'default': True},
            'xyz_step': {'widget': SpinBox(value = 0.05e-6, suffix = 'm', siPrefix=True, dec=True, bounds = (1e-12, 1e-3)), 'display_text': 'XYZ Step'},
            'shrink_every_x_iter': {'widget': QSpinBox(), 'display_text': 'Shrink Every X Iterations', 'default': 1, 'min': 1, 'max': 100},
            'probe_time': {'widget': SpinBox(value=0.4, suffix='s', siPrefix=True, dec=True), 'display_text': 'Probe Time (s)'},
            'n_points': {'widget': QSpinBox(), 'display_text': '# of Points for Feedback', 'default': 1, 'min': 1, 'max': 100},
            'total_fb_time': {'widget': SpinBox(value = 0.0, suffix='s', siPrefix=True, dec=True), 'display_text': 'Total Feedback Time (s)'},
            'verbose': {'widget': QCheckBox(), 'display_text': 'Verbose', 'default': False},
            'dataset': {'widget': QLineEdit(), 'display_text': 'Dataset', 'default': 'MultiBlast'},
        }

        super().__init__(
            params_config,
            experiments.multi_blast,
            'MultiBlast',
            'multi_blast',
            title='Multi Blast'
        )
        
def process_fb_data(sink: DataSink):
    """ Truncates the data to just the data after the last instance of 0 in the x-axis.
    """

    x_data = sink.datasets['x_pos']
    y_data = sink.datasets['y_pos']
    z_data = sink.datasets['z_pos']
    fluorescence_data = sink.datasets['total_fluor']

    # Find the last index where x is 0
    zero_indices = np.where(np.array(x_data)[:,0,0] == 0)[0]
    last_zero_index = zero_indices[-1] if len(zero_indices) > 0 else 0

    # Truncate the data to just after the last zero
    truncated_x = x_data[last_zero_index + 1:]
    truncated_y = y_data[last_zero_index + 1:]
    truncated_z = z_data[last_zero_index + 1:]
    truncated_fluorescence = fluorescence_data[last_zero_index + 1:]

    sink.datasets['latest_x'] = truncated_x
    sink.datasets['latest_y'] = truncated_y
    sink.datasets['latest_z'] = truncated_z
    sink.datasets['latest_fluor'] = truncated_fluorescence

class MultiBlastPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_fb_data)
        
        self.add_plot('latest_x', series='latest_x', scan_i='', scan_j='', processing='Append', iteration=0, hidden=True)
        self.add_plot('latest_y', series='latest_y', scan_i='', scan_j='', processing='Append', iteration=0, hidden=True)
        self.add_plot('latest_z', series='latest_z', scan_i='', scan_j='', processing='Append', iteration=0, hidden=True)
        self.add_plot('latest_fluor', series='latest_fluor', scan_i='', scan_j='', processing='Append', iteration=0, hidden=False)

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('MultiBlast')