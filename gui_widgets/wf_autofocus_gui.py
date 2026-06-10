import numpy as np


from nspyre import ExperimentWidget
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox


import experiments.wf_autofocus


import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

get_param_value_funs={
            QSpinBox: lambda w: w.value(),
        }

class WFAutofocusWidget(ExperimentWidget):
    def __init__(self):
        params_config={
            'coordinates': {
                'display_text': 'Focus (x, y, r)',
                'widget': QtWidgets.QLineEdit('(512, 512, 16)')
            },
            'picture': {
                'display_text': 'Data Series',
                'widget': QtWidgets.QLineEdit('picture')
            }

        }

        super().__init__(
            params_config,
            experiments.wf_autofocus,
            'WFAutofocus',
            'autofocus',
            title='Wide Field Autofocus'
        )

