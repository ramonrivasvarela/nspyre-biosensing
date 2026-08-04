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
        'time_per_point':{
            'type':float,
            'units': 's',
            'default': 1
        },
        'data_download':{
            'type': bool,
        },
        'dozfb':{
            'type':bool,
        },
    }
    ##this feedback has not yet been adapted.
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
        
        #import pdb; pdb.set_trace()
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
        ## PFI channels corresponding to selected ctr (can be reprogrammed)
        ctrs_pfis = {
                    'ctr0': 'PFI8',
                    'ctr1': 'PFI3',
                    'ctr2': 'PFI0',
                    'ctr3': 'PFI5',
        }
        
        ## set up external clock channel. When this clock ticks, data is read from the counter channel
        self.clk_channel = '/' + device + '/' + PS_clk_channel
        
        ## set up read channels and stream readers by looping through the collection channels 
        self.read_tasks = []
        self.readers = []
        self.n_chan = 0
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
        ## control if laser turns on or off.
        ## if laser turns off, you must restart with swabian gui, not NSpyre.
        ## saves the data to an excel sheet.
        if data_download:
            time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            print("name of spyrelet is", self.name+time_string)
            super().save(self.name)
            save_excel(self.name)
            print('data downloaded B)')
        ## experiment finishes
        print("FINALIZE")
            
    
    ## read the buffer from each stream reader and calculate count rate
    ## from counts at the beginning and end of the read window
    ## this assume there are at least two clock ticks per read window
    
    ##currently used on ODMR and PulsedODMR
    # def read_odmr(self, n_runs, buffers, buffer_idx, t0):
                
            
        # ## for each read point; start task, start pulse streaming, and read samples to buffer
        # ## then stop the task and reset the pulse streaming 
        # self.read_tasks[buffer_idx].start()                
        
        
        # #####################################################
        # print('now in read function index:', self.index)
        # print('number of runs per point:', n_runs)
        # print('buffer length:', len(buffers[buffer_idx]))
        # # print('index:', self.index)
        # # print('sequence:', self.seqs[self.index])
        # #####################################################
        # # stream n_runs amount of repetitions (spyrelet specific)
        # t1 = time.time()
        # print('t0, time between setting frequncy and streaming:', t1 - t0)
        # self.pulses.stream(self.seqs[self.index], int(n_runs))  #int(n_runs)    -1
        # ## read into buffer
        # t2 = time.time()
        # print('t1, time between streaming and reading:', t2 - t1)
        # ## time.sleep(100)
        # num_samps = self.readers[buffer_idx].read_many_sample_uint32(
                # buffers[buffer_idx],
                # number_of_samples_per_channel= len(buffers[buffer_idx]),
                # timeout= self.timeout
        # )
        
        # ########################################################
        # #print('buffer length:', len(self.ni_ctr_sample_buffer))
        # #print('num_samps:', num_samps)
        # if num_samps < len(buffers[buffer_idx]):
            # print('something wrong: buffer issue')
            # return
        # ########################################################
        
        
        # ## stop the task and the pulse streaming
        # print('t2, time between starting to read and closing the task:', time.time() - t2)
        # self.read_tasks[buffer_idx].stop() 
        # self.pulses.Pulser.reset()
        # ## perform the math of the specific spyrelet.
        # math_output = self.math_odmr(buffers[buffer_idx])
        # signal = math_output
                
        # #print('signal:', signal)
        # return signal

    def read_odmr(self, n_runs, buffers, buffer_idx, t0):
                
            
        ## for each read point; start task, start pulse streaming, and read samples to buffer
        ## then stop the task and reset the pulse streaming 
        self.read_tasks[buffer_idx].start()                
        
        
        #####################################################
        print('now in read function index:', self.index)
        print('number of runs per point:', n_runs)
        print('buffer length:', len(buffers[buffer_idx]))
        # print('index:', self.index)
        # print('sequence:', self.seqs[self.index])
        #####################################################
        # stream n_runs amount of repetitions (spyrelet specific)
        t1 = time.time()
        print('t0, time between setting frequncy and streaming:', t1 - t0)
        self.pulses.stream(self.seqs[self.index], int(n_runs)) #1 #int(n_runs)    -1
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
        self.pulses.Pulser.forceFinal()
        ## perform the math of the specific spyrelet.
        math_output = self.math_odmr(buffers[buffer_idx])
        signal = math_output
                
        #print('signal:', signal)
        return signal        
        
    def read(self, n_runs, points_per_stream, buffers, buffer_idx, switch = False):
        
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
        if switch:
            self.pulses.stream_umOFF(self.seqs, n_runs, SWITCH = True) # self.seqs is usually a data_ct repeatitions of sequence with the x-axis variable changing 
        else:                                                                            # to make a full run. The stream command streams n_runs amount of full runs (spyrelet specific)
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
        self.pulses.Pulser.forceFinal() 
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
    }

    def main(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
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
        if self.sequence in ('odmr_heat_wait'):
            delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            sum1 = np.sum(delta_buffer[::4]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            sum2 = np.sum(delta_buffer[2::4]) # MW off, but collect bright.
            return [sum1, sum2]
        else:
            delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            print(len(delta_buffer))
            sum1 = np.sum(delta_buffer[:-1][::2]) # MW on
            sum2 = np.sum(delta_buffer[1::2]) # MW off
            
            print('delta_buffer:', delta_buffer)
            print('sum1:', sum1, 'sum2:', sum2)          
            print('Time for streaming per point:', self.pulses.total_time/1e9)
            print('Full experiment time:', self.pulses.total_time/1e9 * self.point_num)
            return [sum1, sum2]
            
    def initialize(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
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
        self.probe_time = int(probe_time.to("ns").m) #laser time per window
        self.point_num = len(frequency)
        
        ## create parameters
        odmr_buffer_size = 2*self.runs + 1 #odmr_buffer_size = 2*(math.floor(time_per_point/(2*probe_time)) + 1)
        print('effective buffer_size:', 2*self.runs + 1)
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

        # setting up the pulses
        if sequence in ('odmr_heat_wait'):
            self.setup_ODMR_wait(probe_time, clock_duration, laser_pause, cooldown_time, self.runs)
        else:        
            self.setup_no_wait(probe_time, clock_duration, self.runs)
        return
        
    def finalize(self, device, channel1, sampling_rate, PS_clk_channel, runs, repetitions,
                    sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
                    probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        ## finalizing base spyrelet
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate,data_download) #time_per_point,             
        return

    def setup_no_wait(self, probe_time, clock_duration, runs):
        print('\n using sequence without wait time')
        self.pulses.read_time = self.probe_time #laser time per window
        self.pulses.clock_time = int(clock_duration.to("ns").m) #width of our clock pulse.
        self.pulses.runs = runs #number of runs per point
        self.seqs = [self.pulses.CWUriMR()] #list of sequences to be compatible with read_odmr() and PulsedODMR class
        
    def setup_ODMR_wait(self, probe_time, clock_duration, laser_pause, long_buffer, runs):
        print('\n using sequence with wait time')
        self.pulses.read_time = int(probe_time.to("ns").m)
        self.pulses.clock_time = int(clock_duration.to("ns").m)
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
        
class nSidebandSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    """
    We run four windows: four different microwave frequencies controlled by analog modulation.
    We read the start of these 50us windows, and we do this 20,000 times. So,
    we have a time per point of 1s.
    We set a timeout for the general sample clock, 
    we can repeat x sweeps every y minutes per z repetitions.
    Note: probe_time is the laser_on_per_window,
    rf_amplitude is the signal generator's power,
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
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': .7
            },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
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
            'type': float,
            'units':'Hz',
            'default': 2.87e9,
        },
        'IQ_freq':{
            'type': str,
            'default': "Q_([2, 5, 9, 12], 'MHz')",
        },
        'IQ':{
            'type': str,
            'default': "[0.5, 0.5]"
        },
        'phase':{
            'type': float,
            'default': 90
        },
        'rf_amplitude':{
            'type': float,
            'default': -20,
        },
        'probe_time':{
            'type': float,
            'default': 50.256e-6,
            'suffix': ' s',
            'units': 's'
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
    }

    def main(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    frequency, IQ_freq, IQ, phase,rf_amplitude, probe_time, timeout, repeat_every_x_minutes,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        
        ## we sweep through the bundles of sweeps we take every x_minutes.
        for rep in self.progress(range(repetitions)):        
        
        # # for sweep in self.progress(range(sweeps)):
        
            ################################################################################################################
            ##             
            ## run xy (and z) spatial feedback if the rep is a multiple of designated number of xy (and z) reps
            if feedback and (rep % sweeps_til_fb == 0) and (rep > 0):
                    self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            ##
            ###############################################################################################################
            ## make sure the sg frequency is set! (overhead of <1ms)
            ## read the ctrs rates for the number of repeats per point
            ## usually this is 20,000, so we have a buffer size of 80,000. 
            ## so, we have self.read_odmr(20,000)
            ## the first point will have a problem, the very last point will not be caught.
            time_before_read = time.time()
            ##print('sweep:',sweep)
            print('rep:',rep)
            ctrs_rates = self.read_odmr(self.len(self.buffers[0])/self.data_bins, self.buffers, 0) # calls read from base spyrelet)
            ## optional, just to clarify
    
            ## acquire the following 
            self.acquire({
                'rep_idx': rep,
                ##'sweep_idx': sweep,
                'omega': [frequency.m + float(e) for e in self.mod_freq],
                'sig': [float(e) for e in ctrs_rates]
            })
            print('time during read and acquire:', time.time() - time_before_read)
            time.sleep(repeat_every_x_minutes * 60)

    
    def math_odmr(self, array):
        ## divide buffer to bright versus dark
        ## note: arm_start_trigger drops first point, so we have to add another point to the end of the buffer
        ## we will also drop the last dark collection, so we will have slightly uneven countings.
        delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
        bins = [np.sum(delta_buffer[::4]) - delta_buffer[0]]
        for i in range(1, self.data_bins):
            bins.append(np.sum(delta_buffer[i::self.data_bins]))
        return bins
        print('delta_buffer:', delta_buffer)
        print('bin1:', bin1, 'bin2:', bin2,'bin3:', bin3, 'bin4:', bin4)          
    def initialize(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    frequency, IQ_freq, IQ, phase,rf_amplitude, probe_time, timeout, repeat_every_x_minutes,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        ## create parameters        
        IQ_freq_quantity = eval(IQ_freq)
        self.data_bins = len(IQ_freq_quantity)
        odmr_buffer_size = self.data_bins * int(time_per_point/probe_time)
        print('buffer_size:', self.odmr_buffer_size)
        self.index = 0
        self.timeout=timeout
        ## using array with contiguous memory region because NI uses C arrays under the hood
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(odmr_buffer_size, dtype=np.uint32))
        
        self.buffers = [ni_ctr_sample_buffer]
        print(len(ni_ctr_sample_buffer))
        ## DAQ must sample quicker than the PS clock ticking rate
        ## ideally, it would sample at the PS clock ticking rate. 
        ## as of now, 02_16_2021, we do not understand the exact conditions required.
        if sampling_rate.to('Hz').m < 1/probe_time.to('s').m:
            print('sampling rate must be equal or larger than 1/probe_time')
            return
        
        ## modulating frequencies must be put into list in Hz
        
        
        mod_freq = np.empty(self.data_bins)
        for k, freq in enumerate(IQ_freq_quantity):
            mod_freq[k] = freq.to('Hz').m
        print(mod_freq)
        if max(mod_freq) > 62e6:
            raise RuntimeError('IQ modulation is too fast, reduce to below half of maximum samples')
            
        IQinfo = eval(IQ)
        ## check that there are no channel repeats
        ## this code barely matters, since it's a remnant from a different code using multiple channels
        ## IGNORE
        self.channel = channel1
        ## initialize base spyrelet
        super().initialize(device, self.buffers, PS_clk_channel,
                           time_per_point, sampling_rate,data_download)

        ## set SG paramaters: running this spyrelet with IQ inputs
        self.sg.rf_amplitude = rf_amplitude
        self.sg.frequency = frequency
        ## setting up the pulses
        self.setup_pulses(mod_freq, probe_time,IQinfo, phase)
        self.mod_freq = mod_freq
        
        return
        
    def finalize(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    frequency, IQ_freq, IQ, phase,rf_amplitude, probe_time, timeout, repeat_every_x_minutes,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        ## finalizing base spyrelet
        super().finalize(device, self.buffers, PS_clk_channel,
                         time_per_point, sampling_rate,data_download)
                        
        return

    def setup_pulses(self, mod_freq, probe_time, IQ, phase):
        ##the probe time is our laser time per window, our clock time is the width of our clock pulse.
        self.pulses.read_time = int(round(probe_time.to("ns").m))
        
        ## due to how the read_odmr() function works, we need this in a list, and we index it at 0.
        ## this is to make it compatible with PulsedODMR as well.
        time_pulse = time.time()
        self.seqs = [self.pulses.n_Sideband(mod_freq, IQ, phase)]
        print('this long to set up the pulses:', time.time() - time_pulse)
        print('total_time, buffer_size', self.pulses.total_time, self.odmr_buffer_size/4)

    @PlotFormatInit(LinePlotWidget, ['latest', 'average'])
    def init_format(p):
        p.xlabel = 'frequency (GHz)'
        p.ylabel = 'PL (cts/s)'
        
            
    ## this plots the ODMR sweep.
    @Plot1D
    def latest(df, cache):
        recent_data = df[df.rep_idx == df.rep_idx.max()]
        return {'sig': [list(latest_data.omega)[0]/1e9, list(latest_data.sig)[0]]}
        
    # # ## this plots a specific ODMR sweep.
    # # @Plot1D
    # # def stack_0(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 0]
        # # ##edit the 0 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
                
    # # @Plot1D
    # # def stack_1(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 1]
        # # ##edit the 1 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
                
    # # @Plot1D
    # # def stack_2(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 2]
        # # ##edit the 2 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
    
    
    # # @Plot1D
    # # def stack_3(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 3]
        # # ##edit the 3 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
                
    # # @Plot1D
    # # def stack_4(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 4]
        # # ##edit the 4 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
                
    # # @Plot1D
    # # def stack_5(df, cache):
        # # recent_data = df[df.rep_idx == 0]
        # # ##edit the 0 above to be whatever repetition you want
        # # latest_data = recent_data[recent_data.sweep_idx == 5]
        # # ##edit the 5 above to be whatever sweep you want
        # # return {'sig': [latest_data.f, latest_data.sig],
                # # 'bg': [latest_data.f, latest_data.bg]}
    
    ## this plots the running average of all sweeps.
    @Plot1D
    def average(df, cache):
        rep_df = df[df.rep_idx == 0]
        avg_sig = np.empty(len(list(rep_df.sig[0])))
        for point_num in range(len(list(rep_df.sig[0]))):
            sum_sig = 0
            for a in range(len(list(rep_df.sig))):
                sum_sig += rep_df.sig[a][point_num]
            avg_sig[point_num] = sum_sig / len(list(rep_df.sig))
        return {'sig': [list(df.omega)[0], list(avg_sig)]}
        

class RabiSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    """
    our most basic function using our normal read.
    we take our optimal frequency (biggest contrast) from ODMR
    and we plug it into Rabi. We then sweep times to apply the microwave,
    such that we generate an oscillation of our signal, showing we have
    full control over the NV's rotation about the Bloch Sphere.
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
        ## we define our clock channel that we use to link
        ## our pulse streamer and our DAQ.
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1,
            },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 2.87e9
        },
        'rf_amplitude':{
            'type': float,
            'default': -20,
        },
        'probe_time':{
            'type': float,
            'default': 5.5e-6,
            'suffix': ' s',
            'units': 's'
        },
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'mw_times':{
            'type': range,
            'units': 'ns',
            'default': {'func': 'linspace',
                        'start': 0e-9,
                        'stop': 600e-9,
                        'num': 21},
        },
        'pi_xy':{
            'type': list,
            'items': list(['x','y']),
            'default': 'x'
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'aom_lag':{
            'type': float,
            'default': 30e-9,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 0.15e-6,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_time':{
            'type': float,
            'default': 6e-7,
            'suffix': ' s',
            'units': 's'
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
    }

    def main(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    buffer_time, singlet_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point):
        
        
        
        for sweep in self.progress(range(sweeps)):
            # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            print('n_runs:', self.run_ct) # time per sweep 
            print('time per read:', self.time_per_point * self.data_ct)
            print('time per experiment:', self.time_per_point * self.data_ct * sweeps)
            ## mw time sweep               
            # # This is an array of shape run_ct by len(mw_times)
            sing_rabi = self.read(self.run_ct, self.data_ct, self.buffers, 0)#math.ceil(self.buffer_size/4))
            self.acquire({
                'run_ct': self.run_ct,
                'sweep_idx': sweep,
                't': [float(e.to('us').m) for e in mw_times],
                'f': frequency,
                'power': rf_amplitude,
                'sig': [float(e) for e in sing_rabi[0]], #*self.ratio,
                'bg': [float(e) for e in sing_rabi[1]], #*self.ratio,
            })
            print("finished acquiring")

    def math(self, array):
        
        ## divide buffer to different experiments
        delta_buffer_start = array[1::4] - array[0::4] 
        delta_buffer_end = array[3::4] - array[2::4] 
        final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
        for i in range(self.data_ct):
            final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
            final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
        return [final_data_dark, final_data_bright]
        # # dark_bright = [delta_buffer_start,delta_buffer_end]
        # # return dark_bright
        
    def initialize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    buffer_time, singlet_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point):
        if aom_lag < clock_duration:
            raise("your laser lag must be longer than the clock pulse duration")            
        ## setup pulses. this counts how many sweeps the program should do.
        self.time_per_point = time_per_point
        self.mw_times = [int(round(mw_time.to('ns').m)) for mw_time in mw_times]
        self.setup_pulses(probe_time, aom_lag, readout_time, buffer_time, singlet_time, clock_duration, pi_xy)
        ## create parameters
        ## sampling rate should be >= 1/(read_window), so 1/400ns
        self.sampling_rate = sampling_rate.to('Hz').m
        ## self.run_ct is determined by total time of the sequence
        ## and time_per_point in setup_pulses
        self.data_ct = len(self.mw_times)
        buffer_size = 4*self.data_ct * self.run_ct# ignore run_ct
        ## we set up the buffer and array we use to get our signal in self.read()
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32)
        self.buffers = [ni_ctr_sample_buffer]
        self.num_signal = 2
        ## we define the timeout in seconds.
        self.timeout = timeout
        ## create channels list and check that there are no repeats
        
        self.channel = channel1
        
        ## initialize base spyrelet
        super().initialize(device, self.buffers, PS_clk_channel,
                            sampling_rate, data_download)

        ## set SG paramaters: running this spyrelet with IQ inputs
        self.sg.frequency = frequency
        self.sg.rf_amplitude = rf_amplitude
        
        
        return
        
    def finalize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    buffer_time, singlet_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point):
        
        ## finalize like every spyrelet.
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate, data_download)        
        return

    def setup_pulses(self, probe_time, aom_lag, readout_time, buffer_time, singlet_time, clock_duration, pi_xy):
        self.pulses.laser_time = int(round(probe_time.to("ns").m))
        self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        self.pulses.readout_time = int(round(readout_time.to("ns").m))
        self.pulses.MW_buf = int(round(buffer_time.to("ns").m))        
        self.pulses.clock_time = int(round(clock_duration.to("ns").m))
        self.pulses.singlet_decay = int(round(singlet_time.to("ns").m))
    
        ##aom_lag really means laser_lag. 
        ##self.seqs is, of course, one sequence,
        ## but it's made by concatenating all sequences of a certain pi time.
        self.seqs = self.pulses.PS_rabi(self.mw_times, pi_xy)     
        
        print('seqs:', self.seqs)
        print('time per point:', self.time_per_point.to('ns').m, 'total pulses time:', self.pulses.total_time)
        print('run_ct not rounded', self.time_per_point.to('ns').m/self.pulses.total_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.time_one))
    
    @PlotFormatInit(LinePlotWidget, ['latest', 'average','diff_average','no_trace_diff_avg'])
    def init_format(p):
        p.xlabel = 'time (us)'
        p.ylabel = 'PL (cts/s)'
        
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_diff_avg'])#['latest', 'avg'])
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(0,0,0,0), width=5)
        
    ## returns the latest rabi sweeps. plural due to our pulse sequence.
    @Plot1D
    def latest(df, cache):
        plot_return = {}
        latest_data = df[df.sweep_idx == df.sweep_idx.max()]
        
        return {'sig': [latest_data.t[0], latest_data.sig[0]], 'bg': [latest_data.t[0], latest_data.bg[0]]}
    ## returns the overall time average of all rabi sweeps, not just for each update.
    ## we are dropping the first point because it was not initialized
    ###### we can probably use it now.
    @Plot1D
    def average(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
                #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        print('finish data rearrangement')
        return {
            'sig': [list(df.t)[0], list(avg_sig)],
            'bg': [list(df.t)[0], list(avg_bg)],
        }
    ## the difference between the average bright and dark signal
    @Plot1D
    def diff_average(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        return {
                'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
                } 
    ## the difference between the average bright and dark signal, with no trace
    @Plot1D
    def no_trace_diff_avg(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
                print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        return {
                'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
 
               } 

class Pent_RabiSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    """
    our most basic function using our normal read.
    we take our optimal frequency (biggest contrast) from ODMR
    and we plug it into Rabi. We then sweep times to apply the microwave,
    such that we generate an oscillation of our signal, showing we have
    full control over the NV's rotation about the Bloch Sphere.
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
        ## we define our clock channel that we use to link
        ## our pulse streamer and our DAQ.
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1,
            },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 3.4e9
        },
        'rf_amplitude':{
            'type': float,
            'default': 5,
        },
        'probe_time':{
            'type': float,
            'default': 300e-6,
            'suffix': ' s',
            'units': 's'
        },
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'mw_times':{
            'type': range,
            'units': 'ns',
            'default': {'func': 'linspace',
                        'start': 0e-9,
                        'stop': 200e-9,
                        'num': 21},
        },
        'pi_xy':{
            'type': list,
            'items': list(['x','y']),
            'default': 'x'
        },
        'readout_time':{
            'type': float,
            'default': 20e-6,
            'suffix': ' s',
            'units': 's'
        },
        'laser_lag':{
            'type': float,
            'default': 30e-9,
            'suffix': ' s',
            'units': 's'
        },
        'TxyDecay_time':{ 
            'type': float,
            'default': 40e-6,
            'suffix': ' s',
            'units': 's'
        },
        # 'buffer_time':{ 
            # 'type': float,
            # 'default': 0.15e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        'TzDecay_time':{ 
            'type': float,
            'default': 800e-6,
            'suffix': ' s',
            'units': 's'
        },
        'initBuffer_time':{ 
            'type': float,
            'default': 100e-9,
            'suffix': ' s',
            'units': 's'
        },           
        # 'singlet_time':{
            # 'type': float,
            # 'default': 6e-7,
            # 'suffix': ' s',
            # 'units': 's'
        # },
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
        'switch': {
            'type': bool,
            'default': False,
        },
    }

    def main(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, laser_lag, readout_time, \
                    TxyDecay_time, TzDecay_time, initBuffer_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point,switch):
        
        for sweep in self.progress(range(sweeps)):
            # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            print('n_runs:', self.run_ct) # time per sweep 
            print('time per read:', self.time_per_point * self.data_ct)
            print('time per experiment:', self.time_per_point * self.data_ct * sweeps)
            ## mw time sweep               
            # # This is an array of shape run_ct by len(mw_times)
            sing_rabi = self.read(self.run_ct, self.data_ct, self.buffers, 0, switch = switch)#math.ceil(self.buffer_size/4))
            self.acquire({
                'run_ct': self.run_ct,
                'sweep_idx': sweep,
                't': [float(e.to('us').m) for e in mw_times],
                'f': frequency,
                'power': rf_amplitude,
                'sig': [float(e) for e in sing_rabi[0]], #*self.ratio,
                'bg': [float(e) for e in sing_rabi[1]], #*self.ratio,
            })
            print("finished acquiring")

    def math(self, array):
        
        ## divide buffer to different experiments
        delta_buffer_start = array[1::4] - array[0::4] 
        delta_buffer_end = array[3::4] - array[2::4]      
        #######################################################################################
        #testing
        # testArray = []
        # for i in range(len(array)):
            # testArray[2*i] = 2*np.cos(2pi*100e-9*
            # testArray[2*i+1] = 1
            # print('testArray:', testArray)
            # delta_buffer_start = testArray[1::4] - testArray[0::4] 
            # delta_buffer_end = testArray[3::4] - testArray[2::4]
        ####################################################################################### 
        final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
        for i in range(self.data_ct):
            final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
            final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
        return [final_data_dark, final_data_bright]
        # # dark_bright = [delta_buffer_start,delta_buffer_end]
        # # return dark_bright
        
    def initialize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, laser_lag, readout_time, \
                    TxyDecay_time, TzDecay_time, initBuffer_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point, switch):
        
        #import pdb; pdb.set_trace()
        if laser_lag < clock_duration:
            raise("your laser lag must be longer than the clock pulse duration")            
        ## setup pulses. this counts how many sweeps the program should do.
        self.time_per_point = time_per_point
        self.mw_times = [int(round(mw_time.to('ns').m)) for mw_time in mw_times]
        self.setup_pulses(probe_time, laser_lag, readout_time, TxyDecay_time, TzDecay_time, initBuffer_time, clock_duration, pi_xy, switch = switch)
        ## create parameters
        ## sampling rate should be >= 1/(read_window), so 1/400ns
        self.sampling_rate = sampling_rate.to('Hz').m
        ## self.run_ct is determined by total time of the sequence
        ## and time_per_point in setup_pulses
        self.data_ct = len(self.mw_times)
        buffer_size = 4*self.data_ct * self.run_ct# ignore run_ct
        ## we set up the buffer and array we use to get our signal in self.read()
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32)
        self.buffers = [ni_ctr_sample_buffer]
        self.num_signal = 2
        ## we define the timeout in seconds.
        self.timeout = timeout
        ## create channels list and check that there are no repeats
        
        self.channel = channel1
        
        ## initialize base spyrelet
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate, data_download)

        ## set SG paramaters: running this spyrelet with IQ inputs
        self.sg.frequency = frequency
        self.sg.rf_amplitude = rf_amplitude
        
        
        return
        
    def finalize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    sweeps, frequency, rf_amplitude, probe_time, laser_lag, readout_time, \
                    TxyDecay_time, TzDecay_time, initBuffer_time, mw_times, pi_xy, timeout, data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    starting_point, switch):
        
        ## finalize like every spyrelet.
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate, data_download)        
        return

    def setup_pulses(self, probe_time, laser_lag, readout_time, TxyDecay_time, TzDecay_time, initBuffer_time, clock_duration, pi_xy, switch = False):
        self.pulses.laser_time = int(round(probe_time.to("ns").m))
        self.pulses.laser_lag = int(round(laser_lag.to("ns").m))
        self.pulses.readout_time = int(round(readout_time.to("ns").m))
        self.pulses.TxyDecay_time = int(round(TxyDecay_time.to("ns").m))        
        self.pulses.TzDecay_time = int(round(TzDecay_time.to("ns").m))
        self.pulses.initBuffer_time = int(round(initBuffer_time.to("ns").m))
        
        ##laser_lag really means laser_lag. 
        ##self.seqs is, of course, one sequence,
        ## but it's made by concatenating all sequences of a certain pi time.
        if switch:
            self.seqs = self.pulses.Pent_rabi_safe(self.mw_times, pi_xy)    
        else:
            self.seqs = self.pulses.Pent_rabi(self.mw_times, pi_xy)
        
        print('seqs:', self.seqs)
        print('time per point:', self.time_per_point.to('ns').m, 'total pulses time:', self.pulses.total_time)
        print('run_ct not rounded', self.time_per_point.to('ns').m/self.pulses.total_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.time_one))

    @PlotFormatInit(LinePlotWidget, ['latest', 'average','diff_average','no_trace_diff_avg'])
    def init_format(p):
        p.xlabel = 'time (us)'
        p.ylabel = 'PL (cts/s)'
        
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_diff_avg'])#['latest', 'avg'])
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(0,0,0,0), width=5)
        
    ## returns the latest rabi sweeps. plural due to our pulse sequence.
    @Plot1D
    def latest(df, cache):
        plot_return = {}
        latest_data = df[df.sweep_idx == df.sweep_idx.max()]
        
        return {'sig': [latest_data.t[0], latest_data.sig[0]], 'bg': [latest_data.t[0], latest_data.bg[0]]}
    ## returns the overall time average of all rabi sweeps, not just for each update.
    ## we are dropping the first point because it was not initialized
    ###### we can probably use it now.
    @Plot1D
    def average(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
                #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        print('finish data rearrangement')
        return {
            'sig': [list(df.t)[0], list(avg_sig)],
            'bg': [list(df.t)[0], list(avg_bg)],
        }
    ## the difference between the average bright and dark signal
    @Plot1D
    def diff_average(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        return {
                'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
                } 
    ## the difference between the average bright and dark signal, with no trace
    @Plot1D
    def no_trace_diff_avg(df, cache):
        frame = df
        avg_sig = np.empty(len(list(frame.sig[0])))
        avg_bg = np.empty(len(list(frame.sig[0])))
        for point_num in range(len(list(frame.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for a in range(len(list(frame.sig))):
                sum_sig += frame.sig[a][point_num]
                sum_bg += frame.bg[a][point_num]
                print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_sig[point_num] = sum_sig / len(list(frame.sig))
            avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        return {
                'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
 
               }
               

 # --------------------------------------------------------------------------------------------               
        
class MSDSwabianSpyrelet(BaseFeedbackSpyrelet):
    """Runs a "mixed state decay" experiment. The system is initialized to a superposition of states in the triplet manifold using laser + MW, 
    the system evolves without excitation for a time tau, and the state is read. Tau is swept to characterize the decay of states in the triplet manifold.

    The frequency, power, pi pulse, and pi/2 pulse times are fixed, and the experiment time
    (either full evolution time or pi pulse separation, depending on type of measurement)
    is varied.
    A two-branch setup is combined with IQ modulation to improve readout contrast and maintain
    a constant duty cycle for all excitations. As the experiment steps through exp_times,
    the time variable in the first branch increases and in the second branch decreases
    (note this only works for linear time steps). One branch reads out the bright state population
    and the other reads out the dark state population (either by applying a pi pulse before readout
    or applying a +-pi/2 pulse at the end of a T2-like sequence). The data from the reverse-time
    branch can then be reversed and subtracted from the forward-time branch to give full spin contrast.
    Sequences also have reference readouts to track slow drift during an experiment.
    The default plotting assumes that channels 2 and 4 carry signal and channels 1 and 3 carry
    references, respectively, and that channels 3 and 4 run forward in time, while channels
    1 and 2 run reversed. Not all experiments need use all of the channels.
    
    Args:
            exp_times:      Array of generic variable time for given sequence
            sequence:       The pulsed experiment to run
            n:              For multi-pi pulse sequences, number of repetitions
            pi_time:        Pi pulse time
            pi_half_time:   Pi/2 pulse time (due to imperfections in equipment, not necessarily pi_time/2)
    """

    REQUIRED_DEVICES = ['sg', 'pulses', 'urixyz'] 
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}

    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'channel':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default':'ctr1',
            },        
        ## sampling rate must be more than 1/read_window (we think)
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1.5,
            },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 1.3e9
        },
        'power':{
            'type': float,
            'default': -20,
        },
        ## these are your tau_times
        'expTimesStart':{
            'type': float,
            'units': 's',
            'default': 5e-8
        },
        'expTimesStop':{
            'type': float,
            'units': 's',
            'default': 1e-3
        },
        'expTimesIter':{
            'type': int,
            'positive': True,
            'default': 21
        },
        'typeRange':{
            'type': list,
            'items': list(['geomspace', 'linspace']),
            'default': 'geomspace',
        },
            
            
        ## this is in the form of a list because it's how the code works.
        ## we got it from Jonathan. It will let you run a ramsey,
        ## hahn echo, and high length CPMG back to back in the same analysis.
        ## our math might not be set up to handle that yet.
        "piTimeMW":{
            'type': float,
            'default': 50e-9,
            'suffix': ' s',
            'units': "s"
        },
        "Tz_relaxation_time":{
            'type': float,
            'default': 800e-6,
            'suffix': ' s',
            'units': "s"
        },
        'init_time':{
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'clock_time':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'aom_lag':{
            'type': float,
            'default': .030e-6,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 1.5e-7,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_time':{
            'type': float,
            'default': 6e-7,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'data_download':{
            'type': bool,
        },
        'feedback':{
            'type': bool,
            'default': True,
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
    }

    def main(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
             power, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, 
             Tz_relaxation_time, typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
             data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
             z_initial, xyz_step,count_step_shrink,starting_point):
        ## this will count however many sweeps have gone for doing feedback.
        ## we repeat the cpmg sweeps. this is how often the plot updates.
        for sweep in self.progress(range(sweeps)):
            
            # # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                print('feedback')
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
                # time.sleep(1)
            
            print('n_runs:', self.run_ct) ## number of runs per sweep. Determined by time per point 
            print('set time per read (s):', self.time_per_point*1e-9 * self.data_ct)
            print('time per experiment:', self.time_per_point*1e-9 * self.data_ct * sweeps)
            ## mw time sweep. if a series of "n" is given, step through
            # # signal_pi is the PL counts for the signal and background for bright and dark states
            signal_pi = self.read(self.run_ct, self.data_ct, self.buffers, 0) # time_per_point / total time
                                                                              # need to fix buffer index to use read for multiple buffers
            
            
            #print('start acquiring')
            self.acquire({
                ## sweep_idx is which plot update it is. 
                ## run_ct records how many runs of the sequence are done each sweep.
                'sweep_idx': sweep,
                'run_ct': self.run_ct,
                ## unfortunately, we cannot acquire numpy arrays.
                ## therefore we convert time and counts to lists.
                't': [float(e) * 1e-3 for e in self.exp_times],
                'f': frequency,
                'power': power,
                'a': [float(e) for e in signal_pi], #brightDecay
            })
            #print('finished acquiring')

    def initialize(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
                    power, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, Tz_relaxation_time,
                    typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        #import pdb; pdb.set_trace()
        # parameters
        self.timeout = timeout
        self.sequence = 'OpticalDutyCycle'
        ## t_p_p and sampling rate should have some dependency on each other
        ## however, setting the sampling rate too low doesn't seem to disrupt the data.
        self.time_per_point = time_per_point
        self.sampling_rate = sampling_rate.to('Hz').m
        if typeRange == 'geomspace':
            self.exp_times = np.geomspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are log spaced.')
        else:
            self.exp_times = np.linspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are linearly spaced.')
        print('\n the rise of exp_times:', self.exp_times[0], 'and the fall of exp_times:', self.exp_times[-1])
        # # if sampling_rate.to('Hz').m < 1/readout_time.to('s').m:
            # # print('sampling rate must be equal or larger than 1/readout_time')
            # # return
        ## self.data_ct is our number of data points.
        self.data_ct = len(self.exp_times)
        if aom_lag < clock_time:
            raise("your laser lag must be longer than the clock pulse duration")
        self.sg.frequency = frequency
        ## this 'n' character only affects CPMG, not XY8 or YY8
        ## therefore, this only registers how many pulse sequences to setup with xy8 or yy8.
        #import pdb; pdb.set_trace()
        self.setup_pulses(self.exp_times, piTimeMW, singlet_time, 
                          init_time, aom_lag, clock_time, readout_time, buffer_time, Tz_relaxation_time)
        
        ## note: self.run_ct has been set.
        ## self.run_ct is how many runs for one point of the sequence.
        ## self.run_ct is also how many runs for each sequence.
        
        # # # # # if sequence == 'CPMG':
            # # # # # self.buffer_size = 8* self.data_ct * self.run_ct# 8 ticks per 1 seq 
        
        self.num_signal = 1 ##self.num_signal is used in read and is determined by how many 
                                                       ##reading windows there are per sequence
        buffer_size = 2 * self.num_signal * self.data_ct * self.run_ct ##buffer size is the total data points collected from the APD.
                                                                       ## 2 per reading window (num_signal) * number of points (data_ct)
                                                                       ## * number of times we sum and avg each run (run_ct) for one sweep
                                                                       ## each sweep is its own read function and hence have a new buffer 
        
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32) ## we create a data buffer with lngth = buffer_size 
        
        self.buffers = [ni_ctr_sample_buffer] ##we append each data buffer to the buffers array in case we are reading from multiple channels
                                              ## currently we only use one channel
        
        
        ## create channels list and check that there are no repeats
        self.channel = channel
        # if len(set(self.channels)) != len(self.channels):
            # raise RuntimeError('counter channels must be different')
        
        ## set signal generator parameters
        self.sg.rf_amplitude = power
        ## initialize super class
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate,data_download)
                            
        return
    
    ## divide buffer to different experiments
    def math(self, read_data):
        average_buffer = np.empty(2 * self.data_ct)
        for i in range(2 * self.data_ct): 
            average_buffer[i] = np.sum(read_data[i::(2 * self.data_ct)])
        print('Avg Buffer length:', len(average_buffer))
        print('Avg Buffer:', average_buffer)
        print('Avg Buffer tick1:', average_buffer[1::2])
        print('Avg Buffer tick2:', average_buffer[0::2])
        brightDecay = average_buffer[1::2] - average_buffer[0::2]
        return brightDecay
              
    def finalize(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
                    power, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, 
                    Tz_relaxation_time, typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink, starting_point):
                    
        ## everything finalizes like everything else.
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate,data_download)
        
        return

    def setup_pulses(self, exp_times,piTimeMW, singlet_time,
                     init_time,aom_lag,clock_time,readout_time, buffer_time, Tz_relaxation_time):
        """Create swabian pulse sequence.
        The sequence selected in PARAMS is created. Not all parameters are used
        in every sequence, e.g., n is not used for T1 sequences.
        Each sequence has a two-branch setup and reference readouts.
        The computed ratio scales the collected data by 1/(readout duty cycle),
        so signals across experiments with the same readout time
        are directly comparable.
        """
        print('now in setup pulses function')
        self.pulses.laser_time = int(round(init_time.to("ns").m))
        self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        self.pulses.readout_time = int(round(readout_time.to("ns").m))
        self.pulses.mw_wait = int(round(buffer_time.to("ns").m))
        self.pulses.clock_time = int(round(clock_time.to("ns").m))
        self.pulses.singlet_decay = int(round(singlet_time.to("ns").m))
        self.pulses.Tz_relaxation_time = int(round(Tz_relaxation_time.to("ns").m)) #EDIT
        exp_times_ns = [int(exp_time) for exp_time in exp_times] 
        self.seqs = self.pulses.mixedStateDecay(exp_times_ns) #EDIT
        
        # run count is total time to run the sequence over period of each sequence.
        print('\n', self.time_per_point, self.data_ct, self.pulses.total_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m * self.data_ct/self.pulses.total_time))
        print('total time is:', self.pulses.total_time, 'n_runs is:', self.run_ct)  

    @PlotFormatInit(LinePlotWidget, ['latest', 'average','four_ch_diff_avg_sig_bg','no_trace_diff_avg', 'signal'])
    def init_format(p):
        p.xlabel = 'time (us)'
        p.ylabel = 'PL (cts/s)'
    
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_diff_avg','norm_diff_avg_not_trace'])#['latest', 'avg'])        
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(255,255,255,10), width=5)

    ## plots the latest data for all four channels of CPMG
    @Plot1D
    def latestMW(df, cache):
        latest_data = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
                'brightDecay': [latest_data.t[0], latest_data.a[0]],
                'darkDecay': [latest_data.t[0], latest_data.b[0]],
                }
               
    @Plot1D
    def latestOpt(df, cache):
        latest_data = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
                'brightDecay': [latest_data.t[0], latest_data.a[0]],
                }

               
    @Plot1D
    def averageMW(df, cache):
        frame = df
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        avg_b = np.empty(len(list(frame.b[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0; sum_b = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
                sum_b += frame.b[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a))
            avg_b[point_num] = sum_b / len(list(frame.b))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'brightDecay': [list(df.t)[0], list(avg_a)],
            'darkDecay': [list(df.t)[0], list(avg_b)],
        }    
        
    @Plot1D
    def avgOpt(df, cache):
        frame = df
        
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a)) 
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        ## a is dark sig, b is bright sig
        return {
            'brightDecay': [list(df.t)[0], list(avg_a)],
        }    
        
        
    @Plot1D
    def averageMWDiff(df, cache):
        # time_stemp = datetime.now().strftime("%Y_%m_%d%_%H_%M_%S")
        # name = "T1Swabian"
        # print("data is saved in:", name+time_stemp)
        frame = df
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        avg_b = np.empty(len(list(frame.b[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0; sum_b = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
                sum_b += frame.b[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a))
            avg_b[point_num] = sum_b / len(list(frame.b))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'bright - dark': [list(df.t)[0], list((avg_a - avg_b)/(avg_a + avg_b))],
        }    
 # --------------------------------------------------------------------------------------------   
 
class PulsedODMRSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',#this is probably not needed
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    """
    we run an ODMR,but this time our 
    mw_on time is a pi_pulse. This gives us a full
    rotation to the dark state, and gives us optimal contrast.
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
            'default': 2.5e6,
        },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': 1
            # },
        ## in this spyrelet, we set n_points
        ## n_points is the amount of times we run one point.
        ## we may also call this "n_runs"
        'n_points':{
            'type':int,
            'default': 10000,
            'positive': True,
            },   
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': range,
            'units':'Hz',
            'default':{'func': 'linspace',
                            'start': 2.8e9,
                            'stop': 2.94e9,
                            'num': 40},
        },
        'rf_amplitude':{
            'type': float,
            'default': -20,
        },
        'pi_time':{
            'type': float,
            'default': .5e-6,
            'suffix': ' s',
            'units': 's',
        },
        'probe_time':{
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'wait_buffer_time':{
            'type': float,
            'default': 800e-6,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_decay':{
            'type': float,
            'default': .6e-6,
            'suffix': ' s',
            'units': 's'
        },
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'aom_lag':{
            'type': float,
            'default': .027e-6,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 0.1e-6,
            'suffix': ' s',
            'units': 's'
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
    }

    def main(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        for sweep in self.progress(range(sweeps)):
            ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            ## frequency sweep
            for f in frequency:
                self.sg.frequency = f # setting sg to frequency f (SG396 communication overhead of <1ms)
                self.t0= time.time()
                ctrs_rates = self.read_odmr(n_points, self.buffers,self.index, self.t0) # calls read from base spyrelet)        
                ## acquire the following 
                self.acquire({
                    'sweep_idx': sweep,
                    'f': f,
                    'x': float(ctrs_rates[0]),
                    'y': float(ctrs_rates[1]),
                })
    def math_odmr(self, array):
        
        ## divide buffer to different experiments
        delta_buffer_start = array[1::4] - array[0::4] 
        delta_buffer_end = array[3::4] - array[2::4] # taking the difference between ticks
        ## the sequence first records the bright state, then the dark state.
        sum2 = np.sum(delta_buffer_start) 
        sum1 = np.sum(delta_buffer_end) 
        ## return dark, bright)
        return [sum1, sum2]

    def initialize(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        ## make sure we only stream one sequence, set timeout for sample clock.
        self.index = 0
        self.timeout=timeout
        ## create channels list and check that there are no repeats
        self.channel = channel1
        ## we set the buffer size, n_points * number of clock pulses in 1 sequence.
        buffer_size = 4*n_points
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(buffer_size, dtype=np.uint32))
        
        self.buffers = [ni_ctr_sample_buffer]
        ## sampling rate should be higher than 1/readout
        self.sampling_rate = sampling_rate.to('Hz').m
        
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate,data_download)
        
        ## initialize instruments. This stuff can probably be moved to 
        self.sg.rf_amplitude = rf_amplitude
        ## set up the pulse streamer.
        self.setup_pulses(pi_time,probe_time,aom_lag,readout_time,buffer_time,singlet_decay, clock_duration,wait_buffer_time)
        return
        
    def finalize(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        ## perform common finalize
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate,data_download)
        return

    def setup_pulses(self,pi_time,probe_time,aom_lag,readout_time,buffer_time,singlet_decay,clock_duration,wait_buffer_time):
        self.pulses.laser_time = int(probe_time.to("ns").m)
        self.pulses.singlet_decay = int(singlet_decay.to("ns").m)
        ## aom_lag is always laser_lag
        self.pulses.aom_lag = int(aom_lag.to("ns").m)
        self.pulses.readout_time = int(readout_time.to("ns").m)
        self.pulses.laser_buf = int(buffer_time.to("ns").m)
        self.pulses.wait_buff = int(round(wait_buffer_time.to("ns").m))
        self.pulses.tick_time = int(clock_duration.to("ns").m)
        ## we set the sequences. we put it in a list so that our index / read_odmr will work.
        self.seqs = [self.pulses.Diff_Pulsed_ODMR(pi_time)]
        print("sequence:", self.seqs)
        ## sets the ratio which we could use to scale up how many counts we get. 
        ## since we sum in our math function, this doesn't matter too much.
        self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)

    @PlotFormatInit(LinePlotWidget, ['latest', 'average','diff_average','div_average','no_trace_div_avg'])
    def init_format(p):
        p.xlabel = 'frequency (Hz)'
        p.ylabel = 'PL (cts/s)'
        
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_div_avg'])#['latest', 'avg'])        
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(0,0,0,0), width=5)
    @Plot1D
    def latest(df, cache):
        latest_data = df[df.sweep_idx == df.sweep_idx.max()]
        return {
                'sig': [latest_data.f, latest_data.x],
                'bg': [latest_data.f, latest_data.y]
                }

    @Plot1D
    def average(df, cache):
        grouped = df.groupby('f')
        xs = grouped.x
        xs_averaged = xs.mean()
        ys = grouped.y
        ys_averaged = ys.mean()
        return {
                'sig': [xs_averaged.index, xs_averaged],
                'bg': [ys_averaged.index, ys_averaged]
                } 

    @Plot1D
    def diff_average(df, cache):
        grouped = df.groupby('f')
        xs = grouped.x
        ys = grouped.y
        xs_averaged = xs.mean()
        ys_averaged = ys.mean()
        return {
                'sig-bg': [xs_averaged.index, xs_averaged - ys_averaged],
                } 
    
    @Plot1D
    def div_average(df, cache):
        grouped = df.groupby('f')
        xs = grouped.x
        ys = grouped.y
        xs_averaged = xs.mean()
        ys_averaged = ys.mean()
        return {
                'sig/bg': [xs_averaged.index, xs_averaged / ys_averaged],
                } 
                
    @Plot1D
    def no_trace_div_avg(df, cache):
        grouped = df.groupby('f')
        xs = grouped.x
        ys = grouped.y
        xs_averaged = xs.mean()
        ys_averaged = ys.mean()
        return {
                'sig/bg': [xs_averaged.index, xs_averaged / ys_averaged],
                } 

