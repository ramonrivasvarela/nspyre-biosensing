#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import time
import numpy as np
import rpyc.utils.classic
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)



class ODMRCenter:
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
        # PID variables
        self.previous_error = 0
        self.integral = 0

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
        _logger.info('Created Experiment instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Experiment instance.')

    def main(self, runs, initial_odmr, odmr_span, sweep_time, PID, probe_time, clock_time, laser_pause, timeout_counter, dataset):
        kp, ki, kd=eval(PID)
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            counter=0
            odmr_freq=initial_odmr
            self.initialize(mgr, runs, odmr_span, sweep_time, probe_time, clock_time, laser_pause)
            while counter<timeout_counter:
                counter+=1
                mgr.sg.set_frequency(odmr_freq-odmr_span/2)
                mgr.DAQcontrol.start_counter()
                mgr.Pulser.stream_sequence(self.sequence_left, runs)
                mgr.sg.set_mod_toggle(True)
                left = rpyc.utils.classic.obtain(mgr.DAQcontrol.read_to_data_array())
                mgr.sg.set_mod_toggle(False)
                mgr.sg.set_frequency(odmr_freq+odmr_span/2)
                mgr.DAQcontrol.start_counter()
                mgr.sg.set_mod_toggle(True)
                mgr.Pulser.stream_sequence(self.sequence_right, runs)
                right = rpyc.utils.classic.obtain(mgr.DAQcontrol.read_to_data_array())

                
                mgr.sg.set_mod_toggle(False)
                left_background, left_signal = self.process_data(runs, int(sweep_time*1.1/probe_time), left, True)
                right_background, right_signal = self.process_data(runs, int(sweep_time*1.1/probe_time), right, False)
                left_contrast=(left_background-left_signal)/left_background
                right_contrast=(right_background-right_signal)/right_background
                print(f"Left contrast: {left_contrast}, Right contrast: {right_contrast}")
                
                # PID control to adjust ODMR frequency
                frequency_adjustment = self.pid_control(left_contrast, right_contrast, kp, ki, kd)
                odmr_freq += frequency_adjustment
                search = abs(frequency_adjustment)  # Update search value based on adjustment magnitude
                
                print(f"Frequency adjustment: {frequency_adjustment:.6f} Hz, New ODMR freq: {odmr_freq:.6f} Hz")
                
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return self.finalize(mgr)
            return self.finalize(mgr)

    def initialize(self, mgr, runs,odmr_span, sweep_time, probe_time, clock_time, laser_pause):
        n_points=int(sweep_time*1.1/probe_time)
        odmr_span=int(odmr_span/probe_time)*probe_time
        sg_span=(odmr_span/sweep_time)*(sweep_time+laser_pause)
        self.sequence_left=mgr.Pulser.odmr_center.create_sequence(mgr, clock_time, probe_time, laser_pause, n_points, left=True)

        self.sequence_right=mgr.Pulser.odmr_center_create_sequence(mgr, clock_time, probe_time, laser_pause, n_points, left=False)
        mgr.sg.continuous_sweep(sg_span, (sweep_time+laser_pause))
        mgr.DAQcontrol.create_counter()
        print("buffer size:", (2*n_points+2)*runs)
        mgr.DAQcontrol.prepare_counting(2/probe_time, (2*n_points+2)*runs-1)
        print(len(mgr.DAQcontrol.ctr_buffer))

        return
    
    def process_data(self, runs, n_points, data, left):
        # Reshape data to separate runs
        points_per_run = 2 * n_points + 2  # (n_points+1) background + n_points signal
        data_reshaped = data.reshape(runs, points_per_run)
        # Separate background and signal for each run
        background_raw = data_reshaped[:, :n_points+1]  # First n_points+1 are background
        signal_raw = data_reshaped[:, n_points+1:2*n_points+1]  # Next n_points are signal
        # else:
        #     # Separate background and signal for each run
        #     signal_raw = data_reshaped[:, :n_points+1]  # First n_points+1 are background
        #     background_raw = data_reshaped[:, n_points+1:2*n_points+2]  # Next n_points are signal
        
        # Apply buffer_to_data logic to each row and sum the differences
        background = np.average([np.sum(np.diff(row)) for row in background_raw])
        signal = np.average([np.sum(np.diff(row)) for row in signal_raw])
        return background, signal

    def finalize(self, mgr):
        # Reset PID variables
        self.previous_error = 0
        self.integral = 0
        mgr.DAQcontrol.finalize_counter()
        return
    
    def create_sequence(self, mgr, clock_time, probe_time, laser_pause, n_points, left):
        clock_time_ns=int(clock_time*1e9)
        probe_time_ns=int(probe_time*1e9)
        laser_pause_ns=int(laser_pause*1e9)
        seq = mgr.Pulser.create_sequence()
        clock_pulse = [(clock_time_ns,1),(probe_time_ns-clock_time_ns,0)] ##ensure clock_time in nanoseconds
        laser=[((n_points+1)*probe_time_ns,1)]
        clock = clock_pulse * (n_points+1)

        switch_on=[(probe_time_ns)]
        if left:
            laser=2*([(laser_pause_ns,0)] + laser)
            clock=2*([(laser_pause_ns,0)] + clock)
            switch=[(2*laser_pause_ns+probe_time_ns,1), (probe_time_ns,0)]
        else:
            laser=2*(  laser+ [(laser_pause_ns,0)])
            clock=2*(clock+[(laser_pause_ns,0)])
            switch=[(probe_time_ns+laser_pause_ns,1), (probe_time_ns,0), (laser_pause_ns,1)]
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        seq.setDigital(mgr.Pulser.channel_dict['laser'], laser)
        seq.setDigital(mgr.Pulser.channel_dict['switch'], switch)
        return seq
    
    def pid_control(self, left_contrast, right_contrast, kp, ki, kd):
        """
        PID controller to determine frequency adjustment based on contrast difference.
        Target is to make left_contrast == right_contrast.
        """
        error = left_contrast - right_contrast
        
        # Proportional term
        proportional = kp * error
        
        # Integral term
        self.integral += error
        integral_term = ki * self.integral
        
        # Derivative term
        derivative = kd * (error - self.previous_error)
        
        # PID output
        output = proportional + integral_term + derivative
        
        # Update previous error for next iteration
        self.previous_error = error
        
        return output
