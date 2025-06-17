# std
import collections

import numpy as np
import time
import math
from itertools import cycle
from itertools import count
import matplotlib.pyplot as plt
import logging
import scipy as sp
from scipy import signal, optimize
import datetime as Dt

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
                               READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
from nidaqmx.stream_readers import CounterReader  # , DigitalSingleChannelWriter

# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

from lantz.drivers.ni.UriFSM import UriSetup
from spacefb import SpatialFeedbackXYZSpyrelet
# from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence

import itertools as it
from nspyre.gui.colors import cyclic_colors, colors
import rpyc

# for data download
from threed.data_and_plot import save_excel

COLORS = cycle(colors.keys())



'''
class BaseFeedbackSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'streamer',
        'urixyz',
        'infrared',
    ]

    """
# This is the base spyrelet that ties together all common functions.
# It enables feedback (once we fix it),it downloads data, it handles the reads for each experiment.
# Unfortunately, many things have to be customized for each experiment, so this is barebones.
"""
    # REQUIRED_SPYRELETS = {
        # 'newSpaceFB': SpatialFeedbackXYZSpyrelet
    # }

    PARAMS = {
        'pos_initial': {
            'type': str,
            'default': "Q_([0.,0.,0.], 'um')",
        },
        # 'xy_max_min_step':{
            # 'type': str,
            # 'default': '[.100, .010, 3]',
        # },
        # 'z_max_min_step':{
            # 'type': str,
            # 'default': '[.100, .010, 3]',
        # },
        # 'starting_point': {
            # 'type': list,
            # 'items': list(['user_input','current_position (ignore input)']),
            # 'default': 'current_position (ignore input)',
        # },
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
        # 'total_time':{
            # 'type':float,
            # 'units': 's',
            # 'default': 1
        # },
        'data_download':{
            'type': bool,
        },
    }
    # ##this feedback has not yet been adapted.
    # def run_feedback(self,sweep_idx,xy_feedback_sweeps,z_feedback_sweeps,starting_point):
        # if np.mod(sweep_idx,z_feedback_sweeps) == 0 and sweep_idx > 0:
            # dozfb = True
        # else:
            # dozfb = False
        
        # feed_params = {
            # 'starting_point': str(starting_point),
            # 'x_initial': self.x_initial,
            # 'y_initial': self.y_initial,
            # 'z_initial': self.z_initial,
            # 'do_z': dozfb,
            # 'xy_max_min_step': self.xy_max_min_step,
            # 'z_max_min_step': self.z_max_min_step,
        # }
        # ## we make sure the laser is turned on.
        # self.streamer.Pulser.constant((0,[7],0.0,0.0))
        
        # #import pdb; pdb.set_trace()
        # self.call(self.newSpaceFB,**feed_params)
        
        
        # ##space_data is the last line of data from spatialfeedbackxyz
        # space_data = self.newSpaceFB.data.tail(1)
        # print(space_data)
        # self.x_initial = Q_(space_data['x_center'].values[0],'um')
        # self.y_initial = Q_(space_data['y_center'].values[0],'um')
        # print('x:', self.x_initial)
        # print('y:', self.y_initial)
        # if dozfb:
            # self.z_initial = Q_(space_data['z_center'].values[0],'um')
            # print('z:', self.z_initial)
            # return self.x_initial, self.y_initial, self.z_initial
        # print(self.x_initial)
        
        # return self.x_initial, self.y_initial

    def initialize(self, pos_initial, device, channel, PS_clk_channel,
                   mwPulseTime, sampling_rate, data_download):
        ## define class parameters
        self.x_initial = eval(pos_initial)[0].to('um').m
        self.y_initial = eval(pos_initial)[1].to('um').m
        self.z_initial = eval(pos_initial)[2].to('um').m
        self.sampling_rate = sampling_rate.to('Hz').m
        # self.xy_max_min_step = xy_max_min_step
        # self.z_max_min_step = z_max_min_step
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
        #self.read_tasks = []
        self.readers = []
        
        
        ## defines the ctr channel
        dev_channel = device + '/' + channel
        
        ## create the read task for each counter channel
        self.read_task =(nidaqmx.Task('THE_read_task'))
        self.read_task.ci_channels.add_ci_count_edges_chan(
                                dev_channel,
                                edge=Edge.RISING,
                                initial_count=0,
                                count_direction=CountDirection.COUNT_UP
        )
        
        ## this is superfluous if the PFI channels are the default options
        PFI = ctrs_pfis[channel]
        pfi_channel = '/' + device + '/' + PFI
        self.read_task.ci_channels.all.ci_count_edges_term = pfi_channel
        
        ## set up read_task timing by external PS clock (triggers automatically when tasks starts)
        self.read_task.timing.cfg_samp_clk_timing(
                                self.sampling_rate, # must be equal or larger than max rate expected by PS
                                source= self.clk_channel,
                                sample_mode=AcquisitionType.FINITE, #CONTINUOUS, # can also limit the number of points
                                samps_per_chan= self.buffer_size
        )
        
        #print('sampling rate:', self.sampling_rate)
        
        ## create counter stream object 
        self.readers.append(CounterReader(self.read_task.in_stream))
        
                
        ##the last thing we do is initialize our signal generator.
        ## arbitrarily, I set the sg frequency before turning it on to ensure
        ## there's no dummy value damage.
        self.sg.frequency = Q_(2.87e9, 'Hz')
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
        
        

                
    def finalize(self, pos_initial, device, channel, PS_clk_channel,
                   mwPulseTime, sampling_rate, data_download):
        
        ## stop and close all tasks
        # for i,read_task in enumerate(self.read_tasks):
            #time.sleep(0.5)
            #self.read_tasks[i].stop()
        self.read_task.close()
            #time.sleep(0.5)
        
        ## turns off instruments
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.streamer.Pulser.reset()
        ## control if laser turns on or off.
        ## if laser turns off, you must restart with swabian gui, not NSpyre.
        ## saves the data to an excel sheet.
         note: saving this data might cause an error, because the self.acquires do not have continuous indexes.
        if data_download:
            print("name of spyrelet is", self.name)
            save_excel(self.name)
            print('data downloaded B)')
        ## experiment finishes
        print("FINALIZE")
    '''        
    
    ## read the buffer from each stream reader and calculate count rate
    ## from counts at the beginning and end of the read window
    ## this assume there are at least two clock ticks per read window
    
    ##currently used on ODMR and PulsedODMR
    # def read_odmr(self, n_runs):
                
        # ## looping through the stream readers (one per channel)
        # for i,reader in enumerate(self.readers): # currently only one collection channel  
            
            # ## for each read point; start task, start pulse streaming, and read samples to buffer
            # ## then stop the task and reset the pulse streaming 
            # self.read_tasks[i].start()                
            
            
            # #####################################################
            # print('now in read function index:', self.index)
            # print('sequence length:', n_runs)
            # print('buffer length:', self.buffer_size)
            # # print('index:', self.index)
            # # print('sequence:', self.seqs[self.index])
            # #####################################################
            # # stream n_runs amount of repetitions (spyrelet specific)
            # t1 = time.time()
            # self.streamer.Pulser.stream(self.seqs[self.index], int(n_runs))  #int(n_runs)    -1
            # ## read into buffer
            # print('t1', time.time() - t1)
            # ## time.sleep(100)
            # num_samps = self.readers[i].read_many_sample_uint32(
                    # self.ni_ctr_sample_buffer,
                    # number_of_samples_per_channel=self.buffer_size,
                    # timeout= self.timeout
            # )
            
            # ########################################################
            # #print('buffer length:', len(self.ni_ctr_sample_buffer))
            # #print('num_samps:', num_samps)
            # if num_samps < self.buffer_size:
                # print('something wrong: buffer issue')
                # return
            # ########################################################
            
            
            # ## stop the task and the pulse streaming
            # self.read_tasks[i].stop() 
            # self.streamer.Pulser.reset()
            # ## perform the math of the specific spyrelet.
            # math_output = self.math(self.ni_ctr_sample_buffer)
            # signal = math_output
                
        # #print('signal:', signal)
        # return signal
        
'''     
    def read(self, n_runs, points_per_stream):
        
        ## defines logic arrays 
        ## self.num_signal designates how many different read windows we collect
        ## n_runs * points_per_stream gives us the amount of times one read window
        ## is collected during one sweep/plot
        signal = np.empty(shape=(self.num_signal, n_runs * points_per_stream))
        
        ## for each read point; start task, start pulse streaming, and read samples to buffer
        ## then stop the task and reset the pulse streaming 
        self.read_task.start()                
        
        #t1 = time.time()
        #print('number of times to stream the seq', n_runs)
        #print('buffer size', self.buffer_size)
        #print('before stream')
        self.streamer.Pulser.stream(self.seqs, n_runs) # stream n_runs amount of repetitions (spyrelet specific)
        t2 = time.time()
        print('points_per_stream', points_per_stream, 'n_runs', n_runs)
        #print('current time:',t2)
        print('buffer size', self.buffer_size)
        #print('shape of sample buffer', np.shape(self.ni_ctr_sample_buffer))
        #print((4 * (points_per_stream) + 4) * self.run_ct)
        #print('time after stream', t2-t1)
        num_samps = self.readers[0].read_many_sample_uint32(
                self.ni_ctr_sample_buffer,
                number_of_samples_per_channel=self.buffer_size,
                timeout = self.timeout
        )
        
        ## clarify there is no buffer issue.
        if num_samps < self.buffer_size:
            print('something wrong: buffer issue')
            return
        
        ## stop the task and the pulse streaming
        ## may not be required
        self.read_task.stop() 
        self.streamer.Pulser.reset() 
        print('read finished:', time.time() - t2)
        ## math logic returns the sum of counts in each read window. 
        ## this data may be acquired to mongo.
        signal = self.math(self.ni_ctr_sample_buffer)
        
        #print('math finished')
        # # Now, the signal is a double list of arrays of size ni_ctr_sample_buffer/4
        return signal
'''