class PulsedTSwabianSpyrelet(BaseFeedbackSpyrelet):
    """Runs a selected pulsed, time-dependent characterization or sensing experiment
    e.g., T1, T2*, T2 Hahn, T2 CPMG, T2 XY..
    The frequency, power, pi pulse, and pi/2 pulse times are fixed, and the experiment time
    (either full evolution time or pi pulse separation, depending on type of measurement)
    is varied.
    A two-branch setup is combined with IQ modulation to improve readout contrast and maintain
    a constant duty cycle for all excitations. As the experiment steps through exp_times,
    the time variable in the first branch increases and in the second branch decreases
    (note this only works for linear time steps). One branch reads out the bright state population
    and the other reads out the dark state population (either by applying a pi pulse before readout
    or applying a +-pi/2 pulse at the end of a T2-like sequence). The data from the reverse-time
    branch can then be reversed and subtracted from the forward-time branch to give full spin contrast.
    Sequences also have reference readouts to track slow drift during an experiment.
    The default plotting assumes that channels 2 and 4 carry signal and channels 1 and 3 carry
    references, respectively, and that channels 3 and 4 run forward in time, while channels
    1 and 2 run reversed. Not all experiments need use all of the channels.
    
    Args:
            exp_times:      Array of generic variable time for given sequence
            sequence:       The pulsed experiment to run
            n:              For multi-pi pulse sequences, number of repetitions
            pi_time:        Pi pulse time
            pi_half_time:   Pi/2 pulse time (due to imperfections in equipment, not necessarily pi_time/2)
    """

    REQUIRED_DEVICES = ['sg', 'pulses', 'urixyz'] 
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}

    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'channel1':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default':'ctr1',
            },        
        ## sampling rate must be more than 1/read_window (we think)
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 0.6,
            },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 2.87e9
        },
        'power':{
            'type': float,
            'default': -20,
        },
        ## these are your tau_times
        'expTimesStart':{
            'type': float,
            'units': 's',
            'default': 5e-8
        },
        'expTimesStop':{
            'type': float,
            'units': 's',
            'default': 1e-4
        },
        'expTimesIter':{
            'type': int,
            'positive': True,
            'default': 21
        },
        'typeRange':{
            'type': list,
            'items': list(['geomspace', 'linspace']),
            'default': 'geomspace',
        },
        "sequence":{
            'type': list,
            'items': list(['CPMG_Norm', 'XY8_Norm', 'YY8_Norm']),#,'AidanCPMG','AidanXY8','AidanYY8']),#'CPMG_Norm', 'XY8_Norm', 'YY8_Norm', 
            'default': 'CPMG_Norm',
        },
        # "n":{
        #     'type': int,
        #     'default': 1,
        #     'nonnegative': True,
        # },
        ## this is in the form of a list because it's how the code works.
        ## we got it from Jonathan. It will let you run a ramsey,
        ## hahn echo, and high length CPMG back to back in the same analysis.
        ## our math might not be set up to handle that yet.
        "CPMG_n":{
            'type': str,
            'default': '[1]',
        },
        "pi_time_x":{
            'type': float,
            'default': 150e-9,
            'suffix': ' s',
            'units': "s"
        },
        "pi_time_y":{
            'type': float,
            'default': 150e-9,
            'suffix': ' s',
            'units': "s"
        },
        "pi_half_time_x":{
            'type': float,
            'default': 75e-9,
            'suffix': ' s',
            'units': "s"
        },
        "pi_half_time_y":{
            'type': float,
            'default': 75e-9,
            'suffix': ' s',
            'units': "s"
        },
        'init_time':{
            'type': float,
            'default': 5.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'clock_time':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'aom_lag':{
            'type': float,
            'default': .030e-6,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 1.5e-7,
            'suffix': ' s',
            'units': 's'
        },
        'heat_decay':{
            'type': float,
            'default': 1e-4,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_time':{
            'type': float,
            'default': 6e-7,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'data_download':{
            'type': bool,
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
    }

    def main(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, power,\
                    init_time, aom_lag, clock_time, readout_time, singlet_time,heat_decay, buffer_time, expTimesStart, expTimesStop, expTimesIter, typeRange,\
                    sequence, CPMG_n, pi_time_x, pi_time_y, pi_half_time_x, pi_half_time_y, timeout, \
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial, \
                    z_initial, xyz_step,count_step_shrink,starting_point):
        ## this will count however many sweeps have gone for doing feedback.
        ## we repeat the cpmg sweeps. this is how often the plot updates.
        for sweep in self.progress(range(sweeps)):
            
            # # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                print('feedback')
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
                # time.sleep(1)
            
            print('n_runs:', self.run_ct) # time per sweep 
            print('time per read:', self.time_per_point * self.data_ct)
            print('time per experiment:', self.time_per_point * self.data_ct * sweeps)
            print('tau range:', [int(round(exp_time)) for exp_time in self.exp_times])
            print('actual tau used:', )
            ## mw time sweep. if a series of "n" is given, step through
            for j, pi_ctr in enumerate(self.n_list):
                self.seqs = self.all_seqs[j]
                
                # # signal_pi is the PL counts for the signal and background for bright and dark states
                signal_pi = self.read(self.run_ct, self.data_ct, self.buffers, 0) # time_per_point / total time
                
                """
                tomorrow I will adjust tau times automatically.
                """
                
                #print('start acquiring')
                if sequence in ('CPMG_Norm', 'XY8_Norm', 'YY8_Norm'):
                    self.acquire({
                        'sequence': sequence,
                        'n': pi_ctr,
                        ## sweep_idx is which plot update it is. 
                        ## run_ct records how many runs of the sequence are done each sweep.
                        'sweep_idx': sweep,
                        'run_ct': self.run_ct,
                        ## unfortunately, we cannot acquire numpy arrays.
                        ## therefore we convert time and counts to lists.
                        't': [float(e)*1e-3 for e in self.exp_times],
                        #'t': [float((e + self.pi_pulse_durations).to('us').m) for e in exp_times],
                        'f': frequency,
                        'power': power,
                        'w': [float(e) for e in signal_pi[2]], #'signalRead'
                        'x': [float(e) for e in signal_pi[3]], #'signalNorm'
                        'y': [float(e) for e in signal_pi[0]], #'bkgdRead'
                        'z': [float(e) for e in signal_pi[1]], #'bkgdNorm'
                        ## these are the normalization constants I will be using
                        ## they are taken for each sweep, not each run_ct.
                        # 'norm_zero': float(signal_pi[4][0]),
                        # 'norm_one': float(signal_pi[4][1]),
                    })
                # elif sequence in ('AidanCPMG', 'AidanXY8', 'AidanYY8'):
                    # self.acquire({
                        # 'sequence': sequence,
                        # 'n': pi_ctr,
                        # ## sweep_idx is which plot update it is. 
                        # ## run_ct records how many runs of the sequence are done each sweep.
                        # 'sweep_idx': sweep,
                        # 'run_ct': self.run_ct,
                        # ## unfortunately, we cannot acquire numpy arrays.
                        # ## therefore we convert time and counts to lists.
                        # 't': [float(e)*1e-3 for e in self.exp_times],
                        # #'t': [float((e + self.pi_pulse_durations).to('us').m) for e in exp_times],
                        # 'f': frequency,
                        # 'power': power,
                        # 'a': [float(e) for e in signal_pi[1]], #'dark_sig'
                        # 'b': [float(e) for e in signal_pi[0]], #'bright_sig'
                        # ## these are the normalization constants I will be using
                        # ## they are taken for each sweep, not each run_ct.
                        # 'norm_zero': float(signal_pi[2][0]),
                        # 'norm_one': float(signal_pi[2][1]),
                    # })
                #print('finished acquiring')

    def initialize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, power,\
                    init_time, aom_lag, clock_time, readout_time, singlet_time,heat_decay, buffer_time, expTimesStart, expTimesStop, expTimesIter, typeRange,\
                    sequence, CPMG_n, pi_time_x, pi_time_y, pi_half_time_x, pi_half_time_y, timeout, \
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial, \
                    z_initial, xyz_step,count_step_shrink,starting_point):
        
        # parameters
        self.timeout = timeout
        self.sequence = sequence # string choosing CPMG, Echo, etc.
        ## t_p_p and sampling rate should have some dependency on each other
        ## however, setting the sampling rate too low doesn't seem to disrupt the data.
        self.time_per_point = time_per_point
        self.sampling_rate = sampling_rate.to('Hz').m
        # # if sampling_rate.to('Hz').m < 1/readout_time.to('s').m:
            # # print('sampling rate must be equal or larger than 1/readout_time')
            # # return
        ## self.data_ct is our number of data points.
        if typeRange == 'geomspace':
            self.exp_times = np.geomspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are log spaced.')
        else:
            self.exp_times = np.linspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are linearly spaced.')
        print('\n the rise of exp_times:', self.exp_times[0], 'and the fall of exp_times:', self.exp_times[-1])
        self.data_ct = len(self.exp_times)   
        if aom_lag < clock_time:
            raise("your laser lag must be longer than the clock pulse duration")
        ###############################################################################################################################
        ## failsafe: make sure that pulse buffer is less than one million.  
        ## 
        self.n_list = eval(CPMG_n)        
        
        if self.n_list == []: # in case of a ramsey sequence it should be n = [0]
            self.n_list = [0]
            
        self.max_n = max(self.n_list)
        #print(self.max_n)
        
        ## setupSR has 10, n = 1 adds 1, n = 2 adds 3, n = 3 adds 5, but echo has the same as echorev, has 3 + 2 + n(0, 1, 3, 5, 7)
        ## these are hard coded because I do not think there's an efficient way to get this information before we setup pulses.
        if self.max_n == 0:
            self.max_pulses = 2*10 + 2*(5)
        else:
            self.max_pulses = 2*10 + 2*(8*(self.max_n) + 1)
        print('self.max_pulses:', self.max_pulses)
        print('self.data_ct:', self.data_ct)
        print('self.max_pulses x self.data_ct = ', self.max_pulses*self.data_ct)
        if self.max_pulses*self.data_ct > 1e6:
            raise('too many pulses for too many data points sweeping overflows the pulse streamer')
            return
        ##
        ###############################################################################################################################
        ## we prime CPMG and then make a function 
        ## so that we get the proper pulse dictionary
        ## in the 'self.n_list'
        self.time   = 0
        def getTimeCPMG(num_pi_pulses, pi_duration = pi_time_y):
            self.time = num_pi_pulses * pi_duration
        
        ## variable controlling xy8 or yy8 time calculation
        timeOctoPulseYY = 8 * pi_time_y
        timeOctoPulseXY = 4 * pi_time_x + 4 * pi_time_y
        ## we create a dictionary to count the number of pi pulses
        piPulseCtrDict = {'AidanCPMG': pi_time_y,
                          'AidanXY8': timeOctoPulseXY,
                          'AidanYY8': timeOctoPulseYY,
                          'CPMG_Norm': pi_time_y,
                          'XY8_Norm': timeOctoPulseXY,
                          'YY8_Norm': timeOctoPulseYY,
                          }
        
        ## now, we add sequences to a list, in case we want to run multiple 
        ## multiple, as in Ramsey and/or Hahn and/or many pulsed CPMG.
        ## in this function we declare the variable that gives us our pi pulse times
        self.all_seqs = []
        for i in self.n_list: # can create sequences with n = [1,3,5,...]
            getTimeCPMG(i, piPulseCtrDict[sequence])
            ## this 'n' character only affects CPMG, not XY8 or YY8
            ## therefore, this only registers how many pulse sequences to setup with xy8 or yy8.
            self.setup_pulses(sequence,self.exp_times,pi_time_y,pi_time_x,pi_half_time_y,pi_half_time_x,i, \
                singlet_time,init_time,aom_lag,clock_time,readout_time,heat_decay, buffer_time)
            self.all_seqs.append(self.seqs) # array of all sequences according to n, where
                                            # each sequence is an array according to exp_times
        
        ## note: self.run_ct has been set.
        ## self.run_ct is how many runs for one point of the sequence.
        ## self.run_ct is also how many runs for each sequence.
        
        ## define buffer for data collection ## DAQ
        #import pdb; pdb.set_trace()
        ## we only set up CPMG and CPMG_Norm for now. later, we must add T1 measurements.
        # # # # # if sequence == 'CPMG':
            # # # # # self.buffer_size = 8* self.data_ct * self.run_ct# 8 ticks per 1 seq 
        if sequence in ('CPMG_Norm', 'XY8_Norm', 'YY8_Norm'):
            buffer_size = (8 * self.data_ct) * self.run_ct
            ##self.num_signal is used in read
            self.num_signal = 4
        # elif sequence in ('AidanCPMG', 'AidanXY8', 'AidanYY8'):
            #here, we create the buffer for T2 measurements, since they both have two read windows.
            # buffer_size = (4 * self.data_ct + 4) * self.run_ct
            ##print('buffer_size in initialize', self.buffer_size)
            # self.num_signal = 2
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32) # data buffer 
        
        self.buffers = [ni_ctr_sample_buffer]
        
        ## create channels list and check that there are no repeats
        self.channel = channel1
        # if len(set(self.channels)) != len(self.channels):
            # raise RuntimeError('counter channels must be different')
        
        ## initialize super class
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate,data_download) #time_per_point

        ## set signal generator parameters
        self.sg.rf_amplitude = power
        self.sg.frequency = frequency
        
        return
    
    ## divide buffer to different experiments
    def math(self, read_data):
        if self.sequence in ('CPMG_Norm', 'XY8_Norm', 'YY8_Norm'):
            ## with the norm, we cannot take all four read windows
            ## otherwise, our normalization pulses at the end of each run
            ## become interwoven with our read windows
            average_buffer = np.empty(8 * self.data_ct)
            ## so, we sum up all our data for our read windows.
            for i in range(8 * self.data_ct): 
              average_buffer[i] = np.sum(read_data[i::(8 * self.data_ct)])
            ###norm_buffer = np.empty(2,self.run_ct)
            ## now, we can isolate the normalization pulses.
            # norm_zero_one = [np.sum(read_data[(8 * self.data_ct + 3)::(8 * self.data_ct + 4)]) - np.sum(read_data[(8 * self.data_ct + 2)::(8 * self.data_ct + 4)]),
                             # np.sum(read_data[(8 * self.data_ct + 1)::(8 * self.data_ct + 4)]) - np.sum(read_data[(8 * self.data_ct + 0)::(8 * self.data_ct + 4)])]
            ## we have found the normalizaiton, now we make sure to divide our data into read windows.
            bkgdRead = np.empty(self.data_ct); bkgdNorm = np.empty(self.data_ct); signalRead = np.empty(self.data_ct); signalNorm = np.empty(self.data_ct)
            bkgdRead = average_buffer[1::8] - average_buffer[0::8]
            bkgdNorm = average_buffer[3::8] - average_buffer[2::8]
            signalRead = average_buffer[5::8] - average_buffer[4::8]
            signalNorm = average_buffer[7::8] - average_buffer[6::8]
            ## we once again return in the order of chronology of the pulse sequence.
            signal = [bkgdRead, bkgdNorm, signalRead, signalNorm]
            return signal
            
        # elif self.sequence in ('AidanCPMG', 'AidanXY8', 'AidanYY8'):
            # average_buffer = np.empty(4 * self.data_ct)
            # so, we sum up all our data for our read windows.
            # for i in range(4 * self.data_ct): 
              # average_buffer[i] = np.sum(read_data[i::(4 * self.data_ct + 4)])
            ##norm_buffer = np.empty(2,self.run_ct)
            # now, we can isolate the normalization pulses.
            # norm_zero_one = [np.sum(read_data[(4 * self.data_ct + 3)::(4 * self.data_ct + 4)]) - np.sum(read_data[(4 * self.data_ct + 2)::(4 * self.data_ct + 4)]),
                             # np.sum(read_data[(4 * self.data_ct + 1)::(4 * self.data_ct + 4)]) - np.sum(read_data[(4 * self.data_ct + 0)::(4 * self.data_ct + 4)])]
            # we have found the normalizaiton, now we make sure to divide our data into read windows.
            # dark_S = np.empty(self.data_ct); bright_S = np.empty(self.data_ct)
            # bright_S = average_buffer[1::4] - average_buffer[0::4]
            # dark_S = average_buffer[3::4] - average_buffer[2::4]
            # we once again return in the order of chronology of the pulse sequence.
            # signal = [bright_S, dark_S, norm_zero_one]
            # return signal
              
    def finalize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, power,\
                    init_time, aom_lag, clock_time, readout_time, singlet_time,heat_decay, buffer_time, expTimesStart, expTimesStop, expTimesIter, typeRange,\
                    sequence, CPMG_n, pi_time_x, pi_time_y, pi_half_time_x, pi_half_time_y, timeout, \
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial, \
                    z_initial, xyz_step,count_step_shrink,starting_point):
                    
        ## everything finalizes like everything else.
        super().finalize(device, self.buffers, PS_clk_channel,sampling_rate,data_download)#time_per_point, 
        
        return

    def setup_pulses(self,sequence,exp_times,pi_time_y,pi_time_x,pi_half_time_y,pi_half_time_x,\
                     n,singlet_time,init_time,aom_lag,clock_time,readout_time,heat_decay, buffer_time):
        """Create swabian pulse sequence.
        The sequence selected in PARAMS is created. Not all parameters are used
        in every sequence, e.g., n is not used for T1 sequences.
        Each sequence has a two-branch setup and reference readouts.
        The computed ratio scales the collected data by 1/(readout duty cycle),
        so signals across experiments with the same readout time
        are directly comparable.
        """
        print('now in setup pulses funtion')
        self.pulses.laser_time = int(round(init_time.to("ns").m))
        self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        self.pulses.readout_time = int(round(readout_time.to("ns").m))
        self.pulses.laser_buf = int(round(buffer_time.to("ns").m))#self.pulses.mw_wait = int(round(buffer_time.to("ns").m))
        self.pulses.heat_decay = int(round(heat_decay.to("ns").m))
        self.pulses.clock_time = int(round(clock_time.to("ns").m))
        self.pulses.singlet_decay = int(round(singlet_time.to("ns").m))
        exp_times_ns = [int(round(exp_time)) for exp_time in exp_times]
            
        pulseSequenceDict = {'AidanCPMG': 'self.pulses.AidanCPMG(exp_times_ns, pi_time_y, pi_half_time_x, n)',
                             'AidanXY8': 'self.pulses.AidanXY8(exp_times_ns, pi_time_y, pi_time_x, pi_half_time_x)',
                             'AidanYY8': 'self.pulses.AidanYY8(exp_times_ns, pi_time_y, pi_half_time_x)',
                             'CPMG_Norm': 'self.pulses.CPMG_Norm(exp_times_ns, pi_time_y, pi_half_time_x, n)',
                             'XY8_Norm': 'self.pulses.XY8_Norm(exp_times_ns, pi_time_y, pi_time_x, pi_half_time_x, n)',
                             'YY8_Norm': 'self.pulses.YY8_Norm(exp_times_ns, pi_time_y, pi_half_time_y, n)',
                             }
        #print(pulseSequenceDict['AidanCPMG'])
        self.seqs = eval(pulseSequenceDict[sequence])
        print(self.seqs)
        self.ratio_Aidan = self.pulses.total_time / (2 * self.pulses.readout_time)
        self.ratio_norm = self.pulses.total_time / (4 * self.pulses.readout_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m * self.data_ct/self.pulses.total_time))
        print('total time is:', self.pulses.total_time, 'n_runs is:', self.run_ct)  

    @PlotFormatInit(LinePlotWidget, ['latest', 'latest_norm', 'average','diff_avg','norm_diff_avg', 'signal'])
    def init_format(p):
        p.xlabel = 'time (us)'
        p.ylabel = 'PL (cts/s)'
    

    ## plots the latest data for all four channels of CPMG
    @Plot1D
    def latest(df, cache):
        latest_data = df[(df.n==df.n[-1]) & (df.sweep_idx == df.sweep_idx.max())] 
        return {
                'ms=1': [latest_data.t[0], latest_data.w[0]],
                #'dark_bg': [latest_data.t[0], latest_data.x[0][::-1]],
                'ms=0': [latest_data.t[0], latest_data.y[0]],
                #'bright_bg': [latest_data.t[0], latest_data.z[0]],
                }

    @Plot1D
    def latest_norm(df, cache):
        latest_data = df[(df.n==df.n[-1]) & (df.sweep_idx == df.sweep_idx.max())] 
        ## we normalize before latest.
        signal = latest_data.w[0]/latest_data.x[0]
        background = latest_data.y[0]/latest_data.z[0]#[(x - latest_data.norm_one[0])/(latest_data.norm_zero[0] - latest_data.norm_one[0]) for x in list(latest_data.x)[0][::-1]]
        #bright_sig = [(y - latest_data.norm_one[0])/(latest_data.norm_zero[0] - latest_data.norm_one[0]) for y in list(latest_data.y)[0]]
        #bright_bg = [(z - latest_data.norm_one[0])/(latest_data.norm_zero[0] - latest_data.norm_one[0]) for z in list(latest_data.z)[0]]
        return {
               'ms=1': [latest_data.t[0], list(signal)],#list(dark_sig)],
               'ms=0': [latest_data.t[0], list(background)],#list(dark_bg)],
               # 'bright_sig': [latest_data.t[0], list(bright_sig)],
               # 'bright_bg': [latest_data.t[0], list(bright_bg)],
               }
               
    @Plot1D
    def average(df, cache):
        frame = df[df.n==df.n[-1]]
        ## we sum across all sweeps and divide by all sweeps
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))            
        ## we flip the dark because we go from max to minimum taus.
        print('average plot finishing')
        signal = avg_w/avg_x; background = avg_y/avg_z
        return {
            'ms=1': [list(df.t)[0], list(signal)],
            'ms=0': [list(df.t)[0], list(background)],
        }
        
    @Plot1D
    def signal(df, cache):
        frame = df#[df.n==df.n[-1]]
        ## we plot only the signals
        avg_w = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        
        
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_y = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_y += frame.y[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_y[point_num] = sum_y / len(list(frame.y))
            
        return {
            'dark_sig': [list(df.t)[0], list(avg_w)],       
            'bright_sig': [list(df.t)[0], list(avg_y)],     
        }
    

    @Plot1D
    def diff_avg(df, cache):
    ## plot_return is a different way to accomplish the same thing above.
    ## we take the average, then the difference, we reverse the dark
    ## then we plot that difference.

    ##note: we flip the dark so the tau times line up.
    #plot_return = {}
    #for i in df.n:
        frame = df#[df.n==i]
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))
        # diff12 = (np.array(avg_w) - np.array(avg_x)) # DARK
        # diff34 = (np.array(avg_y) - np.array(avg_z)) # BRIGHT            
        ## we flip the echo_Rev in our sequence, which sets up our dark state. 
        ## our first read is in the dark, and it's useless data. we also drop the last time.
        # diff12 = list(diff12)[::-1]
        label = 'bright - dark diff '# + str(i)
        print('one cycle of diff_avg')
        #plot_return.update({label: [list(df.t)[0], list(avg_y - avg_w)]})        
        #return plot_return
        return {label: [list(df.t)[0], list(avg_y - avg_w)]}
      
    @Plot1D
    def norm_diff_avg(df, cache):
    ## plot_return is a different way to accomplish the same thing above.
    ## we take the average, then the difference, we reverse the dark
    ## then we plot that difference.

    ##note: we flip the dark so the tau times line up.
    #plot_return = {}
    #for i in df.n:
        frame = df#[df.n==i]
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))
        # diff12 = (np.array(avg_w) - np.array(avg_x)) # DARK
        # diff34 = (np.array(avg_y) - np.array(avg_z)) # BRIGHT            
        ## we flip the echo_Rev in our sequence, which sets up our dark state. 
        ## our first read is in the dark, and it's useless data. we also drop the last time.
        # diff12 = list(diff12)[::-1]
        label = 'bright - dark diff '# + str(i)
        print('one cycle of diff_avg')
        #plot_return.update({label: [list(df.t)[0], list(avg_y - avg_w)]})        
        #return plot_return
        return {label: [list(df.t)[0], list(avg_y/avg_z - avg_w/avg_x)]}
        
        # ## we normalize the previous graph.
        # # plot_return = {}
        # # for i in df.n:
        # frame = df#[df.n==i]
        # avg_w = np.empty(len(list(frame.w[0])))
        # avg_x = np.empty(len(list(frame.w[0])))
        # avg_y = np.empty(len(list(frame.w[0])))
        # avg_z = np.empty(len(list(frame.w[0])))
        # for point_num in range(len(list(frame.w[0]))):
            # sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            # for a in range(len(list(frame.w))):
                # sum_w += frame.w[a][point_num]
                # sum_x += frame.x[a][point_num]
                # sum_y += frame.y[a][point_num]
                # sum_z += frame.z[a][point_num]
            # avg_w[point_num] = sum_w / len(list(frame.w))
            # avg_x[point_num] = sum_x / len(list(frame.x))
            # avg_y[point_num] = sum_y / len(list(frame.y))
            # avg_z[point_num] = sum_z / len(list(frame.z))
        # avg_sig = avg_w/avg_x; avg_bkgd = avg_y/avg_z
        # dark_sig = [(w - frame.norm_one[0])/(frame.norm_zero[0] - frame.norm_one[0]) for w in list(avg_w)]
        # dark_bg = [(x - frame.norm_one[0])/(frame.norm_zero[0] - frame.norm_one[0]) for x in list(avg_x)]
        # bright_sig = [(y - frame.norm_one[0])/(frame.norm_zero[0] - frame.norm_one[0]) for y in list(avg_y)]
        # bright_bg = [(z - frame.norm_one[0])/(frame.norm_zero[0] - frame.norm_one[0]) for z in list(avg_z)]
        # # diff12 = (np.array(dark_sig) - np.array(dark_bg)) # DARK
        # # diff34 = (np.array(bright_sig) - np.array(bright_bg)) # BRIGHT            
        # # diff12 = list(diff12)[::-1]
        # diff = avg_bkgd - avg_sig
        # label = 'bright - dark diff '# + str(i)
        # print('one cycle of norm_diff_avg')
        # #plot_return.update({label: [list(df.t)[0], list(diff)]})        
        # #return plot_return
        # return {label: [list(df.t)[0], list(diff)]}

    @Plot1D
    def Sig_Peaks(df, cache):
        import scipy as sp
        from scipy import signal
        ## plot_return is a different way to accomplish the same thing above.
        ## we take the average, then the difference, we reverse the dark
        ## then we plot that difference.

        ##note: we flip the dark so the tau times line up.
        #plot_return = {}
        #for i in df.n:
        frame = df#[df.n==i]
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))
        # diff12 = (np.array(avg_w) - np.array(avg_x)) # DARK
        # diff34 = (np.array(avg_y) - np.array(avg_z)) # BRIGHT            
        ## we flip the echo_Rev in our sequence, which sets up our dark state. 
        ## our first read is in the dark, and it's useless data. we also drop the last time.
        # diff12 = list(diff12)[::-1]

        n=30
        sigDiff = avg_y - avg_w
        print('sigDiff:',sigDiff)
        peaksArray=sp.signal.find_peaks(sigDiff, height=None, threshold=0, distance=3, prominence=None, width=None, wlen=None, rel_height=0.5, plateau_size=None)
        peaks=[]
        peaks.append(list(peaksArray[0]))
        print('peaks:',peaks)
        print('peaks[0]:',peaks[0])
        for i in range(len(peaks[0])):
            print('peaks value ',i,': ',sigDiff[peaks[0][i]])
        
        while peaks[0][-1]>=n: #print('peaks[0][-1]:', peaks[0][-1])
            peaks[0].pop()
            print('peaks[0][-1] after popping:', peaks[0][-1])
        
        sig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tsig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tarray=np.array(list(df.t)[0])
        sig[0]=max(sigDiff)#sigDiff[0]
        tsig[0]=tarray[0]
        print('sig0:',sig)
        print('tsig0:',tsig)
        tsig[len(peaks[0])+1::]=tarray[n::]
        sig[len(peaks[0])+1::]=sigDiff[n::]
        print('tarray:',tarray)
        for i in range(len(peaks[0])):
            sig[i+1]=sigDiff[peaks[0][i]]
            tsig[i+1]=tarray[peaks[0][i]]
        print('sig:',sig)
        print('tsig:',tsig)
        
    #    for value in sigDiff[n::]:
    #        if value in sig:
    #            print('replaced ', value,' at index', np.where(sig == value), ' with zero')
    #            sig[np.where(sig == value)] = 0

        labels = ['brigh-dark sig','bright - dark peaks']# + str(i)
        print('one cycle of diff_avg')
        #plot_return.update({label: [list(df.t)[0], list(avg_y - avg_w)]})        
        #return plot_return
        return {labels[1]: [tsig, sig],labels[0]:[list(df.t)[0], list(sigDiff)]}

    @Plot1D
    def Norm_Peaks(df, cache):
        import scipy as sp
        from scipy import signal
        ## plot_return is a different way to accomplish the same thing above.
        ## we take the average, then the difference, we reverse the dark
        ## then we plot that difference.

        ##note: we flip the dark so the tau times line up.
        #plot_return = {}
        #for i in df.n:
        frame = df#[df.n==i]
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))
        # diff12 = (np.array(avg_w) - np.array(avg_x)) # DARK
        # diff34 = (np.array(avg_y) - np.array(avg_z)) # BRIGHT            
        ## we flip the echo_Rev in our sequence, which sets up our dark state. 
        ## our first read is in the dark, and it's useless data. we also drop the last time.
        # diff12 = list(diff12)[::-1]

        n=30
        sigDiff = avg_y/avg_z - avg_w/avg_x
        print('sigDiff:',sigDiff)
        peaksArray=sp.signal.find_peaks(sigDiff, height=None, threshold=0, distance=3, prominence=None, width=None, wlen=None, rel_height=0.5, plateau_size=None)
        peaks=[]
        peaks.append(list(peaksArray[0]))
        print('peaks:',peaks)
        print('peaks[0]:',peaks[0])
        for i in range(len(peaks[0])):
            print('peaks value ',i,': ',sigDiff[peaks[0][i]])
        
        while peaks[0][-1]>=n: #print('peaks[0][-1]:', peaks[0][-1])
            peaks[0].pop()
            print('peaks[0][-1] after popping:', peaks[0][-1])
        
        sig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tsig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tarray=np.array(list(df.t)[0])
        sig[0]=max(sigDiff)#sigDiff[0]
        tsig[0]=tarray[0]
        print('sig0:',sig)
        print('tsig0:',tsig)
        tsig[len(peaks[0])+1::]=tarray[n::]
        sig[len(peaks[0])+1::]=sigDiff[n::]
        print('tarray:',tarray)
        for i in range(len(peaks[0])):
            sig[i+1]=sigDiff[peaks[0][i]]
            tsig[i+1]=tarray[peaks[0][i]]
        print('sig:',sig)
        print('tsig:',tsig)
        
    #    for value in sigDiff[n::]:
    #        if value in sig:
    #            print('replaced ', value,' at index', np.where(sig == value), ' with zero')
    #            sig[np.where(sig == value)] = 0

        labels = ['brigh-dark sig','bright - dark peaks']# + str(i)
        print('one cycle of diff_avg')
        #plot_return.update({label: [list(df.t)[0], list(avg_y - avg_w)]})        
        #return plot_return
        return {labels[1]: [tsig, sig],labels[0]:[list(df.t)[0], list(sigDiff)]}

    @Plot1D
    def Weighted_diff_avg(df, cache):
        import scipy as sp
        from scipy import signal
        ## plot_return is a different way to accomplish the same thing above.
        ## we take the average, then the difference, we reverse the dark
        ## then we plot that difference.

        ##note: we flip the dark so the tau times line up.
        #plot_return = {}
        #for i in df.n:
        frame = df#[df.n==i]
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))
        # diff12 = (np.array(avg_w) - np.array(avg_x)) # DARK
        # diff34 = (np.array(avg_y) - np.array(avg_z)) # BRIGHT            
        ## we flip the echo_Rev in our sequence, which sets up our dark state. 
        ## our first read is in the dark, and it's useless data. we also drop the last time.
        # diff12 = list(diff12)[::-1]

        n=5
        sigDiff = (avg_y - avg_w)/(avg_y + avg_w)
        #sigDiff[13]=sigDiff[14]
        print('sigDiff:',sigDiff)
        peaksArray=sp.signal.find_peaks(sigDiff, height=None, threshold=0, distance=3, prominence=None, width=None, wlen=None, rel_height=0.5, plateau_size=None)
        peaks=[]
        peaks.append(list(peaksArray[0]))
        print('peaks:',peaks)
        print('peaks[0]:',peaks[0])
        for i in range(len(peaks[0])):
            print('peaks value ',i,': ',sigDiff[peaks[0][i]])

        while peaks[0][-1]>=n: #print('peaks[0][-1]:', peaks[0][-1])
            peaks[0].pop()
            #print('peaks[0][-1] after popping:', peaks[0][-1])

        sig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tsig=np.zeros(len(peaks[0])+1+len(avg_y[n::]))
        tarray=np.array(list(df.t)[0])
        sig[0]=max(sigDiff)#sigDiff[0]
        tsig[0]=tarray[0]
        print('sig0:',sig)
        print('tsig0:',tsig)
        tsig[len(peaks[0])+1::]=tarray[n::]
        sig[len(peaks[0])+1::]=sigDiff[n::]
        print('tarray:',tarray)
        for i in range(len(peaks[0])):
            sig[i+1]=sigDiff[peaks[0][i]]
            tsig[i+1]=tarray[peaks[0][i]]
        print('sig:',sig)
        print('tsig:',tsig)

    #    for value in sigDiff[n::]:
    #        if value in sig:
    #            print('replaced ', value,' at index', np.where(sig == value), ' with zero')
    #            sig[np.where(sig == value)] = 0

        labels = ['brigh-dark sig']#,'bright - dark peaks']# + str(i)
        print('one cycle of diff_avg')
        #plot_return.update({label: [list(df.t)[0], list(avg_y - avg_w)]})        
        #return plot_return
        return {labels[0]: [tarray+0.022*1472, list(sigDiff)]}#{labels[1]: [tsig+0.022*512, sig],labels[0]:[tarray+0.022*512, list(sigDiff)]}
        
