# std
import numpy as np
from scipy import optimize
import time
from itertools import cycle
from itertools import count
import logging
import scipy.optimize as sciOP
import scipy.interpolate as sciIP
from math import ceil
from nspyre import InstrumentManager
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue
import collections
from collections import OrderedDict

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader
from experiments.spatialfb import SpatialFeedback
from nspyre import InstrumentManager, DataSource, StreamingList
import math
import rpyc.utils.classic

from experiments.advancedtracking import AdvancedTracking


# nspyre


#from lantz.drivers.ni.ni_motion_controller import NIDAQMotionController

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)







class I1I2():
    """
    Shivam: This class is to find the quasilinear slope (that will be inputted into 2 point measurement experiments)
    It has an option to do stationary measurements with intermittent newspaceFB tracking or to do continuous tracking
    while taking measurements (as would be needed inside cell samples)
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
        _logger.info('Created PlaneScan instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed PlaneScan instance.')


    

    def i1i2(self, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                   sweeps, frequencies, slope_range, sideband_frequency, 
                   read_timeout, sweeps_until_feedback, z_feedback_every, 
                   xyz_step_nm, shrink_every_x_iter, starting_point, 
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance, changing_search, search_PID, 
                   search_integral_history, spot_size, advanced_tracking, 
                   diffusion_constant, data_download, dataset, tracking_dataset):
        with InstrumentManager() as mgr, DataSource(dataset) as data_source, DataSource(tracking_dataset) as tracking_data_source:
            self.initialize(mgr, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                    frequencies, slope_range, sideband_frequency,
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance,  search_PID, 
                   spot_size, advanced_tracking, 
                   diffusion_constant)
            freqs, sb_freq = self.process_frequencies(frequencies, sideband_frequency)
            print('main take me off your feet?')
            
            I1_sweeps=StreamingList()
            I2_sweeps=StreamingList()
            I1_tracking=StreamingList()
            I2_tracking=StreamingList()
            # Shivam: The following is the classical case where we are not tracking
            # while taking I1 and I2 data
            n_freqs=len(freqs)
            start_t= time.time()
            if not continuous_tracking:
                
                for sweep in range(sweeps):
                    I1_data=np.empty(n_freqs)
                    I2_data=np.empty(n_freqs)
                    I1_sweeps.append(np.stack([freqs, I1_data]))
                    I2_sweeps.append(np.stack([freqs, I2_data]))
                    print('before feedback')
                    self.feedback(sweep, sweeps_until_feedback, z_feedback_every, xyz_step_nm, shrink_every_x_iter,starting_point)
                    for f in freqs:
                        print("Frequency value is " + str(f))
                        # time_start = time.time()
                        #import pdb; pdb.set_trace()
                        
                        mgr.sg.set_frequency(f)
                        print('frequency:', f)
                        # import pdb; pdb.set_trace()

                        output_buffer = self.odmr_read(mgr, self.buffer, self.APD_task, self.APD_reader, self.sequence,
                                                    self.stream_count, read_timeout)
                        data_I1, data_I2 = self.odmr_math(output_buffer)
                        I1_sweeps[-1][1][f] = data_I1
                        I1_sweeps.updated_item(-1)
                        I2_sweeps[-1][1][f] = data_I2
                        I2_sweeps.updated_item(-1)
                        I1_tracking.append(np.array([np.array(time.time()-start_t), np.array([data_I1])]))
                        I1_tracking.updated_item(-1)
                        I2_tracking.append(np.array([np.array(time.time()-start_t), np.array([data_I2])]))
                        I2_tracking.updated_item(-1)
                        print("ODMR Maths result:")
                        print(data_I1, data_I2)
                        # Shivam: equivalent of return statement, since acquired into mongo database
                        print('are we doing this????')
                        data_source.push({
                            'device': device,
                            'PS_clock_channel': PS_clock_channel,
                            'APD_channel': APD_channel,
                            'sampling_rate': sampling_rate,
                            'time_per_sgpoint': time_per_sgpoint,
                            'mwPulseTime': mwPulseTime,
                            'clockPulseTime': clockPulseTime,
                            'rf_amplitude': rf_amplitude,
                            'sweeps': sweeps,
                            'frequencies': frequencies,
                            'slope_range': slope_range,
                            'sideband_frequency': sideband_frequency,
                            'read_timeout': read_timeout,
                            'sweeps_until_feedback': sweeps_until_feedback,
                            'z_feedback_every': z_feedback_every,
                            'xyz_step_nm': xyz_step_nm,
                            'shrink_every_x_iter': shrink_every_x_iter,
                            'starting_point': starting_point,
                            'continuous_tracking': continuous_tracking,
                            'searchXYZ': searchXYZ,
                            'max_search': max_search,
                            'min_search': min_search,
                            'scan_distance': scan_distance,
                            'search_PID': search_PID,
                            'search_integral_history': search_integral_history,
                            'spot_size': spot_size,
                            'advanced_tracking': advanced_tracking,
                            'diffusion_constant': diffusion_constant,
                            'data_download': data_download,
                            'data_source': dataset,
                            'datasets':{
                                'I1': I1_sweeps,
                                'I2': I2_sweeps
                            }
                        })
                        tracking_data_source.push({
                            'title': 'Tracking Data',
                            'xlabel': 'Time (s)',
                            'datasets': {
                                'I1_tracking': I1_tracking,
                                'I2_tracking': I2_tracking,
                            }
                        })
                        #self.mongo_acquire(data_I1, data_I2, sweep, f, sb_freq, self.total_fluor)
                        
                        # print('time from start of frequency sweep:', time.time() - time_start)

            else:
                # Shivam: The search_error_array has 3 rows for x, y, z and integral_history columns for the latest to oldest error values
                search_error_array = np.zeros((3, search_integral_history))  # Shivam: Same as above but for search radius optimization
                index = 0
                x_tracking=StreamingList()
                y_tracking=StreamingList()
                z_tracking=StreamingList()
                # Counts every time we measure a certain frequency value
                self.counter = 0
                for sweep in range(sweeps):
                    I1_data=np.empty(n_freqs)
                    I2_data=np.empty(n_freqs)
                    I1_sweeps.append(np.stack([freqs, I1_data]))
                    I2_sweeps.append(np.stack([freqs, I2_data]))
                    for f in freqs:
                        # time_start = time.time()
                        #import pdb; pdb.set_trace()
                        mgr.sg.set_frequency(f)
                        print('frequency:', f)
                        # import pdb; pdb.set_trace()

                        self.AdvancedTracking=AdvancedTracking(self.queue_to_exp, self.queue_from_exp)
                        feed_params={
                            'buffer_size':self.bufsize,
                            'index':index,
                            'search': self.search,
                            'scan_distance':self.scan_distance,
                            'read_timeout':read_timeout,
                            'spot_size':self.spot_size, 
                            'do_not_run_feedback': True,
                            'advanced_tracking':advanced_tracking, 
                            'changing_search':changing_search, 
                            'search_error_array':search_error_array, 
                            'search_integral_history':search_integral_history,
                            'sampling_rate':sampling_rate,
                            'drift':self.drift,
                            'x_k':self.x_k, 
                            'p_k':self.p_k, 
                            'n_k':self.n_k,
                            'w':self.w,
                            'diffusion_constant':self.diffusion_constant,
                            'time_elapsed':self.time_elapsed
                            
                        }

                        self.search, temp_data, search_error_array = self.AdvancedTracking.one_axis_measurement(**feed_params)
                        data_I1=temp_data[0]
                        data_I2=temp_data[1]
                        # Shivam: Use self.current_temp to continually use the latest temperature from the initial setting onwards.
                        I1_sweeps[-1][1][f] = data_I1
                        I1_sweeps.updated_item(-1)
                        I2_sweeps[-1][1][f] = data_I2
                        I2_sweeps.updated_item(-1)
                        I1_tracking.append(np.array([np.array(time.time()-start_t), np.array([data_I1])]))
                        I1_tracking.updated_item(-1)
                        I2_tracking.append(np.array([np.array(time.time()-start_t), np.array([data_I2])]))
                        I2_tracking.updated_item(-1)
                        x_tracking.append(np.array([np.array(time.time()-start_t), np.array([self.XYZ_center[0]])]))
                        x_tracking.updated_item(-1)
                        y_tracking.append(np.array([np.array(time.time()-start_t), np.array([self.XYZ_center[1]])]))
                        y_tracking.updated_item(-1)
                        z_tracking.append(np.array([np.array(time.time()-start_t), np.array([self.XYZ_center[2]])]))
                        z_tracking.updated_item(-1)
                        
                        print("Main search_error_array is " + str(search_error_array))
                        print(data_I1, data_I2)
                        # Shivam: equivalent of return statement, since acquired into mongo database

                        
                        
                        # Push all arguments of i1i2 plus measurement results to the DataSource
                        data_source.push({
                            'device': device,
                            'PS_clock_channel': PS_clock_channel,
                            'APD_channel': APD_channel,
                            'sampling_rate': sampling_rate,
                            'time_per_sgpoint': time_per_sgpoint,
                            'mwPulseTime': mwPulseTime,
                            'clockPulseTime': clockPulseTime,
                            'rf_amplitude': rf_amplitude,
                            'sweeps': sweeps,
                            'frequencies': frequencies,
                            'slope_range': slope_range,
                            'sideband_frequency': sideband_frequency,
                            'read_timeout': read_timeout,
                            'sweeps_until_feedback': sweeps_until_feedback,
                            'z_feedback_every': z_feedback_every,
                            'xyz_step_nm': xyz_step_nm,
                            'shrink_every_x_iter': shrink_every_x_iter,
                            'starting_point': starting_point,
                            'continuous_tracking': continuous_tracking,
                            'searchXYZ': searchXYZ,
                            'max_search': max_search,
                            'min_search': min_search,
                            'scan_distance': scan_distance,
                            'search_PID': search_PID,
                            'search_integral_history': search_integral_history,
                            'spot_size': spot_size,
                            'advanced_tracking': advanced_tracking,
                            'diffusion_constant': diffusion_constant,
                            'data_download': data_download,
                            'data_source': dataset,
                            'datasets':{
                                'I1': I1_sweeps,
                                'I2': I2_sweeps
                            }
                        })
                        tracking_data_source.push({
                            'title': 'Tracking Data',
                            'xlabel': 'Time (s)',
                            'datasets': {
                                'I1_tracking': I1_tracking,
                                'I2_tracking': I2_tracking,
                                'x_tracking': x_tracking,
                                'y_tracking': y_tracking,
                                'z_tracking': z_tracking,
                            }
                        })

                        self.counter += 1

                        # Updating the index to loop search axis through 0, 1, 2 = x, y, z
                        index = (index + 1) % 3

                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                self.finalize(data_download)
                                return


    def initialize(self, mgr, device, PS_clock_channel, APD_channel, sampling_rate,
                   time_per_sgpoint, mwPulseTime, clockPulseTime, rf_amplitude,
                    frequencies, slope_range, sideband_frequency,
                   continuous_tracking, searchXYZ, max_search, min_search, 
                   scan_distance,  search_PID, 
                   spot_size, advanced_tracking, 
                   diffusion_constant):
        
        ### NEW METHOD FOR INITIALIZING USING XYZcontrol- inspired on planescan
        self.ns_time_per_sgpoint = int(round(time_per_sgpoint*1e9))
        mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.acq_rate = sampling_rate

        #\if I write self.freq instead of freq, it is addressable in main, so that line of code would be redundant
        
        ## Aidan: In this experiment, do we change our frequencies?
        freq, sb_freq = self.process_frequencies(frequencies, sideband_frequency)
        #self.preparations(device, PS_clock_channel, APD_channel, sampling_rate, time_per_sgpoint, mwPulseTime,
        #                  clockPulseTime, sb_freq, rf_amplitude)  # self.sb_freq,
        

        # SHIVAM: CHECK IF I SHOULD ONLY HAVE THIS IF STATIONARY TRACKING
        self.sequence, self.stream_count, self.new_pulse_time = self.ready_pulse_sequence(mgr, mwPulseTime, clockPulseTime,
                                                                     sb_freq, rf_amplitude)

        self.buffer = self.create_buffer( mwPulseTime)
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

            self.max_search = max_search

            self.min_search = min_search

            # Shivam: Check syntax
            self.scan_distance = scan_distance
            print("scan distance is " + str(self.scan_distance))

            self.bufsize = math.floor(time_per_sgpoint/mwPulseTime)

            self.check_appropriate_distance()

            self.spot_size = spot_size
            print("self.spot_size is " + str(self.spot_size))

            # Shivam: Parameters for tracking
            self.drift = [0, 0, 0]

            # Shivam: Initializing motion controller for data collection. CHECK IF FIRST LINE NEEDED


        
            if advanced_tracking:
                effective_buffer_size = self.bufsize - 2
                num_bins = effective_buffer_size / 2
                self.time_elapsed = num_bins * self.real_time_per_scan
                self.diffusion_constant = diffusion_constant
                self.n_k = (0, 0, 0)
                self.p_k = (2 * diffusion_constant * self.time_elapsed) * 3
                self.x_k = (mgr.DAQcontrol.position['x'],
                            mgr.DAQcontrol.position['y'],
                            mgr.DAQcontrol.position['z'])
                print("x_k is " + str(self.x_k))

                # CHECK THE TUNING OF w
                self.w = self.spot_size ** 2


        
            

        self.XYZ_center = (mgr.DAQcontrol.position['x'],
                           mgr.DAQcontrol.position['y'],
                           mgr.DAQcontrol.position['z'])

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
            if self.scan_distance[i] < (2 * self.search[i] / self.bufsize):
                print("ERROR: scan distance for index " + str(i) + " is too small, please decrease scan distance to at least " + str(self.search[i]*1e3/ self.bufsize) + " nm.")
                raise ValueError('Scan distance too small')
    
    def process_frequencies(self, frequencies, sideband_frequency):
        new_sideband = eval(sideband_frequency) * 1e6
        new_frequencies = np.linspace(eval(frequencies)[0], eval(frequencies)[1], eval(frequencies)[2])
        return new_frequencies, new_sideband       

    # def one_axis_measurement(self, mgr, buffer_size, index, PS_clk_channel,
    #             search, scan_distance, read_timeout, spot_size, advanced_tracking, 
    #             changing_search, search_error_array, search_integral_history,
    #             sampling_rate):
        
    #     print("We are indeed running tracking code")
    #     data, buffer_allocation, remaining_buffer = self.read_stream_flee(mgr, index, PS_clk_channel, search, buffer_size, scan_distance, read_timeout)

    #     ## confirmed, here I have 180-200 ms of lag
    #     print("Length of data is " + str(len(data)))
    #     ## after this is 70-130 ms of lag        
    #     tracking_data, track_steps, data_I1, data_I2 = self.process_data(data, buffer_allocation, remaining_buffer, index, search)

    #     # Shivam: Processes tracking data and sets to new position along index axis
    #     search, search_error_array = self.datanaly(mgr, tracking_data, track_steps, index, search, spot_size, advanced_tracking, 
    #                            changing_search, search_error_array, search_integral_history)

    #     ## total it says i have 250 ms of lag

    #     ## I can have up to 300 ms.

    #     return search, data_I1, data_I2, search_error_array
    

    # def read_stream_flee(self, mgr,index, search, buffer_size, scan_distance, read_timeout):
    #     ## total this has 180 ms of lag.
    #     # time_track = time.time()
    #     xyz_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
    #                             buffer_size)
    #     # Shivam: Assigns the entire XYZ_center array to both newly defined arrays
    #     pos_center_st = self.XYZ_center[:]
    #     pos_center_end = self.XYZ_center[:]
    #     pos_center_st[index] = xyz_steps[0]
    #     pos_center_end[index] = xyz_steps[-1]

    #     distance_of_sweep = (np.abs(pos_center_end[index] - pos_center_st[index]))
    #     print(distance_of_sweep)
    #     print(scan_distance)
    #     number_of_steps = math.ceil(distance_of_sweep / scan_distance[index])
    #     print("The number of steps is " + str(number_of_steps))
    #     effective_scan_distance = distance_of_sweep / number_of_steps
    #     print("The effective scan distance is " + str(effective_scan_distance))
    #     # Shivam: Subtracted by 2 because of the way the buffer is sliced to keep equal photon exposure for I1 and I2 
    #     effective_buffer_size = buffer_size - 2
    #     print("The effective buffer size is " + str(effective_buffer_size))
    #     # Shivam: Buffer allocation for each step of scan
    #     buffer_allocation = math.floor(effective_buffer_size / number_of_steps)
    #     print("The buffer allocation is " + str(buffer_allocation))
    #     # import pdb; pdb.set_trace()
    #     # Shivam: Doing a 1 axis scan from the set start point till end point with buffer_size steps
    #     # Remaining buffer is for later calculations, but this function is primarily for the scan.
    #     # Points per step signifies how many repetitions of the line scan we are doing
    #     remaining_buffer = buffer_size - (number_of_steps * buffer_allocation)
    #     mgr.DAQcontrol.prepare_line_scan(
    #                                         {'x': pos_center_st[0], 'y': pos_center_st[1], 'z': pos_center_st[2]},
    #                                         {'x': pos_center_end[0], 'y': pos_center_end[1], 'z': pos_center_end[2]},
    #                                         number_of_steps, buffer_size)

    #     ###Before this, around .12 seconds have elapsed

    #     'start the pulse streamer and the task close to simultaneously'

    #     mgr.Pulser.stream_sequence(self.sequence, self.run_ct)
    #     ## this is 35 ms all on its own. 
    #     'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
    #     # Shivam: Changed from num_freq * 2 to num_freq because we are not doing background collection
    #     scan_data = mgr.DAQcontrol.start_line_scan()

    #     mgr.Pulser.reset()
    #     ## this is 5 miliseconds
    #     # print('time for read stream flee:', time.time() - time_track)

    #     ## pulser stream to pulser reset has 60ms delay.
        
    #     return rpyc.utils.classic.obtain(scan_data), buffer_allocation, remaining_buffer
    

    # def process_data(self, input_buffer, buffer_allocation, remaining_buffer, index, search):
    #     # Shivam: We are removing the last value of I2 from the buffer to not have the last photon count
    #     # This is because we do not have a clock at the last time period and so would only have 1 out of 2 relevant counts for that segment when subtracting
    #     # This means that we will effectively have n - 1 runs when setting the time per sg point for n runs
    #     print("The input buffer size is " + str(len(input_buffer)))
    #     effective_buffer = input_buffer[:-1]
    #     print("The later effective buffer size is " + str(len(effective_buffer)))
    #     # Shivam: sliced to new array 2nd element onwards subtracting all elements to the left (I1 - I0, I2 - I1, ... ,
    #     interval_data = effective_buffer[1:] - effective_buffer[:-1]

    #     # This gets the number of I1 I2 pulsesequences that we are considering in our calculations
    #     # This is needed for our calculation of total time of photon collection in advanced_tracking

    #     num_bins = int(len(interval_data) / 2)
    #     print("The number of bins is " + str(num_bins))

    #     # Shivam: sums interval data in steps of 4 (I1-I0+I5-I4+...) is the first element
    #     sum_Is = [np.sum(interval_data[i::2]) for i in range(2)]
    #     # \ sum_Is = [#,#,#,#]
    #     # data = sum_Is[0]/sum_Is[1] - sum_Is[2]/sum_Is[3]

    #     # Shivam: I1, I2 total counts for w1 and w2
    #     data_I1 = sum_Is[0]
    #     data_I2 = sum_Is[1]


    #     if remaining_buffer > 0:
    #         tracking_buffer = input_buffer[:(-remaining_buffer + 1)]
    #     else:
    #         print("Error in remaining buffer")

    #     print("Tracking buffer is " + str(tracking_buffer))
    #     print("Length of tracking buffer is " + str(len(tracking_buffer)))

    #     tracking_interval = tracking_buffer[1:] - tracking_buffer[:-1]

    #     print("Tracking interval is " + str(tracking_interval))
    #     print("Length of tracking interval is " + str(len(tracking_interval)))


    #     # Shivam: This sums over the buffer allocation for each position step of the scan and stores in new array
    #     tracking_data = np.sum(tracking_interval.reshape(-1, buffer_allocation), axis=1)
    #     print("Length of tracking data is " + str(len(tracking_data)))
    #     print("Tracking data is " + str(tracking_data))

    #     track_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
    #                             len(tracking_data))
        
        
    #     return tracking_data, track_steps, data_I1, data_I2
    

    # def datanaly(self, mgr, tracking_data, track_steps, index, search, spot_size, advanced_tracking, 
    #              changing_search, search_error_pre_array, search_integral_history):
    #     '''
    #     Calculates Gaussian fit for the tracking data and sets the new center position for the next scan (moves the laser directly)
    #     '''
    #     self.total_fluor = np.sum(tracking_data)
    #     print("Total Fluorescence is " + str(self.total_fluor))
    #     print('Out of XYZ = [0,1,2], this is the', index, 'axis')


    #     # Here we are attempting to fit to Gaussian. spot_size is the initial guess for the FWHM of the Gaussian spot
    #     p0 = [np.max(tracking_data), track_steps[np.argmax(tracking_data)], spot_size, np.min(tracking_data)]
    #     if advanced_tracking:
    #         try:
    #             # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
    #             print("made it to before curve fit")
    #             print("Track steps is " + str(track_steps))
    #             print("Length of track steps is " + str(len(track_steps)))
    #             print("Tracking data is " + str(tracking_data))
    #             print("Length of tracking data is " + str(len(tracking_data)))
    #             popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
    #             print("popt[1] is " + str(popt[1]))
    #             print("popt is " + str(popt))
    #             plot_fitted = self.gaussian(track_steps, *popt)
    #             plot_center_fit = popt[1]
    #             plotbackground = popt[3]
    #             # plotbackground = self.gaussian(track_steps[0], *popt)
    #             plotpeak = self.gaussian(plot_center_fit, *popt)
    #             print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
    #                 plotpeak / plotbackground - 1), '\n')
    #             if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
    #                 # import pdb; pdb.set_trace()
    #                 if popt[0] < 0:
    #                     print("negative fit")

    #                 else:
    #                     self.drift[index] = plot_center_fit - self.XYZ_center[index]
    #                     self.XYZ_center[index] = self.advanced_tracking(plot_center_fit, index)

    #             else:
    #                 print('Gaussian fit max is out of scanning range. Using maximum point instead')
    #                 max_count_position = track_steps[np.argmax(tracking_data)]
    #                 self.drift[index] = max_count_position - self.XYZ_center[index]
    #                 self.XYZ_center[index] = self.advanced_tracking(max_count_position, index)
    #                 "CHECK WHAT THIS BECOMES"
    #         except:
    #             print('no Gaussian fit')
    #             max_count_position = track_steps[np.argmax(tracking_data)]
    #             self.drift[index] = max_count_position - self.XYZ_center[index]
    #             self.XYZ_center[index] = self.advanced_tracking(max_count_position, index)

    #         print("debugging, XYZ center is " + str(self.XYZ_center))
            
    #         mgr.DAQcontrol.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
    #         print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
    #         print('\nHere is where the laser is currently pointing:', mgr.DAQcontrol.get_position())

    #         if changing_search:
    #             search_change = 0.0
    #             ### Shivam: this is the new search change which is adaptive with PID control that has a target 
    #             # to set search radius to double the drift
    #             n = search_integral_history
    #             print("search_error_pre_array is " + str(search_error_pre_array))
    #             # Target value for search radius is thrice the drift
    #             search_error_pre = search_error_pre_array[index][0]
    #             # Shivam: The factor next to self.drift[index] determines how much larger the search radius should be than the drift
    #             search_error = (-1) * (search[index] - self.drift[index] * 2)

    #             print("drift is " + str(self.drift[index]))
    #             print("search_error is " + str(search_error))

    #             # The below line looks like: 
    #             # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
    #             search_error_deques = [collections.deque(row) for row in search_error_pre_array]
    #             print("search_error_deques is " + str(search_error_deques))

    #             # Append the latest search error value to the deque at the relevant index and remove the oldest value
    #             search_error_deques[index].appendleft(search_error)
    #             search_error_deques[index].pop()
    #             # Convert the modified deque into a NumPy array
    #             search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])

    #             print("search_error_array is " + str(search_error_array))


    #             # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

    #             search_change += self.search_kp * search_error

    #             # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
    #             integral_sum = 0.0
    #             for i in np.arange(n):
    #                 integral_sum += search_error_array[index][i]*(0.5**i)

    #             search_change += self.search_ki * integral_sum

    #             search_change += self.search_kd * (search_error - search_error_pre)
                
    #             # Limitations of what search radius can be with min and max search radius
                
    #             # Converting search[index] to float to do maths then back to nm for the variable
    #             search[index] =  search[index] + search_change

    #             if search[index] > self.max_search[index]:
    #                 print("Max search radius for index " + str(index) + " reached.")
    #                 search[index] = self.max_search[index]

    #             if search[index] < self.min_search[index]:
    #                 print("Min search radius for index " + str(index) + " reached.")
    #                 search[index] = self.min_search[index]

    #             print("Search radius for index " + str(index) + " is updated to " + str(search[index]))

         


    #     else:

    #         try:
    #             # Shivam: popt is the return of the optimized values of curve parameters (array of form such as p0)
    #             print("made it to before curve fit")
    #             print("Track steps is " + str(track_steps))
    #             print("Length of track steps is " + str(len(track_steps)))
    #             print("Tracking data is " + str(tracking_data))
    #             print("Length of tracking data is " + str(len(tracking_data)))
    #             popt, pcov = optimize.curve_fit(self.gaussian, track_steps, tracking_data, p0=p0)
    #             print("popt[1] is " + str(popt[1]))
    #             print("popt is " + str(popt))
    #             plot_fitted = self.gaussian(track_steps, *popt)
    #             plot_center_fit = popt[1]
    #             plotbackground = popt[3]
    #             # plotbackground = self.gaussian(track_steps[0], *popt)
    #             plotpeak = self.gaussian(plot_center_fit, *popt)
    #             print('plot peak, background, SBR: ' + str(plotpeak) + ',' + str(plotbackground) + ',' + str(
    #                 plotpeak / plotbackground - 1), '\n')
    #             if np.min(track_steps) <= plot_center_fit <= np.max(track_steps):
    #                 # import pdb; pdb.set_trace()
    #                 if popt[0] < 0:
    #                     print("negative fit")

    #                 else:
    #                     self.drift[index] = plot_center_fit - self.XYZ_center[index]
    #                     self.XYZ_center[index] = plot_center_fit

                    
    #             else:
    #                 print('Gaussian fit max is out of scanning range. Using maximum point instead')
    #                 max_count_position = track_steps[np.argmax(tracking_data)]
    #                 self.drift[index] = max_count_position - self.XYZ_center[index]
    #                 self.XYZ_center[index] = max_count_position


    #         except:
    #             print('no Gaussian fit')
    #             max_count_position = track_steps[np.argmax(tracking_data)]
    #             self.drift[index] = max_count_position - self.XYZ_center[index]
    #             self.XYZ_center[index] = max_count_position

    #         mgr.DAQcontrol.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
    #         print("xyz positions set are " + str(self.XYZ_center[0]) + str(self.XYZ_center[1]) + str(self.XYZ_center[2]))
    #         print('\nHere is where the laser is currently pointing:', mgr.DAQcontrol.get_position())

    #         if changing_search:
    #             search_change = 0.0
    #             ### Shivam: this is the new search change which is adaptive with PID control that has a target 
    #             # to set search radius to double the drift
    #             n = search_integral_history
    #             print("search_error_pre_array is " + str(search_error_pre_array))
    #             # Target value for search radius is twice the drift
    #             search_error_pre = search_error_pre_array[index][0]
    #             search_error = (-1) * (search[index] - self.drift[index] * 2)

    #             print("drift is " + str(self.drift[index]))
    #             print("search_error is " + str(search_error))

    #             # The below line looks like: 
    #             # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
    #             search_error_deques = [collections.deque(row) for row in search_error_pre_array]
    #             print("search_error_deques is " + str(search_error_deques))

    #             # Append the latest search error value to the deque at the relevant index and remove the oldest value
    #             search_error_deques[index].appendleft(search_error)
    #             search_error_deques[index].pop()
    #             # Convert the modified deque into a NumPy array
    #             search_error_array = np.array([list(row_deque) for row_deque in search_error_deques])

    #             print("search_error_array is " + str(search_error_array))


    #             # Check that PID_recurrence values are not 0 to avoid divide by zero error (if any is zero then never use it in calculation)

    #             search_change += self.search_kp * search_error

    #             # Shivam: Implementation of weighted sum of error values (geometric series) for integral component of PID (can change with constant in front of n)
    #             integral_sum = 0.0
    #             for i in np.arange(n):
    #                 integral_sum += search_error_array[index][i]*(0.5**i)

    #             search_change += self.search_ki * integral_sum

    #             search_change += self.search_kd * (search_error - search_error_pre)
                
    #             # Limitations of what search radius can be with min and max search radius
                
    #             # Converting search[index] to float to do maths then back to nm for the variable
    #             search[index] =  search[index] + search_change

    #             if search[index] > self.max_search[index]:
    #                 print("Max search radius for index " + str(index) + " reached.")
    #                 search[index] = self.max_search[index]

    #             if search[index] < self.min_search[index]:
    #                 print("Min search radius for index " + str(index) + " reached.")
    #                 search[index] = self.min_search[index]

    #             print("Search radius for index " + str(index) + " is updated to " + str(search[index]))

         
        
    #     return search, search_error_array
    
    # def advanced_tracking(self, gaussian_center, index):
    #     '''
    #     Helper function to predict position of nanodiamond using a statistical Brownian motion analysis. Found in Harry's paper.
    #     "Probing and manipulation embryogenesis via nanoscale thermometry and temperature control"
    #     '''
    #     # Variable storing how many photons were collected in the scan
    #     self.old_n_k = self.n_k
    #     self.n_k[index] = self.total_fluor

    #     # Value of current Gaussian center in current index of search
    #     c_k = gaussian_center

        
    #     self.old_p_k = self.p_k

    #     self.p_k[index] = ((self.w * self.old_p_k[index]) / (self.w + self.old_n_k[index] * self.old_p_k[index])) + 2 * self.diffusion_constant * self.time_elapsed

    #     self.old_x_k = self.x_k

    #     # Shivam: This is the predicted position of the nanodiamond
    #     print("w is " + str(self.w))
    #     print("pk is " + str(self.p_k))
    #     print("ck is " + str(c_k))
    #     print("nk is " + str(self.n_k))
    #     print("old xk is " + str(self.old_x_k))
    #     self.x_k[index] = (self.w * self.old_x_k[index] + self.n_k[index] * self.p_k[index] * c_k) / (self.w + self.n_k[index] * self.p_k[index])

    #     print("debugging, x_k is " + str(self.x_k))

    #     return self.x_k[index]
        
        


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

    def odmr_read(self, mgr, buffer, ctr_task, ctr_reader, sequence, stream_count, read_timeout):
        # time_read = time.time()
        print(buffer)
        print(len(buffer))
        mgr.DAQcontrol.start_counter()
        ctr_task.start()
        print("Counter Started")
        mgr.Pulser.stream_sequence(sequence, stream_count)
        print("ps start")
        buffer=mgr.DAQcontrol.read_to_data_array(read_timeout*2)
        data_obtain = ctr_reader.read_many_sample_uint32(
            buffer,
            number_of_samples_per_channel=len(buffer),
            timeout=read_timeout * 2
        )
        ctr_task.stop()
        mgr.Pulser.set_state_off()
        # print('the time it took to actually run the pulse sequence and read:', time.time() - time_read)
        print('end of read')
        return buffer

    # def mongo_acquire(self, data_I1, data_I2, sweep, f, sideband_frequency, total_fluor):
    #     # Shivam: check changes to mongo_acquire with new I2_I1 and I2/I1
    #     # Shivam: Change names of the groupby things in plotting below

    #     if not self.continuous_tracking:
    #         self.acquire({
    #             'I2': float(data_I2),
    #             'I1': float(data_I1),
    #             'sweep_number': sweep,
    #             'sig_gen_frequency': f,
    #             'V1': f - float(sideband_frequency),
    #             'V2': f + float(sideband_frequency),
    #             'total_fluor': float(total_fluor),

    #         })

    #     else:
    #         self.acquire({
    #             'I2': float(data_I2),
    #             'I1': float(data_I1),
    #             'sweep_number': sweep,
    #             'sig_gen_frequency': f,
    #             'V1': f - float(sideband_frequency),
    #             'V2': f + float(sideband_frequency),
    #             'total_fluor': float(total_fluor),
    #             'searchX_um': list(self.search)[0],
    #             'searchY_um': list(self.search)[1],
    #             'searchZ_um': list(self.search)[2],
    #             'x_pos': self.XYZ_center[0],
    #             'y_pos': self.XYZ_center[1],
    #             'z_pos': self.XYZ_center[2],
    #             'count': self.counter,
    #         })
    #         print("Total fluorescence is " + str(total_fluor))
    #         print("Search radius is " + str(self.search))
    #         print("count is " + str(self.counter))

    def feedback(self, mgr, sweep, sweeps_until_feedback, z_feedback_every, xyz_step_nm, shrink_every_x_iter,starting_point):
        # \consider taking away sweep>0, allows you to avoid running spatial feedback before experiment

        if (sweep > 0) and (sweep % sweeps_until_feedback == 0):
            if sweep % z_feedback_every == 0:
                dozfb = True
            else:
                dozfb = False
            feed_params = {
                'starting_point': str(starting_point),
                # 'position': position,
                'do_z': dozfb,
                'xyz_step': xyz_step_nm,
                'shrink_every_x_iter': shrink_every_x_iter,
            }
            ## we make sure the laser is turned on.
            self.SpatialFB = SpatialFeedback(self.queue_to_exp, self.queue_from_exp)
            self.SpatialFB.spatial_feedback(**feed_params)

            ##space_data is the last line of data from spatialfeedbackxyz
            space_data = self.SpatialFB.data.tail(1)
            x_initial = space_data['x_center'].values[0]
            y_initial = space_data['y_center'].values[0]
            if dozfb:
                z_initial = space_data['z_center'].values[0]

                mgr.DAQcontrol.move({'x': x_initial, 'y': y_initial, 'z': z_initial})
                return
            # Shivam: Is there supposed to be an else over here?
            mgr.DAQcontrol.move({'x': x_initial, 'y': y_initial, 'z': self.XYZ_center[2]})
            return
        else:
            return


    def ready_pulse_sequence(self, mgr,  mwPulseTime, clockPulse, sideband_frequency, rf_amplitude):
        self.ns_read_time = int(round(mwPulseTime*1e9))
        self.ns_clock_time = int(round(clockPulse*1e9))
        seq, self.new_pulse_time = self.streamer.odmr_temp_calib_no_bg(sideband_frequency)

        mgr.set_rf_amplitude(rf_amplitude)
        mgr.sg.set_mod_type('QAM')
        mgr.sg.set_rf_toggle(1)
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_mod_function('external')
        # Shivam: streamer.total_time is from the odmr_temp_calib function from dr_pulsesequences_Sideband
        # And it is the total time for one pulse sequence
        self.run_ct = self.ns_time_per_sgpoint / self.streamer.total_time

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
            sampling_rate,
            source=clock_channel,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=buffer_size,
        )
        APD_reader = CounterReader(APD_task.in_stream)
        return APD_task, APD_reader

    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        # Shivam: Convert FWHM (width) to standard deviation for Gaussian plot
        if a < 0 or width < 0 or b < 0:
            return math.inf
        sigma = width / (np.sqrt(8 * np.log(2)))
        return a * np.exp(-np.square((xs - x) / (np.sqrt(2) * + sigma))) + b


        

    def finalize(self, data_download):

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
