from nspyre import ExperimentWidget
from pyqtgraph import SpinBox
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox
import numpy as np
from special_widgets.flex_line_plot_widget_fitting import FlexLinePlotWidget


MAXIMUM = 2147483647  # QSpinBox maximum

import experiments.wI1I2
class wI1I2Widget(ExperimentWidget):
    def __init__(self):
        # Pulse timings
        
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
            value=0.2,
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

        fourier_filter_sb = QSpinBox()
        fourier_filter_sb.setMinimum(0)
        fourier_filter_sb.setMaximum(100)

        params_config = {
            # Pulse timings
            'exp_time': {
                'display_text': 'Exposure Time',
                'widget': SpinBox(
                    value=75e-3,
                    suffix='s',
                    siPrefix=True,
                    dec=True,
                    bounds=(1e-6, 1000),
                ),
            },
            'readout_time': {
                'display_text': 'Readout Time',
                'widget': SpinBox(
                value=15e-3,
                suffix='s',
                siPrefix=True,
                dec=True,
                bounds=(1e-6, 1000),
            ),
            },
            # Routine
            'sweeps': {
                'display_text': 'Sweeps',
                'widget': sweeps_sb,
            },
            'label': {
                'display_text': 'Label',
                'widget': QLineEdit('[t, 1, 0, 2]'),
            },
            'frequencies': {
                'display_text': 'Frequencies',
                'widget': QLineEdit('[2.864e9, 2.872e9, 30]'),
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
            'sideband': {
                'display_text': 'Sideband',
                'widget': SpinBox(
                    value=12e6,
                    suffix='Hz',
                    siPrefix=True,
                    dec=True,
                    bounds=(0, 30e6),
                ),
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
            'fourier_filter': {
                'display_text': 'Fourier Filter',
                'widget': fourier_filter_sb,
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
            'dataset': {
                'display_text': 'Data Set',
                'widget': QLineEdit('wI1I2')
            },
            'Misc': {
                'display_text': 'Misc',
                'widget': QLineEdit("{'DEBUG':False}"),
            },
        }


        super().__init__(
            params_config,
            experiments.wI1I2,
            'wI1I2Spyrelet',
            'main',
            title='Widefield ODMR')
class wI1I2PlotWidget(FlexLinePlotWidget):
    
    # def data_processing_func(self, sink):
    #     frequencies=sink.output['frequencies']
    #     n_freqs=len(frequencies)
    #     for ND in range(sink.output['number_ND']):
    #         sink.datasets[f"I1I2_{ND}"]=[]
    #     for sweep in range(sink.output['current_sweep']+1):
    #         for ND in range(sink.output['number_ND']):
    #             I1I2=np.empty(n_freqs)
    #             I1I2[:]=np.nan
    #             sink.datasets[f"I1I2_{ND}"].append(np.stack([frequencies, I1I2]))
    #             for j in range(n_freqs):
    #                 I1=sink.datasets[f"I1_{ND}"][sweep][1][j]
    #                 I2=sink.datasets[f"I2_{ND}"][sweep][1][j]
    #                 bg=sink.datasets[f"background_{ND}"][sweep][1][j]
    #                 sink.datasets[f"I1I2_{ND}"][-1][1][j]=2*(I2-I1)/(I2+I1) if (I2+I1) != 0 else np.nan

    def data_processing_func(self, sink):
        frequencies=sink.output['frequencies']
        n_freqs=len(frequencies)
        sideband = sink.params['sideband']
        for ND in range(sink.output['number_ND']):
            I1I2_sweeps = []
            I1I2_bg_free_sweeps = []
            I1_norm = []
            I2_norm = []
            for s,_ in enumerate(sink.datasets[f"I1_{ND}"]):
                I1=sink.datasets[f"I1_{ND}"][s][1]
                I2=sink.datasets[f"I2_{ND}"][s][1]
                bg=sink.datasets[f"background_{ND}"][s][1]
                pseudo_bg = (I1+I2)/2
                I1I2_sweeps.append(np.stack([frequencies, (I2-I1)/bg if bg.any() else np.full_like(I1, np.nan)]))
                I1I2_bg_free_sweeps.append(np.stack([frequencies, (I2-I1)/pseudo_bg]))
                I1_norm.append(np.stack([np.array(frequencies)-sideband, I1/bg if bg.any() else I1/pseudo_bg]))
                I2_norm.append(np.stack([np.array(frequencies)+sideband, I2/bg if bg.any() else I2/pseudo_bg]))
            sink.datasets[f"I1I2_{ND}"] = I1I2_sweeps
            sink.datasets[f"I1I2_bg_free_{ND}"] = I1I2_bg_free_sweeps
            sink.datasets[f"I1_norm_{ND}"] = I1_norm
            sink.datasets[f"I2_norm_{ND}"] = I2_norm


                    
        return
    def __init__(self):
        super().__init__(data_processing_func=self.data_processing_func)
        self.add_plot('signal_0', series='signal_0', scan_i='', scan_j='', processing='Average', hidden=True)
        self.add_plot('background_0', series='background_0', scan_i='', scan_j='', processing='Average', hidden=True)
        self.add_plot('I1I2_0', series='I1I2_0', scan_i='', scan_j='', processing='Average')
        self.add_plot('I1I2_bg_free_0', series='I1I2_bg_free_0', scan_i='', scan_j='', processing='Average', hidden=True)
        self.add_plot('I1_norm_0', series='I1_norm_0', scan_i='', scan_j='', processing='Average', hidden=True)
        self.add_plot('I2_norm_0', series='I2_norm_0', scan_i='', scan_j='', processing='Average', hidden=True)

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('wI1I2')

