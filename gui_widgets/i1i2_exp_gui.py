import numpy as np
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
from pyqtgraph import SpinBox
from PyQt6.QtWidgets import QLineEdit
import experiments.i1i2
from nspyre import ExperimentWidget
from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget
import pyqtgraph as pg
  




class I1I2Widget(ExperimentWidget):
    def __init__(self):

        # Pre-configured widgets for extra configuration:
        apd_channel_cb = QComboBox()
        apd_channel_cb.addItems(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none'])
        apd_channel_cb.setCurrentText('ctr1')

        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setValue(10)

        read_timeout_sb = QSpinBox()
        read_timeout_sb.setMinimum(0)
        read_timeout_sb.setValue(12)

        sweeps_until_feedback_sb = QSpinBox()
        sweeps_until_feedback_sb.setMinimum(1)
        sweeps_until_feedback_sb.setValue(6)

        z_feedback_every_sb = QSpinBox()
        z_feedback_every_sb.setMinimum(1)
        z_feedback_every_sb.setValue(1)

        shrink_every_x_iter_sb = QSpinBox()
        shrink_every_x_iter_sb.setMinimum(1)
        shrink_every_x_iter_sb.setValue(1)

        search_integral_history_sb = QSpinBox()
        search_integral_history_sb.setMinimum(1)
        search_integral_history_sb.setValue(5)

        sideband_frequency_cb = QComboBox()
        sideband_items = ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                        '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                        '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                        '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                        '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                        '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                        '5.952380952', '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291',
                        '5.2631579', '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222',
                        '2.84090909', '2.5']
        sideband_frequency_cb.addItems(sideband_items)
        sideband_frequency_cb.setCurrentText("10.1010101")
        # New params_config dictionary using only display_text and widget:
        track_z_cb = QCheckBox()
        track_z_cb.setChecked(True)
        params_config = {
            'sampling_rate': {
                'display_text': 'Sampling Rate',
                'widget': SpinBox(
                    value=50000,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                    bounds=(1, 1e9),
                )
            },
            'clockPulseTime': {
                'display_text': 'Clock Pulse Time',
                'widget': SpinBox(
                    value=10e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1),
                )
            },
            'mwPulseTime': {
                'display_text': 'MW Pulse Time',
                'widget': SpinBox(
                    value=50e-6,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-9, 1),
                )
            },
            'time_per_sgpoint': {
                'display_text': 'Time per SG Point',
                'widget': SpinBox(
                    value=0.5,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(0.001, 1000),
                )
            },
            'sweeps': {
                'display_text': 'Sweeps',
                'widget': sweeps_sb
            },
            'frequencies': {
                'display_text': 'Frequencies',
                'widget': QLineEdit("(2.865e9, 2.87e9, 10)")
            },
            'slope_range': {
                'display_text': 'Slope Range',
                'widget': QLineEdit("(2.8665e9, 2.8685e9)")
            },
            'sideband_frequency': {
                'display_text': 'Sideband Frequency',
                'widget': sideband_frequency_cb
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': SpinBox(
                    value=-15,
                    suffix='dBm',
                    siPrefix=False,
                    dec=True,
                    bounds=(-50, 10),
                )
            },
            'read_timeout': {
                'display_text': 'Read Timeout',
                'widget': read_timeout_sb
            },
            'sweeps_until_feedback': {
                'display_text': 'Sweeps Until Feedback',
                'widget': sweeps_until_feedback_sb
            },
            'z_cycle': {
                'display_text': 'Z Feedback Every',
                'widget': z_feedback_every_sb
            },
            'track_z':{
                'display_text': 'Track Z',
                'widget': track_z_cb
            },
            'xyz_step_nm': {
                'display_text': 'XYZ Step',
                'widget': SpinBox(
                    value=0.5e-7,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1e-3),
                )
            },
            'shrink_every_x_iter': {
                'display_text': 'Shrink Every X Iter',
                'widget': shrink_every_x_iter_sb
            },

            'continuous_tracking': {
                'display_text': 'Continuous Tracking',
                'widget': QCheckBox()
            },
            'searchXYZ': {
                'display_text': 'Search XYZ',
                'widget': QLineEdit("[0.5, 0.5, 0.5]")
            },
            'max_search': {
                'display_text': 'Max Search',
                'widget': QLineEdit("(1.0, 1.0, 1.0)")
            },
            'min_search': {
                'display_text': 'Min Search',
                'widget': QLineEdit("(0.1, 0.1, 0.1)")
            },
            'scan_distance': {
                'display_text': 'Scan Distance',
                'widget': QLineEdit("(0.03, 0.03, 0.05)")
            },
            'changing_search': {
                'display_text': 'Changing Search',
                'widget': QCheckBox()
            },
            'search_PID': {
                'display_text': 'Search PID',
                'widget': QLineEdit("(0.5,0.01,0)")
            },
            'search_integral_history': {
                'display_text': 'Search Integral History',
                'widget': search_integral_history_sb
            },
            'spot_size': {
                'display_text': 'Spot Size',
                'widget': SpinBox(
                    value=400e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-12, 1e-3),
                )
            },
            'advanced_tracking': {
                'display_text': 'Advanced Tracking',
                'widget': QCheckBox()
            },
            'diffusion_constant': {
                'display_text': 'Diffusion Constant',
                'widget': SpinBox(
                    value=200,
                    siPrefix=False,
                    dec=True,
                    bounds=(0.1, 10000),
                )
            },
            'data_download': {
                'display_text': 'Data Download',
                'widget': QCheckBox()
            },
            'dataset': {
                'display_text': 'Data Source',
                'widget': QLineEdit('i1i2'),
            },
            'tracking_dataset': {
                'display_text': 'Tracking Data Source',
                'widget': QLineEdit('i1i2_tracking'),
            }
        }
        
        super().__init__(
            params_config,
            experiments.i1i2,
            'I1I2',
            'i1i2',
            title='I1I2 Experiment'
        )