class T1SwabianSpyrelet(BaseFeedbackSpyrelet):
    """Runs a selected pulsed, time-dependent characterization or sensing experiment
    e.g., T1, T2*, T2 Hahn, T2 CPMG, T2 XY..
    The frequency, power, pi pulse, and pi/2 pulse times are fixed, and the experiment time
    (either full evolution time or pi pulse separation, depending on type of measurement)
    is varied.
    A two-branch setup is combined with IQ modulation to improve readout contrast and maintain
    a constant duty cycle for all excitations. As the experiment steps through exp_times,
    the time variable in the first branch increases and in the second branch decreases
    (note this only works for linear time steps). One branch reads out the bright state population
    and the other reads out the dark state population (either by applying a pi pulse before readout
    or applying a +-pi/2 pulse at the end of a T2-like sequence). The data from the reverse-time
    branch can then be reversed and subtracted from the forward-time branch to give full spin contrast.
    Sequences also have reference readouts to track slow drift during an experiment.
    The default plotting assumes that channels 2 and 4 carry signal and channels 1 and 3 carry
    references, respectively, and that channels 3 and 4 run forward in time, while channels
    1 and 2 run reversed. Not all experiments need use all of the channels.
    
    Args:
            exp_times:      Array of generic variable time for given sequence
            sequence:       The pulsed experiment to run
            n:              For multi-pi pulse sequences, number of repetitions
            pi_time:        Pi pulse time
            pi_half_time:   Pi/2 pulse time (due to imperfections in equipment, not necessarily pi_time/2)
    """

    REQUIRED_DEVICES = ['sg', 'pulses', 'urixyz'] 
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}

    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'channel':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default':'ctr1',
            },        
        ## sampling rate must be more than 1/read_window (we think)
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1.5,
            },
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 2.4e9
        },
        'power':{
            'type': float,
            'default': -20,
        },
        ## which T1
        'sequence': {
            'type': list,
            'items': list(['Optical', 'OpticalDutyCycle', 'MW']),
            'default': 'MW',
        },
        ## these are your tau_times
        'expTimesStart':{
            'type': float,
            'units': 's',
            'default': 5e-8
        },
        'expTimesStop':{
            'type': float,
            'units': 's',
            'default': 1e-3
        },
        'expTimesIter':{
            'type': int,
            'positive': True,
            'default': 21
        },
        'typeRange':{
            'type': list,
            'items': list(['geomspace', 'linspace']),
            'default': 'geomspace',
        },
            
            
        # # 'exp_times':{
            # # 'type': range,
            # # 'units': 'ns',
            # # 'default': {'func': 'linspace',
                        # # 'start': 0e-9,
                        # # 'stop': 1e-6,
                        # # 'num': 21},
        # # },
        # "n":{
        #     'type': int,
        #     'default': 1,
        #     'nonnegative': True,
        # },
        ## this is in the form of a list because it's how the code works.
        ## we got it from Jonathan. It will let you run a ramsey,
        ## hahn echo, and high length CPMG back to back in the same analysis.
        ## our math might not be set up to handle that yet.
        "piTimeMW":{
            'type': float,
            'default': 50e-9,
            'suffix': ' s',
            'units': "s"
        },
        'init_time':{
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'clock_time':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'aom_lag':{
            'type': float,
            'default': .030e-6,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 1.5e-7,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_time':{
            'type': float,
            'default': 6e-7,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'data_download':{
            'type': bool,
        },
        'feedback':{
            'type': bool,
            'default': True,
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
    }

    def main(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
                    power, sequence, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, 
                    typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        ## this will count however many sweeps have gone for doing feedback.
        ## we repeat the cpmg sweeps. this is how often the plot updates.
        for sweep in self.progress(range(sweeps)):
            
            # # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                print('feedback')
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
                # time.sleep(1)
            
            print('n_runs:', self.run_ct) ## number of runs per sweep. Determined by time per point 
            print('set time per read (s):', self.time_per_point*1e-9 * self.data_ct)
            print('time per experiment:', self.time_per_point*1e-9 * self.data_ct * sweeps)
            ## mw time sweep. if a series of "n" is given, step through
            # # signal_pi is the PL counts for the signal and background for bright and dark states
            signal_pi = self.read(self.run_ct, self.data_ct, self.buffers, 0) # time_per_point / total time
                                                                              # need to fix buffer index to use read for multiple buffers
            
            """
            tomorrow I will adjust tau times automatically.
            """
            
            #print('start acquiring')
            if sequence == 'MW':
                self.acquire({
                    ## sweep_idx is which plot update it is. 
                    ## run_ct records how many runs of the sequence are done each sweep.
                    'sweep_idx': sweep,
                    'run_ct': self.run_ct,
                    ## unfortunately, we cannot acquire numpy arrays.
                    ## therefore we convert time and counts to lists.
                    't': [float(e) * 1e-3 for e in self.exp_times],
                    'f': frequency,
                    'power': power,
                    'a': [float(e) for e in signal_pi[0]], #brightDecay
                    'b': [float(e) for e in signal_pi[1]], #darkDecay
                })
            else:
                self.acquire({
                    ## sweep_idx is which plot update it is. 
                    ## run_ct records how many runs of the sequence are done each sweep.
                    'sweep_idx': sweep,
                    'run_ct': self.run_ct,
                    ## unfortunately, we cannot acquire numpy arrays.
                    ## therefore we convert time and counts to lists.
                    't': [float(e) * 1e-3 for e in self.exp_times],
                    'f': frequency,
                    'power': power,
                    'a': [float(e) for e in signal_pi], #brightDecay
                })
            #print('finished acquiring')

    def initialize(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
                    power, sequence, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, 
                    typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
        #import pdb; pdb.set_trace()
        # parameters
        self.timeout = timeout
        self.sequence = sequence
        ## t_p_p and sampling rate should have some dependency on each other
        ## however, setting the sampling rate too low doesn't seem to disrupt the data.
        self.time_per_point = time_per_point
        self.sampling_rate = sampling_rate.to('Hz').m
        if typeRange == 'geomspace':
            self.exp_times = np.geomspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are log spaced.')
        else:
            self.exp_times = np.linspace(round(expTimesStart.to('ns').m), round(expTimesStop.to('ns').m), expTimesIter)
            print('\n tau times are linearly spaced.')
        print('\n the rise of exp_times:', self.exp_times[0], 'and the fall of exp_times:', self.exp_times[-1])
        # # if sampling_rate.to('Hz').m < 1/readout_time.to('s').m:
            # # print('sampling rate must be equal or larger than 1/readout_time')
            # # return
        ## self.data_ct is our number of data points.
        self.data_ct = len(self.exp_times)   
        if aom_lag < clock_time:
            raise("your laser lag must be longer than the clock pulse duration")
        self.sg.frequency = frequency
        ## this 'n' character only affects CPMG, not XY8 or YY8
        ## therefore, this only registers how many pulse sequences to setup with xy8 or yy8.
        #import pdb; pdb.set_trace()
        self.setup_pulses(self.exp_times, piTimeMW, singlet_time, sequence, 
                          init_time, aom_lag, clock_time, readout_time, buffer_time)
        
        ## note: self.run_ct has been set.
        ## self.run_ct is how many runs for one point of the sequence.
        ## self.run_ct is also how many runs for each sequence.
        
        # # # # # if sequence == 'CPMG':
            # # # # # self.buffer_size = 8* self.data_ct * self.run_ct# 8 ticks per 1 seq 
        
        self.num_signal = 2 if sequence == 'MW' else 1 ##self.num_signal is used in read and is determined by how many 
                                                       ##reading windows there are per sequence
        buffer_size = 2 * self.num_signal * self.data_ct * self.run_ct ##buffer size is the total data points collected from the APD.
                                                                       ## 2 per reading window (num_signal) * number of points (data_ct)
                                                                       ## * number of times we sum and avg each run (run_ct) for one sweep
                                                                       ## each sweep is its own read function and hence have a new buffer 
        
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32) ## we create a data buffer with lngth = buffer_size 
        
        self.buffers = [ni_ctr_sample_buffer] ##we append each data buffer to the buffers array in case we are reading from multiple channels
                                              ## currently we only use one channel
        
        
        ## create channels list and check that there are no repeats
        self.channel = channel
        # if len(set(self.channels)) != len(self.channels):
            # raise RuntimeError('counter channels must be different')
        
        ## set signal generator parameters
        self.sg.rf_amplitude = power
        ## initialize super class
        super().initialize(device, self.buffers, PS_clk_channel,
                            time_per_point, sampling_rate,data_download)
                            
        return
    
    ## divide buffer to different experiments
    def math(self, read_data):
        if self.sequence == 'MW':
            ## with the norm, we cannot take all four read windows
            ## otherwise, our normalization pulses at the end of each run
            ## become interwoven with our read windows
            average_buffer = np.empty(4 * self.data_ct)## creating average_buffer with length- number of reading 
                                                       ## windows for a full run 
            ## so, we sum up all our data for our runs according to each read window.
            for i in range(4 * self.data_ct): 
              average_buffer[i] = np.sum(read_data[i::(4 * self.data_ct)])
            ###norm_buffer = np.empty(2,self.run_ct)
            ## now, we can isolate the normalization pulses.
            
            ## we have found the normalizaiton, now we make sure to divide our data into read windows.
            brightDecay = average_buffer[1::4] - average_buffer[0::4]
            darkDecay = average_buffer[3::4] - average_buffer[2::4]
            ## we once again return in the order of chronology of the pulse sequence.
            signal = [brightDecay, darkDecay]
            return signal
        else:
            average_buffer = np.empty(2 * self.data_ct)
            for i in range(2 * self.data_ct): 
              average_buffer[i] = np.sum(read_data[i::(2 * self.data_ct)])
            print('Avg Buffer length:', len(average_buffer))
            print('Avg Buffer:', average_buffer)
            print('Avg Buffer tick1:', average_buffer[1::2])
            print('Avg Buffer tick2:', average_buffer[0::2])
            brightDecay = average_buffer[1::2] - average_buffer[0::2]
            return brightDecay
              
    def finalize(self, device, channel, PS_clk_channel, sampling_rate, time_per_point, sweeps, frequency, 
                    power, sequence, init_time, aom_lag, clock_time, readout_time, singlet_time, buffer_time, 
                    typeRange, expTimesStart, expTimesStop, expTimesIter, piTimeMW, timeout,
                    data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    z_initial, xyz_step,count_step_shrink,starting_point):
                    
        ## everything finalizes like everything else.
        super().finalize(device, self.buffers, PS_clk_channel,
                            time_per_point, sampling_rate,data_download)
        
        return

    def setup_pulses(self, exp_times,piTimeMW, singlet_time, sequence,
                     init_time,aom_lag,clock_time,readout_time, buffer_time):
        """Create swabian pulse sequence.
        The sequence selected in PARAMS is created. Not all parameters are used
        in every sequence, e.g., n is not used for T1 sequences.
        Each sequence has a two-branch setup and reference readouts.
        The computed ratio scales the collected data by 1/(readout duty cycle),
        so signals across experiments with the same readout time
        are directly comparable.
        """
        print('now in setup pulses function')
        self.pulses.laser_time = int(round(init_time.to("ns").m))
        self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        self.pulses.readout_time = int(round(readout_time.to("ns").m))
        self.pulses.mw_wait = int(round(buffer_time.to("ns").m))
        self.pulses.clock_time = int(round(clock_time.to("ns").m))
        self.pulses.singlet_decay = int(round(singlet_time.to("ns").m))
        exp_times_ns = [int(exp_time) for exp_time in exp_times]
        if sequence == 'Optical':
            self.seqs = self.pulses.allOpticalT1_new(exp_times_ns, dutyCycle = False)
        elif sequence == 'OpticalDutyCycle':
            self.seqs = self.pulses.allOpticalT1_new(exp_times_ns, dutyCycle = True)
        else:
            self.seqs = self.pulses.MWT1_new(exp_times_ns, piTimeMW, 'x')
        #print(self.seqs)
        # run count is total time to run the sequence over period of each sequence.
        print('\n', self.time_per_point, self.data_ct, self.pulses.total_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m * self.data_ct/self.pulses.total_time))
        print('total time is:', self.pulses.total_time, 'n_runs is:', self.run_ct)  

    @PlotFormatInit(LinePlotWidget, ['latest', 'average','four_ch_diff_avg_sig_bg','no_trace_diff_avg', 'signal'])
    def init_format(p):
        p.xlabel = 'time (us)'
        p.ylabel = 'PL (cts/s)'
    
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_diff_avg','norm_diff_avg_not_trace'])#['latest', 'avg'])        
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(255,255,255,10), width=5)

    ## plots the latest data for all four channels of CPMG
    @Plot1D
    def latestMW(df, cache):
        latest_data = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
                'brightDecay': [latest_data.t[0], latest_data.a[0]],
                'darkDecay': [latest_data.t[0], latest_data.b[0]],
                }
               
    @Plot1D
    def latestOpt(df, cache):
        latest_data = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
                'brightDecay': [latest_data.t[0], latest_data.a[0]],
                }

               
    @Plot1D
    def averageMW(df, cache):
        frame = df
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        avg_b = np.empty(len(list(frame.b[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0; sum_b = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
                sum_b += frame.b[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a))
            avg_b[point_num] = sum_b / len(list(frame.b))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'brightDecay': [list(df.t)[0], list(avg_a)],
            'darkDecay': [list(df.t)[0], list(avg_b)],
        }    
        
    @Plot1D
    def avgOpt(df, cache):
        frame = df
        
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a)) 
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        ## a is dark sig, b is bright sig
        return {
            'brightDecay': [list(df.t)[0], list(avg_a)],
        }    
        
        
    @Plot1D
    def averageMWDiff(df, cache):
        # time_stemp = datetime.now().strftime("%Y_%m_%d%_%H_%M_%S")
        # name = "T1Swabian"
        # print("data is saved in:", name+time_stemp)
        frame = df
        ## we normalize the averages.
        avg_a = np.empty(len(list(frame.a[0])))
        avg_b = np.empty(len(list(frame.b[0])))
        for point_num in range(len(list(frame.a[0]))):
            sum_a = 0; sum_b = 0
            for run in range(len(list(frame.a))):
                sum_a += frame.a[run][point_num]
                sum_b += frame.b[run][point_num]
            avg_a[point_num] = sum_a / len(list(frame.a))
            avg_b[point_num] = sum_b / len(list(frame.b))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'bright - dark': [list(df.t)[0], list((avg_a - avg_b)/(avg_a + avg_b))],
        }    
        
        
class ReadoutCalibrationSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = ['sg', 'pulses']
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}
    """
    This spyrelet calibrates the length of the readout window,
    the position of the readout window in the initialization,
    and the buffer after the pi pulse.
    
    In the respective spyrelets:
    readout_time is unused.
    everything is used.
    and buffer_time is unused.
    The read function works the same way as Rabi and CPMG.
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
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1,
            },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': float,
            'units':'Hz',
            'default': 2.87e9
        },
        'power':{
            'type': float,
            'default': -20,
        },
        "pi_time":{
            'type': float,
            'default': 150e-9,
            'suffix': ' s',
            'units': "s"
        },
        'sequence':{
            'type': list,
            'items': list(['readout','init','MW_buffer', 'MW_sweep']),
        },
        ## we vary readout in readout, the prior initialization time in 'init',
        ## and the buffer after the MW in 'MW_buffer'
        'vary_times':{
            'type': range,
            'units': "ns",
            'default': {'func': 'linspace',
                        'start': 5e-9,
                        'stop': 500e-9,
                        'num': 21},
        },
        ## readout_time is unused in readout calibration
        "readout_time":{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': "s"
        },
        ## this is the overall laser time.
        "initialization":{
            'type': float,
            'default': 5.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        "aom_lag":{
            'type': float,
            'default': 30e-9,
            'suffix': ' s',
            'units': "s"
        },
        ## buffer_time is unused in mw_buffer calibration
        "buffer_time":{
            'type': float,
            'default': .15e-6,
            'suffix': ' s',
            'units': "s"
        },
        "singlet_time":{
            'type': float,
            'default': .6e-6,
            'suffix': ' s',
            'units': "s"
        },
        "clockpulse_duration":{
            'type': float,
            'default': 1e-8,
            'suffix': ' s',
            'units': "s"
        },
        'feedback':{
            'type': bool,
        },
        'dozfb':{
            'type': bool,
            'default': True
        },
        'sweeps_til_fb':{
            'type': int,
            'default': 10,
        },
        'data_download':{
            'type':bool,
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
    }

    def main(self,device,channel1,sampling_rate,time_per_point,sweeps,\
             frequency,power,pi_time,PS_clk_channel,sequence,vary_times,\
             initialization,readout_time,aom_lag,buffer_time,clockpulse_duration,\
             singlet_time,data_download,feedback, dozfb, sweeps_til_fb,\
             x_initial,y_initial,z_initial,starting_point,xyz_step,count_step_shrink):
        ## we print how many times we stream the sequence
        ## how much time until it plots
        ## and how much time it will take to finish, without human intervention.
        print('n_runs:', self.run_ct)
        print('time per read:', self.time_per_point * self.data_ct)
        print('time per experiment:', self.time_per_point * self.data_ct * sweeps)
        for sweep in self.progress(range(sweeps)):
            ## feedback
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            print('before_read')
            ctrs_rates = self.read(self.run_ct, self.data_ct, self.buffers, 0)#)
            print('read_finished')
            ## we do not bother acquiring the sequence, since we'll just make different graphs
            ## they won't work between the sequences but they should all work indiivdually.
            if self.sequence == 'MW_buffer':
                self.acquire({
                    'sweep_idx': sweep,
                    ## the times cannot be quantities.
                    't': [e.to('ns').m for e in vary_times],
                    'f': frequency,
                    'power': power,
                    'w': ctrs_rates[0]*self.ratio,
                    'x': ctrs_rates[1]*self.ratio,
                    'y': ctrs_rates[2]*self.ratio,
                    'z': ctrs_rates[3]*self.ratio,
                })
            elif self.sequence == 'readout':
                self.acquire({
                    'sweep_idx': sweep,
                    't': [e.to('ns').m for e in vary_times],
                    'f': frequency,
                    'power': power,
                    'dark': ctrs_rates[0]*self.ratio,
                    'bright': ctrs_rates[1]*self.ratio,
                })
            else:
                self.acquire({
                    'sweep_idx': sweep,
                    't': [e.to('ns').m for e in vary_times],
                    'f': frequency,
                    'power': power,
                    'counts': ctrs_rates[0]*self.ratio,
                })

    def math(self, array):
        ## array = self.ni_ctr_sample_buffer
        if self.sequence == 'MW_buffer':
            ## we call these groups for simplification
            ## in our case, in MW Buffer, the dark state ms=1 will be group_1 and 2
            group_1 = array[1::8] - array[0::8] 
            group_2 = array[3::8] - array[2::8] 
            group_3 = array[5::8] - array[4::8] 
            group_4 = array[7::8] - array[6::8]
            dark_S = np.empty(self.data_ct); dark_R = np.empty(self.data_ct); bright_S = np.empty(self.data_ct); bright_R = np.empty(self.data_ct)
            for i in range(self.data_ct):
                dark_S[i] = np.sum(group_1[i::self.data_ct])
                dark_R[i] = np.sum(group_2[i::self.data_ct])
                bright_S[i] = np.sum(group_3[i::self.data_ct])
                bright_R[i] = np.sum(group_4[i::self.data_ct])            
            return [dark_S,dark_R,bright_S,bright_R]      
        elif self.sequence in ('init', 'MW_sweep'):
            ## here we only have one read window. simple.
            buffer = array[1::2] - array[::2]
            init_chan = np.empty(self.data_ct)
            for i in range(self.data_ct):
                init_chan[i] = np.sum(buffer[i::self.data_ct])
            return [init_chan]
        else:
            ## divide buffer to ms = 1 and ms = 0 state.
            delta_buffer_start = array[1::4] - array[0::4] 
            delta_buffer_end = array[3::4] - array[2::4] 
            final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
            ## we sum all the counts in ms = 0 and ms = 1
            for i in range(self.data_ct):
                final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
                final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
            return [final_data_dark, final_data_bright]
            
    def initialize(self,device,channel1,sampling_rate,time_per_point,sweeps,\
             frequency,power,pi_time,PS_clk_channel,sequence,vary_times,\
             initialization,readout_time,aom_lag,buffer_time,clockpulse_duration,\
             singlet_time,data_download,feedback, dozfb, sweeps_til_fb,\
             x_initial,y_initial,z_initial,starting_point,xyz_step,count_step_shrink):
        print('now in initialize')
        self.channel = channel1
        ## to make sure super() works we set this x_initial y_initial for right now.
        ## these only work with the spatial feedback which has not yet been selected.
        
        self.timeout = 60
        ## save the sequence so we can access it across multiple functions.
        self.sequence = sequence
        ## buffer stuff
        self.data_ct = len(vary_times)
        self.time_per_point = time_per_point
        
        #####################################################
        ## verify that the spyrelet won't destruct.
        if aom_lag < clockpulse_duration:
            raise("your laser lag must be longer than the clock pulse duration")
        ######################################################
        
        self.setup_pulses(sequence,pi_time,initialization, singlet_time,\
                          vary_times,aom_lag,buffer_time,clockpulse_duration,\
                          readout_time)
        ## buffer_size is our array of points, num_signal is each read_window
        if self.sequence == 'MW_buffer':
            buffer_size = 8 * self.data_ct * self.run_ct
            self.num_signal = 4
        elif self.sequence in ('init', 'MW_sweep'):
            buffer_size = 2 * self.data_ct * self.run_ct
            self.num_signal = 1
        else:
            buffer_size = 4 * self.data_ct * self.run_ct
            self.num_signal = 2
        ## creates the buffer using stuff from setup_pulses
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32) # data buffer 
        
        print('defining self.buffers')
        self.buffers = [ni_ctr_sample_buffer]
        
        ## instrument stuff.
        super().initialize(device, self.buffers, PS_clk_channel,
                            time_per_point, sampling_rate, data_download)
        self.sg.rf_amplitude = power
        self.sg.frequency = frequency
            
        return

    def finalize(self,device,channel1,sampling_rate,time_per_point,sweeps,\
             frequency,power,pi_time,PS_clk_channel,sequence,vary_times,\
             initialization,readout_time,aom_lag,buffer_time,clockpulse_duration,\
             singlet_time,data_download,feedback, dozfb, sweeps_til_fb,\
             x_initial,y_initial,z_initial,starting_point,xyz_step,count_step_shrink):
        ## making sure super() works
        super().finalize(device, self.buffers, PS_clk_channel,
                            time_per_point, sampling_rate, data_download)
        return

    def setup_pulses(self, sequence,pi_time,initialization, singlet_time,\
                     vary_times,aom_lag,buffer_time,clockpulse_duration,\
                     readout_time):
        vary_times_ns = [int(round(vary_time.to('ns').m)) for vary_time in vary_times]
        self.pulses.clock_time = int(round(clockpulse_duration.to("ns").m))
        self.pulses.singlet_decay = int(round(singlet_time.to("ns").m))
        self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        self.pulses.laser_time = int(round(initialization.to("ns").m))
        if sequence == 'MW_buffer':
            """ Required fields:
                laser_time, pi time, aom lag, readout window, clock pulse time, singlet time.
                sweeping MW_buffer time
                
                other_time gives the read window time.
            """
            self.pulses.readout_time = int(readout_time.to("ns").m)
            self.seqs = self.pulses.MW_buffer(vary_times_ns,pi_time)
            ## I put 4 because there are 4 read windows.
            self.ratio = self.pulses.total_time / (4 * self.pulses.readout_time)
        elif sequence == 'MW_sweep':
            """ Required fields:
                laser_time, pi time, aom lag, readout window, clock pulse time, singlet time, buffer time
                sweeping laser start time
                
                other_time gives the read window time.
            """
            self.pulses.read_time = int(round(readout_time.to("ns").m))
            self.seqs = self.pulses.MWSweepPattern(vary_times_ns, pi_time)
            self.ratio = self.pulses.total_time / self.pulses.readout_time
        elif sequence == 'init':
            """ Required fields:
                laser_time, pi time, aom lag, readout window, clock pulse time, singlet time, laser buffer
                sweeping initialization before read.
                
                other_time gives the read window time.
            """
            ## condition given by how the pulses sequences are coded.
            ## to fix this, we'd have to make the sequence too complex.
            if vary_times[-1].to('ns').m + self.pulses.readout_time > self.pulses.laser_time:
                raise("Error: init time before reading is too long for given total initialization time")
                
            self.pulses.readout_time = int(readout_time.to("ns").m)
            self.pulses.laser_buf = int(buffer_time.to("ns").m)
            self.seqs = self.pulses.initcal(vary_times_ns,pi_time)
            ## I put 1 because there is one read window.
            self.ratio = self.pulses.total_time / (1 * self.pulses.readout_time)
        elif sequence == 'readout':
            """ Required fields:
                laser_time, pi time, aom lag, clock pulse time, singlet time, laser buffer
                sweeping readout window
                
                other_time is unused.
            """
            ## we need the read_window big enough to measure
            if vary_times[0] < clockpulse_duration:
                raise("minimum readout window is too short to clock the read period")
            
            self.pulses.laser_buf = int(buffer_time.to("ns").m)
            self.seqs = self.pulses.readout(vary_times_ns,pi_time)
            ## I put 2 because there are two read windows.
            self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
            
        self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.total_time))

    @PlotFormatInit(LinePlotWidget, ['MW_buffer_latest', 'MW_buffer_avg','MW_buffer_avg_diff',
                                     'init_latest','init_avg','readout_latest','readout_average',
                                     'readout_average_diff'])
    def init_format(p):
        p.xlabel = 'time (ns)'
        p.ylabel = 'PL (cts/s)'
    ##adapated from CPMG, MW_buffer
    @Plot1D
    def MW_buffer_latest(df, cache):
        latest_data = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
                'dark_sig': [latest_data.t[0], latest_data.w[0]],
                'dark_bg': [latest_data.t[0], latest_data.x[0]],
                'bright_sig': [latest_data.t[0], latest_data.y[0]],
                'bright_bg': [latest_data.t[0], latest_data.z[0]],
                }

    @Plot1D
    def MW_buffer_avg(df, cache):
        frame = df
        
        avg_w = np.empty(len(list(frame.w[0])))
        avg_x = np.empty(len(list(frame.w[0])))
        avg_y = np.empty(len(list(frame.w[0])))
        avg_z = np.empty(len(list(frame.w[0])))
        for point_num in range(len(list(frame.w[0]))):
            sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
            for a in range(len(list(frame.w))):
                sum_w += frame.w[a][point_num]
                sum_x += frame.x[a][point_num]
                sum_y += frame.y[a][point_num]
                sum_z += frame.z[a][point_num]
            avg_w[point_num] = sum_w / len(list(frame.w))
            avg_x[point_num] = sum_x / len(list(frame.x))
            avg_y[point_num] = sum_y / len(list(frame.y))
            avg_z[point_num] = sum_z / len(list(frame.z))            
            
        return {
            'dark_sig': [list(df.t)[0], list(avg_w)],
            'dark_bg': [list(df.t)[0], list(avg_x)],
            'bright_sig': [list(df.t)[0], list(avg_y)],
            'bright_bg': [list(df.t)[0], list(avg_z)]
        }
    @Plot1D
    def MW_buffer_avg_diff(df, cache):
        plot_return = {}
        for i in range(df.sweep_idx.max()+1):
            frame = df
            avg_w = np.empty(len(list(frame.w[0])))
            avg_x = np.empty(len(list(frame.w[0])))
            avg_y = np.empty(len(list(frame.w[0])))
            avg_z = np.empty(len(list(frame.w[0])))
            for point_num in range(len(list(frame.w[0]))):
                sum_w = 0; sum_x = 0; sum_y = 0; sum_z = 0
                for a in range(len(list(frame.w))):
                    sum_w += frame.w[a][point_num]
                    sum_x += frame.x[a][point_num]
                    sum_y += frame.y[a][point_num]
                    sum_z += frame.z[a][point_num]
                avg_w[point_num] = sum_w / len(list(frame.w))
                avg_x[point_num] = sum_x / len(list(frame.x))
                avg_y[point_num] = sum_y / len(list(frame.y))
                avg_z[point_num] = sum_z / len(list(frame.z))
            diff12 = (np.array(list(avg_w)) - np.array(list(avg_x))) # DARK
            diff34 = (np.array(list(avg_y)) - np.array(list(avg_z))) # BRIGHT            
            diff12 = list(diff12)[::-1]
            label = 'bright - dark diff ' + str(i)
            plot_return.update({label: [list(df.t)[0], diff34 - diff12]})        
        return plot_return
    ## init plots (adapted from CPMG, there might be a better way)
    @Plot1D
    def init_latest(df, cache):
        frame = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
            'counts': [list(frame.t)[0], list(frame.counts)[0]],
        }
    @Plot1D
    def init_avg(df, cache):
        frame = df
        
        avg_counts = np.empty(len(list(frame.counts[0])))
        for point_num in range(len(list(frame.counts[0]))):
            sum_counts = 0
            for a in range(len(list(frame.counts))):
                sum_counts += frame.counts[a][point_num]
            avg_counts[point_num] = sum_counts / len(list(frame.counts))
            
        return {
            'counts': [list(df.t)[0], list(avg_counts)],
        }
    ## readout plots (adapated from Rabi)
    @Plot1D
    def readout_latest(df, cache):
        frame = df[(df.sweep_idx == df.sweep_idx.max())] 
        return {
            'bright': [list(frame.t)[0], list(frame.bright)[0]],
            'dark': [list(frame.t)[0], list(frame.dark)[0]],
        }
    @Plot1D
    def readout_average(df, cache):
        frame = df
        avg_bright = np.empty(len(list(frame.bright[0])))
        avg_dark = np.empty(len(list(frame.dark[0])))
        for point_num in range(len(list(frame.bright[0]))):
            sum_bright = 0; sum_dark = 0
            for a in range(len(list(frame.bright))):
                sum_bright += frame.bright[a][point_num]
                sum_dark += frame.dark[a][point_num]
                #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_bright[point_num] = sum_bright / len(list(frame.bright))
            avg_dark[point_num] = sum_dark / len(list(frame.dark))
            
        print('finish data rearrangement')
        return {
            'bright': [list(df.t)[0], list(avg_bright)],
            'dark': [list(df.t)[0], list(avg_dark)],
        }
    @Plot1D
    def readout_average_diff(df, cache):
        frame = df
        avg_bright = np.empty(len(list(frame.bright[0])))
        avg_dark = np.empty(len(list(frame.dark[0])))
        for point_num in range(len(list(frame.bright[0]))):
            sum_bright = 0; sum_dark = 0
            for a in range(len(list(frame.bright))):
                sum_bright += frame.bright[a][point_num]
                sum_dark += frame.dark[a][point_num]
                #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            avg_bright[point_num] = sum_bright / len(list(frame.bright))
            avg_dark[point_num] = sum_dark / len(list(frame.dark))
            
        print('finish data rearrangement')
        return {
            'bright-dark': [list(df.t)[0], list(avg_bright - avg_dark)],
        }


class PlaylistODMRRabiTuneupSwabianSpyrelet(BaseFeedbackSpyrelet):
    """Runs ODMR and Rabi measurements, over multiple points
    as picked out in a spatial PL map. Separate powers are set for ODMR and Rabi.
    See ODMR and Rabi spyrelets for details.
    A sweep (of frequency or MW time) is run sub_sweeps times, then the laser
    is moved to the next point, etc. This happens sweeps times, so the total
    experiment sweeps at each point is actually sweeps*sub_sweeps. The spyrelet
    moves between points in this fashion so any long equipment drift affects
    all measurements.
    The parameters frequency, pi_pulse, pi_half_pulse, x_initial, and y_initial
    are setup as strings which, when evaluated in the code, are turned into unit-full
    lists. It is necessary that they are of the form "Q_(,'[unit]')"

    Args:
            sweeps:
            sub_sweeps:
            frequency:
            pi_time:
            pi_half_time:
            x_initial:
            y_initial:
    """
    REQUIRED_DEVICES = ['sg', 'pulses', 'urixyz']
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}

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
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        'time_per_point':{
            'type':float,
            'units': 's',
            'suffix': ' s',
            'default': 1,
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'sweeps_ODMR':{
            'type': int,
            'default': 10,
            'positive': True,
        },
        'sweeps_rabi':{
            'type': int,
            'default': 50,
            'positive': True,
        },
        'sub_sweeps':{
            'type': int,
            'default': 2,
            'positive': True,
        },
        'n_points':{
            'type': int,
            'default': 4,
            'positive': True,
        },
        'frequency':{ # for ODMR
            'type': range,
            'units':'GHz',
        },
        'power_odmr':{
            'type': float,
            'default': -20,
        },
        'power_rabi':{
            'type': float,
            'default': -20,
        },
        'mw_times':{
            'type': range,
            'units': 'ns',
            'default': {'func': 'linspace',
                        'start': 0e-9,
                        'stop': 1e-6,
                        'num': 21},
        },
        'pi_xy':{
            'type': list,
            'items': list(['x','y']),
            'default': 'x'
        },
        'probe_time': {
            'type': float,
            'default': 50e-6,
            'units': 's',
        },
        'init_time':{
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'aom_lag':{
            'type': float,
            'default': 30e-9,
            'suffix': ' s',
            'units': 's'
        },
        'clock_time':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_decay':{
            'type':float,
            'default': .6e-6,
            'suffix': ' s',
            'units': 's',
        },
        'buffer_time':{
            'type': float,
            'default': 0.15e-6,
            'suffix': ' s',
            'units': 's'
        },        
        'feedback': {
            'type': bool,
            'default': 1,
        },
        'dozfb': {
            'type': bool,
            'default': 1,
        },
        'x_initial':{
            # 'units': 'um',
            'type': str,
            'default': 'Q_([0,0,0],"um")',
        },
        'y_initial':{
            # 'units': 'um',
            'type': str,
            'default': 'Q_([0,0,0],"um")',
        },
        'z_initial':{
            # 'units': 'um',
            'type': str,
            'default': 'Q_([0,0,0],"um")',
        },
        'xyz_step':{
            'type': float,
            'units': 'm',            
            'default': 60e-9,
        },
        'shrink_every_x_iter':{
            'type': int,
            'default': 2,
        },
        'starting_point': {
            'type': list,
            'items': list(['user_input','current_position (ignore input)']),
            'default': 'current_position (ignore input)',
        },
        'ODMR_fit': {
            'type': list,
            'items': list(['odmr1_fitfn','odmr2_fitfn']),
        },
        'ODMR_f_guess': {
            'type': str,
            'default': 'Q_([2.85,2.886],"GHz")'
        },
        'rabi_T_guess': {
            'type': float,
            'default': 1e-6,
            'units': 'us',
        }
    }

    def main(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
            ## first perform ODMR sweeps until reach max or the fit is stable
            for sweep in self.progress(range(sweeps_ODMR)):
                if np.mean(self.odmr_done) == 1:
                    ## if all the fits are done, break the loop and continue to Rabi
                    ## this means the current point is the last point
                    break
                ## set the new xy position of the current nv.
                for self.pt in range(n_points):
                    if self.pt == 0 and sweep == 0:
                        x_diff_pt = 0
                        y_diff_pt = 0
                    elif self.pt == 0:
                        x_diff_pt = self.x_initial_list[0] - self.x_initial_list[-1]
                        y_diff_pt = self.y_initial_list[0] - self.y_initial_list[-1]
                    else:
                        x_diff_pt = self.x_initial_list[self.pt] - self.x_initial_list[self.pt-1]
                        y_diff_pt = self.y_initial_list[self.pt] - self.y_initial_list[self.pt-1]
                    self.x_initial = self.x_initial + x_diff_pt
                    self.y_initial = self.y_initial + y_diff_pt
                    #self.pulses.stream(self.pulses.Laser_On())
                    ## shorting loop to test rabi
                    # self.odmr_done[self.pt] = 1
                    # self.acquire({
                    #                 'sequence':         'ODMR',
                    #                 'point':            self.pt,
                    #                 'x_initial':        self.x_initial,
                    #                 'y_initial':        self.y_initial,
                    #                 'sweep_idx':        sweep*sub_sweeps,
                    #                 'point_sweep':      sweep,
                    #                 'power':            power_odmr,
                    #                 'f':                2.87e9,
                    #                 'x':                0,
                    #             })
                    # self.acquire({'point':self.pt, 'fit': 'ODMR', 'f_fit': Q_(2.868,'GHz')})
                    # self.frequencies[self.pt] = 2868000000
                    if self.odmr_done[self.pt] == 0:
                        ## if this point is not fit yet, measure
                        if feedback and sweep != 0:
                            self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink)
                            self.x_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x'])
                            self.y_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y'])     
                            self.z_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z'])
                            self.x_initial_list[self.pt] = self.x_initial
                            self.y_initial_list[self.pt] = self.y_initial
                            self.z_initial_list[self.pt] = self.z_initial
                        #self.x_initial, self.y_initial = self.run_feedback(1,1,self.z_sweeps,self.channels)
                        
                        for j in range(sub_sweeps):
                            for f in frequency:
                                try:
                                    self.sg.frequency = f # SG396 communication overhead of <1ms
                                except:
                                    raise RuntimeError('sg messed up')
                                ctrs_rates = self.read_odmr(math.ceil(len(self.buffers[0]/2)), self.buffers, 0)
                                self.acquire({
                                    'sequence':         'ODMR',
                                    'point':            self.pt,
                                    'x_initial':        self.x_initial,
                                    'y_initial':        self.y_initial,
                                    'z_initial':        self.z_initial,
                                    'sweep_idx':        sweep*sub_sweeps + j,
                                    'point_sweep':      sweep,
                                    'power':            power_odmr,
                                    'f':                f,
                                    'sig':              ctrs_rates[0],
                                    'ref':              ctrs_rates[1],
                                })
                            data = pd.DataFrame(self._data)
                            point_sweep = data[data.point == self.pt]
                            grouped = point_sweep.groupby('f')
                            xs = grouped.sig - grouped.ref
                            xs_averaged = xs.mean()
                            try:
                                if ODMR_fit == 'odmr1_fitfn':
                                    p0 = [5e5,-1e10,self.ODMR_f[0],5e6]
                                    popt, pcov = optimize.curve_fit(self.odmr1_fitfn, xs_averaged.index, xs_averaged, p0=p0)
                                elif ODMR_fit == 'odmr2_fitfn':
                                    p0 = [5e5,-1e10,self.ODMR_f[0],5e6,-1e10,self.ODMR_f[1],5e6]
                                    popt, pcov = optimize.curve_fit(self.odmr2_fitfn, xs_averaged.index, xs_averaged, p0=p0)
                                f1s = popt[2] # right now only checks precision of first peak
                                self.odmr_fits['p'+str(self.pt+1)].append(f1s)
                                if self.odmr_fits['p'+str(self.pt+1)].__len__() > 5:
                                    running_avg = np.mean(self.odmr_fits['p'+str(self.pt+1)][-6:-1])
                                    if abs((f1s-running_avg)/running_avg) < .0002:
                                        ## if the fitting has succeeded for this point, save the fit
                                        self.acquire({'point': self.pt, 'fit': 'ODMR', 'f_fit': Q_(f1s*1e-9,'GHz')})
                                        self.odmr_done[self.pt] = 1
                                        self.frequencies[self.pt] = f1s
                                print('it fit with f={}'.format(f1s))
                            except RuntimeError:
                                print('this curve did not fit. keep going.')
                        if sweep == sweeps_ODMR-1 and j == sub_sweeps-1:
                            ## if the fit has not succeeded by the last sweep, just save some courtesy value and move on
                            self.acquire({'point': self.pt, 'fit': 'ODMR', 'f_fit': 2.87e9})

            self.sg.rf_amplitude = power_rabi
            for sweep in self.progress(range(sweeps_rabi)):
                for self.pt in range(n_points):
                    if self.pt == 0:
                        ## ODMR ended at the last point
                        x_diff_pt = self.x_initial_list[0] - self.x_initial_list[-1]
                        y_diff_pt = self.y_initial_list[0] - self.y_initial_list[-1]
                    else:
                        x_diff_pt = self.x_initial_list[self.pt] - self.x_initial_list[self.pt-1]
                        y_diff_pt = self.y_initial_list[self.pt] - self.y_initial_list[self.pt-1]
                    self.x_initial = self.x_initial + x_diff_pt
                    self.y_initial = self.y_initial + y_diff_pt
                    #self.pulses.stream(self.pulses.Laser_On())
                    ## short for testing
                    # self.acquire({
                    #                 'sequence':         'rabi',
                    #                 'point':            self.pt,
                    #                 'x_initial':        self.x_initial,
                    #                 'y_initial':        self.y_initial,
                    #                 'sweep_idx':        sweep*sub_sweeps,
                    #                 'point_sweep':      sweep,
                    #                 'power':            power_rabi,
                    #                 'f':                self.frequencies[self.pt],
                    #                 't':                100,
                    #                 'x':                0,
                    #                 'y':                0,
                    #             })
                    # self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(1000,'ns'), 'p_fit': Q_(100,'ns'), \
                    #              't_pi': Q_(400,'ns'), 't_pi2': Q_(150,'ns')})
                    # self.rabi_done[self.pt] = 1
                    # self.periods[self.pt] = 1000
                    # self.phases[self.pt] = 100
                    if self.rabi_done[self.pt] == 0:
                        if feedback:
                            self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink)
                            self.x_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x'])
                            self.y_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y'])     
                            self.z_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z'])
                            self.x_initial_list[self.pt] = self.x_initial
                            self.y_initial_list[self.pt] = self.y_initial
                            self.z_initial_list[self.pt] = self.z_initial
                        try:
                            self.sg.frequency = self.frequencies[self.pt]
                        except:
                            raise RuntimeError('sg messed up')
                        ## mw time sweep
                        for j in range(sub_sweeps):
                            for i, t in enumerate(mw_times):
                                
                                ctrs_rates = self.read(self.run_ct, self.data_ct, self.buffers, 1)
                                self.acquire({
                                    'sequence':         'rabi',
                                    'point':            self.pt,
                                    'x_initial':        self.x_initial,
                                    'y_initial':        self.y_initial,
                                    'z_initial':        self.z_initial,
                                    'sweep_idx':        sweep*sub_sweeps + j,
                                    'point_sweep':      sweep,
                                    'power':            power_rabi,
                                    'f':                self.frequencies[self.pt],
                                    't':                t,
                                    'sig':              ctrs_rates[0],
                                    'ref':              ctrs_rates[1],
                                })
                            data = pd.DataFrame(self._data)
                            point_sweep = data[(data.sequence == 'rabi') & (data.point == self.pt)]
                            grouped = point_sweep.groupby('t')
                            xs = grouped.x
                            xs_averaged = xs.mean()
                            ys = grouped.y
                            ys_averaged = ys.mean()
                            try:
                                ## fit both signal and bg subtraction
                                p0sig = [rabi_T_guess.to('s').m,0,2e-6,1e3,1e5]
                                poptsig, pcovsig = optimize.curve_fit(self.rabi_fitfn, xs_averaged.index, xs_averaged, p0=p0sig)
                                Tssig = poptsig[0]
                                self.rabi_fits_sig['p'+str(self.pt+1)].append(Tssig)
                                
                                if self.rabi_fits_sig['p'+str(self.pt+1)].__len__() > 5:
                                    ## first check if fit with only signal is good
                                    running_avg = np.mean(self.rabi_fits_sig['p'+str(self.pt+1)][-6:-1])
                                    if abs((Tssig-running_avg)/running_avg) < .03:
                                        self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(Tssig*1e9,'ns'), 'p_fit': Q_(poptsig[1]*1e9,'ns'), \
                                                     't_pi': Q_((Tssig/2-poptsig[1])*1e9,'ns'), 't_pi2': Q_((Tssig/4-poptsig[1])*1e9,'ns')})
                                        self.rabi_done[self.pt] = 1
                                        self.periods[self.pt] = Tssig
                                        self.phases[self.pt] = poptsig[1]
                                print('it fit the signal with T={}'.format(Tssig))
                            except RuntimeError:
                                print('this curve did not fit with signal. keep going.')
                            try:
                                p0bg = [rabi_T_guess.to('s').m,0,2e-6,1e3,1e3]
                                poptbg, pcovbg = optimize.curve_fit(self.rabi_fitfn, xs_averaged.index, xs_averaged-ys_averaged, p0=p0bg)
                                Tsbg = poptbg[0]
                                self.rabi_fits_bg['p'+str(self.pt+1)].append(Tsbg)
                                if self.rabi_fits_bg['p'+str(self.pt+1)].__len__() > 5 and self.rabi_done[self.pt] == 0:
                                    ## then check with background subtracted
                                    running_avg = np.mean(self.rabi_fits_bg['p'+str(self.pt+1)][-6:-1])
                                    if abs((Tsbg-running_avg)/running_avg) < .03:
                                        ## if the fitting has succeeded for this point, save the fit
                                        self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(Tsbg*1e9,'ns'), 'p_fit': Q_(poptbg[1]*1e9,'ns'), \
                                                    't_pi': Q_((Tsbg/2-poptbg[1])*1e9,'ns'), 't_pi2': Q_((Tsbg/4-poptbg[1])*1e9,'ns')})
                                        self.rabi_done[self.pt] = 1
                                        self.periods[self.pt] = Tsbg
                                        self.phases[self.pt] = poptbg[1]
                                print('it fit signal - bg with T={}'.format(Tsbg))
                            except RuntimeError:
                                print('this curve did not fit with bg subtraction. keep going.')
                        ## update for rabi
                        if sweep == sweeps_rabi-1 and j == sub_sweeps-1:
                            ## if the fit has not succeeded by the last sweep, just save some courtesy value and move on
                            self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(1000,'ns'), 'p_fit': Q_(0,'ns'), \
                                        't_pi': Q_(500,'ns'), 't_pi2': Q_(250,'ns')})
                        

    def initialize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
        # self.all_seqs = []
        self.time_per_point
        self.setup_pulses_ODMR(clock_time, probe_time)
        odmr_buffer_size = math.floor(time_per_point/probe_time) + 1
        odmr_buffer = np.zeros(int(odmr_buffer_size), dtype = np.uint32)
        # for i in range(n_points):#self.pi_times.__len_()): must add param for number of points or figure out how to do this right
        self.setup_pulses(init_time,aom_lag,readout_time,clock_time,singlet_decay,buffer_time,mw_times,pi_xy)
        self.data_ct = len(self.mw_times)
        buffer_size = 4*self.data_ct * self.run_ct# ignore run_ct
        ## we set up the buffer and array we use to get our signal in self.read()
        rabi_buffer = np.zeros(int(buffer_size), dtype=np.uint32)
        
        self.buffers = [odmr_buffer, rabi_buffer]
        self.num_signal = 2
            # self.all_seqs.append(self.seqs)
        self.odmr_fits = {}
        self.rabi_fits_sig = {}
        self.rabi_fits_bg = {}
        ODMR_f = eval(ODMR_f_guess)
        self.ODMR_f = ODMR_f.to('Hz').m
        self.index = 0
        # self.f_guesses = {}
        for i in range(n_points):
            label = 'p' + str(i+1)
            self.odmr_fits[label] = []
            self.rabi_fits_sig[label] = []
            self.rabi_fits_bg[label] = []
        self.odmr_done = np.zeros(n_points)
        self.rabi_done = np.zeros(n_points)        
        self.frequencies = np.zeros(n_points)
        self.periods = np.zeros(n_points)
        self.phases = np.zeros(n_points)
        # for i in range(ODMR_f.__len__()):
        #     label = 'x0' + str(i+1)
        #     self.f_guesses[label] = ODMR_f[i]
        # if ODMR_fit == 'odmr1_fitfn':
        #     self.odmr_fit_func = self.odmr1_fitfn(x,**self.f_guesses)
        #     print(self.odmr_fit_func)
        # elif ODMR_fit == 'odmr2_fitfn':
        #     self.odmr_fit_func = self.odmr2_fitfn(**self.f_guesses)
        

        self.x_initial_list = eval(x_initial)
        self.y_initial_list = eval(y_initial)
        self.z_initial_list = eval(z_initial)
        self.x_initial = self.x_initial_list[0]
        self.y_initial = self.y_initial_list[0]
        self.z_initial = self.z_initial_list[0]
        if self.x_initial_list.__len__() != self.y_initial_list.__len__() or self.x_initial_list.__len__()!=self.z_initial_list.__len__():
            print('x_initial and y_initial must have the same number of coordinate')
            return
        ## create channels list and check that there are no repeats
        self.channel = channel1
        #'def initialize(self, device, channels, PS_clk_channel, time_per_point, sampling_rate, data_download):'
        super().initialize(device, self.buffers, PS_clk_channel, time_per_point, sampling_rate, data_download)

        self.sg.rf_amplitude = power_odmr
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
        
        return
        
    def finalize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
        super().finalize(device, self.buffers, PS_clk_channel, time_per_point, sampling_rate, data_download)
        #self.sg.rf_toggle = False
        #self.pulses.Pulser.reset()

        data = pd.DataFrame(self._data)
        print('fitted parameters: \n point\t x\t y\t ODMR sweeps\t freq\t rabi sweeps\t T\t t_pi\t t_pi/2')
        for i in range (n_points):
            ## debug this
            point_data = data[data.point==i]
            print(str(i)+'\t'+str(round(point_data[point_data.sequence=='rabi'].x_initial.values[-1]*1e6,1))+'um\t' \
                    +str(round(point_data[point_data.sequence=='rabi'].y_initial.values[-1]*1e6,1))+'um\t' \
                    +str(int(point_data[point_data.sequence=='ODMR'].sweep_idx.values[-1]))+'\t\t' \
                    +str(round(point_data[point_data.fit=='ODMR'].f_fit.values[-1]*1e-9,4))+'GHz\t' \
                    +str(int(point_data[point_data.sequence=='rabi'].sweep_idx.values[-1]))+'\t' \
                    +str(round(point_data[point_data.fit=='rabi'].T_fit.values[-1]*1e9))+'ns\t' \
                    +str(round(point_data[point_data.fit=='rabi'].t_pi.values[-1]*1e9))+'ns\t' \
                    +str(round(point_data[point_data.fit=='rabi'].t_pi2.values[-1]*1e9))+'ns\t' \
                    )

        return

    def math_odmr(self, array):
        delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
        sum1 = np.sum(delta_buffer[::2]) # MW on, but collects dark (autotriggers and collect starting the first tick)
        sum2 = np.sum(delta_buffer[1::2]) # MW off, but collect bright.
        
        print('delta_buffer:', delta_buffer)
        print('sum1:', sum1, 'sum2:', sum2)          
        return [sum1, sum2]
        
    def math(self, array):
        
        ## divide buffer to different experiments
        delta_buffer_start = array[1::4] - array[0::4] 
        delta_buffer_end = array[3::4] - array[2::4] 
        final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
        for i in range(self.data_ct):
            final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
            final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
        return [final_data_dark, final_data_bright]
        
    def odmr1_fitfn(self,x,b=5e5,a1=-1e10,x01=2.8e9,g1=5e6):
        return b + a1*g1/((x-x01)**2+(g1/2)**2)
    def odmr2_fitfn(self,x,b=5e5,a1=-1e10,x01=2.86e9,g1=5e6,a2=-1e10,x02=2.88e9,g2=5e6):
        return b + a1*g1/((x-x01)**2+(g1/2)**2) + a2*g2/((x-x02)**2+(g2/2)**2)
    def odmr_fitmany(self, x, b = 1, g=5e6, a1=-1e10,x1=2.5e9,a2=-1e10,x2=2.6e9,a3=-1e10,x3=2.7e9,a4=-1e10,x4=2.8e9):
        return b + a1*g/((x-x01)**2+(g/2)**2) + a2*g/((x-x02)**2+(g/2)**2) + a3*g/((x-x3)**2+(g/2)**2) + a4*g/((x-x4)**2+(g/2)**2)
    def rabi_fitfn(self,x,Tr=1e-6,p=0,Td=1e-2,A=1e3,B=-10e4):
        return A*(np.exp(-(x)/Td)*np.cos((2*np.pi*(x+p))/Tr))+B

    def setup_pulses_ODMR(self, clock_time, probe_time):
        """Create list of swabian pulse sequences
        In this case the pulse sequence is a single block that turns
        on the laser and MW excitation and opens a read channel 
        """
        self.pulses.clock_time = int(round(clock_time.to('ns').m))
        self.pulses.read_time = int(round(probe_time.to('ns').m))
        self.seq = self.pulses.CWUriMR()
        self.seqsODMR = self.seq #[self.seq]

    def setup_pulses(self,init_time,aom_lag,readout_time,clock_time, singlet_decay, buffer_time, mw_times,pi_xy):
        """Create list of swabian pulse sequences
        Each sequence has a different microwave excitation time.
        Both branches are equal lengths.
        The computed ratio scales the collected data by 1/(readout duty cycle),
        so signals across experiments with the same readout time
        are directly comparable.
        """
        self.pulses.singlet_decay = int(round(singlet_decay.to('ns').m))
        self.pulses.clock_time = int(round(clock_time.to('ns').m))
        self.pulses.laser_time = int(round(init_time.to("ns").magnitude))
        self.pulses.aom_lag = int(aom_lag.to("ns").magnitude)
        self.pulses.readout_time = int(readout_time.to("ns").magnitude)
        self.pulses.laser_buf = int(buffer_time.to("ns").magnitude)
        mw_times_ns = [int(round(mw_time.to('ns').m)) for mw_time in mw_times]
        self.seqs = self.pulses.PS_rabi(mw_times_ns,pi_xy)
        self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
        self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.time_one))

    @PlotFormatInit(LinePlotWidget, ['latestODMR','averageODMRs'])
    def init_format(p):
        p.xlabel = 'frequency (Hz)'
        p.ylabel = 'PL (cts/s)'

    @PlotFormatInit(LinePlotWidget, ['latestRabi','averageRabis','diff_averageRabis'])
    def init_format(p):
        p.xlabel = 'time (s)'
        p.ylabel = 'PL (cts/s)'
        
    @Plot1D
    def latestODMR(df, cache):
        latest_data = df[(df.point==df.point[-1]) & (df.point_sweep == df.point_sweep.max())]
        return {'ch1': [latest_data.f, latest_data.x]}

    @Plot1D
    def averageODMR(df, cache):
        plot_return = {}
        if df.point_sweep.max() != 0:
            for i in range(df.point.max()+1):
                grouped = df[(df.point==i) & (df.sequence=='ODMR')].groupby('f')
                xs = grouped.x
                xs_averaged = xs.mean()
                label = 'odmr avg' + str(i)
                plot_return.update({label: [xs_averaged.index, xs_averaged]})
        return plot_return

    @Plot1D
    def latestRabi(df, cache):
        latest_data = df[(df.point==df.point[-1]) & (df.point_sweep == df.point_sweep.max()) & (df.sequence=='rabi')]
        return {'ch1': [latest_data.t, latest_data.x],
                'ch2': [latest_data.t, latest_data.y]}
                
    @Plot1D
    def averageRabis(df, cache):
        plot_return = {}
        if df.point_sweep.max() != 0:
            for i in range(df.point.max()+1):
                grouped = df[(df.point==i) & (df.sequence=='rabi')].groupby('t')
                xs = grouped.x
                xs_averaged = xs.mean()
                label = 'rabi signal' + str(i)
                plot_return.update({label: [xs_averaged.index, xs_averaged]})
        return plot_return

    @Plot1D
    def diff_averageRabis(df, cache):
        plot_return = {}
        if df.point_sweep.max() != 0:
            for i in range(df.point.max()+1):
                grouped = df[(df.point==i) & (df.sequence=='rabi')].groupby('t')
                xs = grouped.x
                ys = grouped.y
                xs_averaged = xs.mean()
                ys_averaged = ys.mean()
                label = 'rabi diff' + str(i)
                plot_return.update({label: [xs_averaged.index, xs_averaged - ys_averaged]})
        return plot_return
        
class AOMLagSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        #'urixyz',
        'pulses',
    ]
    REQUIRED_SPYRELETS = {}
    PARAMS = {
        'counter_1': {
            'type': list,
            'items': list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default': 'ctr1',
        },
        'sweeps': {
            'type': int,
            'default': 100,
            'positive': True,
        },
        'gate_start': {
            'type': range,
            'units': "us",
            'default': {'func': 'linspace',
                        'start': 100e-9,
                        'stop': 10e-6,
                        'num': 51},
        },
        "probe_time": {
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        "gate_time": {
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': "s"
        },
        "laser_start": {
            'type': float,
            'default': 2e-6,
            'suffix': ' s',
            'units': "s"
        },
        "clockpulse_length": {
            'type': float,
            'default': 5e-9,
            'suffix': ' s',
            'units': "s"
        },
        'n_runs': {
            'type': int,
            'default': 10000,
            'positive': True,
        },
        'data_download': {
            'type': bool,
            'default': True,
        },
    }
    def main(self,sweeps,gate_time, counter_1, gate_start, probe_time, laser_start, clockpulse_length, n_runs, data_download):
        print('****************main****************')
        for sweep in self.progress(range(sweeps)):
            print('looping through gate start times:', gate_start)
            for i, t in enumerate(gate_start):
                t = int(round(t.to("ns").m))
                print('Currently at reading start time:', t) 
                sw_time = t*1e-3
                #print('reading start time in us:', sw_time) 
                
                self.ctr_tasks[self.index].start()
                #print('arming the trigger by streaming the tick sequence:', self.seq_tick)
                #self.pulses.stream(self.seq_tick, n_runs = 1)
                #self.pulses.Pulser.reset()
                #time.sleep(0.5)
                print('now starting to stream the seq:', self.seqs[i], 'this many times:', self.n_runs)
                print('the shape of buffer is', np.shape(self.buffers[self.index]), 'and the samps per chan is', self.val)
                self.pulses.stream(self.seqs[i], self.n_runs)
                self.streamers[self.index].read_many_sample_uint32(
                        self.buffers[self.index],
                        number_of_samples_per_channel= self.val #4*self.n_runs #nidaqmx.constants.READ_ALL_AVAILABLE #-1
                )
                print('now reading', 4*self.n_runs, 'into the predefined ni sample buffer')
                self.ctr_tasks[self.index].stop()
                self.pulses.Pulser.forceFinal()
                print('raw buffer:', self.buffers[self.index])
                print('raw buffer size:', len(self.buffers[self.index]))
                #for k in range(20):
                 #print(self.buffers[self.index][k])
                ctrs_start = self.buffers[self.index][1::4] - self.buffers[self.index][0::4]
                ctrs_end = self.buffers[self.index][3::4] - self.buffers[self.index][2::4]
                print('signal buffer:', ctrs_start)
                print('signal buffer size:', len(ctrs_start))
                print('background buffer:', ctrs_end)
                print('background buffer size:', len(ctrs_end))
                self.sum1 = np.sum(ctrs_start) # experiment 1: MW on (autotriggers and collect starting the first tick)
                self.sum2 = np.sum(ctrs_end)
                signal = int(self.sum1)-int(self.sum2)
                print('sum1:', self.sum1)
                print('sum2:', self.sum2)
                print('signal:', signal)
                print("done")
                
                self.acquire({
                    'sweep_idx': sweep,
                    't': sw_time,
                    'y': signal, #int(self.sum1) #, #ctrs_rates
                    'probe_time': probe_time.m,
                    'gate_time': gate_time.m,
                    'gate_start_array': [gate_start[0].m,gate_start[-1].m,len(gate_start)],
                    'laser_start': laser_start.m,
                    'n_runs': n_runs
                    #'y': dctrs[0][0]
                })
    def initialize(self, sweeps, gate_time, counter_1, gate_start, probe_time, laser_start, clockpulse_length, n_runs, data_download):
        print('****************initializing****************')
        ## setting up parameters
        self.ctr_tasks = list()
        self.streamers = []
        self.buffers = []
        self.ctrs = [counter_1]
        self.gate_start = [int(round(start_time.to('ns').m)) for start_time in gate_start]
        print('gate start times:', self.gate_start)
        self.clk_channel = '/Dev1/PFI0'
        self.rate = 1e7
        print('sampling rate:', self.rate)
        self.index = -1
        self.n_runs = n_runs
        self.val = 4*self.n_runs
        print('n_runs:', self.n_runs)
        self.ni_ctr_sample_buffer = np.zeros(int(self.val), dtype=np.uint32)#4*self.n_runs
       
       # if len(set(self.ctrs)) != len(self.ctrs):
            # raise RuntimeError('counter channels 1 and 2 must be different')
        
        ## setting up a read task per channel (currently only one channel)
        for i, ctr in enumerate(self.ctrs):
            self.ctr_tasks.append(nidaqmx.Task())#CounterInputTask('counter ch {}'.format(idx))
            print('created task:', self.ctr_tasks[i]) 
            ch = 'Dev1/' + ctr #CountEdgesChannel(ctr)
            self.ctr_tasks[i].ci_channels.add_ci_count_edges_chan(
                                        ch,
                                        edge=Edge.RISING,
                                        initial_count=0,
                                        count_direction=CountDirection.COUNT_UP
            )
            print('added:', ch, 'as a ci count edges channel')       
            
            self.ctr_tasks[i].timing.cfg_samp_clk_timing(
                                        self.rate,
                                        source = self.clk_channel,
                                        sample_mode=AcquisitionType.FINITE,
                                        samps_per_chan= self.val #4*self.n_runs
            )
            print('added:', self.clk_channel, 'as a timing source with max rate', self.rate)
            print('Ticking', 4*self.n_runs, 'times')
            
            # self.ctr_tasks[i].triggers.pause_trigger.dig_lvl_src = self.clk_channel
            # self.ctr_tasks[i].triggers.pause_trigger.dig_lvl_when = nidaqmx.constants.Level.LOW
            #print('set pause trigger for the task when the PS clock channel is LOW')
            
            ## setting the task to be triggered by the PS clock ticks
            # self.ctr_tasks[i].triggers.arm_start_trigger.trig_type = TriggerType.DIGITAL_EDGE
            # self.ctr_tasks[i].triggers.arm_start_trigger.dig_edge_edge = Edge.RISING
            # self.ctr_tasks[i].triggers.arm_start_trigger.dig_edge_src = self.clk_channel
            #print('setting arm trigger source to be:', self.clk_channel)
            
            ## defining the streaming object and buffer
            self.streamers.append(CounterReader(self.ctr_tasks[i].in_stream))
            self.buffers.append(self.ni_ctr_sample_buffer)
            #self.ctr_tasks[i].over_write = nidaqmx.constants.OverwriteMode.DO_NOT_OVERWRITE_UNREAD_SAMPLES
            
            ## starting task without triggering
            #self.ctr_tasks[i].start()
            #print('started the task, but it is not armed and clock is not ticking yet')
            self.index = self.index +1
            self.ctr_tasks[i].control(TaskMode.TASK_COMMIT)
            
        ## setting up pulses
        self.setup_pulses(probe_time,gate_time,laser_start,clockpulse_length)
        
        return
        
    def finalize(self, sweeps, gate_time, counter_1, gate_start, probe_time, laser_start, clockpulse_length, n_runs, data_download):
        for ctr_task in self.ctr_tasks:
            ctr_task.close() #clear()
        #self.sg.rf_toggle = False
        self.pulses.Pulser.reset()
        if data_download:
            time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            print("name of spyrelet is", self.name+time_string)
            save_excel(self.name)
            print('data downloaded B)')
        return
    def setup_pulses(self,probe_time,gate_time,laser_start, clockpulse_length):
        print('setting up pulses') 
        self.pulses.tick_time = int(round(clockpulse_length.to("ns").m))
        self.pulses.laser_time = int(round(probe_time.to("ns").m))
        self.pulses.gate_time = int(round(gate_time.to("ns").m))
        self.pulses.laser_start = int(round(laser_start.to("ns").m))
        print('tick time:', self.pulses.tick_time)
        print('laser time:', self.pulses.laser_time)
        print('gate time:', self.pulses.gate_time)
        print('laser start time:', self.pulses.laser_start)
        self.seqs = self.pulses.Laser_lag(self.gate_start)
        #self.seq_tick = self.pulses.Clock_tick()
        #print('defined full sequences for data collection and a tick sequence for arm-triggering')
        self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
        
    @PlotFormatInit(LinePlotWidget, ['counts'])
    def init_format(p):
        p.xlabel = 'read start time (us)'
        p.ylabel = 'PL (cts/s)'    
    @Plot1D
    def counts(df, cache):
        latest = df[df.sweep_idx == df.sweep_idx.max()]
        return {'laser_counts': [latest.t, latest.y]}

class PentLifetimeSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        #'urixyz',
        'pulses',
    ]
    REQUIRED_SPYRELETS = {}
    PARAMS = {
        'counter_1': {
            'type': list,
            'items': list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default': 'ctr1',
        },
        'sweeps': {
            'type': int,
            'default': 100,
            'positive': True,
        },
        'readDelay': {
            'type': range,
            'units': "us",
            'default': {'func': 'linspace',
                        'start': 0,
                        'stop': 1e-3,
                        'num': 51},
        },
        "probe_time": {
            'type': float,
            'default': 2e-3,
            'suffix': ' s',
            'units': "s"
        },
        "gate_time": {
            'type': float,
            'default': 10e-6,
            'suffix': ' s',
            'units': "s"
        },
        "clockpulse_length": {
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': "s"
        },
        'n_runs': {
            'type': int,
            'default': 10000,
            'positive': True,
        },
        'data_download': {
            'type': bool,
            'default': True,
        },
    }
    def main(self,counter_1,sweeps, readDelay, probe_time, gate_time, clockpulse_length, n_runs, data_download):
        print('****************main****************')
        for sweep in self.progress(range(sweeps)):
            print('looping through readDelay times:', self.readDelay_time)
            for i, t in enumerate(readDelay):
                t = int(round(t.to("ns").m))
                print('Currently at reading start time:', t) 
                sw_time = t*1e-3
                #print('reading start time in us:', sw_time) 
                
                self.ctr_tasks[self.index].start()
                #print('arming the trigger by streaming the tick sequence:', self.seq_tick)
                #self.pulses.stream(self.seq_tick, n_runs = 1)
                #self.pulses.Pulser.reset()
                #time.sleep(0.5)
                print('now starting to stream the seq:', self.seqs[i], 'this many times:', self.n_runs)
                print('the shape of buffer is', np.shape(self.buffers[self.index]), 'and the samps per chan is', self.val)
                self.pulses.stream(self.seqs[i], self.n_runs)#self.seqs[i]
                #time.sleep(10)
                self.streamers[self.index].read_many_sample_uint32(
                        self.buffers[self.index],
                        number_of_samples_per_channel= self.val #4*self.n_runs #nidaqmx.constants.READ_ALL_AVAILABLE #-1
                )
                print('now reading', 4*self.n_runs, 'into the predefined ni sample buffer')
                self.ctr_tasks[self.index].stop()
                self.pulses.Pulser.forceFinal()
                print('raw buffer:', self.buffers[self.index])
                print('raw buffer size:', len(self.buffers[self.index]))
                #for k in range(20):
                 #print(self.buffers[self.index][k])
                ctrs_start = self.buffers[self.index][1::4] - self.buffers[self.index][0::4]
                ctrs_end = self.buffers[self.index][3::4] - self.buffers[self.index][2::4]
                print('signal buffer:', ctrs_start)
                print('signal buffer size:', len(ctrs_start))
                print('background buffer:', ctrs_end)
                print('background buffer size:', len(ctrs_end))
                self.sum1 = np.sum(ctrs_start) # experiment 1: MW on (autotriggers and collect starting the first tick)
                self.sum2 = np.sum(ctrs_end)
                signal = int(self.sum1)-int(self.sum2)
                print('sum1:', self.sum1)
                print('sum2:', self.sum2)
                print('signal:', signal)
                print("done")
                
                self.acquire({
                    'sweep_idx': sweep,
                    't': sw_time,
                    'sig': int(self.sum1),
                    'bg': int(self.sum2),
                    'y': signal, #int(self.sum1) #, #ctrs_rates
                    'probe_time': probe_time.m,
                    'gate_time': gate_time.m,
                    'readDelay_array': [readDelay[0].m,readDelay[-1].m,len(readDelay)],
                    'n_runs': n_runs
                    #'y': dctrs[0][0]
                })
    def initialize(self,counter_1,sweeps, readDelay, probe_time, gate_time, clockpulse_length, n_runs, data_download):
        print('****************initializing****************')
        ## setting up parameters
        self.ctr_tasks = list()
        self.streamers = []
        self.buffers = []
        self.ctrs = [counter_1]
        self.readDelay_time = [int(round(readDelay_time.to('ns').m)) for readDelay_time in readDelay]
        print('readDelay times:', self.readDelay_time)
        self.clk_channel = '/Dev1/PFI0'
        self.rate = 1e7
        print('sampling rate:', self.rate)
        self.index = -1
        self.n_runs = n_runs
        self.val = 4*self.n_runs
        print('n_runs:', self.n_runs)
        self.ni_ctr_sample_buffer = np.zeros(int(self.val), dtype=np.uint32)#4*self.n_runs
       
       # if len(set(self.ctrs)) != len(self.ctrs):
            # raise RuntimeError('counter channels 1 and 2 must be different')
        
        ## setting up a read task per channel (currently only one channel)
        for i, ctr in enumerate(self.ctrs):
            self.ctr_tasks.append(nidaqmx.Task())#CounterInputTask('counter ch {}'.format(idx))
            print('created task:', self.ctr_tasks[i]) 
            ch = 'Dev1/' + ctr #CountEdgesChannel(ctr)
            self.ctr_tasks[i].ci_channels.add_ci_count_edges_chan(
                                        ch,
                                        edge=Edge.RISING,
                                        initial_count=0,
                                        count_direction=CountDirection.COUNT_UP
            )
            print('added:', ch, 'as a ci count edges channel')       
            
            self.ctr_tasks[i].timing.cfg_samp_clk_timing(
                                        self.rate,
                                        source = self.clk_channel,
                                        sample_mode=AcquisitionType.FINITE,
                                        samps_per_chan= self.val #4*self.n_runs
            )
            print('added:', self.clk_channel, 'as a timing source with max rate', self.rate)
            print('Ticking', 4*self.n_runs, 'times')
            
            # self.ctr_tasks[i].triggers.pause_trigger.dig_lvl_src = self.clk_channel
            # self.ctr_tasks[i].triggers.pause_trigger.dig_lvl_when = nidaqmx.constants.Level.LOW
            #print('set pause trigger for the task when the PS clock channel is LOW')
            
            ## setting the task to be triggered by the PS clock ticks
            # self.ctr_tasks[i].triggers.arm_start_trigger.trig_type = TriggerType.DIGITAL_EDGE
            # self.ctr_tasks[i].triggers.arm_start_trigger.dig_edge_edge = Edge.RISING
            # self.ctr_tasks[i].triggers.arm_start_trigger.dig_edge_src = self.clk_channel
            #print('setting arm trigger source to be:', self.clk_channel)
            
            ## defining the streaming object and buffer
            self.streamers.append(CounterReader(self.ctr_tasks[i].in_stream))
            self.buffers.append(self.ni_ctr_sample_buffer)
            #self.ctr_tasks[i].over_write = nidaqmx.constants.OverwriteMode.DO_NOT_OVERWRITE_UNREAD_SAMPLES
            
            ## starting task without triggering
            #self.ctr_tasks[i].start()
            #print('started the task, but it is not armed and clock is not ticking yet')
            self.index = self.index +1
            self.ctr_tasks[i].control(TaskMode.TASK_COMMIT)
            
        ## setting up pulses
        self.setup_pulses(probe_time, gate_time, self.readDelay_time,clockpulse_length)
        
        return
        
    def finalize(self,counter_1,sweeps, readDelay, probe_time, gate_time, clockpulse_length, n_runs, data_download):
        for ctr_task in self.ctr_tasks:
            ctr_task.close() #clear()
        #self.sg.rf_toggle = False
        self.pulses.Pulser.reset()
        if data_download:
            time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            print("name of spyrelet is", self.name+time_string)
            save_excel(self.name)
            print('data downloaded B)')
        return
    def setup_pulses(self,probe_time, gate_time,readDelay,clockpulse_length):
        print('setting up pulses') 
        self.pulses.tick_time = int(round(clockpulse_length.to("ns").m))
        self.pulses.laser_time = int(round(probe_time.to("ns").m))
        self.pulses.gate_time = int(round(gate_time.to("ns").m))
        print('tick time:', self.pulses.tick_time)
        print('laser time:', self.pulses.laser_time)
        print('gate time:', self.pulses.gate_time)
        self.seqs = self.pulses.Pent_lifetime(self.readDelay_time)
        #self.seq_tick = self.pulses.Clock_tick()
        #print('defined full sequences for data collection and a tick sequence for arm-triggering')
        self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
        
    @PlotFormatInit(LinePlotWidget, ['counts'])
    def init_format(p):
        p.xlabel = 'read start time (us)'
        p.ylabel = 'PL (cts/s)'    
    @Plot1D
    def counts(df, cache):
        latest = df[df.sweep_idx == df.sweep_idx.max()]
        return {'counts': [latest.t, latest.y]}
    @Plot1D
    def average(df, cache):
        frame = df
        print('n:',list(df.readDelay_array)[2][2])
        n = int(list(df.readDelay_array)[2][2])
        print('starting')
        print('n:', n)
        print('t first', n, 'pts:',list(df.t)[0:n])
        print('sig first', n, 'pts:',list(df.sig)[0:n])
        print('bg first', n, 'pts:',list(df.bg)[0:n])
        print('sweeps:', max(list(df.sweep_idx)))

        sum_sig = np.zeros(len(list(df.sig)[0:n]))
        sum_bg = np.zeros(len(list(df.sig)[0:n]))

        for i in range(max(list(df.sweep_idx))):
           sum_sig +=  np.array(list(frame.sig)[i*n:(i*n+n)])
           sum_bg +=  np.array(list(frame.bg)[i*n:(i*n+n)])
        print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
           #avg_sig = sum_sig / len(list(frame.sig))
           #avg_bg = sum_bg / len(list(frame.bg)) 
        #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
        return {
            'sig': [list(df.t)[0:n], list(sum_sig)],
            'bg': [list(df.t)[0:n], list(sum_bg)],
        }

class PentODMRSpinDecaySpyrelet(BaseFeedbackSpyrelet): #Need to change math and read functions to the faster version!
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]
    REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}
    # REQUIRED_SPYRELETS = {
        # 'newSpaceFB': SpatialFeedbackXYZSpyrelet
    # }
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
            'default': 10000000,
        },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': 1
            # },
        'run_ct': {
            'type': int,
            'nonnegative': True,
            'default': 1000
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
            'type': float,
            'units':'Hz',
            'default':3.3e9,
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
        'laser_lag':{
            'type': float,
            'default': .080e-6,
            'suffix': ' s',
            'units': 's'
        },
        'bgReadTimes': {
            'type': range,
            'units': "us",
            'default': {'func': 'linspace',
                        'start': 0.1,
                        'stop': 1e2,
                        'num': 51},
        },
        'Gap_before_bg':{
            'type': float,
            'default': 100e-9,
            'suffix': ' s',
            'units': 's'
        },        
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        # 'laser_pause': {
            # 'type': float,
            # 'default': 3e-7,
            # 'suffix' : 's',
            # 'units': 's'
        # },
        
        # 'cooldown_time':{
            # 'type': float,
            # 'default': 5e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'sequence':{
            # 'type': list,
            # 'items': ['odmr_heat_wait', 'odmr_no_wait'],
            # 'default': 'odmr_no_wait',
        # },
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
        
    }

    def main(self, device, channel1, PS_clk_channel, sampling_rate, run_ct, timeout, 
                    sweeps, repeat_every_x_minutes, repetitions, frequency, rf_amplitude, 
                    probe_time, laser_lag, bgReadTimes, Gap_before_bg, clock_duration, data_download, feedback, dozfb,
                    sweeps_til_fb, x_initial, y_initial, z_initial, xyz_step,count_step_shrink,
                    starting_point):
                    
        ## we sweep through the bundles of sweeps we take every x_minutes.
        for rep in range(repetitions):        
            for sweep in self.progress(range(sweeps)):
            # ################################################################################################################
            # ##             
            # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
                # if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    # self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            # ##
            # ###############################################################################################################
                        # # # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
                #return
                print('*******************In main***************************')
                print('n_runs:', self.run_ct, 'type:', type(self.run_ct)) ## number of runs per sweep.
                print('number of data points:', self.data_ct, 'type:', type(self.data_ct))
                print('set time per point (s):', self.time_per_point*1e-9, 'type:', type(self.time_per_point))
                print('set time per read (s):', self.time_per_point *1e-9* self.data_ct)
                print('time per experiment:', self.time_per_point *1e-9 * self.data_ct * sweeps)

                ctrs_rates = self.read(self.run_ct, self.data_ct, self.buffers, 0) 
                print('bg counts:', ctrs_rates[1], 'length:', len(ctrs_rates[1]))
                print('bgReadTimes array (s):', bgReadTimes.to('s').m, 'length:', len(bgReadTimes.to('s').m))             
                
                ## acquire the following
                self.acquire({
                    #'sampling_rate': sampling_rate,
                    #'timeout': timeout,
                    #'repeat_every_x_minutes': repeat_every_x_minutes,
                    #'clock_duration': clock_duration,
                    #'sweeps_til_fb': sweeps_til_fb,
                    'time_per_point': self.time_per_point,
                    'run_ct': self.run_ct,
                    'rep_idx': rep,
                    'sweep_idx': sweep,
                    'f': frequency.to('Hz').m,
                    'rf_amplitude': rf_amplitude,
                    'probe_time': probe_time,
                    'bgReadTime': bgReadTimes.to('us').m,
                    'sig': [float(e/probe_time.to('s').m) for e in ctrs_rates[0]],
                    'bg':  ctrs_rates[1]/bgReadTimes.to('s').m #[float(e/bgReadTimes.to('s').m) for e in ctrs_rates[1]],
                })
            time.sleep(repeat_every_x_minutes * 60)

    # def math_odmr(self, array):
        # ## divide buffer to bright versus dark
        # ## note: arm_start_trigger drops first point, so we have to add another point to the end of the buffer
        # ## we will also drop the last dark collection, so we will have slightly uneven countings.
        # if self.sequence in ('odmr_heat_wait'):
            # delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            # sum1 = np.sum(delta_buffer[::4]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            # sum2 = np.sum(delta_buffer[2::4]) # MW off, but collect bright.
            # return [sum1, sum2]
        # else:
            # delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            # print(len(delta_buffer))
            # sum1 = np.sum(delta_buffer[:-1][::2]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            # sum2 = np.sum(delta_buffer[1::2]) # MW off, but collect bright.
            
            # print('delta_buffer:', delta_buffer)
            # print('sum1:', sum1, 'sum2:', sum2)          
            # return [sum1, sum2]
            
    def initialize(self, device, channel1, PS_clk_channel, sampling_rate, run_ct, timeout, 
                    sweeps, repeat_every_x_minutes, repetitions, frequency, rf_amplitude, 
                    probe_time, laser_lag, bgReadTimes, Gap_before_bg, clock_duration, data_download, feedback, dozfb,
                    sweeps_til_fb, x_initial, y_initial, z_initial, xyz_step,count_step_shrink,
                    starting_point):
        
        print('********************In initialize****************')
     
        ## create parameters
        self.index = 0
        self.timeout=timeout
        #self.time_per_point = int(round(time_per_point.to("ns").m))
        #print('self.time_per_point:', self.time_per_point)
        self.run_ct = run_ct
        self.sampling_rate = sampling_rate.to('Hz').m
        self.data_ct = len(bgReadTimes)
        print('number of runs:', self.run_ct,'number of points:', self.data_ct)
        
        if laser_lag.to('ns').m < clock_duration.to('ns').m:
            raise("your laser lag must be longer than the clock pulse duration")        
             
        ## DAQ must sample quicker than the PS clock ticking rate
        ## ideally, it would sample at the PS clock ticking rate. 
        ## as of now, 02_16_2021, we do not understand the exact conditions required.
        if self.sampling_rate < 1/bgReadTimes[0].to('s').m:
            print('sampling rate must be equal or larger than 1/min(bgReadTimes)')
            #return
        
        ## check that there are no channel repeats
        ## this code barely matters, since it's a remnant from a different code using multiple channels
        ## IGNORE
        self.channel = channel1
        
        ## set SG paramaters: running this spyrelet with IQ inputs
        self.sg.rf_amplitude = rf_amplitude
        self.sg.frequency = frequency
        
        self.setup_pulses(probe_time, clock_duration, bgReadTimes, Gap_before_bg, laser_lag)
        
        ## using array with contiguous memory region because NI uses C arrays under the hood
        self.num_signal = 2
        print('calculating buffer size')
        print(self.data_ct, '# of points X', 2* self.num_signal, 'reading ticks X', self.run_ct, 'runs per sweep')
        print('buffer_size:', 2* self.num_signal * self.data_ct * self.run_ct)
        buffer_size = 2*self.num_signal * self.data_ct * self.run_ct
        ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32) ## we create a data buffer with lngth = buffer_size 
        self.buffers = [ni_ctr_sample_buffer] ##we append each data buffer to the buffers array in case we are reading from multiple channels
                                              ## currently we only use one channel
        
        ## initialize base spyrelet
        print('now initializing super class')
        super().initialize(device, self.buffers, PS_clk_channel,
                           self.time_per_point, sampling_rate,data_download)
 
        
    def finalize(self, device, channel1, PS_clk_channel, sampling_rate, run_ct, timeout, 
                    sweeps, repeat_every_x_minutes, repetitions, frequency, rf_amplitude, 
                    probe_time, laser_lag, bgReadTimes, Gap_before_bg, clock_duration, data_download, feedback, dozfb,
                    sweeps_til_fb, x_initial, y_initial, z_initial, xyz_step,count_step_shrink,
                    starting_point):
        
        ## finalizing base spyrelet
        super().finalize(device, self.buffers, PS_clk_channel,
                         self.time_per_point, sampling_rate,data_download)
                        
        return

    def setup_pulses(self, probe_time, clock_duration, bgReadTimes, Gap_before_bg, laser_lag):
        ##the probe time is our laser time per window, our clock time is the width of our clock pulse.
        self.pulses.read_time = int(round(probe_time.to("ns").m))
        self.pulses.clock_time = int(round(clock_duration.to("ns").m))
        self.pulses.aom_lag = int(round(laser_lag.to("ns").m))
        #print('bgReadTimes (with units):', bgReadTimes)
        #print('bgReadTimes (without units):', bgReadTimes.to("ns").m)
        bgReadTimes_ns = [int(round(bgReadTime)) for bgReadTime in bgReadTimes.to("ns").m]
        ## due to how the read_odmr() function works, we need this in a list, and we index it at 0.
        ## this is to make it compatible with PulsedODMR as well.
        #print('\n', self.time_per_point, self.data_ct, self.pulses.total_time)
       
        self.seqs = self.pulses.PentBgReadODMR(bgReadTimes_ns, int(round(Gap_before_bg.to("ns").m)))
        #print('calculating run_ct')
        #print('tpp:', self.time_per_point, 'data_ct:', self.data_ct, 'run_ct (not rounded):', self.time_per_point * self.data_ct/self.pulses.total_time)
        #self.run_ct = int(round(self.time_per_point * self.data_ct/self.pulses.total_time))
        print('calculating time per point, sweep time, and experiment time')
        print('single sequence time:', self.pulses.total_time, 'data_ct:', self.data_ct, 'runs:', self.run_ct)
        print('tpp (s):', (self.run_ct*self.pulses.total_time/self.data_ct)*1e-9)
        self.time_per_point = self.run_ct*self.pulses.total_time/self.data_ct #in ns
        #self.run_ct = int(round(self.time_per_point * self.data_ct/self.pulses.total_time))
        print('gap:', int(round(Gap_before_bg.to("ns").m)))
        #print('total time per is:', self.pulses.total_time, 'n_runs is (rounded):', self.run_ct) 
        print('seqs:', self.seqs)
        
    def math(self, read_data): #fix the math
            ## with the norm, we cannot take all four read windows
            ## otherwise, our normalization pulses at the end of each run
            ## become interwoven with our read windows
            average_buffer = np.empty(4 * self.data_ct)## creating average_buffer with length- number of reading 
                                                       ## windows for a full run 
            ## so, we sum up all our data for our runs according to each read window.
            for i in range(4 * self.data_ct): 
              average_buffer[i] = np.sum(read_data[i::(4 * self.data_ct)])
            ###norm_buffer = np.empty(2,self.run_ct)
            ## now, we can isolate the normalization pulses.
            
            ## we have found the normalizaiton, now we make sure to divide our data into read windows.
            MW_on = average_buffer[1::4] - average_buffer[0::4]
            MW_off = average_buffer[3::4] - average_buffer[2::4]
            ## we once again return in the order of chronology of the pulse sequence.
            signal = [MW_on, MW_off]
            return signal
    
    @PlotFormatInit(LinePlotWidget, ['latest', 'average', 'average_diff','average_div','no_trace_average_div'])
    def init_format(p):
        p.xlabel = 'Background reading time (us)'
        p.ylabel = 'PL (cts/s)'
        
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_average_div'])#['latest', 'avg'])
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(255,255,255,10), width=5)
            
    ## this plots the ODMR sweep.
    @Plot1D
    def latest(df, cache):
        recent_data = df[df.rep_idx == df.rep_idx.max()]
        latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        return {'sig': [latest_data.bgReadTime, latest_data.sig],
                'bg': [latest_data.bgReadTime, latest_data.bg]}

    @Plot1D
    def latestDiff(df, cache):
        recent_data = df[df.rep_idx == df.rep_idx.max()]
        latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        return {'sig': [latest_data.bgReadTime, latest_data.sig-latest_data.bg]}

    @Plot1D
    def latestDiv(df, cache):
        recent_data = df[df.rep_idx == df.rep_idx.max()]
        latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        return {'sig': [latest_data.bgReadTime, latest_data.sig/latest_data.bg]}
                
    @Plot1D
    def average(df, cache):
        frame = df
        ## we normalize the averages.
        avg_sig = np.empty(len(list(df.sig[0])))
        avg_bg = np.empty(len(list(df.bg[0])))
        for point_num in range(len(list(df.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for run in range(len(list(df.sig))):
                sum_sig += df.sig[run][point_num]
                sum_bg += df.bg[run][point_num]
            avg_sig[point_num] = sum_sig / len(list(df.sig))
            avg_bg[point_num] = sum_bg / len(list(df.bg))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'MW_on': [list(df.bgReadTime)[0], list(avg_sig)],
            'MW_off': [list(df.bgReadTime)[0], list(avg_bg)],
        }
    
    @Plot1D
    def averageDiff(df, cache):
        frame = df
        ## we normalize the averages.
        avg_sig = np.empty(len(list(df.sig[0])))
        avg_bg = np.empty(len(list(df.bg[0])))
        for point_num in range(len(list(df.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for run in range(len(list(df.sig))):
                sum_sig += df.sig[run][point_num]
                sum_bg += df.bg[run][point_num]
            avg_sig[point_num] = sum_sig / len(list(df.sig))
            avg_bg[point_num] = sum_bg / len(list(df.bg))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'Sig-Bg': [list(df.bgReadTime)[0], list(avg_sig-avg_bg)]
        }  
    
    @Plot1D
    def averageDiv(df, cache):
        frame = df
        ## we normalize the averages.
        avg_sig = np.empty(len(list(df.sig[0])))
        avg_bg = np.empty(len(list(df.bg[0])))
        for point_num in range(len(list(df.sig[0]))):
            sum_sig = 0; sum_bg = 0
            for run in range(len(list(df.sig))):
                sum_sig += df.sig[run][point_num]
                sum_bg += df.bg[run][point_num]
            avg_sig[point_num] = sum_sig / len(list(df.sig))
            avg_bg[point_num] = sum_bg / len(list(df.bg))  
        ## we have some troubleshooting here.
        ## you can see why we have to convert stuff from pandas.
        return {
            'Sig-Bg': [list(df.bgReadTime)[0], list(avg_sig/avg_bg)]
        } 
             
   # class ODMRSwabianSpyrelet(BaseFeedbackSpyrelet):
    # REQUIRED_DEVICES = [
        # 'sg',
        # 'pulses',
        # 'urixyz',
    # ]
    # REQUIRED_SPYRELETS = {
        # 'newSpaceFB': SpatialFeedbackXYZSpyrelet
    # }
    # """
    # We run two windows: one with our MW on and the other with the MW off.
    # We read the start of these 50us windows, and we do this 10,000 times. So,
    # we have a time per point of 1s.
    # We set a timeout for the general sample clock, 
    # we can repeat x sweeps every y minutes per z repetitions.
    # We sweep our microwave window over frequencies, generally 30 steps.
    # Note: probe_time is the laser_on_per_window,
    # rf_amplitude is the signal generator's power,
    # clockpulse_duration sets the width of the pulse that clocks eery 50ns.
        # set it to 10ns or so.
    # """
    # PARAMS = {
        # 'device':{
            # 'type': str,
            # 'default': 'Dev1',
        # },
        # 'channel1':{
            # 'type':list,
            # 'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            # 'default':'ctr1',
            # },
        # 'PS_clk_channel':{
            # 'type': str,
            # 'default': 'PFI0',
        # },
        # 'sampling_rate':{
            # 'type':float,
            # 'units':'Hz',
            # 'suffix': ' Hz',
            # 'default': 50000,
        # },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': .7
            # },
        # 'timeout': {
            # 'type': int,
            # 'nonnegative': True,
            # 'default': 300
        # },
        # 'sweeps':{
            # 'type': int,
            # 'default': 100,
            # 'positive': True,
        # },
        # 'repeat_every_x_minutes':{
            # 'type': float,
            # 'default': .1,
            # 'positive': True
        # },
        # 'repetitions':{
            # 'type': int,
            # 'default': 5,
            # 'positive': True
        # },
        # 'frequency':{
            # 'type': range,
            # 'units':'Hz',
            # 'default':{'func': 'linspace',
                            # 'start': 2.82e9,
                            # 'stop': 2.92e9,
                            # 'num': 30},
        # },
        # 'rf_amplitude':{
            # 'type': float,
            # 'default': -20,
        # },
        # 'probe_time':{
            # 'type': float,
            # 'default': 50e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'clock_duration':{
            # 'type': float,
            # 'default': 10e-9,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'laser_pause': {
            # 'type': float,
            # 'default': 3e-7,
            # 'suffix' : 's',
            # 'units': 's'
        # },
        # 'cooldown_time':{
            # 'type': float,
            # 'default': 5e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'sequence':{
            # 'type': list,
            # 'items': ['odmr_heat_wait', 'odmr_no_wait'],
            # 'default': 'odmr_no_wait',
        # },
        # 'feedback':{
            # 'type': bool,
            # 'default': False,
        # },
        # 'dozfb':{
            # 'type': bool,
            # 'default': True
        # },
        # 'sweeps_til_fb':{
            # 'type': int,
            # 'default': 10,
        # },
        # 'x_initial':{
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'y_initial':{
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'z_initial': {
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'xyz_step':{
            # 'type': float,
            # 'units': 'm',
            # 'default': 60e-9,
        # },
        # 'count_step_shrink':{
            # 'type': int,
            # 'default': 2,
        # },
        # 'starting_point': {
            # 'type': list,
            # 'items': list(['user_input','current_position (ignore input)']),
            # 'default': 'current_position (ignore input)',
        # },
        # 'data_download':{
            # 'type': bool,
        # },
    # }

    # def main(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    # sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
                    # probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    # sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    # z_initial, xyz_step,count_step_shrink,starting_point):
        
        
        # ## we sweep through the bundles of sweeps we take every x_minutes.
        # for rep in range(repetitions):        
            # for sweep in self.progress(range(sweeps)):
            # ################################################################################################################
            # ##             
            # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
                # if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    # self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            # ##
            # ###############################################################################################################
            
            # ## sweeping through frequencies (each frequency calls read to create a data point with a new buffer)
            # ## frequency sweep
                # ## frequency modulation within each data point
                # for f in frequency:
                    # ## make sure the sg frequency is set! (overhead of <1ms)
                    # self.sg.frequency = f
                    # ## read the ctrs rates for the number of repeats per point
                    # ## usually this is 10,000, so we have a buffer size of 20,000. 
                    # ## so, we have self.read_odmr(10,000)
                    # ctrs_rates = self.read_odmr(len(self.buffers[0])/2, self.buffers, 0) # calls read from base spyrelet)
                    # ## optional, just to clarify
            
                    # ## acquire the following
                    # self.acquire({
                        # 'rep_idx': rep,
                        # 'sweep_idx': sweep,
                        # 'f': f,
                        # 'sig': int(ctrs_rates[0]),
                        # 'bg': int(ctrs_rates[1])
                    # })
            # time.sleep(repeat_every_x_minutes * 60)

    
    # def math_odmr(self, array):
        # ## divide buffer to bright versus dark
        # ## note: arm_start_trigger drops first point, so we have to add another point to the end of the buffer
        # ## we will also drop the last dark collection, so we will have slightly uneven countings.
        # if self.sequence in ('odmr_heat_wait'):
            # delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            # sum1 = np.sum(delta_buffer[::4]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            # sum2 = np.sum(delta_buffer[2::4]) # MW off, but collect bright.
            # return [sum1, sum2]
        # else:
            # delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
            # print(len(delta_buffer))
            # sum1 = np.sum(delta_buffer[:-1][::2]) # MW on, but collects dark (autotriggers and collect starting the first tick)
            # sum2 = np.sum(delta_buffer[1::2]) # MW off, but collect bright.
            
            # print('delta_buffer:', delta_buffer)
            # print('sum1:', sum1, 'sum2:', sum2)          
            # return [sum1, sum2]
            
    # def initialize(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    # sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
                    # probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    # sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    # z_initial, xyz_step,count_step_shrink,starting_point):
        # #self.ODMR_with_wait = ODMR_with_wait
        # self.sequence = sequence
        # ## create parameters
        # odmr_buffer_size = 2*(math.floor(time_per_point/(2*probe_time)) + 1)
        # print('effective buffer_size:', math.floor(time_per_point/probe_time))
        # if odmr_buffer_size ==1:
            # raise ValueError('the buffer is too small. Increase time per point beyond 2 * probe_time.')
            
        # self.index = 0
        # self.timeout=timeout
        # ## using array with contiguous memory region because NI uses C arrays under the hood
        # ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(odmr_buffer_size, dtype=np.uint32))
        
        # self.buffers = [ni_ctr_sample_buffer]
        
        # ## DAQ must sample quicker than the PS clock ticking rate
        # ## ideally, it would sample at the PS clock ticking rate. 
        # ## as of now, 02_16_2021, we do not understand the exact conditions required.
        # if sampling_rate.to('Hz').m < 1/probe_time.to('s').m:
            # print('sampling rate must be equal or larger than 1/probe_time')
            # return
        
        # ## check that there are no channel repeats
        # ## this code barely matters, since it's a remnant from a different code using multiple channels
        # ## IGNORE
        # self.channel = channel1
        
        # ## set SG paramaters: running this spyrelet with IQ inputs
        # self.sg.rf_amplitude = rf_amplitude
        # ## initialize base spyrelet
        # super().initialize(device, self.buffers, PS_clk_channel,
                           # time_per_point, sampling_rate,data_download)

        
        # # setting up the pulses
        # if sequence in ('odmr_heat_wait'):
            # self.setup_ODMR_wait(probe_time, clock_duration, laser_pause, cooldown_time)
        # else:        
            # self.setup_no_wait(probe_time, clock_duration)
        
        # return
        
    # def finalize(self, device, channel1, sampling_rate, PS_clk_channel, time_per_point, repetitions,
                    # sweeps, frequency, rf_amplitude, laser_pause, cooldown_time,
                    # probe_time, clock_duration, timeout, repeat_every_x_minutes,
                    # sequence, data_download,feedback, dozfb, sweeps_til_fb, x_initial, y_initial,
                    # z_initial, xyz_step,count_step_shrink,starting_point):
        
        # ## finalizing base spyrelet
        # super().finalize(device, self.buffers, PS_clk_channel,
                         # time_per_point, sampling_rate,data_download)
                        
        # return

    # def setup_no_wait(self, probe_time, clock_duration):
        # ##the probe time is our laser time per window, our clock time is the width of our clock pulse.
        # self.pulses.read_time = int(probe_time.to("ns").m)
        # self.pulses.clock_time = int(clock_duration.to("ns").m)
        # ## due to how the read_odmr() function works, we need this in a list, and we index it at 0.
        # ## this is to make it compatible with PulsedODMR as well.
        # print('\n using sequence without wait time')
        # self.seqs = [self.pulses.CWUriMR()]
        
    # def setup_ODMR_wait(self, probe_time, clock_duration, factor_time, long_buffer):
        # self.pulses.read_time = int(probe_time.to("ns").m)
        # self.pulses.clock_time = int(clock_duration.to("ns").m)
        # print('\n using sequence with wait time')
        # self.seqs = [self.pulses.ODMRHeatDissipation(int(round(factor_time.to('ns').m)), int(round(long_buffer.to('ns').m)))]

    # @PlotFormatInit(LinePlotWidget, ['latest', 'average', 'average_diff','average_div','no_trace_average_div'])
    # def init_format(p):
        # p.xlabel = 'frequency (Hz)'
        # p.ylabel = 'PL (cts/s)'
        
    # @PlotFormatUpdate(LinePlotWidget, ['no_trace_average_div'])#['latest', 'avg'])
    # def update_format(p, df, cache):
        # for item in p.plot_item.listDataItems():
            # item.setPen(color=(0,0,0,0), width=5)
            
    # ## this plots the ODMR sweep.
    # @Plot1D
    # def latest(df, cache):
        # recent_data = df[df.rep_idx == df.rep_idx.max()]
        # latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
        
    # ## this plots a specific ODMR sweep.
    # @Plot1D
    # def stack_0(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 0]
        # ##edit the 0 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
                
    # @Plot1D
    # def stack_1(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 1]
        # ##edit the 1 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
                
    # @Plot1D
    # def stack_2(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 2]
        # ##edit the 2 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
    
    
    # @Plot1D
    # def stack_3(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 3]
        # ##edit the 3 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
                
    # @Plot1D
    # def stack_4(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 4]
        # ##edit the 4 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
                
    # @Plot1D
    # def stack_5(df, cache):
        # recent_data = df[df.rep_idx == 0]
        # ##edit the 0 above to be whatever repetition you want
        # latest_data = recent_data[recent_data.sweep_idx == 5]
        # ##edit the 5 above to be whatever sweep you want
        # return {'sig': [latest_data.f, latest_data.sig],
                # 'bg': [latest_data.f, latest_data.bg]}
    
    # ## this plots the running average of all sweeps.
    # @Plot1D
    # def average(df, cache):
        # rep_df = df[df.rep_idx == 0]
        # grouped = rep_df.groupby('f')
        # sigs = grouped.sig
        # bgs = grouped.bg
        # sigs_averaged = sigs.mean()
        # bgs_averaged = bgs.mean()
        # return {'sig': [sigs_averaged.index, sigs_averaged],
                # 'bg': [bgs_averaged.index, bgs_averaged]}
       
    # @Plot1D
    # def avg_sig(df, cache):
        # rep_df = df[df.rep_idx == 0]
        # grouped = rep_df.groupby('f')
        # sigs = grouped.sig
        # sigs_averaged = sigs.mean()
        # return {'sig': [sigs_averaged.index, sigs_averaged]}
        
        
    # ## this plots the difference of the running averages of all sweeps
    # @Plot1D
    # def average_diff(df, cache):
        # rep_df = df[df.rep_idx == 0]
        # grouped = rep_df.groupby('f')
        # sigs = grouped.sig
        # bgs = grouped.bg
        # sigs_averaged = sigs.mean()
        # bgs_averaged = bgs.mean()
        # return {'dark-bright': [sigs_averaged.index, sigs_averaged-bgs_averaged]}
        
    # ## this plots the division of the running averages of all sweeps
    # @Plot1D
    # def average_div(df, cache):
        # rep_df = df[df.rep_idx == 0]
        # grouped = rep_df.groupby('f')
        # sigs = grouped.sig
        # bgs = grouped.bg
        # sigs_averaged = sigs.mean()
        # bgs_averaged = bgs.mean()
        # return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}
        
    # ## this plots the division of the running averages of all sweeps without a trace line.
    # @Plot1D
    # def no_trace_average_div(df, cache):
        # rep_df = df[df.rep_idx == 0]
        # grouped = rep_df.groupby('f')
        # sigs = grouped.sig
        # bgs = grouped.bg
        # sigs_averaged = sigs.mean()
        # bgs_averaged = bgs.mean()
        # return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}


#class PiPeriodTest(BaseFeedbackSpyrelet):
    # REQUIRED_DEVICES = [
        # 'sg',
        # 'pulses',
        # 'urixyz',
    # ]
    # REQUIRED_SPYRELETS = {
        # 'newSpaceFB': SpatialFeedbackXYZSpyrelet
    # }
    # """
    # our most basic function using our normal read.
    # we take our optimal frequency (biggest contrast) from ODMR
    # and we plug it into Rabi. We then sweep times to apply the microwave,
    # such that we generate an oscillation of our signal, showing we have
    # full control over the NV's rotation about the Bloch Sphere.
    # """
    
    # PARAMS = {
        # 'device':{
            # 'type': str,
            # 'default': 'Dev1',
        # },
        # 'channel1':{
            # 'type':list,
            # 'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            # 'default':'ctr1',
            # },
        # ## we define our clock channel that we use to link
        # ## our pulse streamer and our DAQ.
        # 'PS_clk_channel':{
            # 'type': str,
            # 'default': 'PFI0',
        # },
        # 'sampling_rate':{
            # 'type':float,
            # 'units':'Hz',
            # 'suffix': ' Hz',
            # 'default': 2.5e6,
        # },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': 1,
            # },
        # 'sweeps':{
            # 'type': int,
            # 'default': 100,
            # 'positive': True,
        # },
        # 'frequency':{
            # 'type': float,
            # 'units':'Hz',
            # 'default': 2.87e9
        # },
        # 'rf_amplitude':{
            # 'type': float,
            # 'default': -20,
        # },
        # 'probe_time':{
            # 'type': float,
            # 'default': 5.5e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'clock_duration':{
            # 'type': float,
            # 'default': 10e-9,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        
        # 'timeout': {
            # 'type': int,
            # 'nonnegative': True,
            # 'default': 300
        # },
        # 'PiTimes':{
            # 'type': range,
            # 'units': 'ns',
            # 'default': {'func': 'linspace',
                        # 'start': 30,
                        # 'stop': 50,
                        # 'num': 11},
        # },
        # 'pi_xy':{
            # 'type': list,
            # 'items': list(['x','y']),
            # 'default': 'x'
        # },
        # 'readout_time':{
            # 'type': float,
            # 'default': .4e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'aom_lag':{
            # 'type': float,
            # 'default': 30e-9,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'buffer_time':{
            # 'type': float,
            # 'default': 0.15e-6,
            # 'suffix': ' s',
            # 'units': 's'
        # },
        # 'feedback':{
            # 'type': bool,
            # 'default': False,
        # },      
        # 'dozfb':{
            # 'type': bool,
            # 'default': True
        # },  
        # 'sweeps_til_fb':{
            # 'type': int,
            # 'default': 10,
        # },
        # 'x_initial':{
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'y_initial':{
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'z_initial': {
            # 'units': 'um',
            # 'type': float,
            # 'default': 0.0,
        # },
        # 'xyz_step':{
            # 'type': float,
            # 'units': 'm',
            # 'default': 60e-9,
        # },
        # 'count_step_shrink':{
            # 'type': int,
            # 'default': 2,
        # },
        # 'starting_point': {
            # 'type': list,
            # 'items': list(['user_input','current_position (ignore input)']),
            # 'default': 'current_position (ignore input)',
        # },
        # 'data_download':{
            # 'type': bool,
        # },
    # }

    # def main(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    # sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    # buffer_time, mw_times, pi_xy, timeout, data_download,\
                    # feedback, dozfb, sweeps_til_fb,\
                    # x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    # starting_point):
        
        
        
        # for sweep in self.progress(range(sweeps)):
            # # ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            # if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                    # self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            # print('n_runs:', self.run_ct) # time per sweep 
            # print('time per read:', self.time_per_point * self.data_ct)
            # print('time per experiment:', self.time_per_point * self.data_ct * sweeps)
            # ## mw time sweep               
            # # # This is an array of shape run_ct by len(mw_times)
            # sing_rabi = self.read(self.run_ct, self.data_ct, self.buffers, 0)#math.ceil(self.buffer_size/4))
            # self.acquire({
                # 'run_ct': self.run_ct,
                # 'sweep_idx': sweep,
                # 't': [float(e.to('us').m) for e in mw_times],
                # 'f': frequency,
                # 'power': rf_amplitude,
                # 'sig': [float(e) for e in sing_rabi[0]], #*self.ratio,
                # 'bg': [float(e) for e in sing_rabi[1]], #*self.ratio,
            # })
            # print("finished acquiring")

    # def math(self, array):
        
        # ## divide buffer to different experiments
        # delta_buffer_start = array[1::4] - array[0::4] 
        # delta_buffer_end = array[3::4] - array[2::4] 
        # final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
        # for i in range(self.data_ct):
            # final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
            # final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
        # return [final_data_dark, final_data_bright]
        # # # dark_bright = [delta_buffer_start,delta_buffer_end]
        # # # return dark_bright
        
    # def initialize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    # sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    # buffer_time, mw_times, pi_xy, timeout, data_download,\
                    # feedback, dozfb, sweeps_til_fb,\
                    # x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    # starting_point):
        # if aom_lag < clock_duration:
            # raise("your laser lag must be longer than the clock pulse duration")            
        # ## setup pulses. this counts how many sweeps the program should do.
        # self.time_per_point = time_per_point
        # self.mw_times = [int(round(mw_time.to('ns').m)) for mw_time in mw_times]
        # self.setup_pulses(probe_time, aom_lag, readout_time, buffer_time, clock_duration, pi_xy)
        # ## create parameters
        # ## sampling rate should be >= 1/(read_window), so 1/400ns
        # self.sampling_rate = sampling_rate.to('Hz').m
        # ## self.run_ct is determined by total time of the sequence
        # ## and time_per_point in setup_pulses
        # self.data_ct = len(self.mw_times)
        # buffer_size = 4*self.data_ct * self.run_ct# ignore run_ct
        # ## we set up the buffer and array we use to get our signal in self.read()
        # ni_ctr_sample_buffer = np.zeros(int(buffer_size), dtype=np.uint32)
        # self.buffers = [ni_ctr_sample_buffer]
        # self.num_signal = 2
        # ## we define the timeout in seconds.
        # self.timeout = timeout
        # ## create channels list and check that there are no repeats
        
        # self.channel = channel1
        
        # ## initialize base spyrelet
        # super().initialize(device, self.buffers, PS_clk_channel,
                            # time_per_point, sampling_rate, data_download)

        # ## set SG paramaters: running this spyrelet with IQ inputs
        # self.sg.frequency = frequency
        # self.sg.rf_amplitude = rf_amplitude
        
        
        # return
        
    # def finalize(self, device, channel1, sampling_rate, time_per_point, PS_clk_channel, clock_duration,\
                    # sweeps, frequency, rf_amplitude, probe_time, aom_lag, readout_time, \
                    # buffer_time, mw_times, pi_xy, timeout, data_download,\
                    # feedback, dozfb, sweeps_til_fb,\
                    # x_initial, y_initial,z_initial,xyz_step,count_step_shrink,
                    # starting_point):
        
        # ## finalize like every spyrelet.
        # super().finalize(device, self.buffers, PS_clk_channel,
                          # time_per_point, sampling_rate, data_download)        
        # return

    # def setup_pulses(self, probe_time, aom_lag, readout_time, buffer_time, clock_duration, pi_xy):
        # self.pulses.laser_time = int(round(probe_time.to("ns").m))
        # self.pulses.aom_lag = int(round(aom_lag.to("ns").m))
        # self.pulses.readout_time = int(round(readout_time.to("ns").m))
        # self.pulses.laser_buf = int(round(buffer_time.to("ns").m))        
        # self.pulses.clock_time = int(round(clock_duration.to("ns").m))
        # ##aom_lag really means laser_lag. 
        # ##self.seqs is, of course, one sequence,
        # ## but it's made by concatenating all sequences of a certain pi time.
        # self.seqs = self.pulses.PS_rabi(self.mw_times, pi_xy)     
        # print('run_ct not rounded', self.time_per_point.to('ns').m/self.pulses.total_time)
        # self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.time_one))

    # @PlotFormatInit(LinePlotWidget, ['latest', 'average','diff_average','no_trace_diff_avg'])
    # def init_format(p):
        # p.xlabel = 'time (us)'
        # p.ylabel = 'PL (cts/s)'
        
    # @PlotFormatUpdate(LinePlotWidget, ['no_trace_diff_avg'])#['latest', 'avg'])
    # def update_format(p, df, cache):
        # for item in p.plot_item.listDataItems():
            # item.setPen(color=(0,0,0,0), width=5)
        
    # ## returns the latest rabi sweeps. plural due to our pulse sequence.
    # @Plot1D
    # def latest(df, cache):
        # plot_return = {}
        # latest_data = df[df.sweep_idx == df.sweep_idx.max()]
        
        # return {'sig': [latest_data.t[0], latest_data.sig[0]], 'bg': [latest_data.t[0], latest_data.bg[0]]}
    # ## returns the overall time average of all rabi sweeps, not just for each update.
    # ## we are dropping the first point because it was not initialized
    # ###### we can probably use it now.
    # @Plot1D
    # def average(df, cache):
        # frame = df
        # avg_sig = np.empty(len(list(frame.sig[0])))
        # avg_bg = np.empty(len(list(frame.sig[0])))
        # for point_num in range(len(list(frame.sig[0]))):
            # sum_sig = 0; sum_bg = 0
            # for a in range(len(list(frame.sig))):
                # sum_sig += frame.sig[a][point_num]
                # sum_bg += frame.bg[a][point_num]
                # #print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            # avg_sig[point_num] = sum_sig / len(list(frame.sig))
            # avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        # print('finish data rearrangement')
        # return {
            # 'sig': [list(df.t)[0], list(avg_sig)],
            # 'bg': [list(df.t)[0], list(avg_bg)],
        # }
    # ## the difference between the average bright and dark signal
    # @Plot1D
    # def diff_average(df, cache):
        # frame = df
        # avg_sig = np.empty(len(list(frame.sig[0])))
        # avg_bg = np.empty(len(list(frame.sig[0])))
        # for point_num in range(len(list(frame.sig[0]))):
            # sum_sig = 0; sum_bg = 0
            # for a in range(len(list(frame.sig))):
                # sum_sig += frame.sig[a][point_num]
                # sum_bg += frame.bg[a][point_num]
            # avg_sig[point_num] = sum_sig / len(list(frame.sig))
            # avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        # return {
                # 'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
                # } 
    # ## the difference between the average bright and dark signal, with no trace
    # @Plot1D
    # def no_trace_diff_avg(df, cache):
        # frame = df
        # avg_sig = np.empty(len(list(frame.sig[0])))
        # avg_bg = np.empty(len(list(frame.sig[0])))
        # for point_num in range(len(list(frame.sig[0]))):
            # sum_sig = 0; sum_bg = 0
            # for a in range(len(list(frame.sig))):
                # sum_sig += frame.sig[a][point_num]
                # sum_bg += frame.bg[a][point_num]
                # print('sum_sig:',sum_sig,'sum_bg:',sum_bg)
            # avg_sig[point_num] = sum_sig / len(list(frame.sig))
            # avg_bg[point_num] = sum_bg / len(list(frame.bg))
            
        # return {
                # 'sig-bg': [list(df.t)[0], avg_sig - avg_bg],
                # }

# # class PlaylistODMRRabiTuneupSwabianSpyrelet(BaseFeedbackSpyrelet):
    # # """Runs ODMR and Rabi measurements, over multiple points
    # # as picked out in a spatial PL map. Separate powers are set for ODMR and Rabi.
    # # See ODMR and Rabi spyrelets for details.
    # # A sweep (of frequency or MW time) is run sub_sweeps times, then the laser
    # # is moved to the next point, etc. This happens sweeps times, so the total
    # # experiment sweeps at each point is actually sweeps*sub_sweeps. The spyrelet
    # # moves between points in this fashion so any long equipment drift affects
    # # all measurements.
    # # The parameters frequency, pi_pulse, pi_half_pulse, x_initial, and y_initial
    # # are setup as strings which, when evaluated in the code, are turned into unit-full
    # # lists. It is necessary that they are of the form "Q_(,'[unit]')"

    # # Args:
            # # sweeps:
            # # sub_sweeps:
            # # frequency:
            # # pi_time:
            # # pi_half_time:
            # # x_initial:
            # # y_initial:
    # # """
    # # REQUIRED_DEVICES = ['sg', 'pulses', 'urixyz']
    # # REQUIRED_SPYRELETS = {'newSpaceFB': SpatialFeedbackXYZSpyrelet}

    # # PARAMS = {
        # # 'device':{
            # # 'type': str,
            # # 'default': 'Dev1',
        # # },
        # # 'channel1':{
            # # 'type':list,
            # # 'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            # # 'default':'ctr1',
            # # },
        # # 'sampling_rate':{
            # # 'type':float,
            # # 'units':'Hz',
            # # 'suffix': ' Hz',
            # # 'default': 2.5e6,
        # # },
        # # 'time_per_point':{
            # # 'type':float,
            # # 'units': 's',
            # # 'suffix': ' s',
            # # 'default': 1,
        # # },
        # # 'PS_clk_channel':{
            # # 'type': str,
            # # 'default': 'PFI0',
        # # },
        # # 'sweeps_ODMR':{
            # # 'type': int,
            # # 'default': 10,
            # # 'positive': True,
        # # },
        # # 'sweeps_rabi':{
            # # 'type': int,
            # # 'default': 50,
            # # 'positive': True,
        # # },
        # # 'sub_sweeps':{
            # # 'type': int,
            # # 'default': 2,
            # # 'positive': True,
        # # },
        # # 'n_points':{
            # # 'type': int,
            # # 'default': 4,
            # # 'positive': True,
        # # },
        # # 'frequency':{ # for ODMR
            # # 'type': range,
            # # 'units':'GHz',
        # # },
        # # 'power_odmr':{
            # # 'type': float,
            # # 'default': -20,
        # # },
        # # 'power_rabi':{
            # # 'type': float,
            # # 'default': -20,
        # # },
        # # 'mw_times':{
            # # 'type': range,
            # # 'units': 'ns',
            # # 'default': {'func': 'linspace',
                        # # 'start': 0e-9,
                        # # 'stop': 1e-6,
                        # # 'num': 21},
        # # },
        # # 'pi_xy':{
            # # 'type': list,
            # # 'items': list(['x','y']),
            # # 'default': 'x'
        # # },
        # # 'probe_time': {
            # # 'type': float,
            # # 'default': 50e-6,
            # # 'units': 's',
        # # },
        # # 'init_time':{
            # # 'type': float,
            # # 'default': 3.5e-6,
            # # 'suffix': ' s',
            # # 'units': "s"
        # # },
        # # 'readout_time':{
            # # 'type': float,
            # # 'default': .4e-6,
            # # 'suffix': ' s',
            # # 'units': 's'
        # # },
        # # 'aom_lag':{
            # # 'type': float,
            # # 'default': 30e-9,
            # # 'suffix': ' s',
            # # 'units': 's'
        # # },
        # # 'clock_time':{
            # # 'type': float,
            # # 'default': 10e-9,
            # # 'suffix': ' s',
            # # 'units': 's'
        # # },
        # # 'singlet_decay':{
            # # 'type':float,
            # # 'default': .6e-6,
            # # 'suffix': ' s',
            # # 'units': 's',
        # # },
        # # 'buffer_time':{
            # # 'type': float,
            # # 'default': 0.15e-6,
            # # 'suffix': ' s',
            # # 'units': 's'
        # # },        
        # # 'feedback': {
            # # 'type': bool,
            # # 'default': 1,
        # # },
        # # 'dozfb': {
            # # 'type': bool,
            # # 'default': 1,
        # # },
        # # 'x_initial':{
            # # # 'units': 'um',
            # # 'type': str,
            # # 'default': 'Q_([0,0,0],"um")',
        # # },
        # # 'y_initial':{
            # # # 'units': 'um',
            # # 'type': str,
            # # 'default': 'Q_([0,0,0],"um")',
        # # },
        # # 'z_initial':{
            # # # 'units': 'um',
            # # 'type': str,
            # # 'default': 'Q_([0,0,0],"um")',
        # # },
        # # 'xyz_step':{
            # # 'type': float,
            # # 'units': 'm',            
            # # 'default': 60e-9,
        # # },
        # # 'shrink_every_x_iter':{
            # # 'type': int,
            # # 'default': 2,
        # # },
        # # 'starting_point': {
            # # 'type': list,
            # # 'items': list(['user_input','current_position (ignore input)']),
            # # 'default': 'current_position (ignore input)',
        # # },
        # # 'ODMR_fit': {
            # # 'type': list,
            # # 'items': list(['odmr1_fitfn','odmr2_fitfn']),
        # # },
        # # 'ODMR_f_guess': {
            # # 'type': str,
            # # 'default': 'Q_([2.85,2.886],"GHz")'
        # # },
        # # 'rabi_T_guess': {
            # # 'type': float,
            # # 'default': 1e-6,
            # # 'units': 'us',
        # # }
    # # }

    # # def main(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    # # sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    # # mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    # # feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    # # starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
            # # ## first perform ODMR sweeps until reach max or the fit is stable
            # # for sweep in self.progress(range(sweeps_ODMR)):
                # # if np.mean(self.odmr_done) == 1:
                    # # ## if all the fits are done, break the loop and continue to Rabi
                    # # ## this means the current point is the last point
                    # # break
                # # ## set the new xy position of the current nv.
                # # for self.pt in range(n_points):
                    # # if self.pt == 0 and sweep == 0:
                        # # x_diff_pt = 0
                        # # y_diff_pt = 0
                    # # elif self.pt == 0:
                        # # x_diff_pt = self.x_initial_list[0] - self.x_initial_list[-1]
                        # # y_diff_pt = self.y_initial_list[0] - self.y_initial_list[-1]
                    # # else:
                        # # x_diff_pt = self.x_initial_list[self.pt] - self.x_initial_list[self.pt-1]
                        # # y_diff_pt = self.y_initial_list[self.pt] - self.y_initial_list[self.pt-1]
                    # # self.x_initial = self.x_initial + x_diff_pt
                    # # self.y_initial = self.y_initial + y_diff_pt
                    # # #self.pulses.stream(self.pulses.Laser_On())
                    # # ## shorting loop to test rabi
                    # # # self.odmr_done[self.pt] = 1
                    # # # self.acquire({
                    # # #                 'sequence':         'ODMR',
                    # # #                 'point':            self.pt,
                    # # #                 'x_initial':        self.x_initial,
                    # # #                 'y_initial':        self.y_initial,
                    # # #                 'sweep_idx':        sweep*sub_sweeps,
                    # # #                 'point_sweep':      sweep,
                    # # #                 'power':            power_odmr,
                    # # #                 'f':                2.87e9,
                    # # #                 'x':                0,
                    # # #             })
                    # # # self.acquire({'point':self.pt, 'fit': 'ODMR', 'f_fit': Q_(2.868,'GHz')})
                    # # # self.frequencies[self.pt] = 2868000000
                    # # if self.odmr_done[self.pt] == 0:
                        # # ## if this point is not fit yet, measure
                        # # if feedback and sweep != 0:
                            # # self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink)
                            # # self.x_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x'])
                            # # self.y_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y'])     
                            # # self.z_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z'])
                            # # self.x_initial_list[self.pt] = self.x_initial
                            # # self.y_initial_list[self.pt] = self.y_initial
                            # # self.z_initial_list[self.pt] = self.z_initial
                        # # #self.x_initial, self.y_initial = self.run_feedback(1,1,self.z_sweeps,self.channels)
                        
                        # # for j in range(sub_sweeps):
                            # # for f in frequency:
                                # # try:
                                    # # self.sg.frequency = f # SG396 communication overhead of <1ms
                                # # except:
                                    # # raise RuntimeError('sg messed up')
                                # # ctrs_rates = self.read_odmr(math.ceil(len(self.buffers[0]/2)), self.buffers, 0)
                                # # self.acquire({
                                    # # 'sequence':         'ODMR',
                                    # # 'point':            self.pt,
                                    # # 'x_initial':        self.x_initial,
                                    # # 'y_initial':        self.y_initial,
                                    # # 'z_initial':        self.z_initial,
                                    # # 'sweep_idx':        sweep*sub_sweeps + j,
                                    # # 'point_sweep':      sweep,
                                    # # 'power':            power_odmr,
                                    # # 'f':                f,
                                    # # 'sig':              ctrs_rates[0],
                                    # # 'ref':              ctrs_rates[1],
                                # # })
                            # # data = pd.DataFrame(self._data)
                            # # point_sweep = data[data.point == self.pt]
                            # # grouped = point_sweep.groupby('f')
                            # # xs = grouped.sig - grouped.ref
                            # # xs_averaged = xs.mean()
                            # # try:
                                # # if ODMR_fit == 'odmr1_fitfn':
                                    # # p0 = [5e5,-1e10,self.ODMR_f[0],5e6]
                                    # # popt, pcov = optimize.curve_fit(self.odmr1_fitfn, xs_averaged.index, xs_averaged, p0=p0)
                                # # elif ODMR_fit == 'odmr2_fitfn':
                                    # # p0 = [5e5,-1e10,self.ODMR_f[0],5e6,-1e10,self.ODMR_f[1],5e6]
                                    # # popt, pcov = optimize.curve_fit(self.odmr2_fitfn, xs_averaged.index, xs_averaged, p0=p0)
                                # # f1s = popt[2] # right now only checks precision of first peak
                                # # self.odmr_fits['p'+str(self.pt+1)].append(f1s)
                                # # if self.odmr_fits['p'+str(self.pt+1)].__len__() > 5:
                                    # # running_avg = np.mean(self.odmr_fits['p'+str(self.pt+1)][-6:-1])
                                    # # if abs((f1s-running_avg)/running_avg) < .0002:
                                        # # ## if the fitting has succeeded for this point, save the fit
                                        # # self.acquire({'point': self.pt, 'fit': 'ODMR', 'f_fit': Q_(f1s*1e-9,'GHz')})
                                        # # self.odmr_done[self.pt] = 1
                                        # # self.frequencies[self.pt] = f1s
                                # # print('it fit with f={}'.format(f1s))
                            # # except RuntimeError:
                                # # print('this curve did not fit. keep going.')
                        # # if sweep == sweeps_ODMR-1 and j == sub_sweeps-1:
                            # # ## if the fit has not succeeded by the last sweep, just save some courtesy value and move on
                            # # self.acquire({'point': self.pt, 'fit': 'ODMR', 'f_fit': 2.87e9})

            # # self.sg.rf_amplitude = power_rabi
            # # for sweep in self.progress(range(sweeps_rabi)):
                # # for self.pt in range(n_points):
                    # # if self.pt == 0:
                        # # ## ODMR ended at the last point
                        # # x_diff_pt = self.x_initial_list[0] - self.x_initial_list[-1]
                        # # y_diff_pt = self.y_initial_list[0] - self.y_initial_list[-1]
                    # # else:
                        # # x_diff_pt = self.x_initial_list[self.pt] - self.x_initial_list[self.pt-1]
                        # # y_diff_pt = self.y_initial_list[self.pt] - self.y_initial_list[self.pt-1]
                    # # self.x_initial = self.x_initial + x_diff_pt
                    # # self.y_initial = self.y_initial + y_diff_pt
                    # # #self.pulses.stream(self.pulses.Laser_On())
                    # # ## short for testing
                    # # # self.acquire({
                    # # #                 'sequence':         'rabi',
                    # # #                 'point':            self.pt,
                    # # #                 'x_initial':        self.x_initial,
                    # # #                 'y_initial':        self.y_initial,
                    # # #                 'sweep_idx':        sweep*sub_sweeps,
                    # # #                 'point_sweep':      sweep,
                    # # #                 'power':            power_rabi,
                    # # #                 'f':                self.frequencies[self.pt],
                    # # #                 't':                100,
                    # # #                 'x':                0,
                    # # #                 'y':                0,
                    # # #             })
                    # # # self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(1000,'ns'), 'p_fit': Q_(100,'ns'), \
                    # # #              't_pi': Q_(400,'ns'), 't_pi2': Q_(150,'ns')})
                    # # # self.rabi_done[self.pt] = 1
                    # # # self.periods[self.pt] = 1000
                    # # # self.phases[self.pt] = 100
                    # # if self.rabi_done[self.pt] == 0:
                        # # if feedback:
                            # # self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink)
                            # # self.x_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x'])
                            # # self.y_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y'])     
                            # # self.z_initial = rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z'])
                            # # self.x_initial_list[self.pt] = self.x_initial
                            # # self.y_initial_list[self.pt] = self.y_initial
                            # # self.z_initial_list[self.pt] = self.z_initial
                        # # try:
                            # # self.sg.frequency = self.frequencies[self.pt]
                        # # except:
                            # # raise RuntimeError('sg messed up')
                        # # ## mw time sweep
                        # # for j in range(sub_sweeps):
                            # # for i, t in enumerate(mw_times):
                                
                                # # ctrs_rates = self.read(self.run_ct, self.data_ct, self.buffers, 1)
                                # # self.acquire({
                                    # # 'sequence':         'rabi',
                                    # # 'point':            self.pt,
                                    # # 'x_initial':        self.x_initial,
                                    # # 'y_initial':        self.y_initial,
                                    # # 'z_initial':        self.z_initial,
                                    # # 'sweep_idx':        sweep*sub_sweeps + j,
                                    # # 'point_sweep':      sweep,
                                    # # 'power':            power_rabi,
                                    # # 'f':                self.frequencies[self.pt],
                                    # # 't':                t,
                                    # # 'sig':              ctrs_rates[0],
                                    # # 'ref':              ctrs_rates[1],
                                # # })
                            # # data = pd.DataFrame(self._data)
                            # # point_sweep = data[(data.sequence == 'rabi') & (data.point == self.pt)]
                            # # grouped = point_sweep.groupby('t')
                            # # xs = grouped.x
                            # # xs_averaged = xs.mean()
                            # # ys = grouped.y
                            # # ys_averaged = ys.mean()
                            # # try:
                                # # ## fit both signal and bg subtraction
                                # # p0sig = [rabi_T_guess.to('s').m,0,2e-6,1e3,1e5]
                                # # poptsig, pcovsig = optimize.curve_fit(self.rabi_fitfn, xs_averaged.index, xs_averaged, p0=p0sig)
                                # # Tssig = poptsig[0]
                                # # self.rabi_fits_sig['p'+str(self.pt+1)].append(Tssig)
                                
                                # # if self.rabi_fits_sig['p'+str(self.pt+1)].__len__() > 5:
                                    # # ## first check if fit with only signal is good
                                    # # running_avg = np.mean(self.rabi_fits_sig['p'+str(self.pt+1)][-6:-1])
                                    # # if abs((Tssig-running_avg)/running_avg) < .03:
                                        # # self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(Tssig*1e9,'ns'), 'p_fit': Q_(poptsig[1]*1e9,'ns'), \
                                                     # # 't_pi': Q_((Tssig/2-poptsig[1])*1e9,'ns'), 't_pi2': Q_((Tssig/4-poptsig[1])*1e9,'ns')})
                                        # # self.rabi_done[self.pt] = 1
                                        # # self.periods[self.pt] = Tssig
                                        # # self.phases[self.pt] = poptsig[1]
                                # # print('it fit the signal with T={}'.format(Tssig))
                            # # except RuntimeError:
                                # # print('this curve did not fit with signal. keep going.')
                            # # try:
                                # # p0bg = [rabi_T_guess.to('s').m,0,2e-6,1e3,1e3]
                                # # poptbg, pcovbg = optimize.curve_fit(self.rabi_fitfn, xs_averaged.index, xs_averaged-ys_averaged, p0=p0bg)
                                # # Tsbg = poptbg[0]
                                # # self.rabi_fits_bg['p'+str(self.pt+1)].append(Tsbg)
                                # # if self.rabi_fits_bg['p'+str(self.pt+1)].__len__() > 5 and self.rabi_done[self.pt] == 0:
                                    # # ## then check with background subtracted
                                    # # running_avg = np.mean(self.rabi_fits_bg['p'+str(self.pt+1)][-6:-1])
                                    # # if abs((Tsbg-running_avg)/running_avg) < .03:
                                        # # ## if the fitting has succeeded for this point, save the fit
                                        # # self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(Tsbg*1e9,'ns'), 'p_fit': Q_(poptbg[1]*1e9,'ns'), \
                                                    # # 't_pi': Q_((Tsbg/2-poptbg[1])*1e9,'ns'), 't_pi2': Q_((Tsbg/4-poptbg[1])*1e9,'ns')})
                                        # # self.rabi_done[self.pt] = 1
                                        # # self.periods[self.pt] = Tsbg
                                        # # self.phases[self.pt] = poptbg[1]
                                # # print('it fit signal - bg with T={}'.format(Tsbg))
                            # # except RuntimeError:
                                # # print('this curve did not fit with bg subtraction. keep going.')
                        # # ## update for rabi
                        # # if sweep == sweeps_rabi-1 and j == sub_sweeps-1:
                            # # ## if the fit has not succeeded by the last sweep, just save some courtesy value and move on
                            # # self.acquire({'point': self.pt, 'fit': 'rabi', 'T_fit': Q_(1000,'ns'), 'p_fit': Q_(0,'ns'), \
                                        # # 't_pi': Q_(500,'ns'), 't_pi2': Q_(250,'ns')})
                        

    # # def initialize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    # # sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    # # mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    # # feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    # # starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
        # # # self.all_seqs = []
        # # self.time_per_point
        # # self.setup_pulses_ODMR(clock_time, probe_time)
        # # odmr_buffer_size = math.floor(time_per_point/probe_time) + 1
        # # odmr_buffer = np.zeros(int(odmr_buffer_size), dtype = np.uint32)
        # # # for i in range(n_points):#self.pi_times.__len_()): must add param for number of points or figure out how to do this right
        # # self.setup_pulses(init_time,aom_lag,readout_time,clock_time,singlet_decay,buffer_time,mw_times,pi_xy)
        # # self.data_ct = len(self.mw_times)
        # # buffer_size = 4*self.data_ct * self.run_ct# ignore run_ct
        # # ## we set up the buffer and array we use to get our signal in self.read()
        # # rabi_buffer = np.zeros(int(buffer_size), dtype=np.uint32)
        
        # # self.buffers = [odmr_buffer, rabi_buffer]
        # # self.num_signal = 2
            # # # self.all_seqs.append(self.seqs)
        # # self.odmr_fits = {}
        # # self.rabi_fits_sig = {}
        # # self.rabi_fits_bg = {}
        # # ODMR_f = eval(ODMR_f_guess)
        # # self.ODMR_f = ODMR_f.to('Hz').m
        # # self.index = 0
        # # # self.f_guesses = {}
        # # for i in range(n_points):
            # # label = 'p' + str(i+1)
            # # self.odmr_fits[label] = []
            # # self.rabi_fits_sig[label] = []
            # # self.rabi_fits_bg[label] = []
        # # self.odmr_done = np.zeros(n_points)
        # # self.rabi_done = np.zeros(n_points)        
        # # self.frequencies = np.zeros(n_points)
        # # self.periods = np.zeros(n_points)
        # # self.phases = np.zeros(n_points)
        # # # for i in range(ODMR_f.__len__()):
        # # #     label = 'x0' + str(i+1)
        # # #     self.f_guesses[label] = ODMR_f[i]
        # # # if ODMR_fit == 'odmr1_fitfn':
        # # #     self.odmr_fit_func = self.odmr1_fitfn(x,**self.f_guesses)
        # # #     print(self.odmr_fit_func)
        # # # elif ODMR_fit == 'odmr2_fitfn':
        # # #     self.odmr_fit_func = self.odmr2_fitfn(**self.f_guesses)
        

        # # self.x_initial_list = eval(x_initial)
        # # self.y_initial_list = eval(y_initial)
        # # self.z_initial_list = eval(z_initial)
        # # self.x_initial = self.x_initial_list[0]
        # # self.y_initial = self.y_initial_list[0]
        # # self.z_initial = self.z_initial_list[0]
        # # if self.x_initial_list.__len__() != self.y_initial_list.__len__() or self.x_initial_list.__len__()!=self.z_initial_list.__len__():
            # # print('x_initial and y_initial must have the same number of coordinate')
            # # return
        # # ## create channels list and check that there are no repeats
        # # self.channel = channel1
        # # #'def initialize(self, device, channels, PS_clk_channel, time_per_point, sampling_rate, data_download):'
        # # super().initialize(device, self.buffers, PS_clk_channel, time_per_point, sampling_rate, data_download)

        # # self.sg.rf_amplitude = power_odmr
        # # self.sg.mod_type = 'QAM'
        # # self.sg.rf_toggle = True
        # # self.sg.mod_toggle = True
        # # self.sg.mod_function = 'external'
        
        # # return
        
    # # def finalize(self, device, channel1, PS_clk_channel, sampling_rate, time_per_point, probe_time, \
                    # # sweeps_ODMR, sweeps_rabi, sub_sweeps, n_points, frequency, power_odmr, power_rabi,
                    # # mw_times, pi_xy, init_time, aom_lag, readout_time, singlet_decay, buffer_time, clock_time,
                    # # feedback, dozfb, x_initial, y_initial, z_initial, xyz_step, shrink_every_x_iter,
                    # # starting_point, ODMR_fit, ODMR_f_guess, rabi_T_guess):
        # # super().finalize(device, self.buffers, PS_clk_channel, time_per_point, sampling_rate, data_download)
        # # #self.sg.rf_toggle = False
        # # #self.pulses.Pulser.reset()

        # # data = pd.DataFrame(self._data)
        # # print('fitted parameters: \n point\t x\t y\t ODMR sweeps\t freq\t rabi sweeps\t T\t t_pi\t t_pi/2')
        # # for i in range (n_points):
            # # ## debug this
            # # point_data = data[data.point==i]
            # # print(str(i)+'\t'+str(round(point_data[point_data.sequence=='rabi'].x_initial.values[-1]*1e6,1))+'um\t' \
                    # # +str(round(point_data[point_data.sequence=='rabi'].y_initial.values[-1]*1e6,1))+'um\t' \
                    # # +str(int(point_data[point_data.sequence=='ODMR'].sweep_idx.values[-1]))+'\t\t' \
                    # # +str(round(point_data[point_data.fit=='ODMR'].f_fit.values[-1]*1e-9,4))+'GHz\t' \
                    # # +str(int(point_data[point_data.sequence=='rabi'].sweep_idx.values[-1]))+'\t' \
                    # # +str(round(point_data[point_data.fit=='rabi'].T_fit.values[-1]*1e9))+'ns\t' \
                    # # +str(round(point_data[point_data.fit=='rabi'].t_pi.values[-1]*1e9))+'ns\t' \
                    # # +str(round(point_data[point_data.fit=='rabi'].t_pi2.values[-1]*1e9))+'ns\t' \
                    # # )

        # # return

    # # def math_odmr(self, array):
        # # delta_buffer = array[1:] - array[0:-1] # taking the difference between each read window
        # # sum1 = np.sum(delta_buffer[::2]) # MW on, but collects dark (autotriggers and collect starting the first tick)
        # # sum2 = np.sum(delta_buffer[1::2]) # MW off, but collect bright.
        
        # # print('delta_buffer:', delta_buffer)
        # # print('sum1:', sum1, 'sum2:', sum2)          
        # # return [sum1, sum2]
        
    # # def math(self, array):
        
        # # ## divide buffer to different experiments
        # # delta_buffer_start = array[1::4] - array[0::4] 
        # # delta_buffer_end = array[3::4] - array[2::4] 
        # # final_data_dark = np.empty(self.data_ct); final_data_bright = np.empty(self.data_ct)
        # # for i in range(self.data_ct):
            # # final_data_dark[i] = np.sum(delta_buffer_start[i::self.data_ct])
            # # final_data_bright[i] = np.sum(delta_buffer_end[i::self.data_ct])
        # # return [final_data_dark, final_data_bright]
        
    # # def odmr1_fitfn(self,x,b=5e5,a1=-1e10,x01=2.8e9,g1=5e6):
        # # return b + a1*g1/((x-x01)**2+(g1/2)**2)
    # # def odmr2_fitfn(self,x,b=5e5,a1=-1e10,x01=2.86e9,g1=5e6,a2=-1e10,x02=2.88e9,g2=5e6):
        # # return b + a1*g1/((x-x01)**2+(g1/2)**2) + a2*g2/((x-x02)**2+(g2/2)**2)
    # # def odmr_fitmany(self, x, b = 1, g=5e6, a1=-1e10,x1=2.5e9,a2=-1e10,x2=2.6e9,a3=-1e10,x3=2.7e9,a4=-1e10,x4=2.8e9):
        # # return b + a1*g/((x-x01)**2+(g/2)**2) + a2*g/((x-x02)**2+(g/2)**2) + a3*g/((x-x3)**2+(g/2)**2) + a4*g/((x-x4)**2+(g/2)**2)
    # # def rabi_fitfn(self,x,Tr=1e-6,p=0,Td=1e-2,A=1e3,B=-10e4):
        # # return A*(np.exp(-(x)/Td)*np.cos((2*np.pi*(x+p))/Tr))+B

    # # def setup_pulses_ODMR(self, clock_time, probe_time):
        # # """Create list of swabian pulse sequences
        # # In this case the pulse sequence is a single block that turns
        # # on the laser and MW excitation and opens a read channel 
        # # """
        # # self.pulses.clock_time = int(round(clock_time.to('ns').m))
        # # self.pulses.read_time = int(round(probe_time.to('ns').m))
        # # self.seq = self.pulses.CWUriMR()
        # # self.seqsODMR = self.seq #[self.seq]

    # # def setup_pulses(self,init_time,aom_lag,readout_time,clock_time, singlet_decay, buffer_time, mw_times,pi_xy):
        # # """Create list of swabian pulse sequences
        # # Each sequence has a different microwave excitation time.
        # # Both branches are equal lengths.
        # # The computed ratio scales the collected data by 1/(readout duty cycle),
        # # so signals across experiments with the same readout time
        # # are directly comparable.
        # # """
        # # self.pulses.singlet_decay = int(round(singlet_decay.to('ns').m))
        # # self.pulses.clock_time = int(round(clock_time.to('ns').m))
        # # self.pulses.laser_time = int(round(init_time.to("ns").magnitude))
        # # self.pulses.aom_lag = int(aom_lag.to("ns").magnitude)
        # # self.pulses.readout_time = int(readout_time.to("ns").magnitude)
        # # self.pulses.laser_buf = int(buffer_time.to("ns").magnitude)
        # # mw_times_ns = [int(round(mw_time.to('ns').m)) for mw_time in mw_times]
        # # self.seqs = self.pulses.PS_rabi(mw_times_ns,pi_xy)
        # # self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
        # # self.run_ct = int(round(self.time_per_point.to("ns").m/self.pulses.time_one))

    # # @PlotFormatInit(LinePlotWidget, ['latestODMR','averageODMRs'])
    # # def init_format(p):
        # # p.xlabel = 'frequency (Hz)'
        # # p.ylabel = 'PL (cts/s)'

    # # @PlotFormatInit(LinePlotWidget, ['latestRabi','averageRabis','diff_averageRabis'])
    # # def init_format(p):
        # # p.xlabel = 'time (s)'
        # # p.ylabel = 'PL (cts/s)'
        
    # # @Plot1D
    # # def latestODMR(df, cache):
        # # latest_data = df[(df.point==df.point[-1]) & (df.point_sweep == df.point_sweep.max())]
        # # return {'ch1': [latest_data.f, latest_data.x]}

    # # @Plot1D
    # # def averageODMR(df, cache):
        # # plot_return = {}
        # # if df.point_sweep.max() != 0:
            # # for i in range(df.point.max()+1):
                # # grouped = df[(df.point==i) & (df.sequence=='ODMR')].groupby('f')
                # # xs = grouped.x
                # # xs_averaged = xs.mean()
                # # label = 'odmr avg' + str(i)
                # # plot_return.update({label: [xs_averaged.index, xs_averaged]})
        # # return plot_return

    # # @Plot1D
    # # def latestRabi(df, cache):
        # # latest_data = df[(df.point==df.point[-1]) & (df.point_sweep == df.point_sweep.max()) & (df.sequence=='rabi')]
        # # return {'ch1': [latest_data.t, latest_data.x],
                # # 'ch2': [latest_data.t, latest_data.y]}
                
    # # @Plot1D
    # # def averageRabis(df, cache):
        # # plot_return = {}
        # # if df.point_sweep.max() != 0:
            # # for i in range(df.point.max()+1):
                # # grouped = df[(df.point==i) & (df.sequence=='rabi')].groupby('t')
                # # xs = grouped.x
                # # xs_averaged = xs.mean()
                # # label = 'rabi signal' + str(i)
                # # plot_return.update({label: [xs_averaged.index, xs_averaged]})
        # # return plot_return

    # # @Plot1D
    # # def diff_averageRabis(df, cache):
        # # plot_return = {}
        # # if df.point_sweep.max() != 0:
            # # for i in range(df.point.max()+1):
                # # grouped = df[(df.point==i) & (df.sequence=='rabi')].groupby('t')
                # # xs = grouped.x
                # # ys = grouped.y
                # # xs_averaged = xs.mean()
                # # ys_averaged = ys.mean()
                # # label = 'rabi diff' + str(i)
                # # plot_return.update({label: [xs_averaged.index, xs_averaged - ys_averaged]})
        # # return plot_return