
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
        sampling_rate: float = 50000,
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
        data_download: bool = False,
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
        INSTRUMENT_PARAMS = [ sampling_rate, runs,
                             sweeps, mode, frequency, rf_amplitude, laser_lag,
                             cooldown_time, probe_time, clock_duration, timeout,
                             sequence, data_download]

        sig_counts = StreamingList()
        bg_counts = StreamingList()

        ## Connect to the instrument server, data server.
        with InstrumentManager() as mgr, DataSource(dataset) as datasource:
            # Initialize the experiment parameters
            self.initialize(mgr, *INSTRUMENT_PARAMS)


            plots_data={}
            signal=StreamingList(np.array([np.array([f]), np.array([0])]) for f in self.frequency)
            background=StreamingList(np.array([np.array([f]), np.array([0])]) for f in self.frequency)
            n_freq=len(self.frequency)

       
            for sweep in range(sweeps):
                if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    self.run_feedback(starting_point, dozfb, xyz_step, count_step_shrink) 
                for i in range(n_freq):
                    mgr.sg.set_frequency(self.frequency[i])
                    self.t0 = time.time()                   
                    sg, bg = self.read_odmr(mgr, self.runs, self.buffers, self.index, self.t0)

   
                    datasource.push({
                        'params':{
                            'sampling_rate': sampling_rate,
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
                            # 'initial_position': initial_position,
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
                        self.finalize(mgr, device,  sampling_rate, PS_clk_channel, 
                data_download)
                        return


    
    def math_odmr(self, array):
        ## divide buffer to bright versus dark
        print("This is raw data array:")
        print(array)
        if self.sequence in ('odmr_heat_wait'):
            delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            sum1 = np.sum(delta_buffer[::4]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            sum2 = np.sum(delta_buffer[2::4]) # MW off, but collect bright.
            print('odmr_heat_wait delta_buffer:', delta_buffer)
            print('odmr_heat_wait sum1:', sum1, 'odmr_heat_wait sum2:', sum2)
            return [sum1, sum2]
        else:
            delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            print(len(delta_buffer))
            sum1 = np.sum(delta_buffer[:-1:2]) # MW on. Shivam: changed delta_buffer[:-1][::2] to delta_buffer[:-1:2] for readability
            sum2 = np.sum(delta_buffer[1::2]) # MW off
            
            print('odmr_no_wait delta_buffer:', delta_buffer)
            print('odmr_no_wait sum1:', sum1, 'odmr_no_wait sum2:', sum2)          
            #print('Time for streaming per point:', self.pulses.total_time/1e9)
            #print('Full experiment time:', self.pulses.total_time/1e9 * self.point_num)
            return [sum1, sum2]


    #### INITIALIZATION METHODS

    def initialize(self, mgr, sampling_rate, runs,
                   sweeps, mode, frequency, rf_amplitude, laser_lag, cooldown_time,
                   probe_time, clock_duration, use_switch, timeout, data_download,
                   ):
        
        ## Prepare spyrelet parameters
        self.VERBOSE = True # Add as param, make default False once done debugging

        ## Prepare routine parameters

        ## Prepare timing variables
        self.ns_probe_time = int(round(probe_time*1e9)) #laser time per window
        self.ns_laser_lag = int(round(laser_lag*1e9))
        self.ns_clock_duration = int(round(clock_duration*1e9)) #width of our clock pulse.
        self.ns_cooldown_time = int(round(cooldown_time*1e9)) #time to wait after laser pulse
        
        self.ns_pulsewait_time = 0 #time to wait after each run. Not yet implemented as a parameter.
        
        ## Prepare sequence
        if self.ns_cooldown_time == 0 and self.ns_pulsewait_time == 0:
            # self.ODMR_wait = False # Don't need?
            if self.VERBOSE: print('ODMR, no wait time')
            seq_dict = self.setup_no_wait(self.ns_laser_lag, self.ns_probe_time, self.ns_clock_duration, runs, mode, use_switch)
            seq = mgr.Pulse.make_seq(**seq_dict)
        else:
            # self.ODMR_wait = True # Don't need?
            if self.VERBOSE: print('ODMR, with wait time')

        ## Prepare Sig Gen

        ## Prepare DAQ counter







        # self.sequence = sequence #type of ODMR sequence from the list
        # eval_frequency=eval(frequency)
        # self.frequency = np.linspace(eval_frequency[0], eval_frequency[1], eval_frequency[2])
        # self.timeout=timeout #time to wait for clock before raising an error
        # self.runs = runs #number of reading windows to average for each point
        # self.channel = channel1 #reading channel
        # mgr.sg.set_rf_amplitude(rf_amplitude) ## set SG paramaters: running this spyrelet with IQ inputs
        # self.point_num = len(self.frequency)
        
        ## create parameters
        if self.sequence in ('odmr_heat_wait'):
            odmr_buffer_size = 4*self.runs + 1
            print('effective buffer_size:', odmr_buffer_size)
        else:
            odmr_buffer_size = 2*self.runs + 1 #odmr_buffer_size = 2*(math.floor(time_per_point/(2*probe_time)) + 1)
            print('effective buffer_size:', odmr_buffer_size)
        if odmr_buffer_size <2:
            raise ValueError('the buffer is too small. set runs to an integer > 0.')

        ## using array with contiguous memory region because NI uses C arrays under the hood
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(odmr_buffer_size, dtype=np.uint32))
        self.buffers = [ni_ctr_sample_buffer]
        
        ## Ideally, DAQ would sample at the PS clock ticking rate. 
        ## as of now, 02_16_2021, we do not understand the exact conditions required.
        if sampling_rate < 1/probe_time:
            print('sampling rate must be equal or larger than 1/probe_time')
            return

        ## define class parameters
        self.sampling_rate = sampling_rate
        self.read_tasks = []
        self.readers = []
        self.n_chan = 0
        
        ## PFI channels corresponding to selected ctr (can be reprogrammed)
        ctrs_pfis = {
                    'ctr0': 'PFI8',
                    'ctr1': 'PFI3',
                    'ctr2': 'PFI0',
                    'ctr3': 'PFI5',
        }
        
        ## set up external clock channel. When this clock ticks, data is read from the counter channel
        self.clk_channel = '/' + device + '/' + PS_clk_channel
        
        ## set up read channels and stream readers by looping through the collection channels (currently only 1)
        for i,buffer in enumerate(self.buffers): # currently only one collection channel  
            print('buffer size from super class which determines # of samples in clock aquisition:', len(buffer)) 
            ## defines the ctr channel
            dev_channel = device + '/' + self.channel
            
            ## create the read task for each counter channel
            self.read_tasks.append(nidaqmx.Task())
            self.read_tasks[i].ci_channels.add_ci_count_edges_chan(
                                    dev_channel,
                                    edge=Edge.RISING,
                                    initial_count=0,
                                    count_direction=CountDirection.COUNT_UP
            )
            
            ## this is superfluous if the PFI channels are the default options
            PFI = ctrs_pfis[self.channel]
            pfi_channel = '/' + device + '/' + PFI
            self.read_tasks[i].ci_channels.all.ci_count_edges_term = pfi_channel
            
            ## set up read_task timing by external PS clock (triggers automatically when tasks starts)
            self.read_tasks[i].timing.cfg_samp_clk_timing(
                                    self.sampling_rate, # must be equal or larger than max rate expected by PS
                                    source= self.clk_channel,
                                    sample_mode=AcquisitionType.FINITE, #CONTINUOUS, # can also limit the number of points
                                    samps_per_chan= len(buffer)
            )
            
            #print('sampling rate:', self.sampling_rate)
            
            ## create counter stream object 
            self.readers.append(CounterReader(self.read_tasks[i].in_stream))
            
                
        ##the last thing we do is initialize our signal generator.
        ## arbitrarily, I set the sg frequency before turning it on to ensure
        ## there's no dummy value damage.
        mgr.sg.mod_type = 'QAM'
        mgr.sg.rf_toggle = True
        mgr.sg.mod_toggle = True
        mgr.sg.mod_function = 'external'
        
        if mode == 'QAM':
            mgr.sg.set_mod_type('QAM')
        elif mode == 'AM':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_AM_mod_depth(100)
        # setting up the pulses
        if sequence in ('odmr_heat_wait'):
            self.setup_ODMR_wait(mgr)
        else:        
            self.setup_no_wait(mgr, mode)
        return
    
    def setup_no_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        
        
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
            print('self.sequence data: ',  self.sequence.getData())

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
    def setup_ODMR_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, ns_cooldown_time ,runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        
        
        if self.VERBOSE: 
            print('\n using sequence with wait time')
            print('self.read_time:', ns_probe_time)
            print('self.clock_time:',  ns_clock_duration)     
            print('self.cooldown_time:', ns_cooldown_time)  
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
        mwOnOff_clock = [(ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1),
                         (ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1)]
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
            print('self.sequence data: ',  self.sequence.getData())

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
    def read_odmr(self, mgr, n_runs, buffers, buffer_idx, t0):
                
        self.read_tasks[buffer_idx].start()                
        
        ##printing quality control parameters
        #####################################################
        print('now in read function index:', self.index)
        print('number of runs per point:', n_runs)
        print('buffer length:', len(buffers[buffer_idx]))
        # print('index:', self.index)
        # print('sequence:', self.seqs[self.index])
        #####################################################
        # stream n_runs amount of repetitions (spyrelet specific)
        t1 = time.time()
        print('t0, time between setting frequency and streaming:', t1 - t0)
        

        mgr.Pulser.stream_sequence(self.seqs[self.index], int(n_runs)) #1  #int(n_runs)    -1
        ## read into buffer
        t2 = time.time()
        print('t1, time between streaming and reading:', t2 - t1)
        ## time.sleep(100)
        num_samps = self.readers[buffer_idx].read_many_sample_uint32(
                buffers[buffer_idx],
                number_of_samples_per_channel= len(buffers[buffer_idx]),
                timeout= self.timeout
        )
        
        ########################################################
        #print('buffer length:', len(self.ni_ctr_sample_buffer))
        #print('num_samps:', num_samps)
        if num_samps < len(buffers[buffer_idx]):
            print('something wrong: buffer issue')
            return
        ########################################################
        
        
        ## stop the task and the pulse streaming
        print('t2, time between starting to read and closing the task:', time.time() - t2)
        self.read_tasks[buffer_idx].stop() 
        mgr.Pulser.set_state_off()
        ## perform the math of the specific spyrelet.
        math_output = self.math_odmr(buffers[buffer_idx])
        signal = math_output
                
        #print('signal:', signal)
        return signal        


    #### FINALIZATION METHODS

    def finalize(self, mgr, device,  sampling_rate, PS_clk_channel, 
                    data_download):
        
        ## finalizing base spyrelet
        ## stop and close all tasks
        for i,read_task in enumerate(self.read_tasks):
            #time.sleep(0.5)
            #self.read_tasks[i].stop()
            self.read_tasks[i].close()
            #time.sleep(0.5)
        
        ## turns off instruments
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)
        mgr.Pulser.set_state_off()
        
        ## saves the data to an excel sheet.
        # if data_download:
        #     time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        #     print("name of spyrelet is", self.name+time_string)
        #     save_excel(self.name)
        #     print('data downloaded B)')
        ## experiment finishes
        print("FINALIZE")           
        return