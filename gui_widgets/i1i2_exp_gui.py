import numpy as np
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox
from pyqtgraph import SpinBox
from PyQt6.QtWidgets import QLineEdit
from nspyre import ExperimentWidget
from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget
# from special_widgets.flex_line_plot_widget_fitting import CustomLinePlotWidget
import pyqtgraph as pg
  



import experiments.i1i2
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
        z_feedback_every_sb.setValue(5)

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
        sideband_frequency_cb.setCurrentText('12.345679')
        # New params_config dictionary using only display_text and widget:
        track_z_cb = QCheckBox()
        track_z_cb.setChecked(True)

        continuous_tracking_cb = QCheckBox()
        continuous_tracking_cb.setChecked(True)

        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'FM'])
        mode_cb.setCurrentText('FM')

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
                'widget': QLineEdit("(2.864e9, 2.872e9, 10)")
            },
            'slope_range': {
                'display_text': 'Slope Range',
                'widget': QLineEdit("(2.864e9, 2.872e9)")
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
                'widget': continuous_tracking_cb
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
                'widget': QLineEdit("(0.1, 0.1, 0.3)")
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
                'widget': QLineEdit("(0.1,0.01,0)")
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
            'mode': {
                'display_text': 'Mode',
                'widget': mode_cb
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QLineEdit('I1I2'),
            },
        }
        
        super().__init__(
            params_config,
            experiments.i1i2,
            'I1I2',
            'i1i2',
            title='I1I2 Experiment',
            add_export_import_buttons=True
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
                sb = float(sink.params['sideband_frequency'])*1e6  # Get sideband frequency from parameters
                

        
                
                # Check if we have data
                if len(I1_data) == 0 or len(I2_data) == 0:
                    return
                
                # Initialize I2-I1 dataset
                I2_minus_I1 = []
                I1_offset = []
                I2_offset = []
                
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
                        f1 = frequencies - sb
                        f2 = frequencies + sb
                        
                        # Calculate difference I2 - I1
                        div_values = 2 * (I2_values - I1_values) / (I2_values + I1_values)
                        
                        # Store sweep entry with frequencies and difference values as numpy arrays
                        I2_minus_I1.append(np.stack([frequencies, div_values]))
                        I1_offset.append(np.stack([f1, I1_values/ (I2_values + I1_values)]))
                        I2_offset.append(np.stack([f2, I2_values/ (I2_values + I1_values)]))

                
                # Store the processed data
                sink.datasets["I2_I1"] = I2_minus_I1
                sink.datasets["I1_offset"] = I1_offset
                sink.datasets["I2_offset"] = I2_offset

        super().__init__(data_processing_func=processing_function) 
        self.add_plot('I1',        series='I1_offset',   scan_i='',     scan_j='',  processing='Average' ,  iteration=0,  hidden=True)
        self.add_plot('I2',        series='I2_offset',   scan_i='',     scan_j='',  processing='Average',  iteration=0,  hidden=True)
        self.add_plot('I2_I1',      series='I2_I1', scan_i='',     scan_j='',  processing='Average',  iteration=0,  hidden=False)


        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('I1I2')

# class I1I2PIDPlotWidget(CustomLinePlotWidget):
#     """Plot I1I2-derived time traces with PID-smoothed ZFS and QLS estimates.

#     The I1/I2 data are converted into the normalized signal
#     ``(I2 - I1) / (I2 + I1)``.  A ZFS estimate is produced for every
#     measurement point using the current QLS estimate, while the QLS estimate
#     is updated once per pair of measurement points from the local slope.

#     The entire estimator history is recomputed from the current sink data on
#     every processing pass.  This is intentional: changing one of the GUI
#     processing parameters and pressing *Update Processing Function* therefore
#     regenerates the whole trace without double-applying PID history.
#     """

#     def __init__(self):

#         def _pid_update(current, target, P, I, D, integral, previous_error, dt):
#             """Perform one discrete PID update of an estimator toward a target."""
#             if not (np.isfinite(current) and np.isfinite(target)):
#                 return current, integral, previous_error

#             dt = float(dt)
#             if not np.isfinite(dt) or dt <= 0:
#                 dt = 1.0

#             error = target - current
#             integral = integral + error * dt
#             derivative = (
#                 0.0
#                 if previous_error is None
#                 else (error - previous_error) / dt
#             )

#             updated = current + P * error + I * integral + D * derivative
#             return updated, integral, error

#         def _extract_points(sink):
#             """Flatten the sink I1/I2 sweeps into frequency, I1, and I2 arrays."""
#             if 'I1' not in sink.datasets or 'I2' not in sink.datasets:
#                 return np.array([]), np.array([]), np.array([])

#             I1_data = sink.datasets['I1']
#             I2_data = sink.datasets['I2']
#             if len(I1_data) == 0 or len(I2_data) == 0:
#                 return np.array([]), np.array([]), np.array([])

#             frequencies_all = []
#             I1_all = []
#             I2_all = []

#             for sweep_idx in range(min(len(I1_data), len(I2_data))):
#                 I1_sweep = I1_data[sweep_idx]
#                 I2_sweep = I2_data[sweep_idx]

#                 try:
#                     f1 = np.asarray(I1_sweep[0], dtype=float).reshape(-1)
#                     f2 = np.asarray(I2_sweep[0], dtype=float).reshape(-1)
#                     y1 = np.asarray(I1_sweep[1], dtype=float).reshape(-1)
#                     y2 = np.asarray(I2_sweep[1], dtype=float).reshape(-1)
#                 except (IndexError, TypeError, ValueError):
#                     continue

#                 n = min(f1.size, f2.size, y1.size, y2.size)
#                 if n == 0:
#                     continue

#                 # I1 and I2 should normally share the same center frequency.
#                 # Averaging the two makes the code tolerant of tiny numerical
#                 # differences while still representing the intended center.
#                 frequencies_all.append(0.5 * (f1[:n] + f2[:n]))
#                 I1_all.append(y1[:n])
#                 I2_all.append(y2[:n])

#             if not frequencies_all:
#                 return np.array([]), np.array([]), np.array([])

#             return (
#                 np.concatenate(frequencies_all),
#                 np.concatenate(I1_all),
#                 np.concatenate(I2_all),
#             )

#         def processing_function(sink):
#             """Create the I1I2 time trace and PID-smoothed ZFS/QLS traces.

#             Generated datasets have the standard FlexLinePlotWidget format:
#             each is a list containing one ``(2, n)`` numpy array.

#             - ``I2_I1_time_trace``: one point per I1/I2 measurement.
#             - ``ZFS_estimator``: one point per I1/I2 measurement.
#             - ``QLS_estimator``: one point per pair of I1/I2 measurements.

#             For the linear I1I2 model
#             ``signal = QLS * (frequency - ZFS)``, the instantaneous ZFS target
#             is ``frequency - signal / QLS``.  The QLS target is the slope of
#             each consecutive non-overlapping pair of signal points.
#             """
#             QLS_initial_guess = float(self.processing_params['QLS_estimator'])
#             ZFS_initial_guess = float(self.processing_params['ZFS_estimator'])

#             P_QLS = float(self.processing_params['P_QLS'])
#             I_QLS = float(self.processing_params['I_QLS'])
#             D_QLS = float(self.processing_params['D_QLS'])
#             P_ZFS = float(self.processing_params['P_ZFS'])
#             I_ZFS = float(self.processing_params['I_ZFS'])
#             D_ZFS = float(self.processing_params['D_ZFS'])

#             frequencies, I1_values, I2_values = _extract_points(sink)
#             n_points = frequencies.size

#             # Clear processed traces when the source has no usable I1/I2 data,
#             # rather than leaving stale traces from an earlier update.
#             if n_points == 0:
#                 sink.datasets['I2_I1_time_trace'] = []
#                 sink.datasets['ZFS_estimator'] = []
#                 sink.datasets['QLS_estimator'] = []
#                 return

#             # I1I2 currently provides the measurement duration as a parameter
#             # rather than a dedicated timestamp for each frequency point.
#             # Use it to construct an elapsed-time axis.
#             try:
#                 dt_point = float(sink.params.get('time_per_sgpoint', 1.0))
#             except (AttributeError, TypeError, ValueError):
#                 dt_point = 1.0
#             if not np.isfinite(dt_point) or dt_point <= 0:
#                 dt_point = 1.0

#             times = np.arange(n_points, dtype=float) * dt_point

#             denominator = I2_values + I1_values
#             I2_I1 = np.full(n_points, np.nan, dtype=float)
#             valid_denominator = np.isfinite(denominator) & (
#                 np.abs(denominator) > np.finfo(float).eps
#             )
#             np.divide(
#                 I2_values - I1_values,
#                 denominator,
#                 out=I2_I1,
#                 where=valid_denominator,
#             )

#             zfs_current = ZFS_initial_guess
#             qls_current = QLS_initial_guess

#             zfs_integral = 0.0
#             qls_integral = 0.0
#             zfs_previous_error = None
#             qls_previous_error = None

#             zfs_values = []
#             qls_times = []
#             qls_values = []

#             pair_frequency = None
#             pair_signal = None
#             last_qls_time = None

#             qls_epsilon = np.finfo(float).eps

#             for i, (t, frequency, signal) in enumerate(
#                 zip(times, frequencies, I2_I1)
#             ):
#                 # Update QLS every other point using non-overlapping point
#                 # pairs: (0, 1), (2, 3), ... .  This gives floor(N/2) QLS
#                 # samples, as intended by the widget design.
#                 if i % 2 == 0:
#                     pair_frequency = frequency
#                     pair_signal = signal
#                 else:
#                     qls_target = np.nan
#                     if (
#                         pair_frequency is not None
#                         and pair_signal is not None
#                         and np.isfinite(pair_frequency)
#                         and np.isfinite(pair_signal)
#                         and np.isfinite(frequency)
#                         and np.isfinite(signal)
#                     ):
#                         delta_frequency = frequency - pair_frequency
#                         if abs(delta_frequency) > qls_epsilon:
#                             qls_target = (signal - pair_signal) / delta_frequency

#                     if last_qls_time is None:
#                         dt_qls = 2.0 * dt_point
#                     else:
#                         dt_qls = t - last_qls_time

#                     if np.isfinite(qls_target):
#                         (
#                             qls_current,
#                             qls_integral,
#                             qls_previous_error,
#                         ) = _pid_update(
#                             qls_current,
#                             qls_target,
#                             P_QLS,
#                             I_QLS,
#                             D_QLS,
#                             qls_integral,
#                             qls_previous_error,
#                             dt_qls,
#                         )

#                     qls_times.append(t)
#                     qls_values.append(qls_current)
#                     last_qls_time = t
#                     pair_frequency = None
#                     pair_signal = None

#                 # Using the most recently available QLS estimate, calculate
#                 # the instantaneous ZFS implied by this I1I2 point:
#                 # signal = QLS * (frequency - ZFS).
#                 zfs_target = np.nan
#                 if (
#                     np.isfinite(frequency)
#                     and np.isfinite(signal)
#                     and np.isfinite(qls_current)
#                     and abs(qls_current) > qls_epsilon
#                 ):
#                     zfs_target = frequency - signal / qls_current

#                 if np.isfinite(zfs_target):
#                     (
#                         zfs_current,
#                         zfs_integral,
#                         zfs_previous_error,
#                     ) = _pid_update(
#                         zfs_current,
#                         zfs_target,
#                         P_ZFS,
#                         I_ZFS,
#                         D_ZFS,
#                         zfs_integral,
#                         zfs_previous_error,
#                         dt_point,
#                     )

#                 # Keep one ZFS value per measurement point even when an
#                 # individual point is invalid; in that case the estimator is
#                 # simply held at its previous value.
#                 zfs_values.append(zfs_current)

#             sink.datasets['I2_I1_time_trace'] = [
#                 np.stack([times, I2_I1])
#             ]
#             sink.datasets['ZFS_estimator'] = [
#                 np.stack([times, np.asarray(zfs_values, dtype=float)])
#             ]

#             if qls_times:
#                 sink.datasets['QLS_estimator'] = [
#                     np.stack(
#                         [
#                             np.asarray(qls_times, dtype=float),
#                             np.asarray(qls_values, dtype=float),
#                         ]
#                     )
#                 ]
#             else:
#                 sink.datasets['QLS_estimator'] = []

#         super().__init__(
#             processing_params=[
#                 ('P_ZFS', 'I_ZFS', 'D_ZFS'),
#                 ('P_QLS', 'I_QLS', 'D_QLS'),
#                 ('ZFS_estimator', 'QLS_estimator'),
#             ],
#             processing_param_defaults={
#                 'P_ZFS': 0.1,
#                 'I_ZFS': 0.01,
#                 'D_ZFS': 0.0,
#                 'P_QLS': 0.1,
#                 'I_QLS': 0.01,
#                 'D_QLS': 0.0,
#                 'ZFS_estimator': 2.868e9,
#                 'QLS_estimator': 5e-9,
#             },
#             xlabel='Time (s)',
#             title='I1I2 PID',
#             data_processing_func=processing_function,
#         )

#         # Existing tracking data. Keep these available but hidden by default
#         # because their scales differ strongly from the PID estimator traces.
#         self.add_plot(
#             'X_Position', series='x_pos', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'Y_Position', series='y_pos', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'Z_Position', series='z_pos', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'Fluorescence', series='total_fluor', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'X_Search', series='x_search', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'Y_Search', series='y_search', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'Z_Search', series='z_search', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )

#         # Derived PID traces.
#         self.add_plot(
#             'I2_I1_Time_Trace', series='I2_I1_time_trace', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'QLS_PID', series='QLS_estimator', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=True
#         )
#         self.add_plot(
#             'ZFS_PID', series='ZFS_estimator', scan_i='', scan_j='',
#             processing='Append', iteration=0, hidden=False
#         )

#         # retrieve legend object
#         legend = self.line_plot.plot_widget.addLegend()
#         # set the legend location
#         legend.setOffset((-10, -50))

#         self.datasource_lineedit.setText('I1I2')