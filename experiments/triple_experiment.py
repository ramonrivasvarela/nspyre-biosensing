#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
from experiments.confocalODMR import ConfocalODMR
from experiments.i1i2 import I1I2
from experiments.temptime import TemperatureVsTime

#### GENERAL IMPORTS
import time
import numpy as np
import rpyc.utils.classic
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)



class TripleExperiment:
    def __init__(self, queue_to_exp=None, queue_from_exp=None):
        """
        Args:
            queue_to_exp: A multiprocessing Queue object used to send messages
                to the experiment from the GUI.
            queue_from_exp: A multiprocessing Queue object used to send messages
                to the GUI from the experiment.
        """
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp

    def __enter__(self):
        """Perform experiment setup."""
        # config logging messages
        # if running a method from the GUI, it will be run in a new process
        # this logging call is necessary in order to separate log messages
        # originating in the GUI from those in the new experiment subprocess
        nspyre_init_logger(
            log_level=logging.INFO,
            log_path=_HERE / '../logs',
            log_path_level=logging.DEBUG,
            prefix=Path(__file__).stem,
            file_size=10_000_000,
        )
        _logger.info('Created TripleExperiment instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed TripleExperiment instance.')

    def main(self, rf_amplitude=-13, odmr_sweeps=10, i1i2_sweeps=10, probe_time=100e-6, sweeps_till_fb=12, time_per_point=1, odmr_frequency_range="(2.82e9, 2.92e9, 30)", i1i2_frequency_range="(2.85e9, 2.89e9, 20)", slope_range="(2.868e9, 2.871e9)", i1i2_continuous_tracking=False, searchXYZ="(0.5, 0.5, 0.5)", max_search="(1, 1, 1)", min_search="(0.1, 0.1, 0.1)", 
    scan_distance="(0.03, 0.03, 0.05)", changing_search=False, search_PID="(0.5,0.01,0)", search_integral_history=5, z_cycle=1, odmr_dataset='odmr', i1i2_dataset='i1i2', temptime_dataset='temptime'):
        self.initialize()
        self.ODMRExp = ConfocalODMR(self.queue_to_exp, self.queue_from_exp)
        fit_results=self.ODMRExp.confocal_odmr(rf_amplitude=rf_amplitude, sweeps=odmr_sweeps, runs=int(time_per_point/probe_time), frequencies=odmr_frequency_range, sweeps_til_fb=sweeps_till_fb, dataset=odmr_dataset)
        parameters=fit_results['parameters']
        fwhm_hz=(abs(parameters['x2']-parameters['x1'])+parameters['w1']+parameters['w2'])/2
        sideband_frequency_values=['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                        '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                        '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                        '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                        '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                        '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                        '5.952380952', '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291',
                        '5.2631579', '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222',
                        '2.84090909', '2.5']
        fwhm_mhz=fwhm_hz*1e-6
        superior_sideband = min([float(val) for val in sideband_frequency_values if float(val) > fwhm_mhz], default=None)
        self.I1I2Exp = I1I2(self.queue_to_exp, self.queue_from_exp)
        quasilinear_calibration_slope, quasilinear_zero_field_splitting=self.I1I2Exp.i1i2(rf_amplitude=rf_amplitude,sweeps=i1i2_sweeps, frequencies=i1i2_frequency_range, slope_range=slope_range, continuous_tracking=i1i2_continuous_tracking, sideband_frequency=superior_sideband, searchXYZ=searchXYZ, max_search=max_search, min_search=min_search, scan_distance=scan_distance, changing_search=changing_search, search_PID=search_PID, search_integral_history=search_integral_history, dataset=i1i2_dataset)
        self.TvTExp=TemperatureVsTime(self.queue_to_exp, self.queue_from_exp)
        self.TvTExp.temptime(time_per_scan=time_per_point, rf_amplitude=rf_amplitude, quasilinear_slope=quasilinear_calibration_slope, odmr_frequency=quasilinear_zero_field_splitting, mwPulseTime=probe_time, sb_MHz_2fq=superior_sideband, searchXYZ=searchXYZ, max_search=max_search, min_search=min_search, scan_distance=scan_distance, changing_search=changing_search, search_PID=search_PID, search_integral_history=search_integral_history, z_cycle=z_cycle, dataset=temptime_dataset)


        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
            return self.finalize()
        return self.finalize()
        
    def initialize(self):
        return
    
    def finalize(self):
        return