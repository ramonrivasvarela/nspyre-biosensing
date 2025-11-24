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
        _logger.info('Created I1I2 instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed I1I2 instance.')


    

    def i1i2(self,  sampling_rate=50000,
                   time_per_sgpoint=1, mwPulseTime=50e-6, clockPulseTime=10e-9, rf_amplitude=-20,
                   sweeps=10, frequencies='(2.85e9, 2.89e9, 20)', slope_range='(2.868e9, 2.871e9)', sideband_frequency='10.1010101', 
                   read_timeout=12, sweeps_until_feedback=6, z_cycle=1, track_z=True,
                   xyz_step_nm=.5e-7, shrink_every_x_iter=1, 
                   continuous_tracking=False, searchXYZ="(0.5, 0.5, 0.5)", max_search="(1, 1, 1)", min_search="(0.1, 0.1, 0.1)", 
                   scan_distance="(0.03, 0.03, 0.05)", changing_search=False, search_PID="(0.5,0.01,0)", 
                   search_integral_history=5, spot_size=400e-9, advanced_tracking=False, 
                   diffusion_constant=200, data_download=False, dataset='i1i2_data', tracking_dataset='i1i2_tracking'):
        params={'sampling_rate': sampling_rate,
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
                'z_cycle': z_cycle,
                'xyz_step_nm': xyz_step_nm,
                'shrink_every_x_iter': shrink_every_x_iter,
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
                'data_source': dataset,}
        with InstrumentManager() as mgr, DataSource(dataset) as data_source, DataSource(tracking_dataset) as tracking_data_source:
            self.initialize(mgr, sampling_rate,
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
            I1_data=np.empty(n_freqs)
            I2_data=np.empty(n_freqs)
            # I1_sweeps.append(np.stack([freqs, I1_data]))
            # I2_sweeps.append(np.stack([freqs, I2_data]))
            if not continuous_tracking:
                
                for sweep in range(sweeps):
                    I1_empty=np.empty(n_freqs)
                    I1_empty[:]=np.nan
                    I2_empty=np.empty(n_freqs)
                    I2_empty[:]=np.nan
                    I1_sweeps.append(np.stack([freqs, I1_empty]))
                    I2_sweeps.append(np.stack([freqs, I2_empty]))
                    print('before feedback')
                    self.feedback(mgr, sweep, sweeps_until_feedback, z_cycle, xyz_step_nm, shrink_every_x_iter, sampling_rate)
                    for f, freq in enumerate(freqs):
                        print("Frequency value is " + str(f))
                        # time_start = time.time()
                        #import pdb; pdb.set_trace()
                        
                        mgr.sg.set_frequency(freq)
                        print('frequency:', freq)
                        # import pdb; pdb.set_trace()
                        
                        output_buffer = self.odmr_read(mgr, self.sequence, read_timeout)
                        data_I1, data_I2 = self.odmr_math(output_buffer)
                        I1_sweeps[-1][1][f] = data_I1
                        I1_sweeps.updated_item(-1)
                        I2_sweeps[-1][1][f] = data_I2
                        I2_sweeps.updated_item(-1)
                        I1_tracking.append(np.array([np.array([time.time()-start_t]), np.array([data_I1])]))
                        I1_tracking.updated_item(-1)
                        I2_tracking.append(np.array([np.array([time.time()-start_t]), np.array([data_I2])]))
                        I2_tracking.updated_item(-1)
                        print("ODMR Maths result:")
                        print(data_I1, data_I2)
                        # Shivam: equivalent of return statement, since acquired into mongo database
                        print('are we doing this????')
                        data_source.push({
                            'params':params,
                            'datasets':{
                                'I1': I1_sweeps,
                                'I2': I2_sweeps
                            }
                        })
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                return self.finalize(mgr, data_download, I1_sweeps, I2_sweeps)
                                
                        # tracking_data_source.push({
                        #     'title': 'Tracking Data',
                        #     'xlabel': 'Time (s)',
                        #     'datasets': {
                        #         'I1_tracking': I1_tracking,
                        #         'I2_tracking': I2_tracking,
                        #     }
                        # })
                        #self.mongo_acquire(data_I1, data_I2, sweep, f, sb_freq, self.total_fluor)
                        
                        # print('time from start of frequency sweep:', time.time() - time_start)
                
                # Finalize the experiment after all sweeps are complete
                return self.finalize(mgr, data_download, I1_sweeps, I2_sweeps)

            else:
                # Shivam: The search_error_array has 3 rows for x, y, z and integral_history columns for the latest to oldest error values
                search_error_array = np.zeros((3, search_integral_history))  # Shivam: Same as above but for search radius optimization
                index = 0
                x_tracking=StreamingList()
                y_tracking=StreamingList()
                z_tracking=StreamingList()
                total_fluor_tracking=StreamingList()
                # Counts every time we measure a certain frequency value
                self.counter = 0
                for sweep in range(sweeps):
                    I1_empty=np.empty(n_freqs)
                    I1_empty[:]=np.nan
                    I2_empty=np.empty(n_freqs)
                    I2_empty[:]=np.nan
                    I1_sweeps.append(np.stack([freqs, I1_empty]))
                    I2_sweeps.append(np.stack([freqs, I2_empty]))
                    for f, freq in enumerate(freqs):
                        index=(index+1)%3
                        if (not track_z) and (index == 2):
                            continue
                        elif (index == 2) and (index % z_cycle != 0):
                            continue
                        # time_start = time.time()
                        #import pdb; pdb.set_trace()
                        mgr.sg.set_frequency(freq)
                        print('frequency:', freq)
                        # import pdb; pdb.set_trace()

                        self.AdvancedTracking=AdvancedTracking(self.queue_to_exp, self.queue_from_exp)
                        feed_params={
                            'mgr':mgr,
                            'XYZ_center':self.XYZ_center,
                            'buffer_size':self.bufsize,
                            'index':index,
                            'search': self.search,
                            'scan_distance':self.scan_distance,
                            'read_timeout':read_timeout,
                            'spot_size':self.spot_size, 
                            'do_not_run_feedback': False,
                            'advanced_tracking':advanced_tracking, 
                            'changing_search':changing_search, 
                            'search_error_array':search_error_array, 
                            'search_integral_history':search_integral_history,
                            # 'sampling_rate':sampling_rate,
                            'drift':self.drift,
                            'run_ct':self.run_ct,
                            'search_PID':search_PID,
                            'max_search':self.max_search,
                            'min_search':self.min_search,
                            'sequence':self.sequence,
                            'num_freq':n_freqs,
                            
                        }
                        if advanced_tracking:
                            feed_params['diffusion_constant']=self.diffusion_constant
                            feed_params['time_elapsed']=self.time_elapsed
                            feed_params['w']=self.w
                            feed_params['n_k']=self.n_k
                            feed_params['p_k']=self.p_k
                            feed_params['x_k']=self.x_k

                        self.search, temp_data, total_fluor, search_error_array = self.AdvancedTracking.one_axis_measurement(**feed_params)
                        self.XYZ_center=self.AdvancedTracking.XYZ_center
                        self.drift=self.AdvancedTracking.drift
                        data_I1=temp_data[0]
                        data_I2=temp_data[1]
                        
                        # Shivam: Use self.current_temp to continually use the latest temperature from the initial setting onwards.
                        I1_sweeps[-1][1][f] = data_I1
                        I1_sweeps.updated_item(-1)
                        I2_sweeps[-1][1][f] = data_I2
                        I2_sweeps.updated_item(-1)
                        x_tracking.append(np.array([np.array([time.time()-start_t]), np.array([self.XYZ_center[0]])]))
                        x_tracking.updated_item(-1)
                        y_tracking.append(np.array([np.array([time.time()-start_t]), np.array([self.XYZ_center[1]])]))
                        y_tracking.updated_item(-1)
                        z_tracking.append(np.array([np.array([time.time()-start_t]), np.array([self.XYZ_center[2]])]))
                        z_tracking.updated_item(-1)
                        total_fluor_tracking.append(np.array([np.array([time.time()-start_t]), np.array([total_fluor])]))
                        total_fluor_tracking.updated_item(-1)

                        print("Main search_error_array is " + str(search_error_array))
                        print(data_I1, data_I2)
                        # Shivam: equivalent of return statement, since acquired into mongo database

                        
                        
                        # Push all arguments of i1i2 plus measurement results to the DataSource
                        data_source.push({
                            'params':params,
                            
                            'datasets':{
                                'I1': I1_sweeps,
                                'I2': I2_sweeps,
                                'x_pos': x_tracking,
                                'y_pos': y_tracking,
                                'z_pos': z_tracking,
                                'total_fluor': total_fluor_tracking,
                            }
                        })
                        # tracking_data_source.push({
                        #     'title': 'Tracking Data',
                        #     'xlabel': 'Time (s)',
                        #     'datasets': {

                        #         'x_pos': x_tracking,
                        #         'y_pos': y_tracking,
                        #         'z_pos': z_tracking,
                        #         'total_fluor': total_fluor_tracking,
                        #     }
                        # })

                        self.counter += 1

                        # # Updating the index to loop search axis through 0, 1, 2 = x, y, z
                        # index = (index + 1) % 3

                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                return self.finalize(mgr, data_download, I1_sweeps, I2_sweeps)
                                
            
                # Finalize the experiment after all sweeps are complete  
                return self.finalize(mgr, data_download, I1_sweeps, I2_sweeps)


    def initialize(self, mgr, sampling_rate,
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
        print(self.sequence)
        
        # data_channel, clock_channel = self.create_channels(device, PS_clock_channel, APD_channel)
        # self.APD_task, self.APD_reader = self.create_ctr_reader(data_channel, sampling_rate, clock_channel,
        #                                                         len(self.buffer))
        
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
            self.scan_distance = eval(scan_distance)
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


        else:
            self.bufsize= math.floor(time_per_sgpoint/mwPulseTime) 
            '''RAMON: VERY IMPORTANT, DAQcontrol.prepare counting takes as an argument the number of analyzed samples, not the buffer size. Make sure you always substract 1 from the buffer size.'''
            mgr.DAQcontrol.prepare_counting(sampling_rate, self.bufsize-1)
            

        self.XYZ_center = [mgr.DAQcontrol.position['x'],
                           mgr.DAQcontrol.position['y'],
                           mgr.DAQcontrol.position['z']]

        # This will be the variable storing total fluorescence every run
        self.total_fluor = 0

        self.left_frequency_slope = eval(slope_range)[0] 
        self.right_frequency_slope = eval(slope_range)[1]




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

    def odmr_read(self, mgr, sequence, read_timeout):
        # time_read = time.time()
        # print(buffer)
        # print(len(buffer))
        mgr.DAQcontrol.start_counter()
        # ctr_task.start()
        print("Counter Started")
        print(f"Debug: About to stream sequence with stream_count={self.stream_count}")
        mgr.Pulser.stream_sequence(sequence, self.stream_count)
        print("ps start")
        print(mgr.DAQcontrol.ctr_buffer)
        try:
            buffer=np.array(mgr.DAQcontrol.read_to_data_array(read_timeout*2))
        except Exception as e:
            print("Error in reading DAQ counter:", e)
            print(mgr.DAQcontrol.ctr_buffer)
            mgr.DAQcontrol.finalize_counter()
            
            mgr.Pulser.set_state_off()
            raise e
        mgr.Pulser.set_state_off()
        print(mgr.DAQcontrol.ctr_buffer)
        # print('the time it took to actually run the pulse sequence and read:', time.time() - time_read)
        print('end of read')
        return buffer

    def feedback(self, mgr, sweep, sweeps_until_feedback, z_cycle, xyz_step_nm, shrink_every_x_iter, sampling_rate):
        # \consider taking away sweep>0, allows you to avoid running spatial feedback before experiment

        if (sweep > 0) and (sweep % sweeps_until_feedback == 0):
            if sweep % z_cycle == 0:
                dozfb = True
            else:
                dozfb = False
            feed_params = {
                # 'position': position,
                'do_z': dozfb,
                'xyz_step': xyz_step_nm,
                'shrink_every_x_iter': shrink_every_x_iter,
                'counter_already_exists':True,
                'starting_point': 'current_position (ignore input)'
            }
            ## we make sure the laser is turned on.
            self.SpatialFB = SpatialFeedback(self.queue_to_exp, self.queue_from_exp)
            self.SpatialFB.spatial_feedback(**feed_params)
            mgr.DAQcontrol.prepare_counting(sampling_rate, self.bufsize-1)
            

        #     ##space_data is the last line of data from spatialfeedbackxyz
        #     space_data = self.SpatialFB.data.tail(1)
        #     x_initial = space_data['x_center'].values[0]
        #     y_initial = space_data['y_center'].values[0]
        #     if dozfb:
        #         z_initial = space_data['z_center'].values[0]

        #         mgr.DAQcontrol.move({'x': x_initial, 'y': y_initial, 'z': z_initial})
        #         return
        #     # Shivam: Is there supposed to be an else over here?
        #     mgr.DAQcontrol.move({'x': x_initial, 'y': y_initial, 'z': self.XYZ_center[2]})
        #     return
        # else:
        #     return


    def ready_pulse_sequence(self, mgr,  mwPulseTime, clockPulse, sideband_frequency, rf_amplitude):
        ns_read_time = int(round(mwPulseTime*1e9))
        ns_clock_time = int(round(clockPulse*1e9))
        print(f"Debug: ns_read_time={ns_read_time}, ns_clock_time={ns_clock_time}, sideband_frequency={sideband_frequency}")
        print('self.read_time:', ns_read_time)
        print(' self.clock_time:',  ns_clock_time)
        # self.total_time = 0
    
        seq, self.new_pulse_time = mgr.Pulser.odmr_temp_calib_no_bg(sideband_frequency, ns_read_time, ns_clock_time)
        
        # print(seq)
        # seq, self.new_pulse_time = mgr.Pulser.odmr_temp_calib_no_bg(sideband_frequency, ns_read_time, ns_clock_time)
        print(f"Debug: sequence created, new_pulse_time={self.new_pulse_time}")

        mgr.sg.set_rf_amplitude(rf_amplitude)
        mgr.sg.set_mod_type('QAM')
        mgr.sg.set_rf_toggle(1)
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_mod_function('QAM', 'external')
        # Shivam: streamer.total_time is from the odmr_temp_calib function from dr_pulsesequences_Sideband
        # And it is the total time for one pulse sequence
        ns_total_time=2*ns_read_time
        self.run_ct = int(round(self.ns_time_per_sgpoint / ns_total_time))
        
        # Ensure run_ct is at least 1
        if self.run_ct < 1:
            self.run_ct = 1
            print(f"Warning: run_ct was less than 1, setting to 1")
        
        print(f"Debug: run_ct={self.run_ct}, ns_total_time={ns_total_time}")

        # This is an important variable to know how long is spent collecting photons at one center freqeuncy
        self.real_time_per_scan = self.run_ct * ns_total_time

        return seq, self.run_ct, self.new_pulse_time


    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        # Shivam: Convert FWHM (width) to standard deviation for Gaussian plot
        if a < 0 or width < 0 or b < 0:
            return math.inf
        sigma = width / (np.sqrt(8 * np.log(2)))
        return a * np.exp(-np.square((xs - x) / (np.sqrt(2) * + sigma))) + b


        

    def finalize(self, mgr, data_download, I1_sweeps, I2_sweeps):
        mgr.DAQcontrol.finalize_counter()
        self.handle_pulsestreamer(mgr)

        # Process I1 and I2 data to extract frequencies and mean values per frequency
        unique_frequencies, sigs_left_mean, sigs_right_mean = self.process_i1_i2_data(I1_sweeps, I2_sweeps)

        if data_download:
            self.download_excel()

        # Shivam: FUTURE IMPROVEMENTS - Currently the proper slope and zero extraction is only implemented for quasilinear_calibration slope
        # The quasilinear_calibration slope normalizes using only on values and no background values and that is what we have chosen to use for now
        regular_calibration_slope = self.regular_slope_extraction(unique_frequencies, sigs_left_mean, sigs_right_mean)
        quasilinear_calibration_slope, quasilinear_zero_field_splitting = self.quasilinear_slope_extraction(unique_frequencies, sigs_left_mean, sigs_right_mean)
        print('\n\n', regular_calibration_slope,
              'is the slope between the frequency change and the fluorescence change.\n\n')
        
        print(str(quasilinear_calibration_slope) + 
              ' is the quasilinear slope between the frequency change and the fluorescence change. The zero field splitting is '
              + str(quasilinear_zero_field_splitting))
        
        return quasilinear_calibration_slope, quasilinear_zero_field_splitting

    def process_i1_i2_data(self, I1_sweeps, I2_sweeps):
        """
        Process I1 and I2 sweep data to extract frequencies and mean values per frequency.
        
        Args:
            I1_sweeps: StreamingList containing np.arrays created with np.stack([freqs, I1_data])
            I2_sweeps: StreamingList containing np.arrays created with np.stack([freqs, I2_data])
            
        Returns:
            tuple: (unique_frequencies, sigs_left_mean, sigs_right_mean)
        """
        all_frequencies = []
        all_I1_values = []
        all_I2_values = []
        
        # Extract data from all sweeps in I1_sweeps
        for sweep_array in I1_sweeps:
            frequencies = sweep_array[0]  # First row contains frequencies
            I1_values = sweep_array[1]    # Second row contains I1 values
            all_frequencies.extend(frequencies)
            all_I1_values.extend(I1_values)
            
        # Extract I2 values from all sweeps in I2_sweeps  
        for sweep_array in I2_sweeps:
            I2_values = sweep_array[1]    # Second row contains I2 values
            all_I2_values.extend(I2_values)
        
        # Convert to numpy arrays for easier manipulation
        all_frequencies = np.array(all_frequencies)
        all_I1_values = np.array(all_I1_values)
        all_I2_values = np.array(all_I2_values)
        
        # Get unique frequencies and calculate mean I1 and I2 for each frequency
        unique_frequencies = np.unique(all_frequencies)
        sigs_left_mean = np.zeros(len(unique_frequencies))
        sigs_right_mean = np.zeros(len(unique_frequencies))
        
        for i, freq in enumerate(unique_frequencies):
            freq_mask = all_frequencies == freq
            sigs_left_mean[i] = np.mean(all_I1_values[freq_mask])
            sigs_right_mean[i] = np.mean(all_I2_values[freq_mask])
            
        return unique_frequencies, sigs_left_mean, sigs_right_mean

    # Shivam: Change calculations to the latest variable names
    def regular_slope_extraction(self, unique_frequencies, sigs_left_mean, sigs_right_mean):
        # Use the processed mean values instead of DataFrame operations
        print("Test regular slope")
        
        sigs_diff = sigs_right_mean - sigs_left_mean

        # index of the minimum element (absolute value) of the average difference of I2 and I1
        # (Shivam: 0 point of I1-I2 graph)
        integer_index = np.abs(sigs_diff).argmin()
        
        # Calculate change in fluorescence using neighboring points
        if integer_index > 0 and integer_index < len(sigs_diff) - 1:
            change_fluor = sigs_diff[integer_index + 1] - sigs_diff[integer_index - 1]
            # Calculate change in frequency for the same points
            change_freq = unique_frequencies[integer_index + 1] - unique_frequencies[integer_index - 1]
        else:
            # Fallback: use constant frequency step assumption
            change_fluor = sigs_diff[1] - sigs_diff[0] if len(sigs_diff) > 1 else 0
            change_freq = 2 * (unique_frequencies[1] - unique_frequencies[0]) if len(unique_frequencies) > 1 else 1
            
        slope = change_fluor / change_freq  # change_freq in Hz
        return slope
    

    def quasilinear_slope_extraction(self, unique_frequencies, sigs_left_mean, sigs_right_mean):
        """
        Calculate quasilinear slope using processed frequency and intensity data.
        
        Args:
            unique_frequencies: Array of unique frequencies
            sigs_left_mean: Mean I1 values for each frequency
            sigs_right_mean: Mean I2 values for each frequency
            
        Returns:
            tuple: (slope, odmr_zfs) - slope and zero field splitting
        """
        sigs_diff = sigs_right_mean - sigs_left_mean
        sigs_add = (sigs_right_mean + sigs_left_mean) / 2

        sigs_norm = sigs_diff / sigs_add
        
        x_values = unique_frequencies
        y_values = sigs_norm
        
        # Shivam: Getting the indices of the desired frequency range endpoints and slicing our x and y values accordingly
        index_left = np.argmin(np.abs(unique_frequencies - self.left_frequency_slope))
        index_right = np.argmin(np.abs(unique_frequencies - self.right_frequency_slope))

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

    def handle_pulsestreamer(self, mgr):
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)
        mgr.Pulser.set_state_off()

    def download_excel(self):
        # save_excel(self.name)  # TODO: Implement save_excel function
        print('Excel download requested but save_excel function not implemented')
        # print('The name of the excel data:', self.name)
