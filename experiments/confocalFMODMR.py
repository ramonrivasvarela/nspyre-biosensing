'''
Confocal ODMR experiment - FM modulation by SG 394.
Written by: David Ovetsky, 8/12/2025
'''


#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import time
import datetime as Dt
import numpy as np
import rpyc.utils.classic

import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader
from experiments.spatialfb import SpatialFeedback
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)


class ConfocalFMODMR():

    """
    We run two windows: one with our MW on and the other with the MW off.
    We read the start of these 50us windows, and we do this 10,000 times. So,
    we have a time per point of 1s.
    We set a timeout for the general sample clock, 
    we can repeat x sweeps every y minutes per z repetitions.
    We sweep our microwave window over frequencies, generally 30 steps.
    Note: probe_time is the laser_on_per_window,
    rf_amplitude is the signal generator's power,
    clockpulse_duration sets the width of the pulse that clocks eery 50ns.
        set it to 10ns or so.
    """
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
        _logger.info('Created ConfocalFMODMR instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed ConfocalFMODMR instance.')

    def confocal_fmodmr(
        self,
        runs: int = 10,
        sweeps: int = 100,
        frequencies: str ="( 2.82e9, 2.92e9, 30)",
        rf_amplitude: float = -20, 
        laser_lag: float = 80e-9,
        cooldown_time: float = 100e-3,
        probe_time: float = 50e-6,
        clock_duration: float = 10e-9,
        timeout: int = 300,
        feedback: bool = False,
        dozfb: bool = True,
        sweeps_til_fb: int = 10,
        xyz_step: float = 60e-9,
        count_step_shrink: int = 2,
        starting_point: str = "current_position (ignore input)",
        dataset: str = "fmodmr"
    ):
        
        ## Set up key data structures
        INIT_PARAMS = [ runs, frequencies, rf_amplitude, laser_lag, cooldown_time,
                        probe_time, clock_duration, timeout]
        signal=StreamingList()
        background=StreamingList()

        ## Connect tof the instrument server, data server.
        with InstrumentManager() as mgr, DataSource(dataset) as datasource:
            # Initialize the experiment parameters
            self.initialize(mgr, *INIT_PARAMS) # prepares self.seq, among other things
            n_freq = len(self.frequencies)


            ###########################
            #### EXPERIMENTAL LOOP ####
            ###########################
            for sweep in range(sweeps):

                #### Acquire
                mgr.sg.set_frequency(self.frequencies[i])
                mgr.DAQcontrol.start_counter()      
                mgr.Pulser.stream_sequence(self.seq, 1) # number of runs accounted for in construction of the sequence.
                data = np.array(mgr.DAQcontrol.read_to_data_array( timeout = self.timeout)) # Collect ODMR point
                mgr.Pulser.set_state_off()
                #### Format
                sig_sweep, bg_sweep = self.format_data(data, self.ODMR_label, n_freq)
                sig_sweep = np.divide(sig_sweep, (probe_time * runs)) # cts/s
                bg_sweep = np.divide(bg_sweep, (probe_time * runs)) # cts/s
                signal.append(np.stack([self.frequencies, sig_sweep]))
                signal.updated_item(-1) # notify the streaminglist that this entry has updated so it will be pushed to the data server
                background.append(np.stack([self.frequencies, bg_sweep]))
                background.updated_item(-1)
                #### Send
                if self.VERBOSE: print(signal[-1][1], background[-1][1])
                datasource.push({
                    'params':{
                        'runs': runs,
                        'sweeps': sweeps,
                        'frequencies': frequencies,
                        'rf_amplitude': rf_amplitude,
                        'laser_lag': laser_lag,
                        'cooldown_time': cooldown_time,
                        'probe_time': probe_time,
                        'clock_duration': clock_duration,
                        'timeout': timeout,
                        'feedback': feedback,
                        'dozfb': dozfb,
                        'sweeps_til_fb': sweeps_til_fb,
                        'xyz_step': xyz_step,
                        'count_step_shrink': count_step_shrink,
                        'starting_point': starting_point,
                        'dataset': dataset

                    },
                    'x_label': 'Frequency (Hz)',
                    'y_label': 'Fluorescence',
                    'datasets': {
                        'signal': signal,       
                        'background': background,
                    }
                })
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr)
                    return
                time.sleep(cooldown_time) # cooldown time between sweeps
            #### Feedback
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                self.run_feedback(mgr, starting_point, dozfb, xyz_step, count_step_shrink) 


    #### INITIALIZATION METHODS

    def initialize(self, mgr, runs, frequencies, rf_amplitude, laser_lag, cooldown_time,
                   probe_time, clock_duration, timeout ):
        
        ## Prepare spyrelet parameters
        self.VERBOSE = True # Add as param, make default False once done debugging

        self.timeout=timeout #time to wait for clock before raising an error
        eval_frequency=eval(frequencies)
        self.frequencies = np.linspace(eval_frequency[0], eval_frequency[1], eval_frequency[2], endpoint=True)
        self.freq_range = (self.frequencies[-1] - self.frequencies[0])/2
        if self.freq_range > 32e6:
            print('Error, frequency ranges larger than +/- 32 MHz are not supported by FM modulation.')
            '''
            Here's an implementation:

            frequency = np.linspace(2.83e9, 2.9e9, 30)
            ## parse apart frequencies, prepare pulse seqeunce
            n_freq = len(frequency)
            freq_range = (frequency[-1] - frequency[0])
            n_fc = int(freq_range // 64e6 + 1) # number of carrier frequencies
            # Divide frequency into n_fc segments:
            n_freq_subdivided = n_freq / n_fc
            freq_arr = [[] for _ in range(n_fc)]
            print(n_fc, n_freq_subdivided)
            for i,f in enumerate(frequency):
                freq_arr[int(i // n_freq_subdivided)].append(f)
            carrier_freqs = [int(np.mean(freq)) for freq in freq_arr]
            freq_sb_arr = [int(np.abs(freq[-1]-freq[0])/2) for freq in freq_arr]
            mod_arr = [np.divide(np.subtract(freq,carrier_freq),sb) for freq,carrier_freq,sb in zip(freq_arr,carrier_freqs,freq_sb_arr)]    
            '''
            print('Variation of carrier frequency not yet implemented. Triggering finalization.')
            self.finalize(mgr)

        self.carrier_freq = (self.frequencies[-1] + self.frequencies[0])/2
        mod_array = (self.frequencies-self.carrier_freq)/self.freq_range # array for voltage mod values for ps
        


        ## Prepare timing variables
        self.ns_probe_time = int(round(probe_time*1e9)) #laser time per window
        self.ns_laser_lag = int(round(laser_lag*1e9))
        self.ns_clock_duration = int(round(clock_duration*1e9)) #width of our clock pulse.
        self.cooldown_time = cooldown_time        
        
        ## Prepare sequence
        ## Doing it this way will make it easier to (a) add cooldown time, (b) randomized orders
        self.ODMR_label = []
        for i in range(len(self.frequencies)):
            self.ODMR_label+= ([i+1, 0]* runs)
        if self.VERBOSE: print(f'preparing FMODMR sequence: {self.ODMR_label}')
        seq_dict = self.setup_FM_ODMR(self.ns_laser_lag, self.ns_probe_time, self.ns_clock_duration, self.ODMR_label, mod_array)
        self.seq = mgr.Pulse.make_seq(**seq_dict)
        if self.VERBOSE:
            import pickle, os
            print(f'saving sequence to seq.pkl in {os.getcwd()}')
            pickle.dump(self.seq, open('seq.pkl', 'wb'))

        ## Prepare Sig Gen
        mgr.sg.set_rf_amplitude(rf_amplitude) 
        mgr.sg.mod_function = 'external'
        mgr.sg.mod_toggle = True
        mgr.sg.set_mod_type('FM')
        mgr.sg.set_FM_mod_dev(self.freq_range)
        mgr.sg.rf_toggle = True


        ## Prepare DAQ counter
        if cooldown_time != 0:
            sample_rate = max(2/probe_time, 2/cooldown_time)
        else:
            sample_rate = 2/probe_time
        mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.prepare_counting(sample_rate, runs * len(self.ODMR_label)) # +1 to account for signal being a difference of counts

        return
    
    def setup_FM_ODMR(self, ns_laser_lag, ns_probe_time, ns_clock_duration, label, mod_arr):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        Note that the label should handle multiple runs.
        '''

        if self.VERBOSE: 
            print('\n using sequence without wait time')
            print('self.read_time:', ns_probe_time)
            print('self.clock_time:',  ns_clock_duration)       
            print('self.laser_lag:', ns_laser_lag) 

        #### LASER LAG
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        switch = [(ns_laser_lag, 1)]

        mwQ = [(ns_laser_lag, 0.0)]


        #### REPEATING SINGLE PULSE SEQUENCE
        pulse_laser = [(ns_probe_time, 1)]
        pulse_clock = [(ns_clock_duration,1),(ns_probe_time-ns_clock_duration,0)]
        #### VARIABLE REPEATING SINGLE PULSE SEQUENCE
        sig_switch = [(ns_probe_time, 0)]
        bg_switch = [(ns_probe_time, 1)]

        pulse_mwQ = [(ns_probe_time, 0)] # Dummy definition, in case we start with a bg

        #### CONSTRUCT SEQUENCE
        for pulse in label:
            if pulse > 0:
                pulse_mwQ = [(ns_probe_time, float(mod_arr[pulse-1]))]
                switch += sig_switch
            elif pulse == 0:
                switch += bg_switch
            laser += pulse_laser
            clock += pulse_clock
            mwQ += pulse_mwQ

        #### Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        switch += [(ns_clock_duration, 1)]
        mwQ += [(ns_clock_duration, 0.0)] 
        
        #### FINALIZE
        if self.VERBOSE:
            print('Finished setting up pulse sequence')

        seq_dict = {'clock': clock,'laser': laser, 
                    'switch': switch, 'Q': mwQ}
        return seq_dict
        
    #### EXPERIMENTAL METHODS

    def run_feedback(self,mgr, 
                    starting_point:str='current_position (ignore input)',
                    dozfb:bool=False, 
                    xyz_step:float=60e-9, 
                    count_step_shrink:int=2,
                    #current_position=...
                    ):
                
        feed_params = {
            'starting_point': str(starting_point),
            # 'position': position,
            'do_z': dozfb,
            'xyz_step': xyz_step,
            'shrink_every_x_iter': count_step_shrink,
        }
        ## we make sure the laser is turned on.
        mgr.Pulser.set_state([7],0.0,0.0)
        
        #Call feedback spyrelet
        self.SpatialFB = SpatialFeedback(self.queue_to_exp, self.queue_from_exp)
        self.SpatialFB.spatial_feedback(**feed_params)


        ##space_data is the last line of data from spatialfeedbackxyz
        
        self.x_initial = mgr.DAQcontrol.position['x']
        self.y_initial = mgr.DAQcontrol.position['y']
        print('x:', self.x_initial)
        print('y:', self.y_initial)
        if dozfb:
            self.z_initial = mgr.DAQcontrol.position['z']
            print('z:', self.z_initial)
            return self.x_initial, self.y_initial, self.z_initial
        print(self.x_initial)
        
        return self.x_initial, self.y_initial
        

    ## ODMR spyrelets reads point by point, so for each read point: start task, start pulse streaming, 
    ## and read samples to buffer, then stop the task and reset the pulse streaming 
    def acquire(self, mgr, seq):
        '''
        Acquires a single ODMR point, returns the RAW data
        '''
        
        ## Start, Stream, Read
        mgr.DAQcontrol.start_counter()             
        mgr.Pulser.stream_sequence(seq, 1, AM = self.AM, SWITCH = self.SWITCH) # number of runs accounted for in construction of the sequence.
        data = np.array(mgr.DAQcontrol.read_to_data_array(timeout = self.timeout)) # Collect ODMR point
        mgr.Pulser.set_state_off()

        return data  
    
    def format_data(self, data, label, n_freq):
        '''
        Format data according to the label provided.
        Data formatting procedure is ACCUMULATION: return the sum of counts in each label category, separately.
        Keeping also bg signal separate for each frequency. Assumed structure of label is:
        [..., n, 0, n, 0, n+1, 0, ...]
        '''
        delta_buffer = data[1:] - data[0:-1]
        sigs = np.zeros(n_freq)#dtype = int?
        bgs = np.zeros(n_freq)
        if self.VERBOSE:
            print('data: ', data)
            print('compare lengths: ', len(delta_buffer), len(label))

        for i,data_point in enumerate(delta_buffer):
            lbl_idx = label[i]
            if lbl_idx > 0 : sigs[lbl_idx-1] += data_point
            else: bgs[label[i-1]-1] += data_point

        if self.VERBOSE:
            print('delta_buffer:', delta_buffer)
            print('sigs:', sigs, 'bgs:', bgs)
        return sigs, bgs

    #### FINALIZATION METHODS

    def finalize(self, mgr):
        
        ## stop and close all tasks
        mgr.Pulser.set_state_off()
        mgr.DAQcontrol.finalize_counter()
        
        ## turns off sg
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)

        print("FINALIZE")           
        return