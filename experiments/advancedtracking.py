###########################
# imports
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
from nspyre import InstrumentManager
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue
import collections
import math


# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader


# nspyre


#from lantz.drivers.ni.ni_motion_controller import NIDAQMotionController

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

#Jacob's advice
import rpyc

class AdvancedTracking():
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
        _logger.info('Created AdvancedTracking instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed AdvancedTracking instance.')
    def one_axis_measurement(self,
                                buffer_size, index, search_PID, max_search, min_search, 
                             sequence, search, scan_distance, num_freq, do_not_run_feedback, 
                             read_timeout, spot_size, advanced_tracking, changing_search, 
                             search_error_array, search_integral_history,
                             drift=(0,0,0), previous_fluors=(0,0,0), 
                             x_k=None, p_k=None, n_k=None, w=None, diffusion_constant=None, time_elapsed=None):
        self.previous_fluors = previous_fluors
        self.max_search = max_search
        self.min_search = min_search
        self.drift=drift
        if advanced_tracking:
            if x_k is None:
                print("Advanced tracking is enabled but no initial value for x_k was provided.")
                return
            if p_k is None:
                print("Advanced tracking is enabled but no initial value for p_k was provided.")
                return
            if n_k is None:
                print("Advanced tracking is enabled but no initial value for n_k was provided.")
                return
            if w is None:
                print("Advanced tracking is enabled but no initial value for w was provided.")
                return
            if time_elapsed is None:
                print("Advanced tracking is enabled but no initial value for time_elapsed was provided.")
                return
            self.x_k= x_k
            self.p_k= p_k
            self.n_k= n_k
            self.w = w
            self.diffusion_constant = diffusion_constant
            self.time_elapsed = time_elapsed
        
        self.search_kp, self.search_ki, self.search_kd = eval(search_PID)
        with InstrumentManager() as mgr:
            # if trackz and (index == 2):
            #     # Shivam: What is the significance of this if statement?
            #     if ((sweep + lp_idx * (self.heating_scans + self.cooling_scans)) % z_cycle != 0):
            #         return sequence, search, np.array([0] * num_freq)

            ## in this is 180 ms of lag
            self.sequence=sequence
            self.XYZ_center= mgr.DAQcontrol.get_position()
            for i in list(index):
                data = self.read_stream_flee( mgr, index, search, buffer_size, scan_distance, num_freq, read_timeout)

                ## confirmed, here I have 180-200 ms of lag

                ## after this is 70-130 ms of lag        
                tracking_data, track_steps, temp_data, num_bins = self.process_data(i, data, search)

                self.data_analysis(mgr, tracking_data, track_steps, index, search, do_not_run_feedback, spot_size, num_bins, advanced_tracking, 
                 changing_search, search_error_array, search_integral_history)
                mgr.DAQcontrol.move({'x': self.XYZ_center[0], 'y': self.XYZ_center[1], 'z': self.XYZ_center[2]})
                print('\nHere is where the laser is currently pointing:', mgr.DAQcontrol.position)
                for i, num in enumerate(search):
                    search[i] *= 0.9 if abs(self.drift[i]) < (2 / 5 * search[i]) else 1.2 if abs(self.drift[i]) > (
                            7 / 10 * search[i]) else 1
            if advanced_tracking:
                return search, temp_data, search_error_array, self.XYZ_center, self.drift, self.previous_fluors, self.x_k, self.p_k, self.n_k
            return  search, temp_data, search_error_array, self.XYZ_center, self.drift, self.previous_fluors
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
                                    len(tracking_data))
            
        else:
            tracking_data = None
            track_steps = None
            
        return tracking_data, track_steps, temp_data, num_bins
    def read_stream_flee(self, mgr, index, search, buffer_size, scan_distance, num_freq, read_timeout):
        ## total this has 180 ms of lag.
        # time_track = time.time()
        xyz_steps = np.linspace(self.XYZ_center[index] - search[index], self.XYZ_center[index] + search[index],
                                buffer_size)
                                
        # Shivam: Assigns the entire XYZ_center array to both newly defined arrays
        pos_center_st = self.XYZ_center[:]
        pos_center_end = self.XYZ_center[:]
        pos_center_st[index] = xyz_steps[0]
        pos_center_end[index] = xyz_steps[-1]

        distance_of_sweep = np.abs(pos_center_end[index] - pos_center_st[index])
        print(distance_of_sweep)
        print(scan_distance)
        number_of_steps = math.ceil(distance_of_sweep / scan_distance[index])
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
        remaining_buffer = mgr.DAQcontrol.prepare_line_scan(buffer_size, buffer_allocation,
                                            {'x': pos_center_st[0], 'y': pos_center_st[1], 'z': pos_center_st[2]},
                                            {'x': pos_center_end[0], 'y': pos_center_end[1], 'z': pos_center_end[2]},
                                            number_of_steps)

        ###Before this, around .12 seconds have elapsed

        'start the pulse streamer and the task close to simultaneously'

        mgr.Pulser.stream_sequence(self.sequence, self.runs)
        ## this is 35 ms all on its own. 
        'the data is sorted into a i,j,k dimension tensor. num_bins represents i, j is automatically 8 due to the 8 pulses for the MW. k is remainder of the total data points over i*j,'
        # Shivam: Changed from num_freq * 2 to num_freq because we are not doing background collection
        scan_data = mgr.DAQcontrol.start_line_scan(read_timeout)

        mgr.Pulser.reset()
        ## this is 5 miliseconds
        # print('time for read stream flee:', time.time() - time_track)

        ## pulser stream to pulser reset has 60ms delay.
        
        return rpyc.utils.classic.obtain(scan_data), buffer_allocation, remaining_buffer
    
    def data_analysis(self, mgr, XYZ_center, tracking_data, track_steps, index, search, do_not_run_feedback, spot_size, num_bins, advanced_tracking, 
                 changing_search, search_error_array, search_integral_history):
        print("/n/n In data analysis/n")
        #import pdb; pdb.set_trace()
        self.previous_fluors[index-1] = self.total_fluor
        self.total_fluor = np.sum(tracking_data)

        # Shivam: Attempt to fix search radius issue when theres a rapid change in position, but not working well yet
        # if self.total_fluor / self.previous_fluors[index] < 0.5:
            # HAVE MAX SEARCH CONDITION
            # self.search[index] *= 4
            # return search, search_error_array

        print("Total Fluorescence is " + str(self.total_fluor))
        if do_not_run_feedback:
            return search, search_error_array
        
        print('Out of XYZ = [0,1,2], this is the', index, 'axis')
        # if index == 2:
        #     print("Track steps is " + str(track_steps))
        #     print("Tracking data is " + str(tracking_data))
        #     max_count_position = track_steps[np.argmax(tracking_data)]
        #     self.drift[index] = Q_(max_count_position, 'um') - XYZ_center[index]
        #     XYZ_center[index] = Q_(max_count_position, 'um')
        #     self.urixyz.daq_controller.move({'x': XYZ_center[0], 'y': XYZ_center[1], 'z': XYZ_center[2]})
        #     print("xyz positions set are " + str(XYZ_center[0]) + str(XYZ_center[1]) + str(XYZ_center[2]))
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
                        self.drift[index] = plot_center_fit - XYZ_center[index]
                        XYZ_center[index] = self.advanced_tracking(plot_center_fit, index)

                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    self.drift[index] = max_count_position - XYZ_center[index]
                    XYZ_center[index] =self.advanced_tracking(max_count_position, index)     
                    "CHECK WHAT THIS BECOMES"
            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = max_count_position - XYZ_center[index]
                XYZ_center[index] = self.advanced_tracking(max_count_position, index)

            print("debugging, XYZ center is " + str(XYZ_center))
            
            mgr.DAQcontroler.move({'x': XYZ_center[0], 'y': XYZ_center[1], 'z': XYZ_center[2]})
            print("xyz positions set are " + str(XYZ_center[0]) + str(XYZ_center[1]) + str(XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', mgr.DAQcontrol.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_array is " + str(search_error_array))
                
                search_error_pre = search_error_array[index][0]
                # import pdb; pdb.set_trace()

                # Target value for search radius is twice the drift
                search_error = (-1) * (search[index] - np.abs(self.drift[index])) * 2

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_array]
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
                search[index] =  (search[index] + search_change)

                if search[index] > self.max_search[index]:
                    print("Max search radius for index " + str(index) + " reached.")
                    search[index] = self.max_search[index]

                if search[index] < self.min_search[index]:
                    print("Min search radius for index " + str(index) + " reached.")
                    search[index] = self.min_search[index]

                print("Search radius for index " + str(index) + " is updated to " + str(search[index]))


            else:
                search_error_array = None

    

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
                        print("debugging, XYZ center is " + str(XYZ_center))
                        print("debugging, plot center fit is ", plot_center_fit, 'um')
                        # import pdb; pdb.set_trace()
                        self.drift[index] = plot_center_fit - XYZ_center[index]
                        
                        
                        print("debugging, drift is " + str(self.drift[index]))
                        
                        XYZ_center[index] = plot_center_fit

                    
                else:
                    print('Gaussian fit max is out of scanning range. Using maximum point instead')
                    max_count_position = track_steps[np.argmax(tracking_data)]
                    print("debugging, XYZ center is " + str(XYZ_center))
                    print("debugging, max count position is ", max_count_position, 'um')
                    #import pdb; pdb.set_trace()
                    self.drift[index] = max_count_position - XYZ_center[index].m
                    
                    print("debugging, drift is " + str(self.drift[index]))

                    XYZ_center[index] = max_count_position

                print("debugging, XYZ center is " + str(XYZ_center))
                print("drift is " + str(self.drift[index]))


            except:
                print('no Gaussian fit')
                max_count_position = track_steps[np.argmax(tracking_data)]
                self.drift[index] = max_count_position - XYZ_center[index].m
                print("drift is " + str(self.drift[index]))
                XYZ_center[index] = max_count_position

                print("debugging, XYZ center is " + str(XYZ_center))

            mgr.DAQcontrol.move({'x': XYZ_center[0], 'y': XYZ_center[1], 'z': XYZ_center[2]})
            print("xyz positions set are " + str(XYZ_center[0]) + str(XYZ_center[1]) + str(XYZ_center[2]))
            print('\nHere is where the laser is currently pointing:', mgr.DAQcontrol.position)

            if changing_search:
                search_change = 0.0
                ### Shivam: this is the new search change which is adaptive with PID control that has a target 
                # to set search radius to double the drift
                n = search_integral_history
                print("search_error_array is " + str(search_error_array))
                # Target value for search radius is twice the drift
                search_error_pre = search_error_array[index][0]
                #import pdb; pdb.set_trace()
                search_error = (-1) * (search[index] - np.abs(self.drift[index]) * 2)

                print("drift is " + str(self.drift[index]))
                print("search_error is " + str(search_error))

                # The below line looks like: 
                # [deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0]), deque([0.0, 0.0, 0.0, 0.0, 0.0])]
                
                search_error_deques = [collections.deque(row) for row in search_error_array]
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
                search[index] =  search[index] + search_change

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
        c_k = gaussian_center
        
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


    def gaussian(self, xs, a=1, x=0, width=1, b=0):
        # Shivam: Convert FWHM (width) to standard deviation for Gaussian plot
        if a < 0 or width < 0 or b < 0:
            return math.inf
        sigma = width / (np.sqrt(8 * np.log(2)))
        return a * np.exp(-np.square((xs - x) / (np.sqrt(2) * + sigma))) + b
