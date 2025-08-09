import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox
from special_widgets import unit_widgets
import experiments.planescan


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

class PlaneScanWidget(ExperimentWidget):
    def __init__(self):
        # Create SpinBoxes and set minimums
        line_scan_steps_sb = QSpinBox()
        line_scan_steps_sb.setMaximum(1000)
        line_scan_steps_sb.setValue(100)
        line_scan_steps_sb.setMinimum(1)
        
        extent_steps_sb = QSpinBox()
        extent_steps_sb.setMaximum(1000)
        extent_steps_sb.setValue(100)
        extent_steps_sb.setMinimum(1)
    
        repetitions_sb = QSpinBox(value=1)
        repetitions_sb.setMinimum(1)
        stack_count_sb = QSpinBox(value=1)
        stack_count_sb.setMinimum(1)
        pts_per_step_sb = QSpinBox(value=40)
        pts_per_step_sb.setMinimum(1)
        sleep_factor_sb = SpinBox(value=1)
        sleep_factor_sb.setMinimum(1)

        params_config = {
            'point_A': {'display_text': 'Point A',
                        'widget': unit_widgets.PointWidget(-50, 0, 50)},
            'point_B': {'display_text': 'Point B',
                        'widget': unit_widgets.PointWidget(50, 0, 50)},
            'point_C': {'display_text': 'Point C',
                        'widget': unit_widgets.PointWidget(50, 0, 80)},
            'line_scan_steps': {'display_text': 'Line Scan Steps',
                                'widget': line_scan_steps_sb},
            'extent_steps': {'display_text': 'Extent Steps',
                             'widget': extent_steps_sb},
            'ctr_ch': {'display_text': 'Center Channel',
                       'widget': QLineEdit("Dev1/ctr1")},
            'repetitions': {'display_text': 'Repetitions',
                            'widget': repetitions_sb},
            'stack_count': {'display_text': 'Stack Count',
                            'widget': stack_count_sb},
            'stack_stepsize': {'display_text': 'Stack Stepsize',
                               'widget': unit_widgets.MLineEdit(1)},
            'stack_pospref': {'display_text': 'Stack Position Pref',
                              'widget': QCheckBox()},
            'acq_rate': {'display_text': 'Acquisition Rate',
                         'widget': unit_widgets.HzLineEdit(15e3)},
            'pts_per_step': {'display_text': 'Points Per Step',
                             'widget': pts_per_step_sb},
            'xyz_pos': {'display_text': 'XYZ Position',
                        'widget': QCheckBox()},

            'snake_scan': {'display_text': 'Snake Scan',
                           'widget': QCheckBox()},
            'sleep_factor': {'display_text': 'Sleep Factor',
                             'widget': sleep_factor_sb},
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('planescan'),
            },
        
        }

        super().__init__(params_config, 
                         experiments.planescan,
                         'PlaneScan',
                         'planescan',
                         title='Plane Scan', get_param_value_funs=get_param_value_funs)

    

class PlaneScanHeatMapWidget(HeatMapPlotWidget):
    def __init__(self):
        def data_processing_func(sink):
            for i in range(len(sink.datasets)):
                name = f"stack_{i+1}"
                try:
                    val = sink.datasets[name]
                    sink.datasets[name] = np.array(val, dtype=int)
                except KeyError:
                        print(f"Missing dataset: {name}")
                        continue

        super().__init__(data_processing_func=data_processing_func)
        self.datasource_lineedit.setText('planescan')
        super().add_heatmap("Stack 1", "stack_1")
