###########################

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
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue
import collections


# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nspyre import InstrumentManager, DataSource, StreamingList
import math
import rpyc.utils.classic

from experiments.advancedtracking import AdvancedTracking


# nspyre


#from lantz.drivers.ni.ni_motion_controller import NIDAQMotionController

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)







class TemperatureVsTime():
    '''
    This class is meant to be an analogue to counts vs time and plot the temperature of the nanodiamond vs time
    with continuous green laser input.
    '''


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
        _logger.info('Created TemperatureVsTime instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed TemperatureVsTime instance.')

    
    #Shivam: This is reinstated because we need for the no feedback/tracking case measurement
    def create_channels(self, device, PS_clk_channel, APD_channel):
        data_channel = device + '/' + APD_channel
        clock_channel = '/' + device + '/' + PS_clk_channel
        return data_channel, clock_channel


    def initialize(self, mgr, sampling_rate,
                   timeout, time_per_scan, starting_temp, sb_MHz_2fq,
                   two_freq, odmr_frequency, rf_amplitude, clock_time, mwPulseTime,
                   cooling_delay, is_center_modulation,
                   activate_PID, activate_PID_no_sg_change, PID,
                   integral_history, number_jump_avg,
                   searchXYZ, max_search, min_search, search_PID,  
                   do_not_run_feedback, scan_distance, spot_size, 
                   diffusion_constant, infrared_on, infrared_power, heat_on_off_cycle,
                   warm_and_cool_scans):
        print("Cooling delay below:")
        print(cooling_delay)
        
        if infrared_on:
        
            ### Setup heating infrared laser
            self.infrared.modulation_power = infrared_power*1e3

            self.infrared.digital_modulation = True

            self.heating_scans, self.cooling_scans = eval(warm_and_cool_scans)

            # Shivam: CHECK IF THIS IS THE RIGHT CHANNEL CODE
            laser_channel = 'Dev1' + '/port0/line3'
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
        if sampling_rate <= 1 / mwPulseTime:
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

            self.spot_size = spot_size
            print("self.spot_size is " + str(self.spot_size))

            # Shivam: Initializing motion controller for data collection. CHECK IF FIRST LINE NEEDED
            mgr.DAQcontrol.create_counter()
            mgr.DAQcontrol.acq_rate = sampling_rate

            # Shivam: Parameters for tracking
            self.drift = [0, 0, 0]
            current_position=mgr.DAQcontrol.position
            self.XYZ_center = [current_position['x'],
                                current_position['y'],
                                current_position['z']]

        else: 
            self.search = None
            self.max_search = None
            self.min_search = None
            self.scan_distance = None
            self.spot_size = 0
            #Indices correspond to x, y, and z
            self.tracking_data = None
            mgr.DAQcontrol.create_counter()
            mgr.DAQcontrol.acq_rate = sampling_rate
            mgr.DAQcontrol.prepare_counting(sampling_rate, self.bufsize-1)

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
                mgr.sg.set_frequency(self.odmr_frequency)

                # Initialize advanced tracking variables
                # Shivam: Subtracted by 2 because of the way the buffer is sliced to keep equal photon exposure for I1 and I2 

                effective_buffer_size = self.bufsize - 2
                num_bins = effective_buffer_size / 2
                self.time_elapsed = num_bins * self.real_time_per_scan
                # Setting all advanced tracking variables into a vector array for x,y,z
                self.n_k = [0,0,0]
                self.p_k = [2 * diffusion_constant * self.time_elapsed] * 3
                current_position=mgr.DAQcontrol.get_position()
                self.x_k = [current_position['x'],
                            current_position['y'],
                            current_position['z']]
                print("x_k is " + str(self.x_k))

                # CHECK THE TUNING OF w
                self.w = self.spot_size ** 2

            else:
                self.frequencies = [(odmr_frequency - sb_MHz_2fq), (odmr_frequency + sb_MHz_2fq)]
                sg_frequency = (odmr_frequency - (sb_MHz_2fq + 5000))
                self.ps_frequencies = [freq - sg_frequency for freq in
                                    self.frequencies]  # (frequencies.to('Hz').m - sg_frequency)
                mgr.sg.set_frequency(sg_frequency)

                self.sequence = self.setup_LPvT(self.ps_frequencies, mwPulseTime, clock_time, time_per_scan, num_freq, rf_amplitude)
    
        return
    
    
    def check_appropriate_distance(self):
        # This function checks whether the scan distance is too small to cover the entire search range
        for i in range(3):
            # Multiplying self.search by 2 because the search range is from XYZ_center -self.search to XYZ_center + self.search
            if self.scan_distance[i] < 2 * self.search[i] / self.bufsize:
                print("ERROR: scan distance for index " + str(i) + " is too small, please decrease scan distance to at least " + str(self.search[i] / self.bufsize) + " nm.")
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





    def temptime(self, sampling_rate=50000, 
                   timeout=12, time_per_scan=1, starting_temp=25.0, sb_MHz_2fq='10.1010101', quasilinear_slope=0, 
                   two_freq=False, odmr_frequency=2.87e9, rf_amplitude=-20, clock_time=10e-9, mwPulseTime=50e-6, 
                   cooling_delay=0.0, is_center_modulation=True, data_download=False, 
                   activate_PID=False, activate_PID_no_sg_change=False, PID="[0.1,0.01,0]", PID_recurrence="[1,1,0]", 
                   integral_history=1, threshold_temp_jump=2, number_jump_avg=1,
                   searchXYZ="[0.5, 0.5, 0.5]", max_search="[1, 1, 1]", min_search="[0.1, 0.1, 0.1]", changing_search=False, search_PID="[0.5,0.01,0]",
                   search_integral_history=1, z_cycle=1, track_z=True,
                   do_not_run_feedback=False, scan_distance="[0.03, 0.03, 0.05]", spot_size=400e-9, advanced_tracking=False,
                   diffusion_constant=200, infrared_on=False, infrared_power=1e-4, heat_on_off_cycle="[True] + [False]*2",
                   warm_and_cool_scans="[30, 30]", dataset="temp_time", iterations=0):
        params={'quasilinear_slope': quasilinear_slope,
                'two_freq': two_freq,
                'odmr_frequency': odmr_frequency,
                'rf_amplitude': rf_amplitude,
                'clock_time': clock_time,
                'mwPulseTime': mwPulseTime,
                'cooling_delay': cooling_delay,
                'is_center_modulation': is_center_modulation,
                'data_download': data_download,
                'activate_PID': activate_PID,
                'activate_PID_no_sg_change': activate_PID_no_sg_change,
                'PID': PID,
                'PID_recurrence': PID_recurrence,
                'integral_history': integral_history,
                'threshold_temp_jump': threshold_temp_jump,
                'number_jump_avg': number_jump_avg,
                'searchXYZ': searchXYZ,
                'max_search': max_search,
                'min_search': min_search,
                'changing_search': changing_search,
                'search_PID': search_PID,
                'search_integral_history': search_integral_history,
                'z_cycle': z_cycle,
                'track_z': track_z,
                'do_not_run_feedback': do_not_run_feedback,
                'scan_distance': scan_distance,
                'spot_size': spot_size,
                'advanced_tracking': advanced_tracking,
                'diffusion_constant': diffusion_constant,
                'infrared_on': infrared_on,
                'infrared_power': infrared_power,
                'heat_on_off_cycle': heat_on_off_cycle,
                'warm_and_cool_scans': warm_and_cool_scans,
                'dataset': dataset,
                'iterations': iterations}
        with InstrumentManager() as mgr, DataSource(dataset) as data_source:
            self.initialize( mgr, sampling_rate,
                   timeout, time_per_scan, starting_temp, sb_MHz_2fq,
                   two_freq, odmr_frequency, rf_amplitude, clock_time, mwPulseTime,
                   cooling_delay, is_center_modulation,
                   activate_PID, activate_PID_no_sg_change, PID,
                   integral_history, number_jump_avg,
                   searchXYZ, max_search, min_search, search_PID,  
                   do_not_run_feedback, scan_distance, spot_size, 
                   diffusion_constant, infrared_on, infrared_power, heat_on_off_cycle,
                   warm_and_cool_scans)
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
                I1_dataset=StreamingList()
                I2_dataset=StreamingList()
                x_position=StreamingList()
                y_position=StreamingList()
                z_position=StreamingList()
                total_fluor_dataset=StreamingList()
                start_t=time.time()
                odmr_freq_dataset=StreamingList()
                for i in iterator:
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
                                
                                # time_elapsed = time.time() - start_t
                                # import pdb; pdb.set_trace()
                                feed_params={
                                    'buffer_size':self.bufsize,
                                    'index':index,
                                    'search_PID':search_PID,
                                    'max_search':max_search,
                                    'min_search':min_search,
                                    'sequence':self.sequence,
                                    'search':self.search,
                                    'scan_distance':scan_distance,
                                    'num_freq':num_freq,
                                    'do_not_run_feedback':do_not_run_feedback,
                                    'read_timeout':self.read_timeout,
                                    'spot_size':self.spot_size,
                                    'advanced_tracking':advanced_tracking,
                                    'changing_search':changing_search,
                                    'search_error_array':search_error_array,
                                    'search_integral_history':search_integral_history,
                                    'sampling_rate':sampling_rate,
                                    'drift':self.drift,
                                    'previous_fluors':self.previous_fluors,
                                    'run_ct':self.run_ct,
                                    'x_k':self.x_k, 
                                    'p_k':self.p_k, 
                                    'n_k':self.n_k,
                                    'w':self.w, 
                                    'diffusion_constant':self.diffusion_constant, 
                                    'time_elapsed':self.time_elapsed

                                }
                                self.AdvancedTracking=AdvancedTracking(self.queue_to_exp, self.queue_from_exp)
                                current_time = time.time()
                                if advanced_tracking:
                                    self.search, temp_data, total_fluor, search_error_array, self.XYZ_center, self.drift, self.x_k, self.p_k, self.n_k = self.AdvancedTracking.one_axis_measurement(**feed_params)
                                else:
                                    self.search, temp_data, total_fluor, search_error_array, self.XYZ_center, self.drift=self.AdvancedTracking.one_axis_measurement(**feed_params)
                                print("MAIN: search is " + str(list(self.search)))
                                # current_time=time.time()
                                I1_dataset.append(np.array([np.array(current_time-start_t), np.array(temp_data[0])]))
                                I2_dataset.append(np.array([np.array(current_time-start_t), np.array(temp_data[1])]))
                                x_position.append(np.array([np.array(current_time-start_t), np.array(self.XYZ_center[0])]))
                                y_position.append(np.array([np.array(current_time-start_t), np.array(self.XYZ_center[1])]))
                                z_position.append(np.array([np.array(current_time-start_t), np.array(self.XYZ_center[2])]))
                                total_fluor_dataset.append(np.array([np.array(current_time-start_t), np.array(total_fluor)]))
                                odmr_freq_dataset.append(np.array([np.array(current_time-start_t), np.array(self.odmr_frequency)]))
                                I1_dataset.updated_item(-1)
                                I2_dataset.updated_item(-1)
                                x_position.updated_item(-1)
                                y_position.updated_item(-1)
                                z_position.updated_item(-1)
                                total_fluor_dataset.updated_item(-1)
                                odmr_freq_dataset.updated_item(-1)

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
                                        mgr.sg.set_frequency(int(self.odmr_frequency))
                                        # Shivam: Need to check how long it takes to change frequency and make sure the code does not loop again before that

                                else:
                                    self.sequence = self.change_pulse_sequence(freq_change)
                        
                                quasilinear_slope_e9 = quasilinear_slope * 1e9

                                # if do_not_run_feedback:

                                data_source.push({
                                        'params':params,
                                        'datasets': { "I1": I1_dataset, 
                                                     "I2": I2_dataset, 
                                                     "x_pos": x_position, 
                                                     "y_pos": y_position, 
                                                     "z_pos": z_position, 
                                                      "total_fluor": total_fluor_dataset, 
                                                      "odmr_freq": odmr_freq_dataset
                                                       }

                                })
                                    
                                
                                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                    # the GUI has asked us nicely to exit
                                    self.finalize(data_download,mgr, data_download, do_not_run_feedback, infrared_on)
                                    return
                                time.sleep(cooling_delay)
            self.finalize(data_download,mgr, data_download, do_not_run_feedback, infrared_on)


    def ready_center_pulse_sequence(self, mgr,time_per_scan, mwPulseTime, clockPulse, sideband_frequency, rf_amplitude):
        ns_read_time = int(round(mwPulseTime*1e9))
        ns_clock_time = int(round(clockPulse*1e9))
        seq, self.new_pulse_time = mgr.Pulser.odmr_temp_calib_no_bg(ns_read_time, ns_clock_time, sideband_frequency)

        mgr.sg.set_rf_amplitude(rf_amplitude)
        mgr.sg.set_mod_type('QAM')
        mgr.sg.set_rf_toggle(True)
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_mod_function('external')

        # Shivam: streamer.total_time is from the odmr_temp_calib function from dr_pulsesequences_Sideband
        # And it is the total time for one pulse sequence (2 * new_pulse_time)
        total_time=2*mwPulseTime
        self.run_ct = math.ceil(time_per_scan / total_time)
        # This is an important variable to know how long is spent collecting photons at one center frequency
        self.real_time_per_scan = self.run_ct * total_time

        return seq, self.new_pulse_time
    

    def setup_LPvT(self, mgr, freqs, mwPulseTime, clock_time, time_per_scan, num_freq, rf_amplitude):
        ns_read_time = int(round(mwPulseTime*1e9))
        ns_clock_time = int(round(clock_time*1e9))
        

        mgr.sg.set_rf_amplitude(rf_amplitude)
        mgr.sg.set_mod_type('QAM')
        mgr.sg.set_rf_toggle(True)
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_mod_function('QAM', 'external')
        total_time=2*len(freqs)*mwPulseTime
        temp_sequence = mgr.Pulser.setup_LPvT(freqs, ns_read_time, ns_clock_time, num_freq)
        self.run_ct = math.ceil(time_per_scan / total_time) + 1
        # import pdb; pdb.set_trace()
        print('\nThis is my sequence!\n', temp_sequence)
        return temp_sequence


    def change_pulse_sequence(self, mgr, freq_change):

        # self.streamer.clock_time = int(round(clock_time.to('ns').m))
        # self.streamer.probe_time = int(round(probe_time.to('ns').m))
        # sideband_adjustment = odmr_frequency - new_odmr_freq
        print('\nBefore changing pulse frequencies:    ', self.ps_frequencies)
        self.ps_frequencies = list(np.array(self.ps_frequencies) - freq_change)
        print('After changing pulse frequencies:    ', self.ps_frequencies, '\n')
        tempReadout = mgr.Pulser.setup_LPvT(self.ps_frequencies, 2)
        # self.run_ct = math.ceil(self.time_per_scan.to('ns').m / self.streamer.total_time) + 1
        # import pdb; pdb.set_trace()
        return tempReadout
    
    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        # Shivam: Convert FWHM (width) to standard deviation for Gaussian plot
        if a < 0 or width < 0 or b < 0:
            return math.inf
        sigma = width / (np.sqrt(8 * np.log(2)))
        return a * np.exp(-np.square((xs - x) / (np.sqrt(2) * + sigma))) + b




    def finalize(self, mgr, data_download, do_not_run_feedback, infrared_on):
        # self.urixyz.daq_controller.ao_motion_task.stop()
        # self.urixyz.daq_controller.collect_task.stop()
        
        if infrared_on:
            self.laser_ctrl_task.close()


        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)
        print("Turning off laser")
        mgr.Pulser.reset()
        #self.streamer.Pulser.constant(([7],0.0,0.0))
        mgr.Pulser.isStreaming()

                ## turns off instruments
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_mod_toggle(False)

        if do_not_run_feedback:
            print("Closing counter task")

            self.current_counter_task.stop()

            self.current_counter_task.close()

        if data_download:
            save_excel(self.name)
            print('The name of the excel data:', self.name)

