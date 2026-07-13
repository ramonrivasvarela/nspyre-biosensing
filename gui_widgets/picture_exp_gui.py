import numpy as np


from nspyre import ExperimentWidget
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox


import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
        }

import experiments.picture
class PicturesWidget(ExperimentWidget):
    def __init__(self):

        single_picture_cb = QCheckBox()
        single_picture_cb.setChecked(True)
        params_config={
            'readout_time': {
                'display_text': 'Readout Time (External Trigger Only)',
                'widget': pg.SpinBox(value=0.015, bounds=(0, 1), suffix='s', siPrefix=True, dec=True)
            },
            'trigger_time': {
                'display_text': 'Trigger Time (External Trigger Only)',
                'widget': pg.SpinBox(value=0.01, bounds=(0, 1), suffix='s', siPrefix=True, dec=True)
            },
            'buffer_time': {
                'display_text': 'Buffer Time (External Trigger Only)',
                'widget': pg.SpinBox(value=0.005, bounds=(0, 1), suffix='s', siPrefix=True, dec=True)
            },
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
            title='Pictures'
        )

class PicturesHeatMapWidget(HeatMapPlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        

        super().__init__()
                # open in read-only mode; adjust dataset name if needed

        self.datasource_lineedit.setText('picture')
        super().add_heatmap("Latest", "latest_image")
