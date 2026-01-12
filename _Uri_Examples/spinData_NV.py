###########################
# imports
###########################

# std
import numpy as np
import time
import math
from itertools import cycle
import logging
import scipy as sp
from scipy import signal
import datetime as Dt

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
from nidaqmx.stream_readers import CounterReader

# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

from lantz.drivers.ni.UriFSM import UriSetup
from spacefb import SpatialFeedbackXYZSpyrelet
#from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence

import itertools as it
from nspyre.gui.colors import cyclic_colors, colors

# for data download
from threed.data_and_plot import save_excel

COLORS = cycle(colors.keys())

###########################
# classes
###########################
class BaseFeedbackSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]

    """
    This is the base spyrelet that ties together all common functions. 
    It enables feedback (once we fix it),it downloads data, it handles the reads for each experiment.
    Unfortunately, many things have to be customized for each experiment, so this is barebones.
    """
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }

    PARAMS = {
        'x_initial': {
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'y_initial': {
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'z_initial': {
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'xyz_step':{
            'type': float,
            'units': 'm',
            'default': 60e-9,
        },
        'count_step_shrink':{
            'type': int,
            'default': 2,
        },
        'starting_point': {
            'type': list,
            'items': list(['user_input','current_position (ignore input)']),
            'default': 'current_position (ignore input)',
        },
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'ctr_channel':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3'])
            },
        'sampling_rate':{
            'type':float,
            'units':'Hz'
        },
        'data_download':{
            'type': bool,
        },
        'dozfb':{
            'type':bool,
        },
    }
    
    ##Feedback function for focus tracking in x, y, and z
    def run_feedback(self,x_initial, y_initial, z_initial, starting_point,dozfb, xyz_step, count_step_shrink):
                
        feed_params = {
            'starting_point': str(starting_point),
            'x_initial': x_initial.to('um').m,
            'y_initial': y_initial.to('um').m,
            'z_initial': z_initial.to('um').m,
            'do_z': dozfb,
            'xyz_step': xyz_step,
            'shrink_every_x_iter': count_step_shrink,
        }
        ## we make sure the laser is turned on.
        self.pulses.Pulser.constant(([7],0.0,0.0))
        
        #Call feedback spyrelet
        self.call(self.newSpaceFB,**feed_params)
        
        
        ##space_data is the last line of data from spatialfeedbackxyz
        space_data = self.newSpaceFB.data.tail(1)
        print(space_data)
        self.x_initial = Q_(space_data['x_center'].values[0],'um')
        self.y_initial = Q_(space_data['y_center'].values[0],'um')
        print('x:', self.x_initial)
        print('y:', self.y_initial)
        if dozfb:
            self.z_initial = Q_(space_data['z_center'].values[0],'um')
            print('z:', self.z_initial)
            return self.x_initial, self.y_initial, self.z_initial
        print(self.x_initial)
        
        return self.x_initial, self.y_initial

    def initialize(self, device, buffers, PS_clk_channel,
                   sampling_rate, data_download): #time_per_point,
        
        ## define class parameters
        self.sampling_rate = sampling_rate.to('Hz').m
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
        for i,buffer in enumerate(buffers): # currently only one collection channel  
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
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
                
    def finalize(self, device, buffers, PS_clk_channel,
                 sampling_rate, data_download): #time_per_point, 
        
        ## stop and close all tasks
        for i,read_task in enumerate(self.read_tasks):
            #time.sleep(0.5)
            #self.read_tasks[i].stop()
            self.read_tasks[i].close()
            #time.sleep(0.5)
        
        ## turns off instruments
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.pulses.Pulser.reset()
        
        ## saves the data to an excel sheet.
        if data_download:
            time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            print("name of spyrelet is", self.name+time_string)
            save_excel(self.name)
            print('data downloaded B)')
        ## experiment finishes
        print("FINALIZE")
        
    ## ODMR spyrelets reads point by point, so for each read point: start task, start pulse streaming, 
    ## and read samples to buffer, then stop the task and reset the pulse streaming 
    def read_odmr(self, n_runs, buffers, buffer_idx, t0):
                
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
        self.pulses.stream(self.seqs[self.index], int(n_runs)) #1  #int(n_runs)    -1
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
        self.pulses.Pulser.reset()
        ## perform the math of the specific spyrelet.
        math_output = self.math_odmr(buffers[buffer_idx])
        signal = math_output
                
        #print('signal:', signal)
        return signal        
        
    def read(self, n_runs, points_per_stream, buffers, buffer_idx):
        
        ## defines logic arrays 
        ## self.num_signal designates how many different read windows we collect
        ## n_runs * points_per_stream gives us the amount of times one read window
        ## is collected during one sweep/plot
        signal = np.empty(shape=(self.num_signal, n_runs * points_per_stream))## creating a signal array with num_signal (=number of reading windows
                                                                              ## per sequence) entries. Each entry is an array of n_runs * points_per_stream,
                                                                              ## which is the number of sequences per sweep, so, as an example, the first 
                                                                              ## entry of signal array is an array with all reading windows that belong to the
                                                                              ## ms=1, while the next entry will be ms=0, etc.
        
        ## for each read point; start task, start pulse streaming, and read samples to buffer
        ## then stop the task and reset the pulse streaming 
        self.read_tasks[buffer_idx].start() ## we want to do this in a loop for several tasks. Currently only one task so this works                
        
        #t1 = time.time()
        print('*******************In read function*************')
        print('number of times to stream the seq', n_runs, 'type:', type(n_runs))
        #print('buffer size', self.buffer_size)
        print('before stream')
        #import pdb; pdb.set_trace()
        self.pulses.stream(self.seqs, n_runs) # self.seqs is usually a data_ct repeatitions of sequence with the x-axis variable changing 
                                              # to make a full run. The stream command streams n_runs amount of full runs (spyrelet specific)
        t2 = time.time()
        print('points_per_stream', points_per_stream, 'n_runs', n_runs)
        #print('current time:',t2)
        print('buffer size', len(buffers[buffer_idx]))
        num_samps = self.readers[buffer_idx].read_many_sample_uint32(
                buffers[buffer_idx],
                number_of_samples_per_channel=len(buffers[buffer_idx]),
                timeout = self.timeout
        ) ## this collects the signal from the APD. Each 2 entries will create a reading window, so the length of the collection 
          ## is the number of reading windows for a full run (given by number of sequences(=number of points per run)*
          ## reading windows per sequence*number of runs) * 2  
          
        ## clarify there is no buffer issue.
        print('num samps:', num_samps)
        if num_samps < len(buffers[buffer_idx]):
            print('something wrong: buffer issue')
            return
        
        ## stop the task and the pulse streaming
        ## may not be required
        self.read_tasks[buffer_idx].stop() 
        self.pulses.Pulser.reset() 
        print('read finished:', time.time() - t2)
        ## math logic returns the sum of counts in each read window. 
        ## this data may be acquired to mongo.
        signal = self.math(buffers[buffer_idx])
        
        #print('math finished')
        # # Now, the signal is a double list of arrays of size ni_ctr_sample_buffer/4
        return signal

class ODMRSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
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
    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'channel1':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default':'ctr1',
            },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 50000,
        },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': .7
            # },
        'runs':{
            'type': int,
            'default': 1000,
            'positive': True,
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'repeat_every_x_minutes':{
            'type': float,
            'default': .1,
            'positive': True
        },
        'repetitions':{
            'type': int,
            'default': 5,
            'positive': True
        },
        'frequency':{
            'type': range,
            'units':'Hz',
            'default':{'func': 'linspace',
                            'start': 2.82e9,
                            'stop': 2.92e9,
                            'num': 30},
        },
        'rf_amplitude':{
            'type': float,
            'default': -20,
        },
        'probe_time':{
            'type': float,
            'default': 50e-6,
            'suffix': ' s',
            'units': 's'
        },
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'laser_lag': {
            'type': float,
            'default': 80e-9,
            'suffix' : ' s',
            'units': 's'
        },
        'laser_pause': {
            'type': float,
            'default': 3e-7,
            'suffix' : 's',
            'units': 's'
        },
        'cooldown_time':{
            'type': float,
            'default': 5e-6,
            'suffix': ' s',
            'units': 's'
        },
        'sequence':{
            'type': list,
            'items': ['odmr_heat_wait', 'odmr_no_wait'],
            'default': 'odmr_no_wait',
        },
        'feedback':{
            'type': bool,
            'default': False,
        },
        'dozfb':{
            'type': bool,
            'default': True
        },
        'sweeps_til_fb':{
            'type': int,
            'default': 10,
        },
        'x_initial':{
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'y_initial':{
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'z_initial': {
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'xyz_step':{
            'type': float,
            'units': 'm',
            'default': 60e-9,
        },
        'count_step_shrink':{
            'type': int,
            'default': 2,
        },
        'starting_point': {
            'type': list,
            'items': list(['user_input','current_position (ignore input)']),
            'default': 'current_position (ignore input)',
        },
        'data_download':{
            'type': bool,
        },
        'mode':{'type': list,'items': ['QAM','AM'], 'default': 'QAM'},
    }

    def main(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps,mode, frequency, rf_amplitude, laser_lag, laser_pause, cooldown_time,
                    probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        
        ## we sweep through the bundles of sweeps we take every x_minutes.
         
        for rep in range(repetitions):        
            for sweep in self.progress(range(sweeps)):
            ################################################################################################################
            ##             
            ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
                if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            ##
            ###############################################################################################################
            
            ## sweeping through frequencies (each frequency calls read to create a data point with a new buffer)
            ## frequency sweep
                ## frequency modulation within each data point
                for f in frequency:
                    self.sg.frequency = f ## make sure the sg frequency is set! (overhead of <1ms)
                    self.t0= time.time()
                   
                   ## read the ctrs rates for the number of runs per point
                    ctrs_rates = self.read_odmr(self.runs, self.buffers, self.index, self.t0) # calls read from base spyrelet #len(self.buffers[0])/2 #0
            
                    ## acquire the following
                    self.acquire({
                        'rep_idx': rep,
                        'sweep_idx': sweep,
                        'f': f,
                        'sig': int(ctrs_rates[0]),
                        'bg': int(ctrs_rates[1]),
                        'runs': self.runs,
                        'probe_time': self.probe_time,
                        'rf_power': rf_amplitude,
                        'repetitions': repetitions,
                        'repeat_every_x_minutes': repeat_every_x_minutes
                    })
            time.sleep(repeat_every_x_minutes * 60)

    
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
            print('Time for streaming per point:', self.pulses.total_time/1e9)
            print('Full experiment time:', self.pulses.total_time/1e9 * self.point_num)
            return [sum1, sum2]
            
    def initialize(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps, mode, frequency, rf_amplitude, laser_lag, laser_pause, cooldown_time,
                    probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        ## create self parameters
        self.sequence = sequence #type of ODMR sequence from the list
        self.index = 0 
        self.timeout=timeout #time to wait for clock before raising an error
        self.runs = runs #number of reading windows to average for each point
        self.channel = channel1 #reading channel
        self.sg.rf_amplitude = rf_amplitude ## set SG paramaters: running this spyrelet with IQ inputs
        self.probe_time = int(round(probe_time.to("ns").m)) #laser time per window
        self.point_num = len(frequency)
        self.laser_lag = int(round(laser_lag.to("ns").m))
        
        ## create parameters
        if self.sequence in ('odmr_heat_wait'):
            odmr_buffer_size = 4*self.runs + 1
            print('effective buffer_size:', odmr_buffer_size)
        else:
            odmr_buffer_size = 2*self.runs + 1 #odmr_buffer_size = 2*(math.floor(time_per_point/(2*probe_time)) + 1)
            print('effective buffer_size:', odmr_buffer_size)

            # Note to self (David): The +1 is because each read function measures the current counts. So n+1 counts are needed to get 
            # n differences = n samples.

        if odmr_buffer_size <2:
            raise ValueError('the buffer is too small. set runs to an integer > 0.')

        ## using array with contiguous memory region because NI uses C arrays under the hood
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(odmr_buffer_size, dtype=np.uint32))
        self.buffers = [ni_ctr_sample_buffer]
        
        ## Ideally, DAQ would sample at the PS clock ticking rate. 
        ## as of now, 02_16_2021, we do not understand the exact conditions required.
        if sampling_rate.to('Hz').m < 1/probe_time.to('s').m:
            print('sampling rate must be equal or larger than 1/probe_time')
            return

        ## initialize base spyrelet
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate,data_download) #time_per_point,

        if mode == 'QAM':
            self.sg.mod_type = 'QAM'
        elif mode == 'AM':
            self.sg.mod_type = 'AM'
            self.sg.AM_mod_depth = Q_(100, 'pc')
        # setting up the pulses
        if sequence in ('odmr_heat_wait'):
            self.setup_ODMR_wait(probe_time, clock_duration, laser_pause, cooldown_time, self.runs)
        else:        
            self.setup_no_wait(probe_time, clock_duration, self.runs, mode)
        return
        
    def finalize(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps,mode, frequency, rf_amplitude, laser_lag, laser_pause, cooldown_time,
                    probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        ## finalizing base spyrelet
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate,data_download) #time_per_point,             
        return

    def setup_no_wait(self, probe_time, clock_duration, runs,mode):
        print('\n using sequence without wait time')
        self.pulses.laser_lag = self.laser_lag
        self.pulses.read_time = self.probe_time #laser time per window
        self.pulses.clock_time = int(round(clock_duration.to("ns").m)) #width of our clock pulse.
        self.pulses.runs = runs #number of runs per point
        self.seqs = [self.pulses.CWUriMRnew(mode)] #list of sequences to be compatible with read_odmr() and PulsedODMR class
        
    ## still need to change this to new method
    def setup_ODMR_wait(self, probe_time, clock_duration, laser_pause, long_buffer, runs):
        print('\n using sequence with wait time')
        self.pulses.laser_lag = self.laser_lag
        self.pulses.read_time = int(round(probe_time.to("ns").m))
        self.pulses.clock_time = int(round(clock_duration.to("ns").m))
        self.pulses.runs = runs #number of runs per point
        self.seqs = [self.pulses.ODMRHeatDissipation(int(round(laser_pause.to('ns').m)), int(round(long_buffer.to('ns').m)))]

    @PlotFormatInit(LinePlotWidget, ['latest', 'average', 'average_diff','average_div','no_trace_average_div'])
    def init_format(p):
        p.xlabel = 'frequency (Hz)'
        p.ylabel = 'PL (cts/s)'
        
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_average_div'])#['latest', 'avg'])
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(0,0,0,0), width=5)
            
    ## this plots the ODMR sweep.
    @Plot1D
    def latest(df, cache):
        recent_data = df[df.rep_idx == df.rep_idx.max()]
        latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
        
    ## this plots a specific ODMR sweep.
    @Plot1D
    def stack_0(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 0]
        ##edit the 0 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
                
    @Plot1D
    def stack_1(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 1]
        ##edit the 1 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
                
    @Plot1D
    def stack_2(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 2]
        ##edit the 2 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
    
    
    @Plot1D
    def stack_3(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 3]
        ##edit the 3 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
                
    @Plot1D
    def stack_4(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 4]
        ##edit the 4 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
                
    @Plot1D
    def stack_5(df, cache):
        recent_data = df[df.rep_idx == 0]
        ##edit the 0 above to be whatever repetition you want
        latest_data = recent_data[recent_data.sweep_idx == 5]
        ##edit the 5 above to be whatever sweep you want
        return {'sig': [latest_data.f, latest_data.sig],
                'bg': [latest_data.f, latest_data.bg]}
    
    ## this plots the running average of all sweeps.
    @Plot1D
    def average(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'sig': [sigs_averaged.index, sigs_averaged],
                'bg': [bgs_averaged.index, bgs_averaged]}
       
    @Plot1D
    def avg_sig(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        sigs_averaged = sigs.mean()
        return {'sig': [sigs_averaged.index, sigs_averaged]}
        
        
    ## this plots the difference of the running averages of all sweeps
    @Plot1D
    def average_diff(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark-bright': [sigs_averaged.index, sigs_averaged-bgs_averaged]}
        
    ## this plots the division of the running averages of all sweeps
    @Plot1D
    def average_div(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}
        
    ## this plots the division of the running averages of all sweeps without a trace line.
    @Plot1D
    def no_trace_average_div(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}   