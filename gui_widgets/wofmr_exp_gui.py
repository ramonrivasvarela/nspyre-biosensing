import experiments.wfODMR

from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox
import numpy as np


MAXIMUM = 2147483647  # QSpinBox maximum


class wODMRWidget(ExperimentWidget):
    def __init__(self):
        # Pulse timings
        exp_time_sb = SpinBox(
            value=75e-3,
            suffix='s',
            siPrefix=True,
            dec=True,
            bounds=(1e-6, 1000),
        )
        readout_time_sb = SpinBox(
            value=15e-3,
            suffix='s',
            siPrefix=True,
            dec=True,
            bounds=(1e-6, 1000),
        )

        # Routine
        sweeps_sb = QSpinBox()
        sweeps_sb.setMinimum(1)
        sweeps_sb.setMaximum(MAXIMUM)
        sweeps_sb.setValue(3)

        # Gain
        gain_sb = QSpinBox()
        gain_sb.setMinimum(1)
        gain_sb.setMaximum(272)
        gain_sb.setValue(2)

        gain_setting_cb = QComboBox()
        gain_setting_cb.addItems(['optimize', 'override', 'use current'])
        gain_setting_cb.setCurrentText('optimize')

        # Camera settings
        cam_trigger_cb = QComboBox()
        cam_trigger_cb.addItems(['EXTERNAL_EXPOSURE', 'EXTERNAL_FT'])
        cam_trigger_cb.setCurrentText('EXTERNAL_FT')

        # SG
        rf_amplitude_sb = SpinBox(
            value=-15,
            suffix='dBm',
            siPrefix=False,
            dec=True,
            bounds=(-100, 10),
        )

        uw_duty_sb = SpinBox(
            value=1.0,
            siPrefix=False,
            dec=True,
            bounds=(0.001, 1.0),
        )

        uw_rep_sb = SpinBox(
            value=50,
            suffix='Hz',
            siPrefix=True,
            dec=True,
            bounds=(1, 1e6),
        )

        mode_cb = QComboBox()
        mode_cb.addItems(['QAM', 'AM'])
        mode_cb.setCurrentText('QAM')

        # Data acquisition
        alt_label_cb = QCheckBox()
        alt_label_cb.setChecked(False)

        alt_sleep_time_sb = SpinBox(
            value=0.0,
            suffix='s',
            siPrefix=True,
            dec=True,
            bounds=(0.0, 3600.0),
        )

        focus_bool_cb = QCheckBox()
        focus_bool_cb.setChecked(True)

        # Saving
        save_image_cb = QComboBox()
        save_image_cb.addItems(
            ['no_save', 'tracking', 'raw_images', 'raw_images_safe', '[x]per_sweep', '[x]all_sweep']
        )
        save_image_cb.setCurrentText('no_save')

        data_download_cb = QCheckBox()
        data_download_cb.setChecked(False)

        # Debug
        shutdown_cb = QCheckBox()
        shutdown_cb.setChecked(True)

        verbose_cb = QCheckBox()
        verbose_cb.setChecked(True)

        params_config = {
            # Pulse timings
            'exp_time': {
                'display_text': 'Exposure Time',
                'widget': exp_time_sb,
            },
            'readout_time': {
                'display_text': 'Readout Time',
                'widget': readout_time_sb,
            },
            # Routine
            'sweeps': {
                'display_text': 'Sweeps',
                'widget': sweeps_sb,
            },
            'label': {
                'display_text': 'Label',
                'widget': QLineEdit('[t, 1, 0, 1, 0]'),
            },
            'frequencies': {
                'display_text': 'Frequencies',
                'widget': QLineEdit('[2.835e9, 2.905e9, 30]'),
            },
            # Gain
            'gain': {
                'display_text': 'EM Gain',
                'widget': gain_sb,
            },
            'gain_setting': {
                'display_text': 'Gain Setting',
                'widget': gain_setting_cb,
            },
            # Cam settings
            'cooler': {
                'display_text': 'Cooler',
                'widget': QLineEdit('(False, 20)'),
            },
            'cam_trigger': {
                'display_text': 'Camera Trigger',
                'widget': cam_trigger_cb,
            },
            # SG
            'rf_amplitude': {
                'display_text': 'RF Amplitude',
                'widget': rf_amplitude_sb,
            },
            'uw_duty': {
                'display_text': 'uW Duty',
                'widget': uw_duty_sb,
            },
            'uw_rep': {
                'display_text': 'uW Rep',
                'widget': uw_rep_sb,
            },
            'mode': {
                'display_text': 'Mode',
                'widget': mode_cb,
            },
            # Data acquisition
            'ROI_xy': {
                'display_text': 'ROI xy',
                'widget': QLineEdit('[(512,512)]'),
            },
            'alt_label': {
                'display_text': 'Alternate Label',
                'widget': alt_label_cb,
            },
            'alt_sleep_time': {
                'display_text': 'Alt Sleep Time',
                'widget': alt_sleep_time_sb,
            },
            'trackpy_params': {
                'display_text': 'Trackpy Params',
                'widget': QLineEdit("{'trackpy': True, 'sigma': 1.2, 'r_ND': 7, 'min_dist': 8, 'bg_pts': []}"),
            },
            'focus_bool': {
                'display_text': 'Focus Bool',
                'widget': focus_bool_cb,
            },
            # Saving
            'data_path': {
                'display_text': 'Data Path',
                'widget': QLineEdit('Z:\\biosensing_setup\\data\\Widefield\\'),
            },
            'save_image': {
                'display_text': 'Save Image',
                'widget': save_image_cb,
            },
            'data_download': {
                'display_text': 'Data Download',
                'widget': data_download_cb,
            },
            # Debug
            'shutdown': {
                'display_text': 'Shutdown',
                'widget': shutdown_cb,
            },
            'verbose': {
                'display_text': 'Verbose',
                'widget': verbose_cb,
            },
            'window_params': {
                'display_text': 'Window Params',
                'widget': QLineEdit("{'interval': 0, 'all_ROI': False, 'r_display': 16}"),
            },
            'data_source': {
                'display_text': 'Data Source',
                'widget': QLineEdit('wfodmr')
            },
            'Misc': {
                'display_text': 'Misc',
                'widget': QLineEdit("{'DEBUG':False}"),
            },
        }

        def data_processing_func(sink):
            frequencies=sink.params['frequencies']
            n_freqs=len(frequencies)
            number_ND=sink.output['number_ND']
            for i in range(number_ND):
                sink.datasets[f"signal_{i}"]=np.array([])
                sink.datasets[f"background_{i}"]=np.array([])
                sink.datasets[f"signal_all_{i}"]=np.array([])
                sink.datasets[f"signal_div_{i}"]=np.array([])
            for sweep in range(sink.params['sweeps']):
                for i in range(number_ND):
                    signal_counts=np.empty(n_freqs)
                    signal_counts[:]=np.nan
                    sink.datasets[f"signal_{i}"].append(np.stack([frequencies, signal_counts], axis=1))
                    background_counts=np.empty(n_freqs)
                    background_counts[:]=np.nan
                    sink.datasets[f"background_{i}"].append(np.stack([frequencies, background_counts], axis=1))
                    signal_all_counts=np.empty(n_freqs)
                    signal_all_counts[:]=np.nan
                    sink.datasets[f"signal_all_{i}"].append(np.stack([frequencies, signal_all_counts], axis=1))
                    signal_div_counts=np.empty(n_freqs)
                    signal_div_counts[:]=np.nan
                    sink.datasets[f"signal_div_{i}"].append(np.stack([frequencies, signal_div_counts], axis=1))
                    for j in range(n_freqs):
                        sink.datasets[f"signal_{i}"][-1][1][j]=sink.datasets["signal"][sweep][1][j][i]
                        sink.datasets[f"background_{i}"][-1][1][j]=sink.datasets["background"][sweep][1][j][i]
                        sink.datasets[f"signal_all_{i}"][-1][1][j]=sink.datasets["signal_all"][sweep][1][j][i]
                        sink.datasets[f"signal_div_{i}"][-1][1][j]=sink.datasets["signal_div"][sweep][1][j][i]

                    
            return

        super().__init__(
            params_config,
            experiments.wfODMR,
            'wODMRSpyrelet',
            'wfodmr',
            title='Widefield ODMR', data_processing_func=data_processing_func
        )
        self.add_plot('signal_div_1', series='signal_1', scan_i='sweep', scan_j='', processing='Average')

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('wfodmr')

