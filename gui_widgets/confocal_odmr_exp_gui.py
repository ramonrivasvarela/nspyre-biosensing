import numpy as np
from scipy import optimize

from nspyre import FlexLinePlotWidget
from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QSpinBox, QLineEdit, QCheckBox, QComboBox
from pyqtgraph import SpinBox

import experiments.confocalODMR
import sys

import pyqtgraph as pg

from special_widgets.heat_map_plot_widget import HeatMapPlotWidget

cmap = pg.colormap.get('viridis')  

MAXIMUM=2147483647 # There has to be a better way...
class ConfocalODMRWidget(ExperimentWidget):
    def __init__(self):
        from PyQt6.QtWidgets import QLineEdit, QSpinBox, QCheckBox, QComboBox

        # Define widgets that require extra configuration outside of params:
        # channel1_cb = QComboBox()
        # channel1_cb.addItems(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none'])
        # channel1_cb.setCurrentText('ctr1')
        
        runs_sb = QSpinBox()
        runs_sb.setMinimum(1)
        
        runs_sb.setMaximum(MAXIMUM)
        runs_sb.setValue(1000)
        
        timeout_sb = QSpinBox()
        timeout_sb.setMinimum(0)
        timeout_sb.setValue(30)
        
        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setMaximum(MAXIMUM)
        sweeps_sb.setValue(10)


        
        # repetitions_sb = QSpinBox()
        # repetitions_sb.setMinimum(1)
        # repetitions_sb.setValue(1)

        # sequence_cb = QComboBox()
        # sequence_cb.addItems(['odmr_heat_wait', 'odmr_no_wait'])
        # sequence_cb.setCurrentText('odmr_no_wait')
        
        sweeps_til_fb_sb = QSpinBox()
        sweeps_til_fb_sb.setMinimum(0)
        sweeps_til_fb_sb.setMaximum(MAXIMUM)
        sweeps_til_fb_sb.setValue(6)
        
        starting_point_cb = QComboBox()
        starting_point_cb.addItems(['user_input', 'current_position (ignore input)'])
        starting_point_cb.setCurrentText('current_position (ignore input)')
        
        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'AM', 'NoMod'])
        mode_cb.setCurrentText('QAM')

        # sampling_rate_sb=unit_widgets.HzLineEdit(50000)

        # repeat_minutes_sb = SpinBox()
        # repeat_minutes_sb.setValue(0)
        # repeat_minutes_sb.setMinimum(0)
        # repeat_minutes_sb.setMaximum(None)
        # repeat_minutes_sb.setDecimals(3)

        rf_amplitude_sb = QSpinBox()
        rf_amplitude_sb.setMinimum(-100)
        rf_amplitude_sb.setMaximum(7)
        rf_amplitude_sb.setValue(-20)


        dozfb_cb=QCheckBox()
        dozfb_cb.setChecked(True)

        switch_cb=QCheckBox()
        switch_cb.setChecked(False)

        count_step_shrink_sb=QSpinBox()
        count_step_shrink_sb.setMinimum(1)

        
        # Build the parameter configuration dictionary using only display_text and widget.
        # Widgets that require extra config have been defined above.
        params_config = {
            # 'device': {
            #     'display_text': 'Device',
            #     'widget': QLineEdit("Dev1")
            # },
            # 'channel1': {
            #     'display_text': 'Channel1',
            #     'widget': channel1_cb
            # },
            # 'PS_clk_channel': {
            #     'display_text': 'PS Clock Channel',
            #     'widget': QLineEdit("PFI0")
            # },
            # 'sampling_rate': {
            #     'display_text': 'Sampling Rate',
            #     'widget': sampling_rate_sb
            # },
            'runs': {
                'display_text': 'Runs',
                'widget': runs_sb
            },
            'timeout': {
                'display_text': 'Timeout',
                'widget': timeout_sb
            },
            'sweeps': {
                'display_text': 'Sweeps',
                'widget': sweeps_sb
            },
            # 'repeat_every_x_minutes': {
            #     'display_text': 'Repeat Every X Minutes',
            #     'widget': repeat_minutes_sb
            # },
            # 'repetitions': {
            #     'display_text': 'Repetitions',
            #     'widget': repetitions_sb
            # },
            'frequencies': {
                'display_text': 'Frequencies',
                'widget': QLineEdit("(2.84e9, 2.90e9, 30)")
            },
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb
            },
            'probe_time': {
                'display_text': 'Probe Time',
                'widget': SpinBox(
                    value=100e-6,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                )
            },
            'clock_duration': {
                'display_text': 'Clock Duration',
                'widget': SpinBox(
                    value=10e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                )
            },
            'laser_lag': {
                'display_text': 'Laser Lag',
                'widget': SpinBox(
                    value=80e-9,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                )
            },
            'cooldown_time': {
                'display_text': 'Cooldown Time',
                'widget': SpinBox(
                    value=0,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                )
            },
            'use_switch': {
                'display_text': 'Switch',
                'widget': switch_cb
            },
            # 'sequence': {
            #     'display_text': 'Sequence',
            #     'widget': sequence_cb
            # },
            'dozfb': {
                'display_text': 'Z Feedback',
                'widget': dozfb_cb
            },
            'sweeps_til_fb': {
                'display_text': 'Sweeps Till Feedback',
                'widget': sweeps_til_fb_sb
            },
            # 'initial_position': {
            #     'display_text': 'Initial Position',
            #     'widget': unit_widgets.PointWidget(0.0, 0.0, 0.0)
            # },
            
            'xyz_step': {
                'display_text': 'XYZ Step',
                'widget': SpinBox(
                    value=45e-9,
                    suffix='m',
                    siPrefix=True,
                    dec=True,
                )
            },
            'count_step_shrink': {
                'display_text': 'Count Step Shrink',
                'widget': count_step_shrink_sb
            },
            'starting_point': {
                'display_text': 'Starting Point',
                'widget': starting_point_cb
            },
            # 'data_download': {
            #     'display_text': 'Data Download',
            #     'widget': QCheckBox()
            # },
            'mode': {
                'display_text': 'Mode',
                'widget': mode_cb
            },
            'dataset':{
                'display_text':'Data Set',
                'widget':QLineEdit('odmr')
            }
        }
        
        super().__init__(
            params_config,
            experiments.confocalODMR,  # Ensure that experiments.ConfocalODMR exists in your experiments folder
            'ConfocalODMR',
            'confocal_odmr',
            title='Confocal ODMR'
        )

