import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
import experiments.counts_new
from special_widgets import unit_widgets
from nspyre import InstrumentManager
#from special_widgets.experiment_widget import ExperimentWidget
from nspyre import DataSource
import experiments.counts
import experiments.planescan
import experiments.WFODMR
import experiments.spatialfb
import experiments.counts_new
import experiments.picture
import experiments.WFTracking

import experiments.confocalODMR

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