class AlternateODMR(Spyrelet):
    """
    Shivam: This class is to find the quasilinear slope (that will be inputted into 2 point measurement experiments)
    It has an option to do stationary measurements with intermittent newspaceFB tracking or to do continuous tracking
    while taking measurements (as would be needed inside cell samples)
    """

    REQUIRED_DEVICES = [
        'sg',
        'streamer',
        'urixyz',
        'infrared',
    ]
    REQUIRED_SPYRELETS = {

     'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    PARAMS = {
        'device': {
            'type': str,
            'default': 'Dev1',
        },
        'PS_clock_channel': {
            'type': str,
            'default': 'PFI0',
        },
        'APD_channel': {
            'type': list,
            'items': list(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none']),
            'default': 'ctr1',
        },
        'sampling_rate': {
            'type': float,
            'units': 'Hz',
            'suffix': ' Hz',
            'default': 50000,
        },
        'clockPulseTime': {
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'mwPulseTime': {
            'type': float,
            'default': 50e-6,
            'suffix': ' s',
            'units': 's',
        },
        # This value is the equivalent of time_per_point in ODMR, but now in each point we consider two frequencies and
        # with one centered signal generator frequency
        'time_per_sgpoint': {
            'type': float,
            'default': 1,
            'units': 's',
        },

        # 'time_per_measurement': {
        # 'type': float,
        # 'positive': True,
        # 'suffix': ' s',
        # 'units': 's',
        # 'default': 1
        # },
        'sweeps': {
              'type': int,
            'default': 10,
            'positive': True
        },
        'frequencies': {
            'type': str,
            'default': '[2.85e9, 2.89e9, 20]',
        },
        # Shivam: This is the range of values of frequencies that is taken into consideration for the quasilinear slope fitting.
        'slope_range': {
            'type': str,
            'default': '[2.868e9, 2.871e9]',
        },
        'sideband_frequency': {
            'type': list,
            'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                      '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                      '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                      '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                      '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                      '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                      '5.952380952',
                      '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
                      '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
                      '2.5'],

            'default': '10.1010101',
        },
        'rf_amplitude': {
            'type': float,
            'default': -20,
        },
        'read_timeout': {
            'type': int,
            'default': 12,
        },
        'sweeps_until_feedback': {
            'type': int,
            'default': 6,
        },
        'z_feedback_every': {
            'type': int,
            'default': 1,
        },
        'xyz_step_nm': {
            'type': float,
            'units': 'm',
            'default': .5e-7,
        },
        ## this value scales the search window along z, since it is less sensitive.
        ## this can be changed to a factor instead of percentage.
        'shrink_every_x_iter': {
            'type': int,
            'positive': True,
            'default': 1,
        },
        'starting_point': {
            'type': list,
            'items': list(['user_input','current_position (ignore input)']),
            'default': 'current_position (ignore input)',
        },

        # Option to do advanced tracking from Harry's paper
        'continuous_tracking': {
            'type': bool,
            'default': False
        },
        'searchXYZ': {
            'type': str,
            'default': "Q_([500, 500, 500], 'nm')",
        },
        # Search range can vary based on how far NV has drifted, so need max and min bounds
        'max_search': {
            'type': str,
            'default': "Q_([1000, 1000, 1000], 'nm')",
        },
        'min_search': {
            'type': str,
            'default': "Q_([100, 100, 100], 'nm')",
        },
        # Shivam: This parameter is the length of scan in each direction in nm
        'scan_distance': {
            'type': str,
            'default': "Q_([30, 30, 50], 'nm')",
        },
        # This boolean value determines whether the search range is modified based on the drift of the nanodiamond or not
        'changing_search': {
            'type': bool,
            'default': False
        },
        # Shivam: Next two parameters are for changing the search radius with PID control
        # Optimize for search radius to be double the drift distance of the NV
        'search_PID': {
           'type': str,
           'default': "[0.5,0.01,0]" 
        },
        'search_integral_history': {
           'type': int,
           'default': 5 
        },
        # This is the spot size FWHM in micrometers
        'spot_size': {
            'type': float,
            'default': 400e-9,
            'suffix': ' m',
            'units': 'm',
        },
        # Option to do advanced tracking from Harry's paper
        'advanced_tracking': {
            'type': bool,
            'default': False
        },
        # Units of nm^2 / us
        # Does not matter if not doing advanced tracking
        'diffusion_constant': {
            'type': float,
            'default': 200,
        },
    
        'data_download': {
            'type': bool,
        },
    }

    def initialize(self, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                   sweeps, frequencies, slope_range, sideband_frequency, 
                   read_timeout, sweeps_until_feedback, z_feedback_every, 
                   xyz_step_nm, shrink_every_x_iter, starting_point, 
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance, changing_search, search_PID, 
                   search_integral_history, spot_size, advanced_tracking, 
                   diffusion_constant, data_download):
        #\if I write self.freq instead of freq, it is addressable in main, so that line of code would be redundant
        ## Aidan: In this experiment, do we change our frequencies?
        freq, sb_freq = self.process_frequencies(frequencies, sideband_frequency)
        #self.preparations(device, PS_clock_channel, APD_channel, sampling_rate, time_per_sgpoint, mwPulseTime,
        #                  clockPulseTime, sb_freq, rf_amplitude)  # self.sb_freq,
        

        # SHIVAM: CHECK IF I SHOULD ONLY HAVE THIS IF STATIONARY TRACKING
        self.sequence, self.stream_count, self.new_pulse_time = self.ready_pulse_sequence(time_per_sgpoint, mwPulseTime, clockPulseTime,
                                                                     sb_freq, rf_amplitude)

        self.buffer = self.create_buffer(time_per_sgpoint, mwPulseTime)
        data_channel, clock_channel = self.create_channels(device, PS_clock_channel, APD_channel)
        self.APD_task, self.APD_reader = self.create_ctr_reader(data_channel, sampling_rate, clock_channel,
                                                                len(self.buffer))
        
        self.continuous_tracking = continuous_tracking
        if advanced_tracking and not continuous_tracking:
            raise ValueError('Advanced tracking requires continuous tracking to be enabled')
        
        if continuous_tracking:
            self.search_kp, self.search_ki, self.search_kd = eval(search_PID)
            self.search = eval(searchXYZ)
            print("search is " + str(self.search))

            self.max_search = eval(max_search)

            self.min_search = eval(min_search)

            # Shivam: Check syntax
            self.scan_distance = eval(scan_distance)
            print("scan distance is " + str(self.scan_distance))

            self.bufsize = math.floor(time_per_sgpoint/mwPulseTime)

            self.check_appropriate_distance()

            self.spot_size = Q_(spot_size, 'um').m
            print("self.spot_size is " + str(self.spot_size))

            # Shivam: Parameters for tracking
            self.drift = Q_([0, 0, 0], 'um')

            # Shivam: Initializing motion controller for data collection. CHECK IF FIRST LINE NEEDED
            self.urixyz.daq_controller.new_ctr_task(device + '/' + APD_channel)
            self.urixyz.daq_controller.acq_rate = sampling_rate

        
            if advanced_tracking:
                effective_buffer_size = self.bufsize - 2
                num_bins = effective_buffer_size / 2
                self.time_elapsed = num_bins * self.real_time_per_scan
                self.diffusion_constant = diffusion_constant
                self.n_k = [0,0,0]
                self.p_k = [2 * diffusion_constant * self.time_elapsed] * 3
                self.x_k = [self.urixyz.daq_controller.position['x'].to('um').m,
                            self.urixyz.daq_controller.position['y'].to('um').m,
                            self.urixyz.daq_controller.position['z'].to('um').m]
                print("x_k is " + str(self.x_k))

                # CHECK THE TUNING OF w
                self.w = self.spot_size ** 2


        
            

        self.XYZ_center = [self.urixyz.daq_controller.position['x'],
                            self.urixyz.daq_controller.position['y'],
                            self.urixyz.daq_controller.position['z']]

        # This will be the variable storing total fluorescence every run
        self.total_fluor = 0

        self.left_frequency_slope = eval(slope_range)[0] 
        self.right_frequency_slope = eval(slope_range)[1]


        
    '''
    def preparations(self, device, PS_clock_channel, APD_channel, sampling_rate,
                     time_per_sgpoint, mwPulseTime, clockPulseTime, sb_freq, rf_amplitude):

        self.sequence, self.stream_count, new_pulse_time = self.ready_pulse_sequence(time_per_sgpoint, mwPulseTime, clockPulseTime,
                                                                     sb_freq, rf_amplitude)

        self.buffer = self.create_buffer(time_per_sgpoint, mwPulseTime)
        data_channel, clock_channel = self.create_channels(device, PS_clock_channel, APD_channel)
        self.APD_task, self.APD_reader = self.create_ctr_reader(data_channel, sampling_rate, clock_channel,
                                                                len(self.buffer))
    '''


    def check_appropriate_distance(self):
        # This function checks whether the scan distance is too small to cover the entire search range
        for i in range(3):
            # Multiplying self.search by 2 because the search range is from XYZ_center -self.seaarch to XYZ_center + self.search
            #aidan: self.bufsize is defined? previously used len(self.buffer)
            if self.scan_distance[i].to('nm').m < (2 * self.search[i].to('nm').m / self.bufsize):
                print("ERROR: scan distance for index " + str(i) + " is too small, please decrease scan distance to at least " + str(self.search[i].to('nm').m / self.bufsize) + " nm.")
                raise ValueError('Scan distance too small')
    
    def process_frequencies(self, frequencies, sideband_frequency):
        new_sideband = eval(sideband_frequency) * 1e6
        new_frequencies = np.linspace(eval(frequencies)[0], eval(frequencies)[1], eval(frequencies)[2])
        return new_frequencies, new_sideband

    def main(self, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                   sweeps, frequencies, slope_range, sideband_frequency, 
                   read_timeout, sweeps_until_feedback, z_feedback_every, 
                   xyz_step_nm, shrink_every_x_iter, starting_point, 
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance, changing_search, search_PID, 
                   search_integral_history, spot_size, advanced_tracking, 
                   diffusion_constant, data_download):
        
        freq, sb_freq = self.process_frequencies(frequencies, sideband_frequency)
        print('main take me off your feet?')
        

        # Shivam: The following is the classical case where we are not tracking
        # while taking I1 and I2 data

        if not continuous_tracking:
    
            for sweep in range(sweeps):
                print('before feedback')
                self.feedback(sweep, sweeps_until_feedback, z_feedback_every, xyz_step_nm, shrink_every_x_iter,starting_point)
                for f in freq:
                    print("Frequency value is " + str(f))
                    # time_start = time.time()
                    #import pdb; pdb.set_trace()
                    self.sg.frequency = Q_(f, 'Hz')
                    print('frequency:', self.sg.frequency)
                    # import pdb; pdb.set_trace()

                    output_buffer = self.odmr_read(self.buffer, self.APD_task, self.APD_reader, self.sequence,
                                                self.stream_count, read_timeout)
                    data_I1, data_I2 = self.odmr_math(output_buffer)
                    print("ODMR Maths result:")
                    print(data_I1, data_I2)
                    # Shivam: equivalent of return statement, since acquired into mongo database
                    print('are we doing this????')
                    
                    self.mongo_acquire(data_I1, data_I2, sweep, f, sb_freq, self.total_fluor)
                    
                    # print('time from start of frequency sweep:', time.time() - time_start)

        else:
            # Shivam: The search_error_array has 3 rows for x, y, z and integral_history columns for the latest to oldest error values
            search_error_array = np.zeros((3, search_integral_history))  # Shivam: Same as above but for search radius optimization
            index = 0
            # Counts every time we measure a certain frequency value
            self.counter = 0
            for sweep in range(sweeps):
            
                for f in freq:
                    # time_start = time.time()
                    #import pdb; pdb.set_trace()
                    self.sg.frequency = Q_(f, 'Hz')
                    print('frequency:', self.sg.frequency)
                    # import pdb; pdb.set_trace()

                    self.search, data_I1, data_I2, search_error_array = self.one_axis_measurement(self.bufsize, index, PS_clock_channel,
                                                                        self.search, self.scan_distance,
                                                                        read_timeout, self.spot_size, 
                                                                        advanced_tracking, changing_search, 
                                                                        search_error_array, search_integral_history,
                                                                        sampling_rate)
                    
                    # Shivam: Use self.current_temp to continually use the latest temperature from the initial setting onwards.

                    print("Main search_error_array is " + str(search_error_array))
                    print(data_I1, data_I2)
                    # Shivam: equivalent of return statement, since acquired into mongo database

                    
                    
                    self.mongo_acquire(data_I1, data_I2, sweep, f, sb_freq, self.total_fluor)

                    self.counter += 1

                    # Updating the index to loop search axis through 0, 1, 2 = x, y, z
                    index = (index + 1) % 3
                    

    def one_axis_measurement(self, buffer_size, index, PS_clk_channel,
                search, scan_distance, read_timeout, spot_size, advanced_tracking, 
                changing_search, search_error_array, search_integral_history,
                sampling_rate):
        
        print("We are indeed running tracking code")
        data, buffer_allocation, remaining_buffer = self.read_stream_flee(index, PS_clk_channel, search, buffer_size, scan_distance, read_timeout)

        ## confirmed, here I have 180-200 ms of lag
        print("Length of data is " + str(len(data)))
        ## after this is 70-130 ms of lag        
        tracking_data, track_steps, data_I1, data_I2 = self.process_data(data, buffer_allocation, remaining_buffer, index, search)

        # Shivam: Processes tracking data and sets to new position along index axis
        search, search_error_array = self.datanaly(tracking_data, track_steps, index, search, spot_size, advanced_tracking, 
                               changing_search, search_error_array, search_integral_history)

        ## total it says i have 250 ms of lag

        ## I can have up to 300 ms.

        return search, data_I1, data_I2, search_error_array
    

    def read_stream_flee(self, index, PS_clk_channel, search, buffer_size, scan_distance, read_timeout):
        ## total this has 180 ms of lag.
        # time_track = time.time()
        xyz_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                buffer_size)
        # Shivam: Assigns the entire XYZ_center array to both newly defined arrays
        pos_center_st = self.XYZ_center[:]
        pos_center_end = self.XYZ_center[:]
        pos_center_st[index] = xyz_steps[0]
        pos_center_end[index] = xyz_steps[-1]

        distance_of_sweep = (np.abs(pos_center_end[index] - pos_center_st[index])).to('nm').m
        print(distance_of_sweep)
        print(scan_distance)
        number_of_steps = math.ceil(distance_of_sweep / scan_distance[index].to('nm').m)
        print("The number of steps is " + str(number_of_steps))
        effective_scan_distance = distance_of_sweep / number_of_steps
        print("The effective scan distance is " + str(effective_scan_distance))
        # Shivam: Subtracted by 2 because of the way the buffer is sliced to keep equal photon exposure for I1 and I2 
        effective_buffer_size = buffer_size - 2
        print("The effective buffer size is " + str(effective_buffer_size))
        # Shivam: Buffer allocation for each step of scan
        buffer_allocation = math.floor(effective_buffer_size / number_of_steps)
        print("The buffer allocation is " + str(buffer_allocation))
        # import pdb; pdb.set_trace()
        # Shivam: Doing a 1 axis scan from the set start point till end point with buffer_size steps
        # Remaining buffer is for later calculations, but this function is primarily for the scan.
        # Points per step signifies how many repetitions of the line scan we are doing
        remaining_buffer = self.urixyz.daq_controller.hs_prepare(buffer_size, buffer_allocation, PS_clk_channel,
                                            {'x': pos_center_st[0], 'y': pos_center_st[1], 'z': pos_center_st[2]},
                                            {'x': pos_center_end[0], 'y': pos_center_end[1], 'z': pos_center_end[2]},
                                            number_of_steps)

        ###Before this, around .12 seconds have elapsed

        'start the pulse streamer and the task close to simultaneously'

        self.streamer.Pulser.stream(self.sequence, self.run_ct)
        ## this is 35 ms all on its own. 
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        # Shivam: Changed from num_freq * 2 to num_freq because we are not doing background collection
        scan_data = self.urixyz.daq_controller.hs_linescan(read_timeout)

        self.streamer.Pulser.reset()
        ## this is 5 miliseconds
        # print('time for read stream flee:', time.time() - time_track)

        ## pulser stream to pulser reset has 60ms delay.
        
        return rpyc.utils.classic.obtain(scan_data), buffer_allocation, remaining_buffer
    

    def process_data(self, input_buffer, buffer_allocation, remaining_buffer, index, search):
        # Shivam: We are removing the last value of I2 from the buffer to not have the last photon count
        # This is because we do not have a clock at the last time period and so would only have 1 out of 2 relevant counts for that segment when subtracting
        # This means that we will effectively have n - 1 runs when setting the time per sg point for n runs
        print("The input buffer size is " + str(len(input_buffer)))
        effective_buffer = input_buffer[:-1]
        print("The later effective buffer size is " + str(len(effective_buffer)))
        # Shivam: sliced to new array 2nd element onwards subtracting all elements to the left (I1 - I0, I2 - I1, ... ,
        interval_data = effective_buffer[1:] - effective_buffer[:-1]

        # This gets the number of I1 I2 pulsesequences that we are considering in our calculations
        # This is needed for our calculation of total time of photon collection in advanced_tracking

        num_bins = int(len(interval_data) / 2)
        print("The number of bins is " + str(num_bins))

        # Shivam: sums interval data in steps of 4 (I1-I0+I5-I4+...) is the first element
        sum_Is = [np.sum(interval_data[i::2]) for i in range(2)]
        # \ sum_Is = [#,#,#,#]
        # data = sum_Is[0]/sum_Is[1] - sum_Is[2]/sum_Is[3]

        # Shivam: I1, I2 total counts for w1 and w2
        data_I1 = sum_Is[0]
        data_I2 = sum_Is[1]


        if remaining_buffer > 0:
            tracking_buffer = input_buffer[:(-remaining_buffer + 1)]
        else:
            print("Error in remaining buffer")

        print("Tracking buffer is " + str(tracking_buffer))
        print("Length of tracking buffer is " + str(len(tracking_buffer)))

        tracking_interval = tracking_buffer[1:] - tracking_buffer[:-1]

        print("Tracking interval is " + str(tracking_interval))
        print("Length of tracking interval is " + str(len(tracking_interval)))


        # Shivam: This sums over the buffer allocation for each position step of the scan and stores in new array
        tracking_data = np.sum(tracking_interval.reshape(-1, buffer_allocation), axis=1)
        print("Length of tracking data is " + str(len(tracking_data)))
        print("Tracking data is " + str(tracking_data))

        track_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                len(tracking_data)).to('um').m
        
        
        return tracking_data, track_steps, data_I1, data_I2
    

    def datanaly(self, tracking_data, track_steps, index, search, spot_size, advanced_tracking, 
                 changing_search, search_error_pre_array, search_integral_history):
        '''
        Calculates Gaussian fit for the tracking data and sets the new center position for the next scan (moves the laser directly)
        '''
        self.total_fluor = np.sum(tracking_data)
        print("Total Fluorescence is " + str(self.total_fluor))
        print('Out of XYZ = [0,1,2], this is the', index, 'axis')
        # if index == 2:
        #     print("Track steps is " + str(track_steps))
        #     print("Tracking data is " + str(tracking_data))
        #     max_count_position = track_steps[np.argmax(tracking_data)]
        #     self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
        #     self.XYZ_center[index] = Q_(max_count_position, 'um')
        #     self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
        #     print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
        #     print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)
        #     return search

        # Here we are attempting to fit to Gaussian. spot_size is the initial guess for the FWHM of the Gaussian spot
        p0 = [np.max(tracking_data), track_steps[np.argmax(tracking_data)], spot_size, np.min(tracking_data)]
        if advanced_tracking:
            try:
                # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
                print("made it to before curve fit")
                print("Track steps is " + str(track_steps))
                print("Length of track steps is " + str(len(track_steps)))
                print("Tracking data is " + str(tracking_data))
                print("Length of tracking data is " + str(len(tracking_data)))
                popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
                print("popt[1] is " + str(popt[1]))
                print("popt is " + str(popt))
                plot_fitted = self.gaussian(track_steps, *popt)
                plot_center_fit = popt[1]
                plotbackground = popt[3]
                # plotbackground = self.gaussian(track_steps[0], *popt)
                plotpeak = self.gaussian(plot_center_fit, *popt)
                print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
                    plotpeak / plotbackground - 1), '\n')
                if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
                    # import pdb; pdb.set_trace()
                    if popt[0] < 0:
                        print("negative fit")

                    else:
                        self.drift[index] = Q_(plot_center_fit, 'um') - self.XYZ_center[index]
                        self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(plot_center_fit, 'um'), index), 'um')

                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
                    self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(max_count_position, 'um'), index), 'um')
                    "CHECK WHAT THIS BECOMES"
            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
                self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(max_count_position, 'um'), index), 'um')

            print("debugging, XYZ center is " + str(self.XYZ_center))
            
            self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
            print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_pre_array is " + str(search_error_pre_array))
                # Target value for search radius is thrice the drift
                search_error_pre = search_error_pre_array[index][0]
                # Shivam: The factor next to self.drift[index] determines how much larger the search radius should be than the drift
                search_error = (-1) * (search[index] - self.drift[index] * 2).to('nm').m

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_pre_array]
                print("search_error_deques is " + str(search_error_deques))

                # Append the latest search error value to the deque at the relevant index and remove the oldest value
                search_error_deques[index].appendleft(search_error)
                search_error_deques[index].pop()
                # Convert the modified deque into a NumPy array
                search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])

                print("search_error_array is " + str(search_error_array))


                # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

                search_change += self.search_kp * search_error

                # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                integral_sum = 0.0
                for i in np.arange(n):
                    integral_sum += search_error_array[index][i]*(0.5**i)

                search_change += self.search_ki * integral_sum

                search_change += self.search_kd * (search_error - search_error_pre)
                
                # Limitations of what search radius can be with min and max search radius
                
                # Converting search[index] to float to do maths then back to nm for the variable
                search[index] =  Q_(search[index].to('nm').m + search_change, 'nm')

                if search[index] > self.max_search[index]:
                    print("Max search radius for index " + str(index) + " reached.")
                    search[index] = self.max_search[index]

                if search[index] < self.min_search[index]:
                    print("Min search radius for index " + str(index) + " reached.")
                    search[index] = self.min_search[index]

                print("Search radius for index " + str(index) + " is updated to " + str(search[index]))

         


        else:

            try:
                # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
                print("made it to before curve fit")
                print("Track steps is " + str(track_steps))
                print("Length of track steps is " + str(len(track_steps)))
                print("Tracking data is " + str(tracking_data))
                print("Length of tracking data is " + str(len(tracking_data)))
                popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
                print("popt[1] is " + str(popt[1]))
                print("popt is " + str(popt))
                plot_fitted = self.gaussian(track_steps, *popt)
                plot_center_fit = popt[1]
                plotbackground = popt[3]
                # plotbackground = self.gaussian(track_steps[0], *popt)
                plotpeak = self.gaussian(plot_center_fit, *popt)
                print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
                    plotpeak / plotbackground - 1), '\n')
                if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
                    # import pdb; pdb.set_trace()
                    if popt[0] < 0:
                        print("negative fit")

                    else:
                        self.drift[index] = Q_(plot_center_fit, 'um') - self.XYZ_center[index]
                        self.XYZ_center[index] = Q_(plot_center_fit, 'um')

                    
                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
                    self.XYZ_center[index] = Q_(max_count_position, 'um')


            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
                self.XYZ_center[index] = Q_(max_count_position, 'um')

            self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
            print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_pre_array is " + str(search_error_pre_array))
                # Target value for search radius is twice the drift
                search_error_pre = search_error_pre_array[index][0]
                search_error = (-1) * (search[index] - self.drift[index] * 2).to('nm').m

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_pre_array]
                print("search_error_deques is " + str(search_error_deques))

                # Append the latest search error value to the deque at the relevant index and remove the oldest value
                search_error_deques[index].appendleft(search_error)
                search_error_deques[index].pop()
                # Convert the modified deque into a NumPy array
                search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])

                print("search_error_array is " + str(search_error_array))


                # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

                search_change += self.search_kp * search_error

                # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                integral_sum = 0.0
                for i in np.arange(n):
                    integral_sum += search_error_array[index][i]*(0.5**i)

                search_change += self.search_ki * integral_sum

                search_change += self.search_kd * (search_error - search_error_pre)
                
                # Limitations of what search radius can be with min and max search radius
                
                # Converting search[index] to float to do maths then back to nm for the variable
                search[index] =  Q_(search[index].to('nm').m + search_change, 'nm')

                if search[index] > self.max_search[index]:
                    print("Max search radius for index " + str(index) + " reached.")
                    search[index] = self.max_search[index]

                if search[index] < self.min_search[index]:
                    print("Min search radius for index " + str(index) + " reached.")
                    search[index] = self.min_search[index]

                print("Search radius for index " + str(index) + " is updated to " + str(search[index]))

         
        
        return search, search_error_array
    
    def advanced_tracking(self, gaussian_center, index):
        '''
        Helper function to predict position of nanodiamond using a statistical Brownian motion analysis. Found in Harry's paper.
        "Probing and manipulation embryogenesis via nanoscale thermometry and temperature control"
        '''
        # Variable storing how many photons were collected in the scan
        self.old_n_k = self.n_k
        self.n_k[index] = self.total_fluor

        # Value of current Gaussian center in current index of search
        c_k = gaussian_center.to('um').m

        
        self.old_p_k = self.p_k

        self.p_k[index] = ((self.w * self.old_p_k[index]) / (self.w + self.old_n_k[index] * self.old_p_k[index])) + 2 * self.diffusion_constant * self.time_elapsed

        self.old_x_k = self.x_k

        # Shivam: This is the predicted position of the nanodiamond
        print("w is " + str(self.w))
        print("pk is " + str(self.p_k))
        print("ck is " + str(c_k))
        print("nk is " + str(self.n_k))
        print("old xk is " + str(self.old_x_k))
        self.x_k[index] = (self.w * self.old_x_k[index] + self.n_k[index] * self.p_k[index] * c_k) / (self.w + self.n_k[index] * self.p_k[index])

        print("debugging, x_k is " + str(self.x_k))

        return self.x_k[index]
        
        


    def odmr_math(self, input_buffer):
        # Shivam: We are removing the last value of I2 from the buffer to not have the last photon count
        # This is because we do not have a clock at the last time period and so would only have 1 out of 2 relevant counts for that segment when subtracting
        # This means that we will effectively have n - 1 runs when setting the time per sg point for n runs
        effective_buffer = input_buffer[:-1]
        print("The effective buffer is:")
        print(effective_buffer)
        # Shivam: sliced to new array 2nd element onwards subtracting all elements to the left (I1 - I0, I2 - I1, ... ,
        interval_data = effective_buffer[1:] - effective_buffer[:-1]
        # Shivam: sums interval data in steps of 4 (I1-I0+I5-I4+...) is the first element
        sum_Is = [np.sum(interval_data[i::2]) for i in range(2)]
        # \ sum_Is = [#,#,#,#]
        # data = sum_Is[0]/sum_Is[1] - sum_Is[2]/sum_Is[3]

        # Shivam: I1, I2 total counts for w1 and w2
        data_I1 = sum_Is[0]
        data_I2 = sum_Is[1]
        

        return data_I1, data_I2

    def odmr_read(self, buffer, ctr_task, ctr_reader, sequence, stream_count, read_timeout):
        # time_read = time.time()
        print(buffer)
        print(len(buffer))
        ctr_task.start()
        print("Counter Started")
        self.streamer.Pulser.stream(sequence, stream_count)
        print("ps start")
        data_obtain = ctr_reader.read_many_sample_uint32(
            buffer,
            number_of_samples_per_channel=len(buffer),
            timeout=read_timeout * 2
        )
        ctr_task.stop()
        self.streamer.Pulser.reset()
        # print('the time it took to actually run the pulse sequence and read:', time.time() - time_read)
        print('end of read')
        return buffer

    def mongo_acquire(self, data_I1, data_I2, sweep, f, sideband_frequency, total_fluor):
        # Shivam: check changes to mongo_acquire with new I2_I1 and I2/I1
        # Shivam: Change names of the groupby things in plotting below

        if not self.continuous_tracking:
            self.acquire({
                'I2': float(data_I2),
                'I1': float(data_I1),
                'sweep_number': sweep,
                'sig_gen_frequency': f,
                'V1': f - float(sideband_frequency),
                'V2': f + float(sideband_frequency),
                'total_fluor': float(total_fluor),

            })

        else:
            self.acquire({
                'I2': float(data_I2),
                'I1': float(data_I1),
                'sweep_number': sweep,
                'sig_gen_frequency': f,
                'V1': f - float(sideband_frequency),
                'V2': f + float(sideband_frequency),
                'total_fluor': float(total_fluor),
                'searchX_um': list(self.search.to('um').m)[0],
                'searchY_um': list(self.search.to('um').m)[1],
                'searchZ_um': list(self.search.to('um').m)[2],
                'x_pos': self.XYZ_center[0].to('um').m,
                'y_pos': self.XYZ_center[1].to('um').m,
                'z_pos': self.XYZ_center[2].to('um').m,
                'count': self.counter,
            })
            print("Total fluorescence is " + str(total_fluor))
            print("Search radius is " + str(self.search.to('um').m))
            print("count is " + str(self.counter))

    def feedback(self, sweep, sweeps_until_feedback, z_feedback_every, xyz_step_nm, shrink_every_x_iter,starting_point):
        # \consider taking away sweep>0, allows you to avoid running spatial feedback before experiment

        if (sweep > 0) and (sweep % sweeps_until_feedback == 0):
            if sweep % z_feedback_every == 0:
                dozfb = True
            else:
                dozfb = False

            feed_params = {
                'starting_point': str(starting_point),
                'x_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x']),
                'y_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y']),
                'z_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z']),
                'do_z': dozfb,
                'xyz_step': xyz_step_nm,
                'shrink_every_x_iter': shrink_every_x_iter,

            }
            ## we make sure the laser is turned on.
            self.streamer.Pulser.constant(([7], 0.0, 0.0))

            self.call(self.newSpaceFB, **feed_params)

            ##space_data is the last line of data from spatialfeedbackxyz
            space_data = self.newSpaceFB.data.tail(1)
            x_initial = Q_(space_data['x_center'].values[0], 'um')
            y_initial = Q_(space_data['y_center'].values[0], 'um')
            if dozfb:
                z_initial = Q_(space_data['z_center'].values[0], 'um')

                self.urixyz.daq_controller.move({'x': x_initial, 'y': y_initial, 'z': z_initial})
                return
            # Shivam: Is there supposed to be an else over here?
            self.urixyz.daq_controller.move({'x': x_initial, 'y': y_initial, 'z': self.XYZ_center[2]})
            return
        else:
            return


    def ready_pulse_sequence(self, time_per_sgpoint, mwPulseTime, clockPulse, sideband_frequency, rf_amplitude):
        self.streamer.read_time = int(round(mwPulseTime.to('ns').m))
        self.streamer.clock_time = int(round(clockPulse.to('ns').m))
        seq, self.new_pulse_time = self.streamer.odmr_temp_calib_no_bg(sideband_frequency)

        self.sg.rf_amplitude = rf_amplitude
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
        # Shivam: streamer.total_time is from the odmr_temp_calib function from dr_pulsesequences_Sideband
        # And it is the total time for one pulse sequence
        self.run_ct = math.ceil(time_per_sgpoint.to('ns').m / self.streamer.total_time)

        # This is an important variable to know how long is spent collecting photons at one center freqeuncy
        self.real_time_per_scan = self.run_ct * self.streamer.total_time

        return seq, self.run_ct, self.new_pulse_time


    def create_buffer(self, time_per_sgpoint, mwPulseTime):
        # Shivam: mwPulseTime is the read_time of one segment of pulse sequence
        bufsize = math.floor(time_per_sgpoint / mwPulseTime) 
        buffer = np.ascontiguousarray(np.zeros(bufsize, dtype=np.uint32))
        return buffer


    def create_channels(self, device, PS_clk_channel, APD_channel):
        data_channel = device + '/' + APD_channel
        clock_channel = '/' + device + '/' + PS_clk_channel
        return data_channel, clock_channel

    def create_ctr_reader(self, data_channel, sampling_rate, clock_channel, buffer_size):
        APD_task = nidaqmx.Task('trans_ODMR_reading_task')
        APD_task.ci_channels.add_ci_count_edges_chan(
            data_channel,
            edge=Edge.RISING,
            initial_count=0,
            count_direction=CountDirection.COUNT_UP
        )
        APD_task.timing.cfg_samp_clk_timing(
            sampling_rate.to('Hz').m,
            source=clock_channel,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=buffer_size,
        )
        APD_reader = CounterReader(APD_task.in_stream)
        return APD_task, APD_reader

    '''
    @PlotFormatInit(LinePlotWidget, ['average'])
    def init_format(plot):
        plot.xlabel = 'frequency (GHz)'
        plot.ylabel = 'Fluorescence difference'

    @Plot1D
    def average(df, cache):
        grouped = df.groupby('sig_gen_frequency')
        difference_by_freq = grouped.I2_I1
        average_freq_diff = difference_by_freq.mean()
        return {'I2-I1': [average_freq_diff.index, average_freq_diff]}

    @Plot1D
    def I2_I1(df, cache):
        grouped = df.groupby('sig_gen_frequency')
        # groups like a table with frequency and corresponding intensity values
        I1_data = grouped.I1.mean()
        I2_data = grouped.I2.mean()

        return {'I1': [I1_data.index, I1_data],
                'I2': [I2_data.index, I2_data]}
    '''

    # Shivam's Attempts at Plots:

    @PlotFormatInit(LinePlotWidget, ['average'])
    def init_format(plot):
        plot.xlabel = 'frequency (GHz)'
        plot.ylabel = 'Fluorescence difference (cts)'


    # Use this for testing: df = pd.DataFrame({'f': [1,2,3,4,1,2,3,4], 'V1' : [0.5,1.5,2.5,3.5,4.5,5.5,6.5,7.5], 'V2': [1.5,2.5,3.5,4.5,5.5,6.5,7.5,8.5], 'I1': [10,20,30,40,50,60,70,80], 'I2': [20,30,40,50,60,70,80,90]})
    
    # This plots the ODMR sweep.
    @Plot1D
    def latest(df, cache):
        print(df)
        latest_data = df[df.sweep_number == df.sweep_number.max()]
        print(latest_data)
       

        return {'sig 1': [latest_data.V1, latest_data.I1], 'sig 2': [latest_data.V2, latest_data.I2]}

    # This plots the running average of all sweeps.
    @Plot1D
    def average(df, cache):
        grouped = df.groupby('sig_gen_frequency')
        freq_left = grouped.V1
        freq_right = grouped.V2
        sigs_left = grouped.I1
        sigs_right = grouped.I2
    

        freq_left_mean = freq_left.mean()
        freq_right_mean = freq_right.mean()
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        # return {'sig': np.concatenate(([freq_left_mean, sigs_left_mean], [freq_right_mean, sigs_right_mean]), axis=1),
                # 'bg': np.concatenate(([freq_left_mean, bgs_left_mean], [freq_right_mean, bgs_right_mean]), axis=1)}

        return {'sig 1': [freq_left_mean, sigs_left_mean], 'sig 2': [freq_right_mean, sigs_right_mean]}

    # This plots the difference of the running averages of all sweeps
   

    # This plots the division of the running averages of all sweeps
    @Plot1D
    def average_normalized(df, cache):
        grouped = df.groupby('sig_gen_frequency')
        freq_left = grouped.V1
        freq_right = grouped.V2
        sigs_left = grouped.I1
        sigs_right = grouped.I2
   

        freq_left_mean = freq_left.mean()
        freq_right_mean = freq_right.mean()
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()


        return {'Left Frequency': [freq_left_mean, (sigs_left_mean) / ((sigs_right_mean + sigs_left_mean)/2)],
                'Right Frequency': [freq_right_mean, (sigs_right_mean) / ((sigs_right_mean + sigs_left_mean)/2)]}


    @Plot1D
    def I2_I1(df, cache):
        # Regular Frequency Jump Signal
        grouped = df.groupby('sig_gen_frequency')
        sigs_left = grouped.I1
        sigs_right = grouped.I2

        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean
       

        return {'Regular Frequency Jump': [sigs_diff.index, sigs_diff]}
    
    @Plot1D
    def I2_I1_norm(df, cache):
        # Shivam: Latest quasilinear slope normalization technique (without background)
        print(df)
        grouped = df.groupby('sig_gen_frequency')
        sigs_left = grouped.I1
        sigs_right = grouped.I2

        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean
        sigs_add = (sigs_right_mean + sigs_left_mean) / 2

        sigs_norm = sigs_diff / sigs_add

        return {'Regular Frequency Jump': [sigs_norm.index, sigs_norm]}
    
    
    @Plot1D
    def x_drift(df, cache):
        return {'X Tracking': [df['count'].tolist(), df['x_pos'].tolist()]}
    
    @Plot1D
    def y_drift(df, cache):
        return {'Y Tracking': [df['count'].tolist(), df['y_pos'].tolist()]}
    
    @Plot1D
    def z_drift(df, cache):
        return {'Z Tracking': [df['count'].values, df['z_pos'].values]}
    
    @Plot1D
    def total_fluor(df, cache):
        return {'Total Fluorescence': [df['count'].tolist(), df['total_fluor'].tolist()]}
    
    @Plot1D
    def x_search(df, cache):
        return {'X Search Radius': [df['count'].values, df['searchX_um'].values]}
    
    @Plot1D
    def y_search(df, cache):
        return {'X Search Radius': [df['count'].values, df['searchY_um'].values]}
    
    @Plot1D
    def z_search(df, cache):
        return {'X Search Radius': [df['count'].values, df['searchZ_um'].values]}
    


    

    def finalize(self, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                   sweeps, frequencies, slope_range, sideband_frequency, 
                   read_timeout, sweeps_until_feedback, z_feedback_every, 
                   xyz_step_nm, shrink_every_x_iter, starting_point, 
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance, changing_search, search_PID, 
                   search_integral_history, spot_size, advanced_tracking, 
                   diffusion_constant, data_download):

        ## this is here, because i want to look at
        ## self.data
        ## so that I can find the slope and return it in the console. Of course, I should also plot.

        # import pdb; pdb.set_trace()
        self.finalize_action(self.APD_task, data_download)
        print("Finalize")

    def finalize_action(self, ctr_task, data_download):
        self.close_task(ctr_task)
        self.handle_pulsestreamer()



        if data_download:
            self.download_excel()

        # Shivam: FUTURE IMPROVEMENTS - Currently the proper slope and zero extraction is only implemented for quasilinear_calibration slope
        # The quasilinear_calibration slope normalizes using only on values and no background values and that is what we have chosen to use for now
        regular_calibration_slope = self.regular_slope_extraction()
        quasilinear_calibration_slope, quasilinear_zero_field_splitting = self.quasilinear_slope_extraction()
        print('\n\n', regular_calibration_slope,
              'is the slope between the frequency change and the fluorescence change.\n\n')
        
        print(str(quasilinear_calibration_slope) + 
              ' is the quasilinear slope between the frequency change and the fluorescence change. The zero field splitting is '
              + str(quasilinear_zero_field_splitting))

    # Shivam: Change calculations to the latest variable names
    def regular_slope_extraction(self):
        df = self.data
        # \ I have Sweeps many data lines
        print("Test regular slope")
        grouped = df.groupby('sig_gen_frequency')
        sigs_left = grouped.I1
        sigs_right = grouped.I2

        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean

        # index of the minimum element (absolute value) of the average difference of I2 and I1
        # (Shivam: 0 point of I1-I2 graph)
        integer_index = np.abs(sigs_diff).argmin()
        # freq_index = lambda x: avg_I2_I1_diff.index[x]
        change_fluor = sigs_diff[sigs_diff.index[integer_index + 1]]- sigs_diff[sigs_diff.index[integer_index - 1]]
        # Shivam: Why is it index 1 and 0 for frequency?
        # Ans: It seems to be because the differences in generated frequency are constant
        change_freq = 2 * (df.sig_gen_frequency[1] - df.sig_gen_frequency[0])
        slope = change_fluor / change_freq  # change_freq in Hz???
        return slope
    

    def quasilinear_slope_extraction(self):
        df = self.data
        # \ I have Sweeps many data lines
        grouped = df.groupby('sig_gen_frequency')
        sigs_left = grouped.I1
        sigs_right = grouped.I2

        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean
        sigs_add = (sigs_right_mean + sigs_left_mean) / 2

        sigs_norm = sigs_diff / sigs_add
        
        x_values = np.array(sigs_norm.index)
        y_values = np.array(sigs_norm)
        
        # Shivam: Getting the indices of the desired frequency range endpoints and slicing our x and y values accordingly
        index_left = np.abs(df.sig_gen_frequency - self.left_frequency_slope).idxmin()

        index_right = np.abs(df.sig_gen_frequency - self.right_frequency_slope).idxmin()

        x_values = x_values[index_left : index_right + 1]

        y_values = y_values[index_left : index_right + 1]

        linear_regression = np.polyfit(x_values, y_values, 1)

        # Shivam: Calculating the slope of the line and the y = 0 value (zero field splitting of ODMR)

        slope = linear_regression[0]

        odmr_zfs = -linear_regression[1] / linear_regression[0]

        print(slope)

        print(odmr_zfs)

        return slope, odmr_zfs

    def close_task(self, ctr_task):
        ctr_task.stop()
        ctr_task.close()

    def handle_pulsestreamer(self):
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.streamer.Pulser.reset()

    def download_excel(self):
        save_excel(self.name)
        print('The name of the excel data:', self.name)

    