def double_lorentzian(x, A1, x1, w1, A2, x2, w2, offset):
    """Double Lorentzian function."""
    return (A1 * w1**2 / ((x - x1)**2 + w1**2) + 
            A2 * w2**2 / ((x - x2)**2 + w2**2) + offset)

def process_ODMR_data(sink: DataSink):
    """Subtract the signal from background trace and add it as a new 'diff' dataset."""
    div_sweeps = []
    for s,_ in enumerate(sink.datasets['signal']):
        freqs = sink.datasets['signal'][s][0]
        sig = sink.datasets['signal'][s][1]
        bg = sink.datasets['background'][s][1]
        div_sweeps.append(np.stack([freqs, sig / bg]))
    sink.datasets['div'] = div_sweeps
    
    # Try to fit double Lorentzian to averaged div data
    if len(div_sweeps) > 0:
        # Average all sweeps
        all_freqs = np.concatenate([sweep[0] for sweep in div_sweeps])
        all_ratios = np.concatenate([sweep[1] for sweep in div_sweeps])
        
        # Get unique frequencies and average ratios
        unique_freqs = np.unique(all_freqs)
        avg_ratios = np.array([np.mean(all_ratios[all_freqs == f]) for f in unique_freqs])
        
        # Check if there are no NaN values
        if not np.any(np.isnan(avg_ratios)):
            try:
                # Calculate frequency spacing
                d_freq = unique_freqs[1] - unique_freqs[0] if len(unique_freqs) > 1 else 1e6
                
                # Find initial guesses
                min_ratio = np.min(avg_ratios)
                max_ratio = np.max(avg_ratios)
                min_arg = np.argmin(avg_ratios)
                x1_guess = unique_freqs[min_arg]
                
                # Find second minimum
                w1_guess = 4e8
                diff = int(w1_guess / d_freq)
                mask = np.ones(len(avg_ratios), dtype=bool)
                mask[max(0, min_arg-diff):min(len(avg_ratios), min_arg+diff+1)] = False
                
                if np.sum(mask) > 0:
                    n_ratios = avg_ratios[mask]
                    n_freqs = unique_freqs[mask]
                    min_arg2 = np.argmin(n_ratios)
                    x2_guess = n_freqs[min_arg2]
                else:
                    x2_guess = x1_guess + w1_guess
                
                # Initial parameter guesses
                offset_guess = max_ratio
                A1_guess = A2_guess = min_ratio - max_ratio
                freq_range = np.max(unique_freqs) - np.min(unique_freqs)
                w1_guess = w2_guess = freq_range / 10
                
                initial_guess = [A1_guess, x1_guess, w1_guess, A2_guess, x2_guess, w2_guess, offset_guess]
                
                # Parameter bounds
                bounds = (
                    [-np.inf, np.min(unique_freqs), 0, -np.inf, np.min(unique_freqs), 0, -np.inf],
                    [0, np.max(unique_freqs), freq_range, 0, np.max(unique_freqs), freq_range, np.inf]
                )
                
                # Perform fit
                popt, pcov = optimize.curve_fit(
                    double_lorentzian,
                    unique_freqs,
                    avg_ratios,
                    p0=initial_guess,
                    bounds=bounds,
                    maxfev=10000
                )
                
                # Generate fitted curve with same x-axis values
                fitted_values = double_lorentzian(unique_freqs, *popt)
                
                # Add fit as a new dataset
                sink.datasets['div_fit'] = [np.stack([unique_freqs, fitted_values])]
                
                # Calculate R²
                residuals = avg_ratios - fitted_values
                ss_res = np.sum(residuals ** 2)
                ss_tot = np.sum((avg_ratios - np.mean(avg_ratios)) ** 2)
                r_squared = 1 - (ss_res / ss_tot)
                
                print(f"Double Lorentzian Fit: R² = {r_squared:.4f}")
                print(f"Center 1: {popt[1]:.2e} Hz, Width 1: {popt[2]:.2e} Hz")
                print(f"Center 2: {popt[4]:.2e} Hz, Width 2: {popt[5]:.2e} Hz")
                print(f"FWHM: {abs(popt[1]-popt[4])+popt[2]+popt[5]:.2e} Hz")
                
            except Exception as e:
                print(f"Fit failed: {e}")


class ConfocalODMRPlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_ODMR_data)
        # create some default signal plots
        self.add_plot('sig_avg',        series='signal',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('sig_latest',     series='signal',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default background plots
        self.add_plot('bg_avg',         series='background',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('bg_latest',      series='background',   scan_i='-1',   scan_j='',  processing='Average')

        # create some default diff plots
        self.add_plot('div_avg',       series='div',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('div_latest',    series='div',  scan_i='-1',    scan_j='',  processing='Average')
        
        # add fit plot
        self.add_plot('div_fit',       series='div_fit',  scan_i='',      scan_j='',  processing='Average')

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmr')