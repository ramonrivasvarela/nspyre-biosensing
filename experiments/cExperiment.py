'''
A Python module for defining the base structure of a confocal experiment, as well as common methods
for confocal experiments. This module is intended to be subclassed for specific experiments and does
not do anything on its own.
'''
## GENERAL IMPORTS ##########################################################################
import numpy as np

class cExperiment():

    ## INITIALIZATION ##########################################################################
    def init_routine(self, frequencies, runs):
        '''
        Initialize the routine for the experiment. Assumes frequencies and runs are useful. Override if necessary with fewer parameters.
        Args:
            frequencies: The frequencies (Hz) to sweep over for the experiment.
            runs: The number of times to repeat the experiment at each frequency.
        '''
        eval_freqs = eval(frequencies)
        self.frequencies = np.linspace(eval_freqs[0], eval_freqs[1], eval_freqs[2])
        self.runs = runs
        self.n_points = ...
        
        sampling_rate = int(2 / self.probe_time)  # Assuming probe_time is defined in seconds
        
        raise NotImplementedError("init_routine must be implemented to represent experiment routine")
        return sampling_rate

    def init_timings(self, probe_time, laser_lag, clock_duration, cooldown_time):
        '''
        Assumes all timings useful. Override if necessary with fewer timings. 
        Args:
            probe_time: The time (s) of illumination (and uw drive) for data collection
            laser_lag: The time (s) to wait after turning on the laser before probing.
            clock_duration: The duration (s) of the clock signal for the experiment.
            cooldown_time: The time (s) to wait after probing before starting the next iteration.
              (laser off, uw off)
        '''
        self.ns_probe_time = int(probe_time * 1e9)
        self.ns_laser_lag = int(laser_lag * 1e9)
        self.ns_clock_duration = int(clock_duration * 1e9)
        self.ns_cooldown_time = int(cooldown_time * 1e9)
        raise NotImplementedError("init_timings must be implemented to represent experiment timings")

    def init_DAQ(self, mgr, timeout, sampling_rate):
        '''
        Initialize the DAQ for the experiment. Assumes sampling rate to be int(2/self.probe_time)
        '''
        mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.prepare_counting(sampling_rate=sampling_rate, n_points=self.n_points, bounded_sample=True)
        self.timeout = timeout

    def init_xyz(self, mgr):
        '''
        Initialize the XYZ positioning, XYZ control, especially for spatial feedback.
        '''
        self.current_position = mgr.DAQcontrol.get_position()
        self.init_position = self.current_position # dictionary with keys 'x', 'y', 'z'
        raise NotImplementedError("init_xyz must be implemented to represent experiment XYZ positioning")

    def init_seq(mgr):
        '''
        Initialize the pulse sequence for the experiment. Override if necessary.
        '''
        #self.sequence = self.mgr.Pulser.[insert sequence creation method here]
        raise NotImplementedError("init_seq must be implemented to represent experiment pulse sequence")

    def init_sg(mgr):
        '''
        Initialize the signal generator for the experiment. Override if necessary.
        '''
        raise NotImplementedError("init_sg must be implemented to represent experiment signal generator")

    def initialize(self, mgr, timeout, frequencies, probe_time, laser_lag, clock_duration, cooldown_time, runs, verbose):
        '''
        A generic confocal experiment initialization function. Assumes usage of DLnsec, Pulser, and DAQcontrol.


        Args:

        '''
        self.verbose = verbose
        sampling_rate = self.init_routine(frequencies, runs) # Defines self.frequencies, self.runs, self.n_points, and returns the sampling rate for the DAQ
        self.init_timings(probe_time, laser_lag, clock_duration, cooldown_time) # Defines self.ns_probe_time, self.ns_laser_lag, self.ns_clock_duration, self.ns_cooldown_time
        self.init_DAQ(mgr, timeout, sampling_rate) # Defines self.timeout, Initializes the DAQ for the experiment, 
        self.init_xyz(mgr) # Defines self.current_position, self.init_position, Initializes the XYZ positioning for the experiment
        self.init_seq(mgr) # Defines self.sequence
        raise NotImplementedError("initialize must be implemented to represent experiment initialization")

    ## FINALIZATION ##########################################################################

    def finalize(self, mgr):
        mgr.DAQcontrol.finalize_counter() # Finalize DAQ
        mgr.Pulser.set_state_off() # Finalize Pulser
        # Finalize position
        # Finalize SG
        raise NotImplementedError("finalize must be implemented to represent experiment finalization")

    ## MAIN EXPERIMENT METHODS ##########################################################################