class I1I2PlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        
        # create some default signal plots
        def processing_function(sink):
            """
            Processing function to calculate I2-I1 difference from I1I2 experiment data.
            
            The I1I2 experiment returns data where I1 and I2 are lists containing:
            - Each entry is a list with [frequencies_array, values_array]
            
            This function calculates I2-I1 for each frequency point.
            """
            if 'I1' in sink.datasets and 'I2' in sink.datasets:
                I1_data = sink.datasets['I1']
                I2_data = sink.datasets['I2']
                
                # Check if we have data
                if len(I1_data) == 0 or len(I2_data) == 0:
                    return
                
                # Initialize I2-I1 dataset
                I2_minus_I1 = []
                
                # Process each sweep (assuming I1 and I2 have same number of sweeps)
                min_sweeps = min(len(I1_data), len(I2_data))
                
                for i in range(min_sweeps):
                    # Extract frequency and value arrays from each sweep
                    I1_sweep = I1_data[i]
                    I2_sweep = I2_data[i]
                    
                    # Each sweep is [frequencies, values]
                    if len(I1_sweep) >= 2 and len(I2_sweep) >= 2:
                        frequencies = np.array(I1_sweep[0])
                        I1_values = np.array(I1_sweep[1])
                        I2_values = np.array(I2_sweep[1])
                        
                        # Calculate difference I2 - I1
                        div_values = (I2_values - I1_values)/(2*(I2_values + I1_values))
                        
                        # Store sweep entry with frequencies and difference values as numpy arrays
                        I2_minus_I1.append(np.stack([frequencies, div_values]))
                
                # Store the processed data
                sink.datasets["I2_I1"] = I2_minus_I1
                
        super().__init__(data_processing_func=processing_function) 
        self.add_plot('I1',        series='I1',   scan_i='',     scan_j='',  processing='Average' , hidden=True)
        self.add_plot('I2',        series='I2',   scan_i='',     scan_j='',  processing='Average', hidden=True)
        self.add_plot('I2-I1/2(I1+I2)',      series='I2_I1', scan_i='',     scan_j='',  processing='Average')


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('i1i2')