class TemperatureVsTime(Spyrelet):
    '''
    This class is meant to be an analogue to counts vs time and plot the temperature of the nanodiamond vs time
    with continuous green laser input.
    '''
    REQUIRED_DEVICES = [
        'sg',
        'streamer',
        'urixyz',
        'infrared',
    ]
    REQUIRED_SPYRELETS = {

     'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }

    PARAMS = {
        'device': {
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel': {
            'type': str,
            'default': 'PFI0',
        },
        'APD_channel': {
            'type': list,
            'items': list(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none']),
            'default': 'ctr1',
        },
        'sampling_rate': {
            'type': float,
            'units': 'Hz',
            'suffix': ' Hz',
            'default': 50000,
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 12
        },
        'time_per_scan': {
            'type': float,
            'default': .25,
            'suffix': ' s',
            'units': 's',
        },
        'starting_temp': {
            'type': float,
            'default': 25.0
        },

        ### Shivam: COMMENTED OUT FOR NOW SINCE WE ARE NOT DOING 4 POINT MEASUREMENT
       
        # 'sbChoice_MHz_big': {
        #     'type': list,
        #     'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
        #               '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
        #               '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
        #               '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
        #               '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
        #               '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
        #               '5.952380952',
        #               '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
        #               '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
        #               '2.5'],

        #     'default': '10.1010101',
        # },
        # 'sbChoice_MHz_small': {
        #     'type': list,
        #     'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
        #               '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
        #               '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
        #               '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
        #               '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
        #               '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
        #               '5.952380952',
        #               '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
        #               '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
        #               '2.5'],
        #     'default': '6.94444444',
        # },

        'sb_MHz_2fq': {
            'type': list,
            'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                      '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                      '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                      '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                      '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                      '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                      '5.952380952',
                      '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
                      '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
                      '2.5'],

            'default': '10.1010101',
        },
        'quasilinear_slope': {
            'type': float,
            'default': .01,
        },
        'two_freq': {
            'type': bool,
            'default': True,
        },
        'odmr_frequency': {
            'type': float,
            'default': 2.87e9,
        },
        'rf_amplitude': {
            'type': float,
            'default': -20,
        },
        'clock_time': {
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'mwPulseTime': {
            'type': float,
            'default': 50e-6,
            'suffix': ' s',
            'units': 's',
        },
        'cooling_delay': {
            'type': float,
            'default': 0.0,
            'suffix': ' s',
            'units': 's',
        },
        'is_center_modulation': {
            'type': bool,
            'default': True,
        },
        'data_download': {
            'type': bool,
        },
        'activate_PID': {
           'type': bool,
           'default': True, 
        },
        # PID with no signal generator frequency change
        'activate_PID_no_sg_change': {
           'type': bool,
           'default': False, 
        },
        'PID': {
           'type': str,
           'default': "[0.1,0.01,0]" 
        },
        # Shivam: This parameter gives flexibility on how frequently each of the P, I, and D are used in the adjustment of center frequency
        'PID_recurrence': {
           'type': str,
           'default': "[1,1,0]" 
        },
        # Shivam: This parameter determines how many previous error values are taken into account for integral calculations in PID
        'integral_history': {
           'type': int,
           'default': 5 
        },
        # Shivam: This parameter is the threshold temperature difference detected that activates P to be 1 to jump to the new temperature
        'threshold_temp_jump': {
           'type': int,
           'default': 2 
        },
        # Shivam: This parameter is linked to the above parameter and determines how many times the threshold temperature difference is detected before the jump is made
        # The average over these 5 times is taken to make sure that the temperature difference is not a fluke
        'number_jump_avg': {
           'type': int,
           'default': 5 
        },
        'searchXYZ': {
            'type': str,
            'default': "Q_([500, 500, 500], 'nm')",
        },
        # Search range can vary based on how far NV has drifted, so need max and min bounds
        'max_search': {
            'type': str,
            'default': "Q_([1000, 1000, 1000], 'nm')",
        },
        'min_search': {
            'type': str,
            'default': "Q_([100, 100, 100], 'nm')",
        },
        # This boolean value determines whether the search range is modified based on the drift of the nanodiamond or not
        'changing_search': {
            'type': bool,
            'default': False
        },
        # Shivam: Next two parameters are for changing the search radius with PID control
        # Optimize for search radius to be double the drift distance of the NV
        'search_PID': {
           'type': str,
           'default': "[0.5,0.01,0]" 
        },
        'search_integral_history': {
           'type': int,
           'default': 5 
        },
        'z_cycle': {
            'type': int,
            'default': 10,
        },
       'track_z': {
            'type': bool,
            'default': True,
        },
        'do_not_run_feedback': {
            'type': bool,
            'default': False
        },
        # Shivam: This parameter is the length of scan in each direction in nm
        'scan_distance': {
            'type': str,
            'default': "Q_([30, 30, 50], 'nm')",
        },
        # This is the spot size FWHM in micrometers
        'spot_size': {
            'type': float,
            'default': 400e-9,
            'suffix': ' m',
            'units': 'm',
        },
        # Option to do advanced tracking from Harry's paper
        'advanced_tracking': {
            'type': bool,
            'default': False
        },
        # Units of nm^2 / us
        # Does not matter if not doing advanced tracking
        'diffusion_constant': {
            'type': float,
            'default': 200,
        },
        # Toggle to turn infrared heating on or off
        'infrared_on': {
            'type': bool,
            'default': False
        },
        ## for the strength of the heating laser
        'infrared_power': {
            'type': float,
            'default': 0.1,
            'suffix': ' mW',
            'units': 'mW',
        },
        # Duty cycle of when heating laser is on and off
        'heat_on_off_cycle': {
            'type': str,
            'default': "[True] + [False]*2",
        },
        # Number of iterations heating on and number of iteration heating off
        'warm_and_cool_scans': {
            'type': str,
            'default': '[30, 30]'
        },

    }

    ''' 
    Shivam: Not needed anymore as done in hs_prepare and hs_linescan
    def create_buffer(self, time_per_scan, mwPulseTime):
        # Shivam: Make sure that mwPulseTime matches the read_time in dr_pulsesequences_Sideband.py
        self.bufsize = math.floor(time_per_scan/mwPulseTime)
        buffer = np.ascontiguousarray(np.zeros(self.bufsize, dtype=np.uint32))
        return buffer
    '''

    
    #Shivam: This is reinstated because we need for the no feedback/tracking case measurement
    def create_channels(self, device, PS_clk_channel, APD_channel):
        data_channel = device + '/' + APD_channel
        clock_channel = '/' + device + '/' + PS_clk_channel
        return data_channel, clock_channel

    
    ''' 
    Shivam: Not needed anymore as done in hs_prepare and hs_linescan
    def create_ctr_reader(self, data_channel, sampling_rate, clock_channel, buffer_size):
        APD_task = nidaqmx.Task('temperature reading task')
        APD_task.ci_channels.add_ci_count_edges_chan(
            data_channel,
            edge=Edge.RISING,
            initial_count=0,
            count_direction=CountDirection.COUNT_UP
        )
        APD_task.timing.cfg_samp_clk_timing(
            sampling_rate.to('Hz').m,
            source=clock_channel,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=buffer_size,
        )
        APD_reader = CounterReader(APD_task.in_stream)
        return APD_task, APD_reader
    '''

    def initialize(self, device, PS_clk_channel, APD_channel, sampling_rate, 
                   timeout,time_per_scan, starting_temp, sb_MHz_2fq, quasilinear_slope, 
                   two_freq, odmr_frequency, rf_amplitude, clock_time, mwPulseTime, 
                   cooling_delay, is_center_modulation, data_download, 
                   activate_PID, activate_PID_no_sg_change, PID, PID_recurrence, 
                   integral_history, threshold_temp_jump, number_jump_avg, 
                   searchXYZ, max_search, min_search, changing_search, search_PID, 
                   search_integral_history, z_cycle, track_z, 
                   do_not_run_feedback, scan_distance, spot_size, advanced_tracking, 
                   diffusion_constant, infrared_on, infrared_power, heat_on_off_cycle,
                   warm_and_cool_scans, iterations = 0):
        print("Cooling delay below:")
        print(cooling_delay.m)

        if infrared_on:
        
            ### Setup heating infrared laser
            self.infrared.modulation_power = Q_(infrared_power, 'mW')

            self.infrared.digital_modulation = True

            self.heating_scans, self.cooling_scans = eval(warm_and_cool_scans)

            # Shivam: CHECK IF THIS IS THE RIGHT CHANNEL CODE
            laser_channel = device + '/port0/line3'
            # Shivam: Corresponds to the minimum time window of a True or False, generally do lower frequency if switching between True and False regularly
            # Current setting of 2e5 corresponds to 5 us windows
            laser_update_freq = 2e5 #Hz
            'daq update frequency is slower than the documentation claims.'
            'update freq must be considered with the laser sequence'

            self.laser_ctrl_task = nidaqmx.Task('Laser_ctrl_task')
            self.laser_ctrl_task.do_channels.add_do_chan(laser_channel,
                                                        line_grouping=nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
            self.laser_ctrl_task.timing.cfg_samp_clk_timing(
                laser_update_freq,
                sample_mode=AcquisitionType.CONTINUOUS,  # CONTINUOUS, # can also limit the number of points
            )
            # import pdb; pdb.set_trace()
            laser_values = eval(heat_on_off_cycle)
            self.laser_ctrl_task.write(laser_values, auto_start=False, timeout=timeout)

            ### End of setting up heating infrared laser

        
        # Shivam: WRITE WHAT SAMPLING RATE DOES   
        if sampling_rate.to('Hz').m <= 1 / mwPulseTime.to('s').m:
            print('sampling rate must be equal or larger than 1/probe_time')
            pass
        print('please initialize')
        
        self.starting_odmr_frequency = odmr_frequency
        self.odmr_frequency = odmr_frequency

        sb_MHz_2fq = eval(sb_MHz_2fq) * 1e6

        self.diffusion_constant = diffusion_constant

        self.read_timeout = timeout

        self.bufsize = math.floor(time_per_scan/mwPulseTime)
        if self.bufsize % 2 == 1:
            raise ValueError('Buffer size must be even, choose time_per_scan and mwPulseTime accordingly (bufsize = math.floor(time_per_scan/mwPulseTime))')
        
        if integral_history < number_jump_avg:
            raise ValueError('Integral history must be greater or equal than number of jumps averaged over (number_jump_avg <= integral_history)')

        # This will be the variable storing total fluorescence every run
        self.total_fluor = 0

        if activate_PID and activate_PID_no_sg_change:
            raise ValueError('activate_PID and activate_PID_no_sg_change cannot both be true')
        
        # Shivam: Initialize PID control variables

        self.kp, self.ki, self.kd = eval(PID)

        

        self.previous_fluors = np.array([0,0,0])

        
        self.search_kp, self.search_ki, self.search_kd = eval(search_PID)

        if not do_not_run_feedback:
            self.tracking_data = [[0], [0], [0]]

            self.search = eval(searchXYZ)
            print("self.search is " + str(self.search))
            # output is: 'self.search is [500 500 500] nanometer'

            self.max_search = eval(max_search)

            self.min_search = eval(min_search)

            # Shivam: Check syntax
            self.scan_distance = eval(scan_distance)
            print(self.scan_distance)

            self.check_appropriate_distance()

            self.spot_size = Q_(spot_size, 'um').m
            print("self.spot_size is " + str(self.spot_size))

            # Shivam: Initializing motion controller for data collection. CHECK IF FIRST LINE NEEDED
            self.urixyz.daq_controller.new_ctr_task(device + '/' + APD_channel)
            self.urixyz.daq_controller.acq_rate = sampling_rate

            # Shivam: Parameters for tracking
            self.drift = [0, 0, 0]
            self.XYZ_center = [self.urixyz.daq_controller.position['x'],
                                self.urixyz.daq_controller.position['y'],
                                self.urixyz.daq_controller.position['z']]

        else: 
            self.search = None
            self.max_search = None
            self.min_search = None
            self.scan_distance = None
            self.spot_size = 0
            #Indices correspond to x, y, and z
            self.tracking_data = None

            data_channel, clock_channel = self.create_channels(device, PS_clk_channel, APD_channel)

            self.counter_buffer = np.ascontiguousarray(np.zeros(self.bufsize), dtype = np.uint32)

            self.current_counter_task = nidaqmx.Task("counter_no_tracking")

            self.current_counter_task.ci_channels.add_ci_count_edges_chan(
                data_channel, 
                edge = Edge.RISING, 
                initial_count=0, 
                count_direction=nidaqmx.constants.CountDirection.COUNT_UP)

            self.current_counter_task.timing.cfg_samp_clk_timing(
                            sampling_rate.to('Hz').m, # must be equal or larger than max rate expected by PS
                            source= clock_channel,
                            sample_mode=nidaqmx.constants.AcquisitionType.FINITE, #CONTINUOUS, # can also limit the number of points-
                            samps_per_chan= self.bufsize
            )

            self.sample_reader_stream = CounterReader(self.current_counter_task.in_stream)


        # self.buffer = self.create_buffer(time_per_scan, mwPulseTime)

        # data_channel, clock_channel = self.create_channels(device, PS_clk_channel, APD_channel)

        # self.APD_task, self.APD_reader = self.create_ctr_reader(data_channel, sampling_rate, clock_channel,
        #                                                         len(self.buffer))
        # Initialize starting temperature of sample before temperature versus time
        self.starting_temp = starting_temp
        self.current_temp = starting_temp
      


        ## this is setting up the pulse streamer frequencies, signal generator frequencies, and the temperature change frequency
        ## it is dependent whether you chose to do two freq modulation or four freq modulation.

        ### Shivam: WE HAVE NOT IMPLEMENTED 4 FREQUENCY TEMP SCANNING SO THIS CONDITION WILL NOT BE USED
        if not two_freq:
            print("Four frequency modulation is not implemented yet, please select two frequency modulation")
            # sb_big = Q_(eval(sbChoice_MHz_big), 'MHz')
            # sb_small = Q_(eval(sbChoice_MHz_small), 'MHz')
            # frequencies = [(odmr_frequency - sb_big), (odmr_frequency - sb_small),
            #                (odmr_frequency + sb_small), (odmr_frequency + sb_big)]
            # sg_frequency = (odmr_frequency - (sb_big + sb_small)).to(
            #     'Hz').m  # frequencies[3].to('Hz').m - sb_frequency*1e6
            # print('the maximum sideband frequency is:', 2 * sb_big + 2 * sb_small)
            # num_freq = 4

            # omega1 = (frequencies[0] + frequencies[1]) / 2
            # omega2 = (frequencies[2] + frequencies[3]) / 2
            # self.delomega = (omega2 - omega1).to('kHz').m

        else:
            num_freq = 2

            # Shivam: Center modulation is the technique where the carrier frequency is in the middle
            # while the sideband modulation is to the left and right. The alternative is if the 
            # carrier frequency is to the right or left of the two sideband frequencies.

            if is_center_modulation:
                self.sequence, self.new_pulse_time = self.ready_center_pulse_sequence(time_per_scan, mwPulseTime, clock_time,
                                                                        sb_MHz_2fq, rf_amplitude) 
                self.sg.frequency = self.odmr_frequency

                # Initialize advanced tracking variables
                # Shivam: Subtracted by 2 because of the way the buffer is sliced to keep equal photon exposure for I1 and I2 

                effective_buffer_size = self.bufsize - 2
                num_bins = effective_buffer_size / 2
                self.time_elapsed = num_bins * self.real_time_per_scan
                # Setting all advanced tracking variables into a vector array for x,y,z
                self.n_k = [0,0,0]
                self.p_k = [2 * diffusion_constant * self.time_elapsed] * 3
                self.x_k = [self.urixyz.daq_controller.position['x'].to('um').m,
                            self.urixyz.daq_controller.position['y'].to('um').m,
                            self.urixyz.daq_controller.position['z'].to('um').m]
                print("x_k is " + str(self.x_k))

                # CHECK THE TUNING OF w
                self.w = self.spot_size ** 2

            else:
                self.frequencies = [(odmr_frequency - sb_MHz_2fq), (odmr_frequency + sb_MHz_2fq)]
                sg_frequency = (odmr_frequency - (sb_MHz_2fq + Q_(5, 'MHz'))).to('Hz').m
                self.ps_frequencies = [freq.to('Hz').m - sg_frequency for freq in
                                    self.frequencies]  # (frequencies.to('Hz').m - sg_frequency)
                self.sg.frequency = sg_frequency

                self.sequence = self.setup_LPvT(self.ps_frequencies, mwPulseTime, clock_time, time_per_scan, num_freq, rf_amplitude)
    
        return
    
    
    def check_appropriate_distance(self):
        # This function checks whether the scan distance is too small to cover the entire search range
        for i in range(3):
            # Multiplying self.search by 2 because the search range is from XYZ_center -self.search to XYZ_center + self.search
            if self.scan_distance[i].to('nm').m < 2 * self.search[i].to('nm').m / self.bufsize:
                print("ERROR: scan distance for index " + str(i) + " is too small, please decrease scan distance to at least " + str(self.search[i].to('nm').m / self.bufsize) + " nm.")
                raise ValueError('Scan distance too small')


    def measure_2pt_temp(self, temp_data, odmr_frequency, quasilinear_slope, error_pre_array, 
                         current_temp, activate_PID, PID, PID_recurrence, integral_history, 
                         activate_PID_no_sg_change, iteration_num, threshold_temp_jump, number_jump_avg):
        # STILL NEED TO IMPLEMENT TIME_INCREMENT PROPERLY FOR PID CONTROL
        # def make_digestible(matrix):
        # return np.sum(matrix, axis = 1)
        # Shivam: Creating an array that holds the previous n error values for integral implementation of PID control
        # cont. This array holds error value * time_elapsed since that is the value required for a Riemann integral
        print("Current Temperature is " + str(current_temp))
        print("Temp Data is " + str(temp_data))

        subtracted_error = float(temp_data[1]) - float(temp_data[0])
        normalization_error = (float(temp_data[1]) + float(temp_data[0])) / 2

        jump_error = subtracted_error / normalization_error

        constant = quasilinear_slope  # fluor / Hz

        # latest error is a frequency change value
        latest_error = -1 * jump_error / constant

        if not activate_PID and not activate_PID_no_sg_change:
            error_array = None
            freq_change = latest_error

            # Convert frequency from Hz to kHz
            freq_change_kHz = freq_change * 1e-3

            #Calculate temperature change from frequency change
            temp_change = (freq_change_kHz) / (-74.2)

            # Shivam: Updating the current temperature based on the error calculations above
            # ODMR center frequency is not updated in this mode but still recorded of what it is measured as with jump frequency

            current_temp = self.starting_temp + temp_change

            odmr_frequency = self.starting_odmr_frequency + freq_change

            return odmr_frequency, error_array, freq_change, temp_change, current_temp, subtracted_error, normalization_error

            
        elif activate_PID:

            n = integral_history
            error_pre = error_pre_array[0]
            '''
            if temp_data.all() == 0:
                return sum(frequencies) / 2, error_pre, 0
            '''
            # Shivam: Converting array to deque to maintain latest n error values (adding new one and removing oldest one)
            # First element of deque is the latest measured error value.
            error_deque = collections.deque(error_pre_array)
            error_deque.appendleft(latest_error)
            error_deque.pop()
            error_array = np.array(error_deque)


            ### NEW ADDITION: If error is consistently larger than threshold_temp_jump for previous last_n_freq_change values, 
            # P = 1 and mean of last_n_freq_change error values applied for temp change


            # Shivam: Last n frequency change values to check if temperature is jumping
            last_n_freq_change = error_array[0:number_jump_avg]


            # Convert frequency from Hz to kHz
            freq_change_kHz = last_n_freq_change * 1e-3

            #Calculate temperature change from frequency change
            temp_change = 0.2*(freq_change_kHz) / (-74.2)

            print("temp_change is " + str(temp_change))


            # if np.all(temp_change > threshold_temp_jump) or np.all(temp_change < (-1) * threshold_temp_jump):
            #     print("%%%%%%%%%%%%%%%%%%%%%%%%%%% temperature jumping %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            #     temp_change = np.mean(temp_change)
            #     freq_change = np.mean(last_n_freq_change)

            #     current_temp += temp_change
            #     odmr_frequency += freq_change

            #     return odmr_frequency, error_array, freq_change, temp_change, current_temp
            
            ### END OF NEW ADDITION


            # Initialize frequency change variable
            freq_change = 0.0

            # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

            if eval(PID_recurrence)[0] != 0:
                if iteration_num % eval(PID_recurrence)[0] == 0:
                    freq_change += self.kp * latest_error

            if eval(PID_recurrence)[1] != 0:
                if iteration_num % eval(PID_recurrence)[1] == 0:
                    # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                    integral_sum = 0.0
                    for index in np.arange(n):
                        integral_sum += error_array[index]*(0.5**index)

                    freq_change += self.ki * integral_sum

            if eval(PID_recurrence)[2] != 0:
                if iteration_num % eval(PID_recurrence)[2] == 0:
                    freq_change += self.kd * (latest_error - error_pre)

            # Shivam: All divisions or multiplications by time elapsed above have been removed since that can be absorbed into the constants. CHECK

    
            # Shivam: Need to check the calibration for the constant -74.2
            # Convert frequency from Hz to kHz
            freq_change_kHz = freq_change * 1e-3

            #Calculate temperature change from frequency change
            temp_change = (freq_change_kHz) / (-74.2)
            
            # Have a 1000 inside the denominator to convert from kHz to Hz
            # temp_change = (freq_change) / (-74.2 * 1000)

            # Shivam: Updating the current temperature and ODMR center frequency based on the error calculations above

            current_temp += temp_change

            odmr_frequency += freq_change

            return odmr_frequency, error_array, freq_change, temp_change, current_temp, subtracted_error, normalization_error
        
        elif activate_PID_no_sg_change:
             
            n = integral_history
            error_pre = error_pre_array[0]
            '''
            if temp_data.all() == 0:
                return sum(frequencies) / 2, error_pre, 0
            '''
            # Conversion of latest_error to be relative to the previous error value
            latest_error = latest_error - (self.odmr_frequency - self.starting_odmr_frequency)
            # Shivam: Converting array to deque to maintain latest n error values (adding new one and removing oldest one)
            # First element of deque is the latest measured error value.
            error_deque = collections.deque(error_pre_array)
            error_deque.appendleft(latest_error)
            error_deque.pop()
            error_array = np.array(error_deque)

            ### NEW ADDITION: If error is consistently larger than threshold_temp_jump for previous last_n_freq_change values, 
            # P = 1 and mean of last_n_freq_change error values applied for temp change


            # Shivam: Last n frequency change values to check if temperature is jumping
            last_n_freq_change = error_array[0:number_jump_avg]


            # Convert frequency from Hz to kHz
            freq_change_kHz = last_n_freq_change * 1e-3

            #Calculate temperature change from frequency change
            temp_change = 0.2*(freq_change_kHz) / (-74.2)

            # if np.all(temp_change > threshold_temp_jump) or np.all(temp_change < threshold_temp_jump):
            #     print("%%%%%%%%%%%%%%%%%%%%%%%%%%% temperature jumping %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            #     temp_change = np.mean(temp_change)
            #     freq_change = np.mean(last_n_freq_change)

            #     current_temp += temp_change
            #     odmr_frequency += freq_change

            #     return odmr_frequency, error_array, freq_change, temp_change, current_temp
            
            ### END OF NEW ADDITION

            # Initialize frequency change variable
            freq_change = 0.0

            # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

            if eval(PID_recurrence)[0] != 0:
                if iteration_num % eval(PID_recurrence)[0] == 0:
                    freq_change += self.kp * latest_error

            if eval(PID_recurrence)[1] != 0:
                if iteration_num % eval(PID_recurrence)[1] == 0:
                    # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                    integral_sum = 0.0
                    for index in np.arange(n):
                        integral_sum += error_array[index]*(0.5**index)

                    freq_change += self.ki * integral_sum

            if eval(PID_recurrence)[2] != 0:
                if iteration_num % eval(PID_recurrence)[2] == 0:
                    freq_change += self.kd * (latest_error - error_pre)

            # Shivam: All divisions or multiplications by time elapsed above have been removed since that can be absorbed into the constants. CHECK


            # Shivam: Need to check the calibration for the constant -74.2
            # Convert frequency from Hz to kHz
            freq_change_kHz = freq_change * 1e-3

            #Calculate temperature change from frequency change
            temp_change = (freq_change_kHz) / (-74.2)

            # Have a 1000 inside the denominator to convert from kHz to Hz
            # temp_change = (freq_change) / (-74.2 * 1000)

            # Shivam: Updating the current temperature and ODMR center frequency based on the error calculations above

            current_temp += temp_change

            odmr_frequency += freq_change

            return odmr_frequency, error_array, freq_change, temp_change, current_temp, subtracted_error, normalization_error



    def read_stream_flee(self, index, PS_clk_channel, search, buffer_size, scan_distance, num_freq, read_timeout):
        ## total this has 180 ms of lag.
        # time_track = time.time()
        xyz_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                buffer_size)
                                
        # Shivam: Assigns the entire XYZ_center array to both newly defined arrays
        pos_center_st = self.XYZ_center[:]
        pos_center_end = self.XYZ_center[:]
        pos_center_st[index] = xyz_steps[0]
        pos_center_end[index] = xyz_steps[-1]

        distance_of_sweep = (np.abs(pos_center_end[index] - pos_center_st[index])).to('nm').m
        print(distance_of_sweep)
        print(scan_distance)
        number_of_steps = math.ceil(distance_of_sweep / scan_distance[index].to('nm').m)
        print("The number of steps is " + str(number_of_steps))
        effective_scan_distance = distance_of_sweep / number_of_steps
        print("The effective scan distance is " + str(effective_scan_distance))
        # Shivam: Subtracted by 2 because of the way the buffer is sliced to keep equal photon exposure for I1 and I2 
        effective_buffer_size = buffer_size - 2
        print("The effective buffer size is " + str(effective_buffer_size))
        # Shivam: Buffer allocation for each step of scan
        buffer_allocation = math.floor(effective_buffer_size / number_of_steps)
        print("The buffer allocation is " + str(buffer_allocation))
        # import pdb; pdb.set_trace()
        # Shivam: Doing a 1 axis scan from the set start point till end point with buffer_size steps
        # Remaining buffer is for later calculations, but this function is primarily for the scan.
        # Remaining buffer is the number of extra measurements that were taken at the last voltage position
        # Points per step signifies how many repetitions of the line scan we are doing
        remaining_buffer = self.urixyz.daq_controller.hs_prepare(buffer_size, buffer_allocation, PS_clk_channel,
                                            {'x': pos_center_st[0], 'y': pos_center_st[1], 'z': pos_center_st[2]},
                                            {'x': pos_center_end[0], 'y': pos_center_end[1], 'z': pos_center_end[2]},
                                            number_of_steps)

        ###Before this, around .12 seconds have elapsed

        'start the pulse streamer and the task close to simultaneously'

        self.streamer.Pulser.stream(self.sequence, self.run_ct)
        ## this is 35 ms all on its own. 
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        # Shivam: Changed from num_freq * 2 to num_freq because we are not doing background collection
        scan_data = self.urixyz.daq_controller.hs_linescan(read_timeout)

        self.streamer.Pulser.reset()
        ## this is 5 miliseconds
        # print('time for read stream flee:', time.time() - time_track)

        ## pulser stream to pulser reset has 60ms delay.
        
        return rpyc.utils.classic.obtain(scan_data), buffer_allocation, remaining_buffer
    
    def process_data(self, input_buffer, buffer_allocation, remaining_buffer, index, search, do_not_run_feedback):
        # Shivam: We are removing the last value of I2 from the buffer to not have the last photon count
        # This is because we do not have a clock at the last time period and so would only have 1 out of 2 relevant counts for that segment when subtracting
        # This means that we will effectively have n - 1 runs when setting the time per sg point for n runs
        print("/n/n In process data/n")
        print("The input buffer size is " + str(len(input_buffer)))
        effective_buffer = input_buffer[:-1]
        print("The later effective buffer size is " + str(len(effective_buffer)))
        # Shivam: sliced to new array 2nd element onwards subtracting all elements to the left (I1 - I0, I2 - I1, ... ,
        interval_data = effective_buffer[1:] - effective_buffer[:-1]

        # This gets the number of I1 I2 pulsesequences that we are considering in our calculations
        # This is needed for our calculation of total time of photon collection in advanced_tracking

        num_bins = int(len(interval_data) / 2)
        print("The number of bins is " + str(num_bins))
        # Shivam: sums interval data in steps of 4 (I1-I0+I5-I4+...) is the first element
        sum_Is = [np.sum(interval_data[i::2]) for i in range(2)]
        # \ sum_Is = [#,#,#,#]
        # data = sum_Is[0]/sum_Is[1] - sum_Is[2]/sum_Is[3]

        # Shivam: I1, I2 total counts for w1 and w2
        data_I1 = sum_Is[0]
        data_I2 = sum_Is[1]

        # Shivam: Appending the to normalized intensity values into an array
        temp_data = []
  
        temp_data.append(data_I1)
        temp_data.append(data_I2)

        
        if not do_not_run_feedback:
            # Shivam: Now process particle tracking data

            # Shivam: Remove the extra points from the buffer that are not used in the scan 
            # (leftovers from the last position calculated in linear_func_hs in driver)
            if remaining_buffer > 0:
                tracking_buffer = input_buffer[:(-remaining_buffer + 1)]
            else:
                print("Error in remaining buffer")

            print("/n We are processing tracking data with feedback")

            print("Tracking buffer is " + str(tracking_buffer))
            print("Length of tracking buffer is " + str(len(tracking_buffer)))

            tracking_interval = tracking_buffer[1:] - tracking_buffer[:-1]

            print("Tracking interval is " + str(tracking_interval))
            print("Length of tracking interval is " + str(len(tracking_interval)))


            # Shivam: This sums over the buffer allocation for each position step of the scan and stores in new array
            tracking_data = np.sum(tracking_interval.reshape(-1, buffer_allocation), axis=1)
            print("Length of tracking data is " + str(len(tracking_data)))
            print("Tracking data is " + str(tracking_data))

            track_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                    len(tracking_data)).to('um').m
            
        else:
            tracking_data = None
            track_steps = None
            
        return tracking_data, track_steps, temp_data, num_bins
    
    '''
    Shivam: This is the old process_data that Aidan had implemented.
    def process_data(self, index, scan_data, search):
        # temp_dat_storage, index, scan_data, search):

        half_num = int(len(scan_data) / 2)
        temp_data = np.array([None] * half_num)
        for i in range(half_num):
            # Shivam: This seems wrong
            temp_data[i] = np.sum(scan_data[i] + scan_data[- 1 - i])

        tracking_data = np.sum(scan_data, axis=0)

        # temp_dat_storage.append(temp_data)
        # temp_data = np.array(temp_data, dtype = np.float)
        track_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                  len(tracking_data)).to('um').m

        return tracking_data, track_steps, temp_data
    '''
    
    
    def datanaly(self, tracking_data, track_steps, index, search, do_not_run_feedback, spot_size, num_bins, advanced_tracking, 
                 changing_search, search_error_pre_array, search_integral_history):
        '''
        Calculates Gaussian fit for the tracking data and sets the new center position for the next scan (moves the laser directly)
        '''

        print("/n/n In data analysis/n")

        #import pdb; pdb.set_trace()
        self.previous_fluors[index-1] = self.total_fluor
        self.total_fluor = np.sum(tracking_data)

        # Shivam: Attempt to fix search radius issue when theres a rapid change in position, but not working well yet
        # if self.total_fluor / self.previous_fluors[index] < 0.5:
            # HAVE MAX SEARCH CONDITION
            # self.search[index] *= 4
            # return search, search_error_pre_array

        print("Total Fluorescence is " + str(self.total_fluor))
        if do_not_run_feedback:
            return search, search_error_array
        
        print('Out of XYZ = [0,1,2], this is the', index, 'axis')
        # if index == 2:
        #     print("Track steps is " + str(track_steps))
        #     print("Tracking data is " + str(tracking_data))
        #     max_count_position = track_steps[np.argmax(tracking_data)]
        #     self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
        #     self.XYZ_center[index] = Q_(max_count_position, 'um')
        #     self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
        #     print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
        #     print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)
        #     return search

        # Here we are attempting to fit to Gaussian. spot_size is the initial guess for the FWHM of the Gaussian spot
        p0 = [np.max(tracking_data), track_steps[np.argmax(tracking_data)], spot_size, np.min(tracking_data)]
        if advanced_tracking:
            try:
                # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
                print("made it to before curve fit")
                print("Track steps is " + str(track_steps))
                print("Length of track steps is " + str(len(track_steps)))
                print("Tracking data is " + str(tracking_data))
                print("Length of tracking data is " + str(len(tracking_data)))
                popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
                print("popt[1] is " + str(popt[1]))
                print("popt is " + str(popt))
                plot_fitted = self.gaussian(track_steps, *popt)
                plot_center_fit = popt[1]
                plotbackground = popt[3]
                # plotbackground = self.gaussian(track_steps[0], *popt)
                plotpeak = self.gaussian(plot_center_fit, *popt)
                print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
                    plotpeak / plotbackground - 1), '\n')
                if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
                    # import pdb; pdb.set_trace()
                    if popt[0] < 0:
                        print("negative fit")

                    else:
                        self.drift[index] = plot_center_fit - self.XYZ_center[index].m
                        self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(plot_center_fit, 'um'), index), 'um')

                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    self.drift[index] = max_count_position - self.XYZ_center[index].m
                    self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(max_count_position, 'um'), index), 'um')
                    "CHECK WHAT THIS BECOMES"
            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = max_count_position - self.XYZ_center[index].m
                self.XYZ_center[index] = Q_(self.advanced_tracking(Q_(max_count_position, 'um'), index), 'um')

            print("debugging, XYZ center is " + str(self.XYZ_center))
            
            self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
            print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_pre_array is " + str(search_error_pre_array))
                
                search_error_pre = search_error_pre_array[index][0]
                # import pdb; pdb.set_trace()

                # Target value for search radius is twice the drift
                search_error = (-1) * (search[index] - Q_(np.abs(self.drift[index]), 'um') * 2).to('nm').m

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_pre_array]
                print("search_error_deques is " + str(search_error_deques))

                # Append the latest search error value to the deque at the relevant index and remove the oldest value
                search_error_deques[index].appendleft(search_error)
                search_error_deques[index].pop()
                # Convert the modified deque into a NumPy array
                search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])


                # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

                search_change += self.search_kp * search_error

                # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                integral_sum = 0.0
                for i in np.arange(n):
                    integral_sum += search_error_array[index][i]*(0.5**i)

                search_change += self.search_ki * integral_sum

                search_change += self.search_kd * (search_error - search_error_pre)
                
                # Limitations of what search radius can be with min and max search radius
                
                # Converting search[index] to float to do maths then back to nm for the variable
                search[index] =  Q_(search[index].to('nm').m + search_change, 'nm')

                if search[index] > self.max_search[index]:
                    print("Max search radius for index " + str(index) + " reached.")
                    search[index] = self.max_search[index]

                if search[index] < self.min_search[index]:
                    print("Min search radius for index " + str(index) + " reached.")
                    search[index] = self.min_search[index]

                print("Search radius for index " + str(index) + " is updated to " + str(search[index]))


            else:
                search_error_array = None

         

            

            


            
            ### Shivam: this is the old search change which is not adaptive and has a constant multiplier
            # if changing_search:
            #     if abs(self.drift[index]) < ((1 / 5) * search[index]):
            #         if search[index] * 0.9 >= self.min_search[index]:
            #             search[index] *= 0.9
            #         else:
            #             print("Min search radius for index " + str(index) + " reached.")
            #             search[index] = self.min_search[index]
            #     elif abs(self.drift[index]) > ((3 / 5) * search[index]) and abs(self.drift[index]) <= ((4 / 5) * search[index]):
            #         if search[index] * 1.5 <= self.max_search[index]:
            #             search[index] *= 1.5
            #         else:
            #             print("Max search radius for index " + str(index) + " reached.")
            #             search[index] = self.max_search[index]

            #     elif abs(self.drift[index]) > ((4 / 5) * search[index]):
            #         if search[index] * 2 <= self.max_search[index]:
            #             search[index] *= 2
            #         else:
            #             print("Max search radius for index " + str(index) + " reached.")
            #             search[index] = self.max_search[index]

            #     print("Search radius for index " + str(index) + " is updated to " + str(search[index]))



            ### Shivam: this is the new search change which is adaptive with PID control that has a target 
            # to set search radius to double the drift


        else:

            try:
                # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
                print("made it to before curve fit")
                print("Track steps is " + str(track_steps))
                print("Length of track steps is " + str(len(track_steps)))
                print("Tracking data is " + str(tracking_data))
                print("Length of tracking data is " + str(len(tracking_data)))
                popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
                print("popt[1] is " + str(popt[1]))
                print("popt is " + str(popt))
                plot_fitted = self.gaussian(track_steps, *popt)
                plot_center_fit = popt[1]
                plotbackground = popt[3]
                # plotbackground = self.gaussian(track_steps[0], *popt)
                plotpeak = self.gaussian(plot_center_fit, *popt)
                print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
                    plotpeak / plotbackground - 1), '\n')
                if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
                    
                    if popt[0] < 0:
                        print("negative fit")

                    else:
                        print("Fitting to Gaussian")
                        print("debugging, XYZ center is " + str(self.XYZ_center))
                        print("debugging, plot center fit is " + str(Q_(plot_center_fit, 'um')))
                        # import pdb; pdb.set_trace()
                        self.drift[index] = plot_center_fit - self.XYZ_center[index].m
                        
                        
                        print("debugging, drift is " + str(self.drift[index]))
                        
                        self.XYZ_center[index] = Q_(plot_center_fit, 'um')

                    
                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    print("debugging, XYZ center is " + str(self.XYZ_center))
                    print("debugging, max count position is " + str(Q_(max_count_position, 'um')))
                    #import pdb; pdb.set_trace()
                    self.drift[index] = max_count_position - self.XYZ_center[index].m
                    
                    print("debugging, drift is " + str(self.drift[index]))

                    self.XYZ_center[index] = Q_(max_count_position, 'um')

                print("debugging, XYZ center is " + str(self.XYZ_center))
                print("drift is " + str(self.drift[index]))


            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = max_count_position - self.XYZ_center[index].m
                print("drift is " + str(self.drift[index]))
                self.XYZ_center[index] = Q_(max_count_position, 'um')

                print("debugging, XYZ center is " + str(self.XYZ_center))

            self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
            print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_pre_array is " + str(search_error_pre_array))
                # Target value for search radius is twice the drift
                search_error_pre = search_error_pre_array[index][0]
                #import pdb; pdb.set_trace()
                search_error = (-1) * (search[index] - Q_(np.abs(self.drift[index]), 'um') * 2).to('nm').m

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_pre_array]
                print("search_error_deques is " + str(search_error_deques))

                # Append the latest search error value to the deque at the relevant index and remove the oldest value
                search_error_deques[index].appendleft(search_error)
                search_error_deques[index].pop()
                # Convert the modified deque into a NumPy array
                search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])


                # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

                search_change += self.search_kp * search_error

                # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
                integral_sum = 0.0
                for i in np.arange(n):
                    integral_sum += search_error_array[index][i]*(0.5**i)

                search_change += self.search_ki * integral_sum

                search_change += self.search_kd * (search_error - search_error_pre)
                
                # Limitations of what search radius can be with min and max search radius
                
                # Converting search[index] to float to do maths then back to nm for the variable
                search[index] =  Q_(search[index].to('nm').m + search_change, 'nm')

                if search[index] > self.max_search[index]:
                    print("Max search radius for index " + str(index) + " reached.")
                    search[index] = self.max_search[index]

                if search[index] < self.min_search[index]:
                    print("Min search radius for index " + str(index) + " reached.")
                    search[index] = self.min_search[index]

                print("Search radius for index " + str(index) + " is updated to " + str(search[index]))


            else:
                search_error_array = None

         
        
        return search, search_error_array
    
    def advanced_tracking(self, gaussian_center, index):
        '''
        Helper function to predict position of nanodiamond using a statistical Brownian motion analysis. Found in Harry's paper.
        "Probing and manipulation embryogenesis via nanoscale thermometry and temperature control"
        '''
        # Variable storing how many photons were collected in the scan
        self.old_n_k = self.n_k
        self.n_k[index] = self.total_fluor

        # Value of current Gaussian center in current index of search
        c_k = gaussian_center.to('um').m

        
        self.old_p_k = self.p_k

        self.p_k[index] = ((self.w * self.old_p_k[index]) / (self.w + self.old_n_k[index] * self.old_p_k[index])) + 2 * self.diffusion_constant * self.time_elapsed

        self.old_x_k = self.x_k

        # Shivam: This is the predicted position of the nanodiamond
        print("w is " + str(self.w))
        print("pk is " + str(self.p_k))
        print("ck is " + str(c_k))
        print("nk is " + str(self.n_k))
        print("old xk is " + str(self.old_x_k))
        self.x_k[index] = (self.w * self.old_x_k[index] + self.n_k[index] * self.p_k[index] * c_k) / (self.w + self.n_k[index] * self.p_k[index])

        print("debugging, x_k is " + str(self.x_k))

        return self.x_k[index]

    def one_axis_measurement(self, buffer_size, index, track_z, z_cycle, PS_clk_channel,
                iteration, search, scan_distance, num_freq, do_not_run_feedback, read_timeout, 
                spot_size, advanced_tracking, changing_search, search_error_array, search_integral_history,
                sampling_rate):

        # if track_z and (index == 2):
        #     # Shivam: What is the significance of this if statement?
        #     # Seems to be how often z axis is scanned.
        #     if iteration % z_cycle != 0:
        #         return search, np.array([0] * num_freq)

        ## in this is 180 ms of lag

        if do_not_run_feedback:
            

            self.current_counter_task.start()

            self.streamer.Pulser.stream(self.sequence, self.run_ct)

            self.sample_reader_stream.read_many_sample_uint32(self.counter_buffer,
                                            number_of_samples_per_channel=len(self.counter_buffer),
                                            timeout = read_timeout * 2)
            
            self.current_counter_task.stop()

            # self.current_counter_task.clear()
            

            buffer_allocation = None
            remaining_buffer = None

            data = self.counter_buffer

        else:
            print("-------------------")
            print("\n\n\nWe are indeed running tracking code")
            data, buffer_allocation, remaining_buffer = self.read_stream_flee(index, PS_clk_channel, search, buffer_size, scan_distance, num_freq, read_timeout)

        ## confirmed, here I have 180-200 ms of lag
        print("Length of data is " + str(len(data)))
        ## after this is 70-130 ms of lag        
        tracking_data, track_steps, temp_data, num_bins = self.process_data(data, buffer_allocation, remaining_buffer, index, search, do_not_run_feedback)
        print("Tracking data X is " + str(self.tracking_data[0]))
        self.tracking_data[index] = tracking_data

        search, search_error_array = self.datanaly(tracking_data, track_steps, index, search, do_not_run_feedback, spot_size, num_bins, advanced_tracking, 
                               changing_search, search_error_array, search_integral_history)

        ## total it says i have 250 ms of lag

        ## I can have up to 300 ms.

        return search, temp_data, search_error_array
    
    def main(self, device, PS_clk_channel, APD_channel, sampling_rate, 
                   timeout,time_per_scan, starting_temp, sb_MHz_2fq, quasilinear_slope, 
                   two_freq, odmr_frequency, rf_amplitude, clock_time, mwPulseTime, 
                   cooling_delay, is_center_modulation, data_download, 
                   activate_PID, activate_PID_no_sg_change, PID, PID_recurrence, 
                   integral_history, threshold_temp_jump, number_jump_avg, 
                   searchXYZ, max_search, min_search, changing_search, search_PID, 
                   search_integral_history, z_cycle, track_z, 
                   do_not_run_feedback, scan_distance, spot_size, advanced_tracking, 
                   diffusion_constant, infrared_on, infrared_power, heat_on_off_cycle,
                   warm_and_cool_scans, iterations = 0):
        
        if two_freq:
            num_freq = 2
            error_array = np.zeros(integral_history)  # Shivam: Array of PID error values from latest to oldest (integral_history number of latest errors)
            # Shivam: The search_error_array has 3 rows for x, y, z and integral_history columns for the latest to oldest error values
            search_error_array = np.zeros((3, search_integral_history))  # Shivam: Same as above but for search radius optimization

            start_t = time.time()
            print('Starting Time:', start_t)
            iterator = count() if iterations == 0 else range(iterations)
            # Shivam: Initialize total time elapsed variable.
            time_elapsed = 0
            threshold_index = 0
            laser_on = False
            for i in self.progress(iterator):
                if infrared_on:
                    # Shivam: Code to alternate between infrared laser on scans and off scans
                    if i == threshold_index:
                        # check if laser is on
                        # if not, then turn on and add self.heating_scans to threshold_index
                        # if yes, then turn off and add self.cooling_scans to threshold_index
                        if laser_on and self.cooling_scans != 0:
                            self.laser_ctrl_task.stop()
                            print("Heating laser is off")
                            laser_on = False
                            threshold_index += self.cooling_scans
                        elif not laser_on and self.heating_scans != 0:
                            self.laser_ctrl_task.start()
                            print("Heating laser is on")
                            laser_on = True
                            threshold_index += self.heating_scans

                # Shivam: Scanning loop through z, x, y axes.
                for index in [2, 0, 1]:
                            # Shivam: If track_z is true, then z axis is scanned every z_cycle iterations.
                            # Shivam: Not sure why this is here, but we should just assert that z_cycle is greater than 0 if track_z is true.
                            # if z_cycle == 0:
                            #     continue
                            if (not track_z) and (index == 2):
                                continue
                            elif (index == 2) and (i % z_cycle != 0):
                                continue
                            
                            time_elapsed = time.time() - start_t
                            # import pdb; pdb.set_trace()
                            self.search, temp_data, search_error_array = self.one_axis_measurement(self.bufsize, index, track_z,
                                                                                    z_cycle, PS_clk_channel,
                                                                                    i, self.search, self.scan_distance,
                                                                                    num_freq, do_not_run_feedback, 
                                                                                    self.read_timeout, self.spot_size, 
                                                                                    advanced_tracking, changing_search, 
                                                                                    search_error_array, search_integral_history,
                                                                                    sampling_rate)
                            print("MAIN: search is " + str(list(self.search.to('um').m)))
                
               
                            # Shivam: Use self.current_temp to continually use the latest temperature from the initial setting onwards.
                            self.odmr_frequency, error_array, freq_change, temp_change, self.current_temp, subtracted_error, normalization_error = self.measure_2pt_temp(temp_data, self.odmr_frequency, 
                                            quasilinear_slope, error_array, self.current_temp, activate_PID, PID, PID_recurrence, integral_history, 
                                            activate_PID_no_sg_change, i, threshold_temp_jump, number_jump_avg)


                            # Changing carrier frequency based on whether activate_PID or activate_PID_no_sg_change (only change for former)

                            # Shivam: Right now need to do int for self.odmr_frequency = new_odmr_freq because the signal generator cannot take values
                            # with many decimal places. Check with Uri.
                            if is_center_modulation:
                                if activate_PID:
                                    # The signal generator frequency is only changed if we are in PID mode
                                    self.sg.frequency = int(self.odmr_frequency)
                                    # Shivam: Need to check how long it takes to change frequency and make sure the code does not loop again before that

                            else:
                                self.sequence = self.change_pulse_sequence(freq_change)
                    
                            quasilinear_slope_e9 = quasilinear_slope * 1e9

                            if do_not_run_feedback:

                                self.acquire({
                                    't': time_elapsed,
                                    'temperature': self.current_temp,
                                    'temp_change': temp_change,
                                    'freq_change':freq_change,
                                    'sg_frequency': self.sg.frequency,
                                    'new_odmr_center': int(self.odmr_frequency),
                                    'total_fluorescence': self.total_fluor,
                                    'subtracted_error': subtracted_error,
                                    'normalization_error': normalization_error,
                                    'quasilinear_slope_e9': quasilinear_slope_e9,
                                                })
                                
                            else:
                                self.acquire({
                                    't': time_elapsed,
                                    'temperature': self.current_temp,
                                    'temp_change': temp_change,
                                    'freq_change':freq_change,
                                    'new_odmr_center': self.odmr_frequency,
                                    'set_sg_frequency': self.sg.frequency,
                                    'searchX_um': list(self.search.to('um').m)[0],
                                    'searchY_um': list(self.search.to('um').m)[1],
                                    'searchZ_um': list(self.search.to('um').m)[2],
                                    'tracking_data_X': self.tracking_data[0],
                                    'x_pos': self.XYZ_center[0].to('um').m,
                                    'y_pos': self.XYZ_center[1].to('um').m,
                                    'z_pos': self.XYZ_center[2].to('um').m,
                                    'total_fluorescence': int(self.total_fluor),
                                    'subtracted_error': subtracted_error,
                                    'normalization_error': normalization_error,
                                    'quasilinear_slope': quasilinear_slope_e9,
                                                })
                            
                            time.sleep(cooling_delay.m)

       
        '''
        else:
            num_freq = 4
            for rep in self.progress(range(repetitions)):
                for lp_idx, lp in enumerate(self.laser_powers):  # self.laser_powers):
                    # print(lp)
                    # import pdb; pdb.set_trace()
                    sequence = self.sequence
                    self.infrared.modulation_power = lp
                    self.laser_ctrl_task.start()
                    # print("task has started")
                    # start_time = time.time()
                    thermo_data = [[], [], []]

                    for sweep in range(self.heating_scans):
                        flex = time.time()
                        for index in range(3):
                            sequence, search, temp_data = self.one_axis_measurement(self.buffer_size, index, track_z,
                                                                                    sweep, lp_idx, z_cycle,
                                                                                    PS_clk_channel,
                                                                                    channel, sequence, search, rep, 0,
                                                                                    num_freq, do_not_run_feedback)

                            thermo_data[index].append(temp_data)
                            # if sequence == None:
                            # continue
                        print('\nevery scan takes this long:', time.time() - flex, '\n')
                    hot_dat_storage = thermo_data
                    thermo_data = [[], [], []]
                    self.laser_ctrl_task.stop()
                    for sweep in range(self.cooling_scans):
                        for index in range(3):
                            sequence, search, temp_dat_storage = self.one_axis_measurement(self.buffer_size, index,
                                                                                           track_z, sweep, lp_idx,
                                                                                           z_cycle, PS_clk_channel,
                                                                                           channel, sequence, search,
                                                                                           rep, 0, num_freq,
                                                                                           do_not_run_feedback)
                            thermo_data[index].append(temp_data)
                    cold_dat_storage = thermo_data
                    thermo_data = [[], [], []]
                    rise_in_temperature, fall_in_temperature, fluo_h, fluo_c = self.measure_4pt_temp(hot_dat_storage,
                                                                                                     cold_dat_storage)

                    self.acquire({
                        'lp_repetitions': rep,
                        'laserPower': lp.to('mW').m,
                        'lp_idx': lp_idx,
                        'heat_data': fluo_h,
                        'cooling_data': fluo_c,
                        'tempRising': rise_in_temperature,
                        'tempFalling': fall_in_temperature,
        
                    })
        '''


    def ready_center_pulse_sequence(self, time_per_scan, mwPulseTime, clockPulse, sideband_frequency, rf_amplitude):
        self.streamer.read_time = int(round(mwPulseTime.to('ns').m))
        self.streamer.clock_time = int(round(clockPulse.to('ns').m))
        seq, self.new_pulse_time = self.streamer.odmr_temp_calib_no_bg(sideband_frequency)

        self.sg.rf_amplitude = rf_amplitude
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'

        # Shivam: streamer.total_time is from the odmr_temp_calib function from dr_pulsesequences_Sideband
        # And it is the total time for one pulse sequence (2 * new_pulse_time)
        self.run_ct = math.ceil(time_per_scan.to('ns').m / self.streamer.total_time)

        # This is an important variable to know how long is spent collecting photons at one center freqeuncy
        self.real_time_per_scan = self.run_ct * self.streamer.total_time

        return seq, self.new_pulse_time
    

    def setup_LPvT(self, freqs, mwPulseTime, clock_time, time_per_scan, num_freq, rf_amplitude):
        self.streamer.read_time = int(round(mwPulseTime.to('ns').m))
        self.streamer.clock_time = int(round(clock_time.to('ns').m))

        self.sg.rf_amplitude = rf_amplitude
        self.sg.mod_type = 'QAM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'

        temp_sequence = self.streamer.setup_LPvT(freqs, num_freq)
        self.run_ct = math.ceil(time_per_scan.to('ns').m / self.streamer.total_time) + 1
        # import pdb; pdb.set_trace()
        print('\nThis is my sequence!\n', temp_sequence)
        return temp_sequence


    def change_pulse_sequence(self, freq_change):

        # self.streamer.clock_time = int(round(clock_time.to('ns').m))
        # self.streamer.probe_time = int(round(probe_time.to('ns').m))
        # sideband_adjustment = odmr_frequency - new_odmr_freq
        print('\nBefore changing pulse frequencies:    ', self.ps_frequencies)
        self.ps_frequencies = list(np.array(self.ps_frequencies) - freq_change)
        print('After changing pulse frequencies:    ', self.ps_frequencies, '\n')
        tempReadout = self.streamer.setup_LPvT(self.ps_frequencies, 2)
        # self.run_ct = math.ceil(self.time_per_scan.to('ns').m / self.streamer.total_time) + 1
        # import pdb; pdb.set_trace()
        return tempReadout
    
    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        # Shivam: Convert FWHM (width) to standard deviation for Gaussian plot
        if a < 0 or width < 0 or b < 0:
            return math.inf
        sigma = width / (np.sqrt(8 * np.log(2)))
        return a * np.exp(-np.square((xs - x) / (np.sqrt(2) * + sigma))) + b

    '''
    Shivam: This is no longer needed as its role is fulfilled by hs_prepare() and hs_linescan() in dr_ni_motion_controller.py
    def read_data(self, buffer, ctr_task, ctr_reader, sequence):
                            
        'start the pulse streamer and the task close to simultaneously'
        ctr_task.start()
        self.streamer.Pulser.stream(sequence, self.run_ct)

        data_obtain = ctr_reader.read_many_sample_uint32(
            buffer,
            number_of_samples_per_channel=len(buffer),
            timeout= self.read_timeout
        )
        ctr_task.stop()
        
        self.streamer.Pulser.reset() 
    
        return buffer
    '''

    
    
    '''
    Shivam: This is no longer needed as we are doing spatial tracking while taking measurements.
    def feedback(self, sweep, sweeps_until_feedback, z_feedback_every, xyz_step_nm, shrink_every_x_iter,starting_point):
        # Shivam: This is the standard spatial feedback method employed in other ODMR Spyrelets.

        if (sweep > 0) and (sweep % sweeps_until_feedback == 0):
            if sweep % z_feedback_every == 0:
                dozfb = True
            else:
                dozfb = False

            feed_params = {
                'starting_point': str(starting_point),
                'x_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x']),
                'y_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y']),
                'z_initial': rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z']),
                'do_z': dozfb,
                'xyz_step': xyz_step_nm,
                'shrink_every_x_iter': shrink_every_x_iter,

            }
            ## we make sure the laser is turned on.
            self.streamer.Pulser.constant(([7], 0.0, 0.0))

            self.call(self.newSpaceFB, **feed_params)

            ##space_data is the last line of data from spatialfeedbackxyz
            space_data = self.newSpaceFB.data.tail(1)
            x_initial = Q_(space_data['x_center'].values[0], 'um')
            y_initial = Q_(space_data['y_center'].values[0], 'um')
            if dozfb:
                z_initial = Q_(space_data['z_center'].values[0], 'um')

                self.urixyz.daq_controller.move({'x': x_initial, 'y': y_initial, 'z': z_initial})
                return
            # Shivam: Is there supposed to be an else over here?
            self.urixyz.daq_controller.move({'x': x_initial, 'y': y_initial, 'z': self.XYZ_center[2]})
            return
        else:
            return
    '''



    @PlotFormatInit(LinePlotWidget, ['temp'])
    def init_format(plot):
        plot.xlabel = 'Time (s)'
        plot.ylabel = 'Temperature (C)'


    @Plot1D
    def all(df, cache):
        return {'Temperature':[df.t.values, df.temperature.values]}

    @Plot1D
    def latest(df, cache):
        return {'Temperature':[df.t.tail(100).values, df.temperature.tail(100).values]}
    
    @Plot1D
    def freq_shift(df, cache):
        return {'ZFS':[df.t.values, df['new_odmr_center'].values]}
    
    @Plot1D
    def set_sg(df, cache):
        return {'ZFS':[df.t.values, df['set_sg_frequency'].values]}
    
    @Plot1D
    def x_drift(df, cache):
        return {'X Tracking': [df.t.values, df['x_pos'].values]}
    
    @Plot1D
    def y_drift(df, cache):
        return {'Y Tracking': [df.t.values, df['y_pos'].values]}
    
    @Plot1D
    def z_drift(df, cache):
        return {'Z Tracking': [df.t.values, df['z_pos'].values]}
    
    @Plot1D
    def total_fluor(df, cache):
        return {'Total Fluorescence': [df.t.values, df['total_fluorescence'].values]}
    
    @Plot1D
    def x_search(df, cache):
        return {'X Search Radius': [df.t.values, df['searchX_um'].values]}
    
    @Plot1D
    def y_search(df, cache):
        return {'X Search Radius': [df.t.values, df['searchY_um'].values]}
    
    @Plot1D
    def z_search(df, cache):
        return {'X Search Radius': [df.t.values, df['searchZ_um'].values]}
    



    def finalize(self, device, PS_clk_channel, APD_channel, sampling_rate, 
                   timeout,time_per_scan, starting_temp, sb_MHz_2fq, quasilinear_slope, 
                   two_freq, odmr_frequency, rf_amplitude, clock_time, mwPulseTime, 
                   cooling_delay, is_center_modulation, data_download, 
                   activate_PID, activate_PID_no_sg_change, PID, PID_recurrence, 
                   integral_history, threshold_temp_jump, number_jump_avg, 
                   searchXYZ, max_search, min_search, changing_search, search_PID, 
                   search_integral_history, z_cycle, track_z, 
                   do_not_run_feedback, scan_distance, spot_size, advanced_tracking, 
                   diffusion_constant, infrared_on, infrared_power, heat_on_off_cycle,
                   warm_and_cool_scans, iterations = 0):
        # self.urixyz.daq_controller.ao_motion_task.stop()
        # self.urixyz.daq_controller.collect_task.stop()
        
        if infrared_on:
            self.laser_ctrl_task.close()


        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        print("Turning off laser")
        self.streamer.Pulser.reset()
        #self.streamer.Pulser.constant(([7],0.0,0.0))
        self.streamer.Pulser.isStreaming()

                ## turns off instruments
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False

        if do_not_run_feedback:
            print("Closing counter task")

            self.current_counter_task.stop()

            self.current_counter_task.close()

        if data_download:
            save_excel(self.name)
            print('The name of the excel data:', self.name)



    


