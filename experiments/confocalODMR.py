
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


class ConfocalODMR():

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
        _logger.info('Created ConfocalODMR instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed ConfocalODMR instance.')

    def confocal_odmr(
        self,
        runs: int = 1000,
        sweeps: int = 100,
        mode: str = "QAM",
        frequency: str ="( 2.82e9, 2.92e9, 30)",
        rf_amplitude: float = -20, 
        laser_lag: float = 80e-9,
        cooldown_time: float = 5e-6,
        probe_time: float = 50e-6,
        clock_duration: float = 10e-9,
        timeout: int = 300,
        use_switch: bool = False,
        # data_download: bool = False,
        feedback: bool = False,
        dozfb: bool = True,
        sweeps_til_fb: int = 10,
        # initial_position: dict = {'x': 0.0, 'y': 0.0, 'z': 0.0},
        xyz_step: float = 60e-9,
        count_step_shrink: int = 2,
        starting_point: str = "current_position (ignore input)",
        dataset: str = "odmr"
    ):
        
        ## Set up experiment parameters
        INIT_PARAMS = [ runs, mode, frequency, rf_amplitude, laser_lag, cooldown_time,
                        probe_time, clock_duration, use_switch, timeout]
        n_freq = len(self.frequencies)

        signal=StreamingList()
        background=StreamingList()

        ## Connect to the instrument server, data server.
        with InstrumentManager() as mgr, DataSource(dataset) as datasource:
            # Initialize the experiment parameters
            self.initialize(mgr, *INIT_PARAMS) # prepares self.seq, among other things

            ###########################
            #### EXPERIMENTAL LOOP ####
            ###########################
            for sweep in range(sweeps):
                #### Prepare Sweep Data Structure
                # photon counts corresponding to each frequency
                # initialize to NaN
                sig_counts = np.empty(n_freq)
                sig_counts[:] = np.nan
                signal.append(np.stack([frequency, sig_counts]))
                bg_counts = np.empty(n_freq)
                bg_counts[:] = np.nan
                background.append(np.stack([frequency, bg_counts]))

                for i in range(n_freq):
                    #### Acquire
                    mgr.sg.set_frequency(self.frequencies[i])
                    mgr.DAQCounter.start()             
                    mgr.Pulser.stream_sequence(self.seq, 1) # number of runs accounted for in construction of the sequence.
                    data = mgr.DAQCounter.read_to_data(timeout = self.timeout) # Collect ODMR point
                    mgr.Pulser.set_state_off()
                    #### Format
                    sig_point, bg_point = self.format_data(data, self.ODMR_label)
                    signal[-1][1][i] = sig_point
                    signal.updated_item(-1) # notify the streaminglist that this entry has updated so it will be pushed to the data server
                    background[-1][1][i] = bg_point
                    background.updated_item(-1)
                    #### Send
                    datasource.push({
                        'params':{
                            'runs': runs,
                            'sweeps': sweeps,
                            'mode': mode,
                            'frequency': frequency,
                            'rf_amplitude': rf_amplitude,
                            'laser_lag': laser_lag,
                            'cooldown_time': cooldown_time,
                            'probe_time': probe_time,
                            'clock_duration': clock_duration,
                            'timeout': timeout,
                            'use_switch': use_switch,
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
                #### Feedback
                if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    self.run_feedback(starting_point, dozfb, xyz_step, count_step_shrink) 


    #### INITIALIZATION METHODS

    def initialize(self, mgr, runs, mode, frequency, rf_amplitude, laser_lag, cooldown_time,
                   probe_time, clock_duration, use_switch, timeout ):
        
        ## Prepare spyrelet parameters
        self.VERBOSE = True # Add as param, make default False once done debugging

        self.timeout=timeout #time to wait for clock before raising an error
        eval_frequency=eval(frequency)
        self.frequencies = np.linspace(eval_frequency[0], eval_frequency[1], eval_frequency[2])

        ## Prepare timing variables
        self.ns_probe_time = int(round(probe_time*1e9)) #laser time per window
        self.ns_laser_lag = int(round(laser_lag*1e9))
        self.ns_clock_duration = int(round(clock_duration*1e9)) #width of our clock pulse.
        self.ns_cooldown_time = int(round(cooldown_time*1e9)) #time to wait after laser pulse
        
        self.ns_pulsewait_time = 0 #time to wait after each run. Not yet implemented as a parameter.
        
        ## Prepare sequence
        if self.ns_cooldown_time == 0 and self.ns_pulsewait_time == 0:
            self.ODMR_label = [1, 0] # sig, bg
            if self.VERBOSE: print('ODMR, no wait time')
            seq_dict = self.setup_no_wait(self.ns_laser_lag, self.ns_probe_time, self.ns_clock_duration, runs, mode, use_switch)
        else:
            self.ODMR_label = [1, 'x', 0, 'x'] # sig, discard, bg, discard
            if self.VERBOSE: print('ODMR, with wait time')
            seq_dict = self.setup_ODMR_wait(self.ns_laser_lag, self.ns_probe_time, self.ns_clock_duration, self.ns_cooldown_time, runs, mode, use_switch)

        self.seq = mgr.Pulse.make_seq(**seq_dict)
        if self.VERBOSE:
            import pickle, os
            print(f'saving sequence to seq.pkl in {os.getcwd()}')
            pickle.dump(self.seq, open('seq.pkl', 'wb'))

        ## Prepare Sig Gen

        mgr.sg.set_rf_amplitude(rf_amplitude) 
        mgr.sg.mod_function = 'external'
        mgr.sg.mod_toggle = True
        if mode == 'QAM':
            mgr.sg.set_mod_type('QAM')
        elif mode == 'AM' or mode == 'NoMod':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_AM_mod_depth(100)
        mgr.sg.rf_toggle = True


        ## Prepare DAQ counter

        if cooldown_time != 0:
            sample_rate = max(2/probe_time, 2/cooldown_time)
        else:
            sample_rate = 2/probe_time
        mgr.DAQCounter.set_sampling_rate(sample_rate)  # Automatically determined by 2/probe_time
        mgr.DAQCounter.create_buffer(runs*len(self.ODMR_label)+1) # +1 to account for signal being a difference of counts
        mgr.DAQCounter.initialize()

        return
    
    def setup_no_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        self.IQ0 = [-0.0025,-0.0025]
        self.IQpx = [0.4461,-.0025]
        
        if self.VERBOSE: 
            print('\n using sequence without wait time')
            print('self.read_time:', ns_probe_time)
            print('self.clock_time:',  ns_clock_duration)       
            print('self.laser_lag:', ns_laser_lag) 

        #### LASER LAG
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        if mode == 'QAM': 
            mwQ = [(ns_laser_lag, self.IQ0[0])]
            mwI = [(ns_laser_lag, self.IQ0[1])]
        elif mode == 'AM':
            mwQ = [(ns_laser_lag, -1)]
        elif mode == 'NoMod':
            if not switch:
                raise ValueError('NoMod mode requires switch to be True')

        if switch:
            if self.VERBOSE: print('using switch')
            switch = [(ns_laser_lag, 1)]


        #### (mwOnOff repeating sequence defn)
        mwOnOff_laser = [(ns_probe_time, 1), (ns_probe_time, 1)]
        if mode == 'QAM':
            mwOnOff_mwQ = [(ns_probe_time, self.IQpx[0]), (ns_probe_time, self.IQ0[0])]
            mwOnOff_mwI = [(ns_probe_time, self.IQpx[1]), (ns_probe_time, self.IQ0[1])]
        elif mode == 'AM':
            mwOnOff_mwQ = [(ns_probe_time, 0), (ns_probe_time, -1)]
        elif mode == 'NoMod':
            pass
        mwOnOff_clock = [(ns_clock_duration,1),(ns_probe_time-ns_clock_duration,0),(ns_clock_duration,1),(ns_probe_time-ns_clock_duration,0)]
        if switch:
            mwOnOff_switch = [(ns_probe_time, 0), (ns_probe_time, 1)]

        #### REPEATING MICROWAVE ON/OFF SEQUENCE
        for i in range(runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwQ += mwOnOff_mwQ
            if mode == 'QAM':
                mwI += mwOnOff_mwI
            if switch:
                switch += mwOnOff_switch
        
        #### Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        if mode == 'QAM':
            mwQ += [(ns_clock_duration, self.IQ0[0])]
            mwI += [(ns_clock_duration, self.IQ0[1])]
        elif mode == 'AM':
            mwQ += [(ns_clock_duration, -1)] 
        elif mode == 'NoMod':
            pass
        if switch:
            switch += [(ns_clock_duration, 1)]
        
        #### FINALIZE
        if self.VERBOSE:
            print('Finished setting up pulse sequence')

        seq_dict = {'clock': clock,'laser': laser}
        if mode == 'QAM':
            seq_dict['Q'] = mwQ
            seq_dict['I'] = mwI
        elif mode == 'AM':
            seq_dict['Q'] = mwQ
        elif mode == 'NoMod':
            pass

        if switch:
            seq_dict['switch'] = switch

        return seq_dict
        
    ## still need to change this to new method
    def setup_ODMR_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, ns_cooldown_time, ns_pulsewait_time ,runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        
        self.IQ0 = [-0.0025,-0.0025]
        self.IQpx = [0.4461,-.0025]
        
        if self.VERBOSE: 
            print('\n using sequence with wait time')
            print('self.read_time:', ns_probe_time)
            print('self.clock_time:',  ns_clock_duration)     
            print('self.cooldown_time:', ns_cooldown_time)  
            print('self.laser_lag:', ns_laser_lag) 
            print('self.pulsewait_time:', ns_pulsewait_time)

        #### LASER LAG
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        if mode == 'QAM': 
            mwQ = [(ns_laser_lag, self.IQ0[0])]
            mwI = [(ns_laser_lag, self.IQ0[1])]
        elif mode == 'AM':
            mwQ = [(ns_laser_lag, -1)]
        elif mode == 'NoMod':
            if not switch:
                raise ValueError('NoMod mode requires switch to be True')

        if switch:
            if self.VERBOSE: print('using switch')
            switch = [(ns_laser_lag, 1)]


        #### (mwOnOff repeating sequence defn)
        mwOnOff_laser = [(ns_probe_time, 1), (ns_cooldown_time,0),
                          (ns_probe_time, 1), (ns_cooldown_time,0), (ns_pulsewait_time, 0)]
        if mode == 'QAM':
            mwOnOff_mwQ = [(ns_probe_time, self.IQpx[0]), 
                            (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, self.IQ0[0])]
            mwOnOff_mwI = [(ns_probe_time, self.IQpx[1]), 
                           (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, self.IQ0[1])]
        elif mode == 'AM':
            mwOnOff_mwQ = [(ns_probe_time, 0), 
                            (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, -1)]
        elif mode == 'NoMod':
            pass
        mwOnOff_clock = [(ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1), (ns_cooldown_time + ns_pulsewait_time, 0)
                         (ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1), (ns_cooldown_time + ns_pulsewait_time, 0)]
        if switch:
            mwOnOff_switch = [(ns_probe_time, 0),
                               (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, 1)]

        #### REPEATING MICROWAVE ON/OFF SEQUENCE
        for i in range(runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwQ += mwOnOff_mwQ
            if mode == 'QAM':
                mwI += mwOnOff_mwI
            if switch:
                switch += mwOnOff_switch
        
        #### Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        if mode == 'QAM':
            mwQ += [(ns_clock_duration, self.IQ0[0])]
            mwI += [(ns_clock_duration, self.IQ0[1])]
        elif mode == 'AM':
            mwQ += [(ns_clock_duration, -1)] 
        elif mode == 'NoMod':
            pass
        if switch:
            switch += [(ns_clock_duration, 1)]
        
        #### FINALIZE
        if self.VERBOSE:
            print('Finished setting up pulse sequence')

        seq_dict = {'clock': clock,'laser': laser}
        if mode == 'QAM':
            seq_dict['Q'] = mwQ
            seq_dict['I'] = mwI
        elif mode == 'AM':
            seq_dict['Q'] = mwQ
        elif mode == 'NoMod':
            pass

        if switch:
            seq_dict['switch'] = switch

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
        
        self.x_initial = mgr.XYZcontrol.get_x()
        self.y_initial = mgr.XYZcontrol.get_y()
        print('x:', self.x_initial)
        print('y:', self.y_initial)
        if dozfb:
            self.z_initial = mgr.XYZcontrol.get_z()
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
        mgr.DAQCounter.start()             
        mgr.Pulser.stream_sequence(seq, 1) # number of runs accounted for in construction of the sequence.
        data = mgr.DAQCounter.read_to_data(timeout = self.timeout) # Collect ODMR point
        mgr.Pulser.set_state_off()

        return data  
    
    def format_data(self, data, label):
        '''
        Format data according to the label provided.
        Data formatting procedure is ACCUMULATION: return the sum of counts in each label category, separately.

        i.e.:
        for a pulse sequence labeled [1, 'x', 0, 'x'],
        we sum all counts in the '1' windows, and sum all counts in the '0' windows, and discard the 'x' windows.
        then we return both sums.
        '''
        delta_buffer = data[1:] - data[0:-1]
        for i,data_point in enumerate(delta_buffer):
            idx_sig = label.index(1)
            idx_bg = label.index(0)
            interval = len(label)
            sum_sig = np.sum(delta_buffer[idx_sig::interval]) # MW on
            sum_bg = np.sum(delta_buffer[idx_bg::interval]) # MW off
        if self.VERBOSE:
            print('delta_buffer:', delta_buffer)
            print('sum_sig:', sum_sig, 'sum_bg:', sum_bg)
        return sum_sig, sum_bg

    #### FINALIZATION METHODS

    def finalize(self, mgr):
        
        ## stop and close all tasks
        mgr.Pulser.set_state_off()
        mgr.DAQCounter.finalize()
        
        ## turns off sg
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)

        print("FINALIZE")           
        return