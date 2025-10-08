import numpy as np


from nspyre import ExperimentWidget
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
from special_widgets import unit_widgets


import experiments.picture


import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
        }

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

class PicturesHeatMapWidget(HeatMapPlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        

        super().__init__()
                # open in read-only mode; adjust dataset name if needed

        self.datasource_lineedit.setText('picture')
        super().add_heatmap("Picture", "picture")