class TemperatureCalibrationSpyrelet(Spyrelet):

    """
    Shivam: This class is meant to create a plot of temperature vs infrared laser power
    """

    REQUIRED_DEVICES = [
        'sg',
        'streamer',
        'urixyz',
        'infrared',
    ]
    # # REQUIRED_SPYRELETS = {
    # # 'newSpaceFB': SpatialFeedbackXYZSpyrelet
    # # }
    PARAMS = {
        'device': {
            'type': str,
            'default': 'Dev1',
        },
        'channel': {
            'type': list,
            'items': list(['ctr0', 'ctr1', 'ctr2', 'ctr3', 'none']),
            'default': 'ctr1',
        },
        'PS_clk_channel': {
            'type': str,
            'default': 'PFI0',
        },
        'sampling_rate': {
            'type': float,
            'units': 'Hz',
            'suffix': ' Hz',
            'default': 50000,
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 12
        },
        'repetitions': {
            'type': int,
            'default': 5,
            'positive': True
        },
        ## for the strength of the heating laser
        'laserpower_start_stop_iter': {
            'type': str,
            'default': "[Q_(.1, 'mW'),Q_(1, 'mW'), 5]"
        },
        ## for the heat pulses
        # Shivam: why is there a *9 on the false and what does this mean?
        # Answer is that the on pulse is shorter than off to limit the temperature change
        'heat_on_off_array': {
            'type': str,
            'default': "[True] + [False]*9",
        },
        'time_per_scan': {
            'type': float,
            'default': 1,
            'suffix': ' s',
            'units': 's',
        },
   
        'sbChoice_MHz_big': {
            'type': list,
            'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                      '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                      '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                      '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                      '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                      '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                      '5.952380952',
                      '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
                      '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
                      '2.5'],

            'default': '10.1010101',
        },
        'sbChoice_MHz_small': {
            'type': list,
            'items': ['62.5', '55.55555555', '50', '41.666666666', '37.0370370', '33.33333333', '31.25',
                      '27.77777777', '25', '20.833333', '18.51851851', '17.857142857', '16.66666667', '15.8730158730',
                      '15.625', '14.2857142857', '13.88888889', '12.5', '12.345679', '11.36363636', '11.1111111',
                      '10.41666667', '10.1010101', '10', '9.615384615', '9.25925926', '9.09090909', '8.92857142',
                      '8.547008547', '8.33333333', '7.936507936507', '7.8125', '7.6923077', '7.407407407', '7.3529412',
                      '7.14285714', '6.94444444', '6.6666667', '6.5789474', '6.5359477', '6.25', '6.1728395',
                      '5.952380952',
                      '5.8823529', '5.84795322', '5.68181818', '5.55555556', '5.4347826', '5.291005291', '5.2631579',
                      '5.2083333', '5.05050505', '5', '4.4642857', '4.0322581', '3.78787879', '3.4722222', '2.84090909',
                      '2.5'],
            'default': '6.94444444',
        },
        'sb_MHz_2fq': {
            'type': float,
            'default': 15e6,
            'units': 'Hz',
        },
        # 'useSbList':{
        # 'type': bool,
        # 'default': True,
        # },
        'two_freq': {
            'type': bool,
            'default': True,
        },
        'quasilinear_slope': {
            'type': float,
            'default': .01,
        },
        'odmr_frequency': {
            'type': float,
            'units': 'Hz',
            'default': 2.87e9,
        },
        'rf_amplitude': {
            'type': float,
            'default': -20,
        },
        'searchZXY': {
            'type': str,
            'default': "Q_([500, 500, 500], 'nm')",
        },
        'warm_and_cool_scans': {
            'type': str,
            'default': '[30, 30]',
        },
        'clock_time': {
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'mwPulseTime': {
            'type': float,
            'default': 50e-6,
            'suffix': ' s',
            'units': 's',
        },
        'pos_initial': {
            'type': str,
            'default': "Q_([0.,0.,0.], 'um')",
        },
        'z_cycle': {
            'type': int,
            'default': 10,
            'positive': True,
        },
        'track_z': {
            'type': bool,
            'default': True,
        },
        'do_not_run_feedback': {
            'type': bool,
            'default': False
        },
        'data_download': {
            'type': bool,
        },
        
    }

    '''
    For two frequencies, we have some considerations
    How often do we measure the temperature?
    From what standard do we measure the temperature?
    
    in four frequency, omega is constant. In this one, we change omega according to the signal generator frequency each time.
    Therefore, it would make sense to acquire it every 
    
    '''

    def read_stream_flee(self, index, PS_clk_channel, channel, sequence, search, buffer_size, num_freq):
        ## total this has 180 ms of lag.
        # time_track = time.time()
        xyz_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                buffer_size)
        # Shivam: Assigns the entire XYZ_center array to both newly defined arrays
        pos_center_st = self.XYZ_center[:]
        pos_center_end = self.XYZ_center[:]
        pos_center_st[index] = xyz_steps[0]
        pos_center_end[index] = xyz_steps[-1]
        # import pdb; pdb.set_trace()
        # Shivam: Doing a 1 axis scan from the set start point till end point with buffer_size steps
        self.urixyz.daq_controller.hs_prepare(buffer_size, PS_clk_channel, channel,
                                              {'x': pos_center_st[0], 'y': pos_center_st[1], 'z': pos_center_st[2]},
                                              {'x': pos_center_end[0], 'y': pos_center_end[1], 'z': pos_center_end[2]},
                                              buffer_size, pts_per_step=0)

        ###Before this, around .12 seconds have elapsed

        'start the pulse streamer and the task close to simultaneously'

        self.streamer.Pulser.stream(sequence, self.run_ct)
        ## this is 35 ms all on its own. 
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        scan_data = self.urixyz.daq_controller.hs_linescan(num_freq * 2)

        self.streamer.Pulser.reset()
        ## this is 5 miliseconds
        # print('time for read stream flee:', time.time() - time_track)

        ## pulser stream to pulser reset has 60ms delay.
        
        return rpyc.utils.classic.obtain(scan_data)

    def process_data(self, index, scan_data, search):
        # temp_dat_storage, index, scan_data, search):

        half_num = int(len(scan_data) / 2)
        temp_data = np.array([None] * half_num)
        for i in range(half_num):
            # Shivam: This seems wrong
            temp_data[i] = np.sum(scan_data[i] + scan_data[- 1 - i])

        tracking_data = np.sum(scan_data, axis=0)

        # temp_dat_storage.append(temp_data)
        # temp_data = np.array(temp_data, dtype = np.float)
        track_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                  len(tracking_data)).to('um').m

        return tracking_data, track_steps, temp_data

    def measure_2pt_temp(self, temp_data, frequencies, half_gamma, quasilinear_slope, time_elapsed, error_pre_array):
        # def make_digestible(matrix):
        # return np.sum(matrix, axis = 1)
        # Shivam: Creating an array that holds the previous n error values for integral implementation of PID control
        # cont. This array holds error value * time_elapsed since that is the value required for a Riemann integral
        n = np.size(error_pre_array)
        error_pre = error_pre_array[0]
        
        if temp_data.all() == 0:
            return sum(frequencies) / 2, error_pre, 0

        # fluo_data = make_digestible(temp_data)
        print(temp_data)
        # import pdb; pdb.set_trace()
        # Shivam: is there a need for dividing by gamma here? Might not be
        # f_process_variable = (float(temp_data[1]) - float(temp_data[0]))/(2*half_gamma) Shivam: Aidan's Old Code
        f_process_variable = (float(temp_data[1]) - float(temp_data[0])) # should be negative if temperature increasing
        f_set_variable = 0
        f_error = f_process_variable - f_set_variable
        constant = quasilinear_slope  # fluor / Hz
        latest_error = f_error / constant

        # Shivam: Converting array to deque to maintain latest n error values (adding new one and removing oldest one)
        error_deque = collections.deque(error_pre_array)
        error_deque.appendleft(latest_error)
        error_deque.pop()
        error_array = np.array(error_deque)

        # kp = .8; ki = .01; kd = 0 Shivam: Aidan's Old Code
        # Shivam: PID control coefficients
        kp = 1.0
        ki = 0.01
        kd = 0.0


        # Shivam: Implementation of weighted sum of error values for integral component of PID
        integral_sum = 0.0
        for index in np.arange(n):
            integral_sum = integral_sum + error_array[index]*(0.5**n)

        freq_change = kp * latest_error + ki * integral_sum  # + kd * (error - error_pre) / (time_elapsed)

        new_odmr_freq = sum(frequencies) / 2 - freq_change  # temp_change should be in Hz!!!!!

        return new_odmr_freq, error_array, freq_change

    def change_pulse_sequence(self, freq_change):

        # self.streamer.clock_time = int(round(clock_time.to('ns').m))
        # self.streamer.probe_time = int(round(probe_time.to('ns').m))
        # sideband_adjustment = odmr_frequency - new_odmr_freq
        print('\nBefore changing pulse frequencies:    ', self.ps_frequencies)
        self.ps_frequencies = list(np.array(self.ps_frequencies) - freq_change)
        print('After changing pulse frequencies:    ', self.ps_frequencies, '\n')
        tempReadout = self.streamer.setup_LPvT(self.ps_frequencies, 2)
        # self.run_ct = math.ceil(self.time_per_scan.to('ns').m / self.streamer.total_time) + 1
        # import pdb; pdb.set_trace()
        return tempReadout

    def measure_4pt_temp(self, hot_dat_storage, cold_dat_storage):
        dDdT = -74.2  # 'kHz/K'

        # fluo_1h, fluo_2h, fluo_3h, fluo_4h = sum(self.hot_x_data[0]), sum(self.hot_x_data[2]), sum(self.hot_x_data[3]), sum(self.hot_x_data[1])
        # can minimize code by writing a dictionary
        # def temp_data(matrix):
        # return np.sum(matrix, axis = 1)

        fluo_h_x = hot_dat_storage[0]
        fluo_h_y = hot_dat_storage[1]
        fluo_h_z = hot_dat_storage[2]
        import pdb;
        pdb.set_trace()
        # for i in range(len(fluo_h_x) - len(fluo_h_z)): 
        # fluo_h_z.append(np.zeros([4]))

        fluo_h = np.array(fluo_h_x) + np.array(fluo_h_y) + np.array(fluo_h_z)

        # fluo_h_x = [temp_data(self.hot_x_data) for h in range(len(self.hot_x_data))]
        # fluo_h_y = [np.sum(self.hot_y_data[:][index], axis = 1) for h in range(4)]
        # fluo_h_z = [np.sum(self.hot_z_data[:][index], axis = 1) for h in range(4)]
        # fluo_c_x = [temp_data(buffer) for buffer in cold_dat_storage[1]]
        # fluo_c_y = [temp_data(buffer) for buffer in cold_dat_storage[2]]
        # fluo_c_z = [temp_data(buffer) for buffer in cold_dat_storage[0]]

        fluo_c_x = cold_dat_storage[0::3]
        fluo_c_y = cold_dat_storage[1::3]
        fluo_c_z = cold_dat_storage[2::3]

        # for i in range(len(fluo_c_x) - len(fluo_c_z)):
        # fluo_c_z.append(np.zeros([4]))

        fluo_c = np.array(fluo_c_x) + np.array(fluo_c_y) + np.array(fluo_c_z)

        # fluo_c = [list_cold_data(c) for c in range(4)]

        fh = np.sum(fluo_h, axis=0)
        fc = np.sum(fluo_c, axis=0)

        # import pdb; pdb.set_trace()
        temp_hot_change = self.delomega / dDdT * (fh[0] + fh[1] - fh[2] - fh[3]) / (fh[0] - fh[1] + fh[3] - fh[2])
        temp_cold_change = self.delomega / dDdT * (fc[0] + fc[1] - fc[2] - fc[3]) / (fc[0] - fc[1] + fc[3] - fc[2])

        return temp_hot_change, temp_cold_change, fluo_h, fluo_c

    def datanaly(self, tracking_data, track_steps, index, search, do_not_run_feedback):
        if do_not_run_feedback:
            return
        print('Out of XYZ, this is the', index, 'axis')
        p0 = [np.max(tracking_data), track_steps[np.argmax(tracking_data)], .4, np.min(tracking_data)]
        try:
            # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
            popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
            plot_fitted = self.gaussian(track_steps, *popt)
            plot_center_fit = popt[1]
            plotbackground = self.gaussian(track_steps[0], *popt)
            plotpeak = self.gaussian(plot_center_fit, *popt)
            print('plot peak, background, SBR:' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
                plotpeak / plotbackground - 1), '\n')
            if np.min(track_steps) < plot_center_fit < np.max(track_steps):
                # import pdb; pdb.set_trace()
                if popt[0] < 0:
                    print("negative fit")

                elif np.abs(Q_(plot_center_fit, 'um') - self.XYZ_center[index]) < search[index]:
                    self.drift[index] = Q_(plot_center_fit, 'um') - self.XYZ_center[index]
                    self.XYZ_center[index] = Q_(plot_center_fit, 'um')

                    print('plot_center from fit:', plot_center_fit)
                else:
                    print("Z drift limit reached. Setting to previous value.")
            else:
                print('Optimum Z out of scan range. Setting to previous value.')
        except RuntimeError:
            print('no z fit')
            max_count_position = track_steps[np.argmax(tracking_data)]
            self.drift[index] = Q_(max_count_position, 'um') - self.XYZ_center[index]
            self.XYZ_center[index] = Q_(max_count_position, 'um')
            # #z_fitted = self.gaussian(track_steps, *p0)
            # self.XYZ_center[index] = self.XYZ_center[index]

        # self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})

    def acquire_tracking(self, search, scan, sweep, lp_idx, rep):
        self.urixyz.daq_controller.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
        print('\nHere is where the laser is currently pointing:', self.urixyz.daq_controller.position)
        for i, num in enumerate(search):
            search[i] *= 0.9 if abs(self.drift[i]) < (2 / 5 * search[i]) else 1.2 if abs(self.drift[i]) > (
                    7 / 10 * search[i]) else 1
        # import pdb; pdb.set_trace()
        search_um = search.to('um').m
        self.acquire({
            'laserPowerIdx': lp_idx,
            'iteration': scan + sweep,
            # 'driftX_um': self.drift[1].to('um').m,
            # 'driftY_um': self.drift[2].to('um').m,
            # 'driftZ_um': self.drift[0].to('um').m,
            'searchZXY_um': list(search_um),
            'x_data_um': self.XYZ_center[0].to('um').m,
            'y_data_um': self.XYZ_center[1].to('um').m,
            'z_data_um': self.XYZ_center[2].to('um').m,
            # 'pos_data_um' : [self.position[0].to('um').m, self.position[1].to('um').m, self.position[2].to('um').m],
            'tracking_rep': rep,
        })
        return search

    def setup_LPvT(self, freqs, probe_time, clock_time, time_per_scan, num_freq=4):
        self.streamer.clock_time = int(round(clock_time.to('ns').m))
        self.streamer.probe_time = int(round(probe_time.to('ns').m))
        # Shivam: what is streamer.setup_LPvT()?
        tempReadout = self.streamer.setup_LPvT(freqs, num_freq)
        self.run_ct = math.ceil(time_per_scan.to('ns').m / self.streamer.total_time) + 1
        # import pdb; pdb.set_trace()
        print('\nThis is my sequence!\n', tempReadout)
        return tempReadout

    def one_axis_measurement(self, buffer_size, index, track_z, sweep, lp_idx, z_cycle, PS_clk_channel, channel,
                             sequence, search, rep, scan, num_freq, do_not_run_feedback):

        if track_z and (index == 2):
            # Shivam: What is the significance of this if statement?
            if ((sweep + lp_idx * (self.heating_scans + self.cooling_scans)) % z_cycle != 0):
                return sequence, search, np.array([0] * num_freq)

        ## in this is 180 ms of lag

        data = self.read_stream_flee(index, PS_clk_channel, channel, sequence, search, buffer_size, num_freq)

        ## confirmed, here I have 180-200 ms of lag

        ## after this is 70-130 ms of lag        
        tracking_data, track_steps, temp_data = self.process_data(index, data, search)

        self.datanaly(tracking_data, track_steps, index, search, do_not_run_feedback)

        search = self.acquire_tracking(search, scan, sweep, lp_idx, rep)

        ## total it says i have 250 ms of lag

        ## I can have up to 300 ms.

        return sequence, search, temp_data

    def main(self, device, channel, PS_clk_channel, sampling_rate, timeout,
             repetitions, laserpower_start_stop_iter, heat_on_off_array, time_per_scan,
             sbChoice_MHz_big, sbChoice_MHz_small, sb_MHz_2fq, quasilinear_slope,
             two_freq, odmr_frequency, rf_amplitude, searchZXY,
             warm_and_cool_scans, clock_time, mwPulseTime,
             pos_initial, z_cycle, track_z, do_not_run_feedback, data_download):

        x_center = self.urixyz.daq_controller.position['x']
        y_center = self.urixyz.daq_controller.position['y']
        z_center = self.urixyz.daq_controller.position['z']
        # Shivam: does the below line convert searchZXY to int data type?
        search = eval(searchZXY)
        temp_dat_storage = []
        # trial_time = time.time()
        # for i in range(100000000):
        # x = time.time()
        # print(time.time() - trial_time)
        # import pdb; pdb.set_trace()
        if two_freq:
            num_freq = 2

            sequence = self.sequence
            error_array = np.zeros(5)  # Shivam: Array of PID error values from latest to oldest
            time_start = time.time()
            print('time is indeed starting in this file:', time_start)
            '''
            implement clean 4 frequency
            '''
            for rep in self.progress(range(repetitions)):
                for lp_idx, lp in enumerate(self.laser_powers):
                    self.infrared.modulation_power = lp
                    self.laser_ctrl_task.start()
                    # print(time.time(), " is the time after the 808nm laser turns on\n")
                    for sweep in range(self.heating_scans + self.cooling_scans):
                        # Shivam: Loop for one heating or cooling
                        if sweep == self.heating_scans:
                            self.laser_ctrl_task.stop()
                        # print(time.time())
                        # Shivam: what are these indices?
                        for index in [2, 0, 1]:
                            time_elapsed = time.time() - time_start
                            print('my time elapsed will be the following:', time_elapsed)
                            # import pdb; pdb.set_trace()
                            sequence, search, temp_data = self.one_axis_measurement(self.buffer_size, index, track_z,
                                                                                    sweep, lp_idx, z_cycle,
                                                                                    PS_clk_channel,
                                                                                    channel, sequence, search, rep, 0,
                                                                                    num_freq, do_not_run_feedback)
                            time_start = time.time()

                            if temp_data.all() == 0:
                                # Shivam: continue skips this iteration of loop and goes back to start of loop for
                                # next iteration. But what is the point of doing this?
                                continue
                            # def measure_2pt_temp(self, temp_data, frequencies, half_gamma, quasilinear_slope,
                            # time_elapsed, error_pre):
                            new_odmr_freq, error_array, freq_change = self.measure_2pt_temp(temp_data,
                                                                                            self.ps_frequencies,
                                                                                            sb_MHz_2fq.to('Hz').m,
                                                                                            quasilinear_slope,
                                                                                            time_elapsed, error_array)

                            # def change_pulse_sequence(self, new_odmr_freq, two_freq, sequence):
                            sequence = self.change_pulse_sequence(freq_change)
                            # Shivam: why is number of sweeps being compared to heating scans?
                            if sweep < self.heating_scans:
                                temp = 'heating up'
                            else:
                                temp = 'cooling down'
                            # resetting temp_dat_storage because I do not want to continue appending it to the list

                            self.acquire({
                                'lp_repetitions': rep,
                                'laserPower': lp.to('mW').m,
                                'lp_idx': lp_idx,
                                'hot_or_cold': temp,
                                'tempChange': freq_change / (-74.2 * 1000),  # kHz/K
                                'new_odmr_center': new_odmr_freq + self.sg.frequency.to('Hz').m,
                                'original_odmr_center': odmr_frequency,
                                'index': index,
                                'sweep': sweep,
                            })

        else:
            num_freq = 4
            for rep in self.progress(range(repetitions)):
                for lp_idx, lp in enumerate(self.laser_powers):  # self.laser_powers):
                    # print(lp)
                    # import pdb; pdb.set_trace()
                    sequence = self.sequence
                    self.infrared.modulation_power = lp
                    self.laser_ctrl_task.start()
                    # print("task has started")
                    # start_time = time.time()
                    thermo_data = [[], [], []]

                    for sweep in range(self.heating_scans):
                        flex = time.time()
                        for index in range(3):
                            sequence, search, temp_data = self.one_axis_measurement(self.buffer_size, index, track_z,
                                                                                    sweep, lp_idx, z_cycle,
                                                                                    PS_clk_channel,
                                                                                    channel, sequence, search, rep, 0,
                                                                                    num_freq, do_not_run_feedback)

                            thermo_data[index].append(temp_data)
                            # if sequence == None:
                            # continue
                        print('\nevery scan takes this long:', time.time() - flex, '\n')
                    hot_dat_storage = thermo_data
                    thermo_data = [[], [], []]
                    self.laser_ctrl_task.stop()
                    for sweep in range(self.cooling_scans):
                        for index in range(3):
                            sequence, search, temp_dat_storage = self.one_axis_measurement(self.buffer_size, index,
                                                                                           track_z, sweep, lp_idx,
                                                                                           z_cycle, PS_clk_channel,
                                                                                           channel, sequence, search,
                                                                                           rep, 0, num_freq,
                                                                                           do_not_run_feedback)
                            thermo_data[index].append(temp_data)
                    cold_dat_storage = thermo_data
                    thermo_data = [[], [], []]
                    rise_in_temperature, fall_in_temperature, fluo_h, fluo_c = self.measure_4pt_temp(hot_dat_storage,
                                                                                                     cold_dat_storage)

                    self.acquire({
                        'lp_repetitions': rep,
                        'laserPower': lp.to('mW').m,
                        'lp_idx': lp_idx,
                        'heat_data': fluo_h,
                        'cooling_data': fluo_c,
                        'tempRising': rise_in_temperature,
                        'tempFalling': fall_in_temperature,
                    })

    def initialize(self, device, channel, PS_clk_channel, sampling_rate, timeout,
                   repetitions, laserpower_start_stop_iter, heat_on_off_array, time_per_scan,
                   sbChoice_MHz_big, sbChoice_MHz_small, sb_MHz_2fq, quasilinear_slope,
                   two_freq, odmr_frequency, rf_amplitude, searchZXY,
                   warm_and_cool_scans, clock_time, mwPulseTime,
                   pos_initial, z_cycle, track_z, do_not_run_feedback, data_download):

        # (self, device, channel, PS_clk_channel, sampling_rate, timeout,
        # repetitions, laserpower_start_stop_iter, heat_on_off_array, time_per_scan,
        # sbChoice_MHz_big, sbChoice_MHz_small, sb_MHz_2fq,
        # two_freq, odmr_frequency, rf_amplitude, searchZXY,
        # warm_and_cool_scans, clock_time, mwPulseTime,
        # pos_initial, z_cycle, track_z, data_download):
        if sampling_rate.to('Hz').m <= 1 / mwPulseTime.to('s').m:
            print('sampling rate must be equal or larger than 1/probe_time')
            pass
        print('please initialize')
        print(
            '\nbefore continuining, ensure that the laser key has been turned and the infrared is on.\n\n Check to see if the shutter is closed.\n')

        self.buffer_size = math.floor(time_per_scan / mwPulseTime) + 1

        def setup_random_params(warm_and_cool_scans, heat_on_off_array, laserpower_start_stop_iter):
            self.heating_scans, self.cooling_scans = eval(warm_and_cool_scans)
            self.usegaussian = True

            self.urixyz.daq_controller.acq_rate = sampling_rate

            self.drift = Q_([0, 0, 0], 'um')
            # self.XYZ_center = [rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['x']),
            # rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['y']),
            # rpyc.utils.classic.obtain(self.urixyz.daq_controller.position['z'])]
            self.XYZ_center = [self.urixyz.daq_controller.position['x'],
                               self.urixyz.daq_controller.position['y'],
                               self.urixyz.daq_controller.position['z']]

            self.sg.frequency = Q_(2.87e9, 'Hz')
            self.sg.mod_type = 'QAM'
            self.sg.rf_toggle = True
            self.sg.mod_toggle = True
            self.sg.mod_function = 'external'

            self.laser_powers = np.linspace(eval(laserpower_start_stop_iter)[0], eval(laserpower_start_stop_iter)[1],
                                            eval(laserpower_start_stop_iter)[2])

            heat_array = eval(heat_on_off_array)
            return heat_array

        laser_values = setup_random_params(warm_and_cool_scans, heat_on_off_array, laserpower_start_stop_iter)

        ### this can go in its own function
        ## this is setting up the pulse streamer frequencies, signal generator frequencies, and the temperature change frequency
        ## it changes whether you chose to do two_freq modulation or not.
        if not two_freq:
            sb_big = Q_(eval(sbChoice_MHz_big), 'MHz');
            sb_small = Q_(eval(sbChoice_MHz_small), 'MHz')
            frequencies = [(odmr_frequency - sb_big), (odmr_frequency - sb_small),
                           (odmr_frequency + sb_small), (odmr_frequency + sb_big)]
            sg_frequency = (odmr_frequency - (sb_big + sb_small)).to(
                'Hz').m  # frequencies[3].to('Hz').m - sb_frequency*1e6
            print('the maximum sideband frequency is:', 2 * sb_big + 2 * sb_small)
            num_freq = 4

            omega1 = (frequencies[0] + frequencies[1]) / 2
            omega2 = (frequencies[2] + frequencies[3]) / 2
            self.delomega = (omega2 - omega1).to('kHz').m

        else:

            frequencies = [(odmr_frequency - sb_MHz_2fq), (odmr_frequency + sb_MHz_2fq)]
            sg_frequency = (odmr_frequency - (sb_MHz_2fq + Q_(5, 'MHz'))).to('Hz').m
            self.frequencies = frequencies
            num_freq = 2
        # import pdb; pdb.set_trace()
        self.ps_frequencies = [freq.to('Hz').m - sg_frequency for freq in
                               frequencies]  # (frequencies.to('Hz').m - sg_frequency)
        self.sg.frequency = sg_frequency

        self.seqTempReadout = self.setup_LPvT(self.ps_frequencies, mwPulseTime, clock_time, time_per_scan, num_freq)
        self.sequence = self.seqTempReadout

        def laser_init(device, timeout):
            self.infrared.digital_modulation = True

            laser_channel = device + '/port0/line3'
            # Shivam: Corresponds to the minimum time window of a True or False, generally do lower frequency if switching between True and False regularly
            laser_update_freq = 3.33e5 #Hz
            'daq update frequency is slower than the documentation claims.'
            'update freq must be considered with the laser sequence'

            self.laser_ctrl_task = nidaqmx.Task('Laser_ctrl_task')
            self.laser_ctrl_task.do_channels.add_do_chan(laser_channel,
                                                         line_grouping=nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
            self.laser_ctrl_task.timing.cfg_samp_clk_timing(
                laser_update_freq,
                sample_mode=AcquisitionType.CONTINUOUS,  # CONTINUOUS, # can also limit the number of points
            )
            # import pdb; pdb.set_trace()
            self.laser_ctrl_task.write(laser_values, auto_start=False, timeout=timeout)

        laser_init(device, timeout)

        return

    def finalize(self, device, channel, PS_clk_channel, sampling_rate, timeout,
                 repetitions, laserpower_start_stop_iter, heat_on_off_array, time_per_scan,
                 sbChoice_MHz_big, sbChoice_MHz_small, sb_MHz_2fq, quasilinear_slope,
                 two_freq, odmr_frequency, rf_amplitude, searchZXY,
                 warm_and_cool_scans, clock_time, mwPulseTime,
                 pos_initial, z_cycle, track_z, do_not_run_feedback, data_download):

        # (self, device, channel, PS_clk_channel, sampling_rate, timeout,
        # repetitions, laserpower_start_stop_iter, heat_on_off_array, time_per_scan,
        # sbChoice_MHz_big, sbChoice_MHz_small, sb_MHz_2fq, useSbList,
        # two_freq, odmr_frequency, rf_amplitude, searchZXY,
        # warm_and_cool_scans, clock_time, mwPulseTime,
        # pos_initial, z_cycle, track_z, data_download):
        # # # super().finalize(pos_initial, device, channel, PS_clk_channel,
        # # # mwPulseTime, sampling_rate,data_download)

        self.urixyz.daq_controller.ao_motion_task.stop()
        self.laser_ctrl_task.close()
        self.urixyz.daq_controller.collect_task.stop()

        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.streamer.Pulser.reset()

        ## control if laser turns on or off.
        ## if laser turns off, you must restart with swabian gui, not NSpyre.
        ## saves the data to an excel sheet.
        ''' note: saving this data might cause an error, because the self.acquires do not have continuous indexes.'''
        if data_download:
            print("name of spyrelet is", self.name)
            save_excel(self.name)
            print('data downloaded B)')
        ## experiment finishes
        print("FINALIZE")
        return

    'fitting_functions'

    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        return a * np.exp(-np.square((xs - x) / width)) + b

    '''graph time!'''

    @PlotFormatInit(LinePlotWidget, ['drift'])
    def init_format(plot):
        plot.xlabel = 'iterations (sweeps)'
        plot.ylabel = 'NV center (um)'

    @PlotFormatInit(LinePlotWidget, ['heating'])
    def init_format(p):
        p.xlabel = 'laser power (mW)'
        p.ylabel = 'temperature difference recorded (K)'

    # @PlotFormatUpdate(LinePlotWidget, ['no_line_plot'])
    # def update_format(p, df, cache):
    # for item in p.plot_item.listDataItems():
    # item.setPen(color=(0,0,0,0), width=5)

    @Plot1D
    def temp_2pt_change(df, cache):
        df_rep = df.groupby(by=['lp_repetitions'])
        print(df)
        print(df_rep)
        # datag = df[['lp_repetitions','new_odmr_center', 'laserPower', 'hot_or_cold', 'lp_idx', 'tempChange', 'original_odmr_center']]
        dDdT = 74.2  # 'kHz/K

        plot_return = {}
        # print(df)
        # print(datag)
        # print(df_rep)
        print(df_rep.new_odmr_center)
        print(df_rep.original_odmr_center)
        for i in range(int(df.lp_repetitions.max() + 1)):
            temp = (df_rep.new_odmr_center - df_rep.original_odmr_center) / dDdT
            hot_temp = temp[temp['hot_or_cold'] == 'heating up'];
            cold_temp = temp[temp['hot_or_cold'] == 'cooling_down']
            print(temp)
            # print(tempChange)
            label_hot = 'hot temp' + str(i)
            label_cold = 'cold temp' + str(i)
            plot_return = {label_hot: [df_rep.laserPower['hot_or_cold'], hot_temp],
                           label_cold: [df_rep.laserPower['cooling down'], cold_temp]}
        return plot_return

    @Plot1D
    def temp_2pt_change_avg(df, cache):
        # # #datag = df[['lp_repetitions','new_odmr_center', 'laserPower', 'hot_or_cold', 'lp_idx', 'tempChange', 'original_odmr_center']]
        # # dDdT = 74.2 #'kHz/K
        # # df_rep = df.groupby(by=['lp_repetitions']).mean()
        # # print('\n\nThe new odmr center:', df_rep.new_odmr_center)
        # # print('\n\nThe original odmr center:', df_rep.original_odmr_center)
        # # temp = ((df_rep.new_odmr_center - df_rep.original_odmr_center)/dDdT)#.mean()
        # # hot_temp = temp['heating up']; cold_temp = temp['cooling down']
        # # #print(temp)
        # # #print(tempChange)
        # # label_hot = 'hot temp avg'
        # # label_cold = 'cold temp avg'
        # # return  {label_hot: [df_rep.laserPower['heating_up'], hot_temp],
        # # label_cold: [df_rep.laserPower['cooling down'], cold_temp]}

        import pandas as pd
        # datag = df[['lp_repetitions','new_odmr_center', 'laserPower', 'hot_or_cold', 'lp_idx', 'tempChange', 'original_odmr_center']]
        dDdT = 74.2  # 'kHz/K
        multidx = pd.MultiIndex.from_frame(df[['laserPower', 'lp_repetitions']])
        print(multidx)
        print(multidx[1::2])
        dataf = pd.DataFrame(np.array(df[['tempChange', 'new_odmr_center', 'original_odmr_center']]),
                             index=multidx, columns=['tempChange_inst', 'new_odmr_center', 'original_odmr_center'])
        print(df['tempChange'])
        print(dataf[1::2])
        df_group = df.groupby(by=['laserPower'])
        df_rep = df.groupby(by=['laserPower']).mean()
        print('\n\nThe new odmr center:', df_rep.new_odmr_center)
        print('\n\nThe original odmr center:', df_rep.original_odmr_center)
        temp = ((df_rep.new_odmr_center - df_rep.original_odmr_center) / dDdT)
        print(temp)
        print(df_rep.tempChange)
        # print(df_group['hot_or_cold'][1])
        # df_laser = df_group.groupby(by=['laserPower'])
        # print(df_laser)
        print(df_group.mean())
        hot_temp = temp['heating up'];
        cold_temp = temp['cooling down']
        # print(temp)
        # print(tempChange)
        label_hot = 'hot temp avg'
        label_cold = 'cold temp avg'
        return {label_hot: [df_rep.laserPower['heating_up'], hot_temp],
                label_cold: [df_rep.laserPower['cooling down'], cold_temp]}

    @Plot1D
    def drift(df, cache):
        tracking_data = df[df.tracking_rep == df.tracking_rep.max()]
        # print('right now, we are failing to address the secondary index of pos_data_um')
        x_drift = tracking_data.x_data_um  # pos_data_um[:][0] + tracking_data.driftX_um
        y_drift = tracking_data.y_data_um  # pos_data_um[:][1] + tracking_data.driftY_um
        z_drift = tracking_data.z_data_um  # pos_data_um[:][2] + tracking_data.driftZ_um
        sweep_number = tracking_data.iteration + tracking_data.iteration.max() * tracking_data.laserPowerIdx
        return {'x tracking': [sweep_number, x_drift], 'y tracking': [sweep_number, y_drift],
                'z_tracking': [sweep_number, z_drift]}

    @Plot1D
    def heating(df, cache):
        # # recent_data = df[df.rep_idx == df.rep_idx.max()]
        # # latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        # # return {'sig': [latest_data.f, latest_data.sig],
        # # 'bg': [latest_data.f, latest_data.bg]}
        # tempRising

        # laser powers: laserPower
        # tempFalling
        frame = df[df.lp_repetitions == df.lp_repetitions.max()]
        return {'Heating': [frame.laserPower, frame.tempRising],
                'Cooling': [frame.laserPower, frame.tempFalling]}

    @Plot1D
    def avg_heating(df, cache):
        # # recent_data = df[df.rep_idx == df.rep_idx.max()]
        # # latest_data = recent_data[recent_data.sweep_idx == recent_data.sweep_idx.max()]
        # # return {'sig': [latest_data.f, latest_data.sig],
        # # 'bg': [latest_data.f, latest_data.bg]}
        # tempRising
        grouping = df.groupby('laserPower')
        heatings = grouping.tempRising
        coolings = grouping.tempFalling
        avg_heating = heatings.mean()
        avg_cooling = coolings.mean()
        return {'Heating': [avg_heating.index, avg_heating],
                'Cooling': [avg_cooling.index, avg_cooling]}
        # # rep_df = df[df.rep_idx == 0]
        # # grouped = rep_df.groupby('f')
        # # sigs = grouped.sig
        # # bgs = grouped.bg
        # # sigs_averaged = sigs.mean()
        # # bgs_averaged = bgs.mean()
        # # return {'sig': [sigs_averaged.index, sigs_averaged],
        # # 'bg': [bgs_averaged.index, bgs_averaged]}

    @Plot1D
    def cumDrift(df, cache):
        tracking_group = df
        x_drift = tracking_group.x_data_um
        y_drift = tracking_group.y_data_um
        z_drift = tracking_group.z_data_um
        sweep_number = tracking_group.iteration + \
                       tracking_group.iteration.max() * tracking_group.laserPowerIdx + \
                       tracking_group.iteration.max() * tracking_group.laserPowerIdx.max() * tracking_group.tracking_rep

        return {'x tracking': [sweep_number, x_drift], 'y tracking': [sweep_number, y_drift],
                'z_tracking': [sweep_number, z_drift]}

        # # # # else:
        # # # # # # p0 = [np.max(tracking_y), y_center, y_center, .4, 0, np.max(tracking_y), 0]
        # # # # # # try:
        # # # # # # popt, pcov = optimize.curve_fit(self.gaussparab, y_track_steps, tracking_y, p0=p0)
        # # # # # # y_fitted = self.gaussparab(y_track_steps, *popt)
        # # # # # # y_center_fit = popt[1]
        # # # # # # if np.min(y_track_steps) < y_center_fit < np.max(y_track_steps):
        # # # # # # if popt[0] < 0:
        # # # # # # print("negative fit")
        # # # # # # elif np.abs(Q_(y_center_fit,'um') - y_center) < search[2]:
        # # # # # # self.drift[2] = Q_(y_center_fit,'um') - y_center
        # # # # # # y_center = Q_(y_center_fit,'um')
        # # # # # # print('y_center from fit:', y_center)
        # # # # # # else:
        # # # # # # print("Y drift limit reached. Setting to previous value.")
        # # # # # # else:
        # # # # # # print('Optimum Y out of scan range. Setting to previous value.')
        # # # # # # except RuntimeError:
        # # # # # # print('no y fit')
        # # # # # # y_fitted = self.gaussparab(y_track_steps, *p0)
        # # # # # # y_center = p0[1]

    """
    
        "z scan "
        
        'the z stuff is not added properly yet. this will be the next thing I do.'
        #import pdb; pdb.set_trace()
        #import pdb; pdb.set_trace()
        
        if track_z and (  (sweep + lp_idx * (self.heating_scans + self.cooling_scans)  )   % z_cycle == 0):    
            z_time = time.time()
            z_steps = np.linspace(z_center - search[0], z_center + search[0], self.buffer_size)
            'prepare the tasks. since the data collection is uncoupled from the analog movement, we want them to start as simultaenously as possible'
            #import pdb; pdb.set_trace()
            #import pdb; pdb.set_trace()
            self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                                   {'x': x_center,'y': y_center,'z': z_steps[0]},
                                   {'x': x_center,'y': y_center,'z': z_steps[-1]},
                                   self.buffer_size, pts_per_step = 0)
                                   
            '''
            fix combo with hs_prepare and hs_linescan
            '''
            'start the pulse streamer and the task close to simultaneously'
            self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
            print('finish stream')
            'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
            z_scan_data = self.urixyz.daq_controller.hs_linescan()
            self.streamer.Pulser.reset()
            print('time for z read:', time.time() - z_time)
            ###### ###### in case I want to use the whole data without selecting the bins that I like most.
            ###### ###### odmr_data_wnoise = [np.sum(scan_data[i]) for i, dummy in enumerate(range(8))]
            # # # # # # # for i,data1 in enumerate(scan_data):
                # # # # # # # for j,data2 in enumerate(scan_data.shape[0]):
                    # # # # # # # z_scan_data[i][j] = np.sum(scan_data[i,j,:])     
            'this data should now have dimension i,j, where i is 1-8 and j is the run_ct.'
            
            'the odmr data will be interpreted in x_data, and the spatial tracking data will be interpreted in tracking_x'
            
            #import pdb; pdb.set_trace()
            z_data = np.array([z_scan_data[0] + z_scan_data[7], z_scan_data[1] + z_scan_data[6], z_scan_data[2] + z_scan_data[5],z_scan_data[3] + z_scan_data[4]])
            tracking_z = np.sum(rpyc.utils.classic.obtain(z_scan_data), axis=0)
            #import pdb; pdb.set_trace()
            self.hot_z_data.append(z_data)
            '''does this make sense?????'''
            'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
            z_track_steps = np.linspace(z_center - search[0], z_center + search[0], len(tracking_z)).to('um').m
            #import pdb; pdb.set_trace()
            if self.usegaussian:
                p0 = [np.max(tracking_z), z_track_steps[np.argmax(tracking_z)], .4, np.min(tracking_z)]
                try:
                    popt, pcov = optimize.curve_fit(self.gaussian, z_track_steps, tracking_z, p0=p0)
                    z_fitted = self.gaussian(z_track_steps, *popt)
                    z_center_fit = popt[1]
                    zbackground = self.gaussian(z_track_steps[0], *popt)
                    zpeak = self.gaussian(z_center_fit,*popt)
                    print('z peak, background, SBR:' + str(zpeak) +','+ str(zbackground)+','+str(zpeak/zbackground - 1))
                    if np.min(z_track_steps) < z_center_fit < np.max(z_track_steps):
                        #import pdb; pdb.set_trace()
                        if popt[0] < 0:
                            print("negative fit")
                        
                        elif np.abs(Q_(z_center_fit,'um') - z_center) < search[0]:
                            self.drift[0] = Q_(z_center_fit,'um') - z_center
                            z_center = Q_(z_center_fit,'um')
                            
                            print('z_center from fit:', z_center)
                        else:
                            print("Z drift limit reached. Setting to previous value.")
                    else:
                        print('Optimum Z out of scan range. Setting to previous value.')
                except RuntimeError:
                    print('no z fit')
                    #z_fitted = self.gaussian(z_track_steps, *p0)
                    z_center = z_center
                
            

            #self.urixyz.daq_controller.position['x'] = Q_(float(x_center),'um')
            'we move to the new position'
            self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        
        "x scan"
        
        #x_start_time = time.time()
        x_steps = np.linspace(x_center - search[1], x_center + search[1], self.buffer_size)
        'prepare the tasks. since the data collection is uncoupled from the analog movement, we want them to start as simultaenously as possible'
        self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                               {'x': x_steps[0],'y': y_center,'z': z_center},
                               {'x': x_steps[-1],'y': y_center,'z': z_center},
                               self.buffer_size, pts_per_step = 0)
        'start the pulse streamer and the task close to simultaneously'
        self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
        #import pdb; pdb.set_trace()
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        x_scan_data = self.urixyz.daq_controller.hs_linescan()            
        self.streamer.Pulser.reset()
        #x_stream_time = time.time()
        #print('stream_time w/ data collection:', x_stream_time - x_start_time)
        # 'this data should now have dimension i,j, where the k elements should be summed together.'
        # for i,data1 in enumerate(scan_data):
            # for j,data2 in enumerate(scan_data.shape[0]):
                # x_scan_data[i][j] = np.sum(scan_data[i,j,:])     
        'the odmr data will be interpreted in x_data, and the spatial tracking data will be interpreted in tracking_x'
        'x_data has shape of freq 1, freq 4, freq 2, freq 3'
        x_data = np.array([x_scan_data[0] + x_scan_data[7], x_scan_data[1] + x_scan_data[6], x_scan_data[2] + x_scan_data[5],x_scan_data[3] + x_scan_data[4]])
        #import pdb; pdb.set_trace()
        tracking_x = np.sum(rpyc.utils.classic.obtain(x_scan_data), axis=0) #[sum(x_scan_data[:, i]) for i in range(x_scan_data.shape[1])]
        #import pdb; pdb.set_trace()
        self.hot_x_data.append(x_data)
        '''does this make sense?????'''
        'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
        x_track_steps = np.linspace(x_center - search[1], x_center + search[1], len(tracking_x)).to('um').m
        #x_steps = x_steps.to('um').m
        if self.usegaussian:
            p0 = [np.max(tracking_x), x_track_steps[np.argmax(tracking_x)], .4, np.min(tracking_x)]
            try:
                #import pdb; pdb.set_trace()
                popt, pcov = optimize.curve_fit(self.gaussian, x_track_steps, tracking_x, p0=p0)
                x_fitted = self.gaussian(x_track_steps, *popt)
                x_center_fit = popt[1]
                xbackground = self.gaussian(x_track_steps[0], *popt)
                xpeak = self.gaussian(x_center_fit,*popt)
                print('x peak, background, SBR:' + str(xpeak) +','+ str(xbackground)+','+str(xpeak/xbackground - 1))
                if np.min(x_track_steps) < x_center_fit < np.max(x_track_steps):
                    if popt[0] < 0:
                        print("negative fit")
                    elif np.abs(Q_(x_center_fit,'um') - x_center) < search[1]:
                        self.drift[1] = Q_(x_center_fit,'um') - x_center
                        x_center = Q_(x_center_fit,'um')
                        
                        print('x_center from fit:', x_center)
                    else:
                        print("X drift limit reached. Setting to previous value.")
                else:
                    print('Optimum X out of scan range. Setting to previous value.')
            except RuntimeError:
                print('no x fit')
                
                #import pdb; pdb.set_trace()
                'for right now, self.gaussian does not work because all the data are zeros.'
                'this means it is commented out. this needs to be uncommented to work properly.'
                #x_fitted = self.gaussian(x_track_steps, *p0)
                x_center = x_center
            
        

        #self.urixyz.daq_controller.position['x'] = Q_(float(x_center),'um')
        'we move to the new position'
        #print('new position:', 'x:', x_center, 'y:', y_center, 'z:', z_center)
        self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        #print('data_manipulation time:', time.time() - x_stream_time)
        
        "y scan"
        
        y_steps = np.linspace(y_center - search[2], y_center + search[2], self.buffer_size)
        self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                               {'x': x_center,'y': y_steps[0],'z': z_center},
                               {'x': x_center,'y': y_steps[-1],'z': z_center},
                               self.buffer_size, pts_per_step = 0)
        self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
        y_scan_data = self.urixyz.daq_controller.hs_linescan()
        self.streamer.Pulser.reset()
        # for i,data1 in enumerate(scan_data):
            # for j,data2 in enumerate(scan_data.shape[0]):
                # y_scan_data[i][j] = np.sum(scan_data[i,j])
        y_data = np.array([y_scan_data[0] + y_scan_data[7], y_scan_data[1] + y_scan_data[6], y_scan_data[2] + y_scan_data[5], y_scan_data[3] + y_scan_data[4]])
        #import pdb; pdb.set_trace()
        tracking_y = np.sum(rpyc.utils.classic.obtain(y_scan_data), axis=0) #[sum(y_scan_data[:, i]) for i in range(y_scan_data.shape[1])]
        #import pdb; pdb.set_trace()
        self.hot_y_data.append(y_data)
        '''does this make sense?????'''
        'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
        '''does this make sense'''
        y_track_steps = np.linspace(y_center - search[2], y_center + search[2], len(tracking_y)).to('um').m
        if self.usegaussian:
            p0 = [np.max(tracking_y), y_track_steps[np.argmax(tracking_y)], .4, np.min(tracking_y)]
            try:
                popt, pcov = optimize.curve_fit(self.gaussian, y_track_steps, tracking_y, p0=p0)
                y_fitted = self.gaussian(y_track_steps, *popt)
                y_center_fit = popt[1]
                ybackground = self.gaussian(y_track_steps[0], *popt)
                ypeak = self.gaussian(y_center_fit,*popt)
                print('y peak, background, SBR:' + str(ypeak) +','+ str(ybackground)+','+str(ypeak/ybackground - 1))
                #import pdb; pdb.set_trace()
                if np.min(y_track_steps) < y_center_fit < np.max(y_track_steps):
                    if popt[0] < 0:
                        print("negative fit")
                    elif np.abs(Q_(y_center_fit,'um') - y_center) < search[2]:
                        self.drift[2] = Q_(y_center_fit,'um') - y_center
                        y_center = Q_(y_center_fit,'um')
                        print('y_center from fit:', y_center)
                    else:
                        print("Y drift limit reached. Setting to previous value.")
                else:
                    print('Optimum Y out of scan range. Setting to previous value.')
            except RuntimeError:
                print('no y fit')
                'once again, commenting out the y fitting parameter'
                #y_fitted = self.gaussian(y_track_steps, *p0)
                y_center = y_center
            
        
                
        #self.urixyz.daq_controller.position['y'] = Q_(float(y_center),'um')
        #print('new position:', 'x:', x_center, 'y:', y_center, 'z:', z_center)
        #import pdb; pdb.set_trace()
        self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        for i, num in enumerate(search):
            search[i] *= 0.9 if abs(self.drift[i]) < (2/5 * search[i]) else 1.2 if abs(self.drift[i]) > (7/10 * search[i]) else 1
        #import pdb; pdb.set_trace()
        search_um = search.to('um').m
        
        self.acquire({
            'laserPowerIdx': lp_idx,
            'iteration': sweep,
            'driftX_um': self.drift[1].to('um').m,
            'driftY_um': self.drift[2].to('um').m,
            'driftZ_um': self.drift[0].to('um').m,
            'searchZXY_um': list(search_um),
            'x_data_um': x_center,
            'y_data_um': y_center,
            'z_data_um': z_center,
            #'pos_data_um' : [self.position[0].to('um').m, self.position[1].to('um').m, self.position[2].to('um').m],
            'tracking_rep' : rep,
            }),
    self.laser_ctrl_task.stop()   
    #print('heating_scan takes:', time.time() - start_time, 'seconds')
    for scan in range(self.cooling_scans):
        
        "z scan"
        
        'the z stuff is not added properly yet. this will be the next thing I do.'
        #import pdb; pdb.set_trace()
        #import pdb; pdb.set_trace()
        
        if track_z and (  (scan + lp_idx * (self.heating_scans + self.cooling_scans) + sweep  )   % z_cycle == 0):    
            z_time = time.time()
            z_steps = np.linspace(z_center - search[0], z_center + search[0], self.buffer_size)
            'prepare the tasks. since the data collection is uncoupled from the analog movement, we want them to start as simultaenously as possible'
            #import pdb; pdb.set_trace()
            #import pdb; pdb.set_trace()
            self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                                   {'x': x_center,'y': y_center,'z': z_steps[0]},
                                   {'x': x_center,'y': y_center,'z': z_steps[-1]},
                                   self.buffer_size, pts_per_step = 0)
                                   
            '''
            fix combo with hs_prepare and hs_linescan
            '''
            'start the pulse streamer and the task close to simultaneously'
            self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
            print('finish stream')
            'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
            z_scan_data = self.urixyz.daq_controller.hs_linescan()
            self.streamer.Pulser.reset()
            print('time for z read:', time.time() - z_time)
            ###### ###### in case I want to use the whole data without selecting the bins that I like most.
            ###### ###### odmr_data_wnoise = [np.sum(scan_data[i]) for i, dummy in enumerate(range(8))]
            # # # # # # # for i,data1 in enumerate(scan_data):
                # # # # # # # for j,data2 in enumerate(scan_data.shape[0]):
                    # # # # # # # z_scan_data[i][j] = np.sum(scan_data[i,j,:])     
            'this data should now have dimension i,j, where i is 1-8 and j is the run_ct.'
            
            'the odmr data will be interpreted in x_data, and the spatial tracking data will be interpreted in tracking_x'
            
            #import pdb; pdb.set_trace()
            z_data = np.array([z_scan_data[0] + z_scan_data[7], z_scan_data[1] + z_scan_data[6], z_scan_data[2] + z_scan_data[5],z_scan_data[3] + z_scan_data[4]])
            tracking_z = np.sum(rpyc.utils.classic.obtain(z_scan_data), axis=0)      #tracking_z = [np.sum(z_scan_data[:, i]) for i,dummy in range(z_scan_data.axis[1])]
            self.cold_z_data.append(z_data)
            '''does this make sense?????'''
            'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
            z_track_steps = np.linspace(z_center - search[0], z_center + search[0], len(tracking_z)).to('um').m
            #import pdb; pdb.set_trace()
            if self.usegaussian:
                p0 = [np.max(tracking_z), z_track_steps[np.argmax(tracking_z)], .4, np.min(tracking_z)]
                try:
                    popt, pcov = optimize.curve_fit(self.gaussian, z_track_steps, tracking_z, p0=p0)
                    z_fitted = self.gaussian(z_track_steps, *popt)
                    z_center_fit = popt[1]
                    zbackground = self.gaussian(z_track_steps[0], *popt)
                    zpeak = self.gaussian(z_center_fit,*popt)
                    print('z peak, background, SBR:' + str(zpeak) +','+ str(zbackground)+','+str(zpeak/zbackground - 1))
                    if np.min(z_track_steps) < z_center_fit < np.max(z_track_steps):
                        #import pdb; pdb.set_trace()
                        if popt[0] < 0:
                            print("negative fit")
                        
                        elif np.abs(Q_(z_center_fit,'um') - z_center) < search[0]:
                            self.drift[0] = Q_(z_center_fit,'um') - z_center
                            z_center = Q_(z_center_fit,'um')
                            print('z_center from fit:', z_center)
                        else:
                            print("Z drift limit reached. Setting to previous value.")
                    else:
                        print('Optimum Z out of scan range. Setting to previous value.')
                except RuntimeError:
                    print('no z fit')
                    #z_fitted = self.gaussian(z_track_steps, *p0)
                    z_center = z_center
                
            

            #self.urixyz.daq_controller.position['x'] = Q_(float(x_center),'um')
            'we move to the new position'
            self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        "x scan"
        #x_start_time = time.time()
        x_steps = np.linspace(x_center - search[1], x_center + search[1], self.buffer_size)
        'prepare the tasks. since the data collection is uncoupled from the analog movement, we want them to start as simultaenously as possible'
        self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                               {'x': x_steps[0],'y': y_center,'z': z_center},
                               {'x': x_steps[-1],'y': y_center,'z': z_center},
                               self.buffer_size, pts_per_step = 0)
        'start the pulse streamer and the task close to simultaneously'
        self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
        #import pdb; pdb.set_trace()
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        x_scan_data = self.urixyz.daq_controller.hs_linescan()            
        self.streamer.Pulser.reset()
        #x_stream_time = time.time()
        #print('stream_time w/ data collection:', x_stream_time - x_start_time)
        # 'this data should now have dimension i,j, where the k elements should be summed together.'
        # for i,data1 in enumerate(scan_data):
            # for j,data2 in enumerate(scan_data.shape[0]):
                # x_scan_data[i][j] = np.sum(scan_data[i,j,:])     
        'the odmr data will be interpreted in x_data, and the spatial tracking data will be interpreted in tracking_x'
        'x_data has shape of freq 1, freq 4, freq 2, freq 3'
        x_data = np.array([x_scan_data[0] + x_scan_data[7], x_scan_data[1] + x_scan_data[6], x_scan_data[2] + x_scan_data[5],x_scan_data[3] + x_scan_data[4]])
        #import pdb; pdb.set_trace()
        tracking_x = np.sum(rpyc.utils.classic.obtain(x_scan_data), axis=0) #[sum(x_scan_data[:, i]) for i in range(x_scan_data.shape[1])]
        #import pdb; pdb.set_trace()
        self.cold_x_data.append(x_data)
        '''does this make sense?????'''
        'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
        x_track_steps = np.linspace(x_center - search[1], x_center + search[1], len(tracking_x)).to('um').m
        #x_steps = x_steps.to('um').m
        if self.usegaussian:
            p0 = [np.max(tracking_x), x_track_steps[np.argmax(tracking_x)], .4, np.min(tracking_x)]
            try:
                #import pdb; pdb.set_trace()
                popt, pcov = optimize.curve_fit(self.gaussian, x_track_steps, tracking_x, p0=p0)
                x_fitted = self.gaussian(x_track_steps, *popt)
                x_center_fit = popt[1]
                xbackground = self.gaussian(x_track_steps[0], *popt)
                xpeak = self.gaussian(x_center_fit,*popt)
                print('x peak, background, SBR:' + str(xpeak) +','+ str(xbackground)+','+str(xpeak/xbackground - 1))
                if np.min(x_track_steps) < x_center_fit < np.max(x_track_steps):
                    if popt[0] < 0:
                        print("negative fit")
                    elif np.abs(Q_(x_center_fit,'um') - x_center) < search[1]:
                        self.drift[1] = Q_(x_center_fit,'um') - x_center
                        x_center = Q_(x_center_fit,'um')
                        print('x_center from fit:', x_center)
                    else:
                        print("X drift limit reached. Setting to previous value.")
                else:
                    print('Optimum X out of scan range. Setting to previous value.')
            except RuntimeError:
                print('no x fit')
                
                #import pdb; pdb.set_trace()
                'for right now, self.gaussian does not work because all the data are zeros.'
                'this means it is commented out. this needs to be uncommented to work properly.'
                #x_fitted = self.gaussian(x_track_steps, *p0)
                x_center = x_center
            
        

        #self.urixyz.daq_controller.position['x'] = Q_(float(x_center),'um')
        'we move to the new position'
        #print('new position:', 'x:', x_center, 'y:', y_center, 'z:', z_center)
        self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        #print('data_manipulation time:', time.time() - x_stream_time)
        
        "y scan"
        
        y_steps = np.linspace(y_center - search[2], y_center + search[2], self.buffer_size)
        self.urixyz.daq_controller.hs_prepare(self.buffer_size, PS_clk_channel, channel,
                               {'x': x_center,'y': y_steps[0],'z': z_center},
                               {'x': x_center,'y': y_steps[-1],'z': z_center},
                               self.buffer_size, pts_per_step = 0)
        self.streamer.Pulser.stream(self.seqTempReadout, self.run_ct)
        y_scan_data = self.urixyz.daq_controller.hs_linescan()
        self.streamer.Pulser.reset()
        # for i,data1 in enumerate(scan_data):
            # for j,data2 in enumerate(scan_data.shape[0]):
                # y_scan_data[i][j] = np.sum(scan_data[i,j])
        y_data = np.array([y_scan_data[0] + y_scan_data[7], y_scan_data[1] + y_scan_data[6], y_scan_data[2] + y_scan_data[5], y_scan_data[3] + y_scan_data[4]])
        #import pdb; pdb.set_trace()
        tracking_y = np.sum(rpyc.utils.classic.obtain(y_scan_data), axis=0) #[sum(y_scan_data[:, i]) for i in range(y_scan_data.shape[1])]
        #import pdb; pdb.set_trace()
        self.cold_y_data.append(y_data)
        '''does this make sense?????'''
        'now I do a gaussian fit, like in our spatial feedback software, to determine where the particle is.'
        '''does this make sense'''
        y_track_steps = np.linspace(y_center - search[2], y_center + search[2], len(tracking_y)).to('um').m
        if self.usegaussian:
            p0 = [np.max(tracking_y), y_track_steps[np.argmax(tracking_y)], .4, np.min(tracking_y)]
            try:
                popt, pcov = optimize.curve_fit(self.gaussian, y_track_steps, tracking_y, p0=p0)
                y_fitted = self.gaussian(y_track_steps, *popt)
                y_center_fit = popt[1]
                ybackground = self.gaussian(y_track_steps[0], *popt)
                ypeak = self.gaussian(y_center_fit,*popt)
                print('y peak, background, SBR:' + str(ypeak) +','+ str(ybackground)+','+str(ypeak/ybackground - 1))
                #import pdb; pdb.set_trace()
                if np.min(y_track_steps) < y_center_fit < np.max(y_track_steps):
                    if popt[0] < 0:
                        print("negative fit")
                    elif np.abs(Q_(y_center_fit,'um') - y_center) < search[2]:
                        self.drift[2] = Q_(y_center_fit,'um') - y_center
                        y_center = Q_(y_center_fit,'um')
                        print('y_center from fit:', y_center)
                    else:
                        print("Y drift limit reached. Setting to previous value.")
                else:
                    print('Optimum Y out of scan range. Setting to previous value.')
            except RuntimeError:
                print('no y fit')
                'once again, commenting out the y fitting parameter'
                #y_fitted = self.gaussian(y_track_steps, *p0)
                y_center = y_center
            
        # # 
                
        #self.urixyz.daq_controller.position['y'] = Q_(float(y_center),'um')
        #print('new position:', 'x:', x_center, 'y:', y_center, 'z:', z_center)
        self.urixyz.daq_controller.move({'x': x_center, 'y': y_center, 'z': z_center})
        for i, num in enumerate(search):
            search[i] *= 0.9 if abs(self.drift[i]) < (2/5 * search[i]) else 1.2 if abs(self.drift[i]) > (7/10 * search[i]) else 1
        #import pdb; pdb.set_trace()
        search_um = search.to('um').m
        self.acquire({
            'laserPowerIdx': lp_idx,
            'iteration': scan + sweep,
            'driftX_um': self.drift[1].to('um').m,
            'driftY_um': self.drift[2].to('um').m,
            'driftZ_um': self.drift[0].to('um').m,
            'searchZXY_um': list(search_um),
            'x_data_um': x_center.to('um').m,
            'y_data_um': y_center.to('um').m,
            'z_data_um': z_center.to('um').m,
            #'pos_data_um' : [self.position[0].to('um').m, self.position[1].to('um').m, self.position[2].to('um').m],
            'tracking_rep' : rep,
            }),
    #self.laser_ctrl_task.stop()   
    
    dDdT = -74.2 #'kHz/K'
    
    #fluo_1h, fluo_2h, fluo_3h, fluo_4h = sum(self.hot_x_data[0]), sum(self.hot_x_data[2]), sum(self.hot_x_data[3]), sum(self.hot_x_data[1])   
    #can minimize code by writing a dictionary
    
    def temp_data(matrix):
        return np.sum(matrix, axis = 1)
        
    fluo_h_x = [temp_data(buffer) for buffer in self.hot_x_data]
    fluo_h_y = [temp_data(buffer) for buffer in self.hot_y_data]
    fluo_h_z = [temp_data(buffer) for buffer in self.hot_z_data]
    for i in range(len(fluo_h_x) - len(fluo_h_z)): fluo_h_z.append(np.zeros([4]))
    fluo_h = np.array(fluo_h_x) + np.array(fluo_h_y) + np.array(fluo_h_z)
    
    # fluo_h_x = [temp_data(self.hot_x_data) for h in range(len(self.hot_x_data))]
    # fluo_h_y = [np.sum(self.hot_y_data[:][index], axis = 1) for h in range(4)]
    # fluo_h_z = [np.sum(self.hot_z_data[:][index], axis = 1) for h in range(4)]
    fluo_c_x = [temp_data(buffer) for buffer in self.cold_x_data]
    fluo_c_y = [temp_data(buffer) for buffer in self.cold_y_data]
    fluo_c_z = [temp_data(buffer) for buffer in self.cold_z_data]
    for i in range(len(fluo_c_x) - len(fluo_c_z)): fluo_c_z.append(np.zeros([4]))
    fluo_c = np.array(fluo_c_x) + np.array(fluo_c_y) + np.array(fluo_c_z)
    
    #fluo_c = [list_cold_data(c) for c in range(4)]
    
    fh = np.sum(fluo_h, axis = 0)
    fc = np.sum(fluo_c, axis = 0)
    
    #import pdb; pdb.set_trace()
    temp_hot_change = self.delomega / dDdT * (fh[0] + fh[1] - fh[2] - fh[3])/(fh[0] - fh[1] + fh[3] - fh[2])
    temp_cold_change = self.delomega / dDdT * (fc[0] + fc[1] - fc[2] - fc[3])/(fc[0] - fc[1] + fc[3] - fc[2])
    
    self.acquire({
        'lp_repetitions': rep,
        'laserPower': lp.to('mW').m,
        'heat_data': fluo_h,
        'cooling_data': fluo_c,
        'tempRising': temp_hot_change,
        'tempFalling': temp_cold_change,
    })
    
    
    
"""
