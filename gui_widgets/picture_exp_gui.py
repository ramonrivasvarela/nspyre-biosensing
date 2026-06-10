import numpy as np


from nspyre import ExperimentWidget
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox


import experiments.picture


import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
        }

class PicturesWidget(ExperimentWidget):
    def __init__(self):

        single_picture_cb = QCheckBox()
        single_picture_cb.setChecked(True)
        params_config={
            'zoom': {
                'display_text': 'Zoom',
                'widget': QCheckBox()
            },
            'zoom_coordinates': {
                'display_text': 'Zoom (x, y, r)',
                'widget': QtWidgets.QLineEdit('(512, 512, 16)')
            },
            'single_picture': {
                'display_text': 'Single Picture',
                'widget': single_picture_cb
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
