'''
A Python File for auxiliary functions for the WF Spyrelets
Also describes the file structure of the WF Spyrelets

Structure:
Imports
Params
Initialization
 = > General Param Formatting
 = > SG Init
 = > Camera Init
 = > Sequence Init
 = > Experiment Specific Init
 = > Cooldown if necessary
 = > Checks for validity
 = > Data formatting, pickle prep
Main:
 = > Optimize gain/ take images to reset camera dynamics
 = > Trackpy, Autofocus prep
 = > Begin Experiment
    => Prepare camera, SG
    => main loop:
        => Set SG frequency
        => Acquire data (with GetPic or GetPic_Alternating)
        => Go through the new data and format it. Add it to unsaved imgs.
        => Track NDs
        => Analyze signals
        => Acquire (dependent on process, but likely involves saving data in a dict and calling self.acquire)
    => Save any remaining unsaved images for this sweep if save_image is 'raw_images' or 'tracking'
Finalize:
 = > SG off
 = > Cam close
 = > Additional Analysis
 = > Data saving
 = > Final Print Statements

Helper Functions:
 = > cool_loop: for cooling camera with user input
    = > GetPicSimple: Runs an acquisition of n pictures over a given sequence, returns pictures as a parsed list of 1D arrays of length 'im_size'. Automatically coordinates self.window. 
    = > GetPic: Similar to GetPicSimple but with more options for saving images during acquisition.
    = > GetPic_Alternating: Similar to GetPic but alternates between two sequences for balanced labels, with an optional sleep time between them. Also has options for saving images during acquisition.
    = > img_1D_to_2D: Reshapes a 1D image array into a 2D array with given dimensions.
    = > gain_optimization: Runs a loop to optimize camera gain based on the max pixel value of acquired images, with options for saving images during the process.
    = > identify_NDs: Uses trackpy to identify NDs in a given image, with options for parameters and whether to include a background point.
    = > track_NDs: Uses simple brightest-spot detection to track the locations of NDs across images, with options for search radius.
    = > analyze_sig: Experiment specific. Analyzes the signals from the tracked NDs in a given set of images, returns whatever metrics are relevant for the experiment.

TODO: Plotting functions
'''
#### IMPORTS ###############################################################################################

## Standard
import numpy as np
from scipy.optimize import curve_fit 
import time
import pickle
import os

## Trackpy
from scipy.ndimage import gaussian_filter
import trackpy as tp
from skimage.feature import blob_log
from scipy.ndimage import maximum_filter, label, find_objects

## NSpyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors, cyclic_colors # Unused?
from nspyre.definitions import Q_

## Camera
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

## PID [Not Always Used]
from collections import deque 

class WFSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'psWF',
        'urixyz',
    ]

    PARAMS = {
        #### ALL-WF-PARAMS
        ## Pulse Timings
        'exp_time':{'type':float,'units':'s','suffix': 's','default': 75e-3,},
        'readout_time':{'type':float,'units':'s','suffix': 's','default': 15e-3,}, #must be greater than 39ms for EXTERNAL_EXPOSURE
        ## Routine
        'sweeps':{'type': int, 'default': 3}, 
        'label':{'type': str, 'default': '[t, 1, 0, 1, 0]'}, #'[t, 1, 0, 2, 0]' for I1I2
        'frequencies':{'type': str,'default': '[2.868e9, 2.871e9, 11]'}, #I1I2 Only | [start, stop, num_points]
        ## Gain
        'gain':{'type':int,'default': 2,'positive': True}, #EM gain for camera, goes from 1-272
        'gain_setting':{'type': list,'items': ['optimize', 'override', 'use current'], 'default': 'optimize'},
        ## Cam Settings
        'cooler':{'type': str, 'default': '(False, 20)'},
        'cam_trigger':{'type': list,'items': ['EXTERNAL_EXPOSURE','EXTERNAL_FT'], 'default': 'EXTERNAL_FT'},
        ## SG
        'rf_amplitude':{'type': float,'default': -15,},
        ## Data Acquisition
        'ROI_xy':{'type': str, 'default': '[(512,512)]'},
        'alt_label': {'type': bool,'default': False}, # Alternate label to get more balanced results
        'alt_sleep_time': {'type': float,'default': 0,'suffix': 's','units': 's'}, #sleep time between alternating labels, if alt_label is True
        'trackpy_params': {'type': str,'default': "{'trackpy': True, 'sigma': 1.2, 'r_ND': 7, 'min_dist': 8, 'buffer': 35, 'bg_pts': []}"},
        'focus_bool': {'type': bool, 'default':True}, # Whether to use the first ND as a focus point and keep it in the center of the image. If False, no autofocus is done and the first ND is treated like all the others.
        ## Saving
        'data_path': {'type': str,'default': 'Z:\\biosensing_setup\\data\\Widefield\\no_path_set'},
        'save_image':{'type': list,'items': ['no_save', 'tracking','raw_images','raw_images_safe','[x]per_sweep','[x]all_sweep'], 'default': 'no_save'}, # determines how images are compressed when saved: do not save, save every image, save a float16 image per sweep, or save a float16 image per frequency
        'data_download':{'type': bool,},
        ## Debug
        'shutdown': {'type': bool, 'default': True}, # Whether to shut down the camera SDK at the end of the experiment. May want to turn off for debugging to avoid needing to re-initialize the camera for each run.
        'verbose': {'type': bool, 'default': True},
        'window_params': {'type' : str, 'default' : "{'interval': 0, 'all_ROI': False, 'r_display': 16}"}, #parameters for display window updating
        'Misc': {'type': str,'default': "{'DEBUG':False}" },
        

        #### VARIABLE-PARAMS, DEPENDENT ON EXPERIMENT.
        ## Routine
        'uw_duty':{'type': float,'default': 1,}, # ODMR   
        'uw_rep':{'type': int,'default': 50,}, # ODMR
        'mode':{'type': list,'items': ['QAM','AM'  ], 'default': 'QAM'}, # ODMR
        'routine':{'type': str, 'default': '[2,3,100,0,-1]'}, #runs, sweeps, two-pt interval, two-pt averaging, total reps | I1I2_Track (w/ ODMR)
        'sideband': {'type': float,'units':'Hz','suffix': 'Hz','default': 14e6,}, #I1I2_ODMR, I1I2_Track
        'ZFS':{ 'type':float,'units':'Hz','suffix': 'Hz','default': 2.86878e9,}, #I1I2_Track
        'QLS':{'type':str,'default': '[-5e-9]',}, #I1I2_Track
        'QL_range': {'type': str,'default': '[2.868e9, 2.871e9]',}, #I1I2
        'end_ODMR':{'type': bool, 'default': False}, #I1I2_Track (w/ ODMR)
        'PID': {'type': str, 'default': "{'Kp':0.03, 'Ki': 0.005, 'Kd':0.01, 'Mem': 15, 'Mem_decay': 2.0}"}, #I1I2_Track
    }

    #### INIT HELPER FUNCTIONS ###############################################################################################
    ## Param Setting Functions (set variables)
    def set_pulse_self_params(self, exp_time, readout_time, trigger_time, buffer_time):
        self.exp_time = exp_time.m * 1e9 # nanoseconds
        self.readout_time = readout_time.m * 1e9 # nanoseconds
        self.trigger_time = trigger_time * 1e9 # nanoseconds
        self.buffer_time = buffer_time * 1e9 # nanoseconds
        ## timeout
        self.pulse_len = (self.exp_time + self.readout_time + self.buffer_time) * 1e-9 # seconds
        return

    def set_windowing_self_params(self, window_params):
        window_params = eval(window_params)
        self.window_interval = window_params.get('interval', 0)
        self.ct_for_window = 0
        self.window = False    
        self.all_ROI = window_params.get('all_ROI', False)         
        self.r_display = window_params.get('R_display', 16)
        return

    def set_ND_self_params(self, ROI_xy, r_track, r_targ):
        self.ND_list = eval(ROI_xy)
        self.r_track = r_track                    #(Hardcoded) | radius for tracking
        self.r_targ = r_targ                         #(Hardcoded) | radius for summing
        self.z_pos = self.urixyz.daq_controller.position['z'].to('um').m
        return
    
    def set_label_self_params(self, label, alt_label): # TEMPLATE
        # TEMPLATE
        t = 't' # Needed to parse apart 't' (throwaway) pulses in input
        self.label = eval(label)
        self.label_inv = []
        if alt_label:
            for pulse in self.label:
                pass # Dependent on protocol
        self.full_label = self.label+ self.label_inv
        self.full_label_filtered = [pulse for pulse in self.full_label if pulse != 't']
        raise NotImplementedError('Label initialization is highly dependent on the experiment and protocol. Please implement this function, or initialize self.label directly in the initialize function.')
    
    def set_timeout_param(self):
        timeout_limit_min = int(len(self.label) * self.pulse_len/0.05)+1
        self.timeout_limit = timeout_limit_min + self.Misc.get('timeout_limit', len(self.label) * 3) # adds 150 ms per pulse.
        if self.debug or self.verbose: print(f'Timeout limit for main loop acquisition set to {self.timeout_limit} ({self.timeout_limit * 0.05} s). \n[ min: {timeout_limit_min} ({timeout_limit_min*0.05} s) ]')
    ## Initialization Functions (set up devices and more complex variables)
    def init_sg(self, rf_amplitude): # TEMPLATE
        self.sg.rf_amplitude = rf_amplitude
        raise NotImplementedError('SG initialization may require additional parameters depending on the experiment and protocol. Please implement this function, or initialize the SG directly in the initialize function.')
    
    def init_seq(self, alt_label): # TEMPLATE
        self.seq_key = ... # Dependent on protocol
        # EX...
        # self.psWF.I1I2(..., key = seq_key) # Dependent on protocol
        # self.psWF.ODMR(..., key = seq_key) # Dependent on protocol
        if alt_label:
            ... # Dependent on protocol
            self.alt_key = ...
        self.gain_key = 'gain_seq'
        self.n_gain = 2                                      #(Hardcoded) | number of pulses in gain sequence, should be at least 2 to get a sense of dynamics
        self.psWF.prep_gain_seq(self.n_gain,self.exp_time, self.readout_time, trig = self.trigger_time, buff = self.buffer_time, key = self.gain_key)
        raise NotImplementedError('Sequence initialization is highly dependent on the experiment and protocol. Please implement this function, or initialize the sequences directly in the initialize function.')

    def init_data_saving(self, data_path, data_download, save_image):
        self.data_path = data_path
        if(data_download or save_image!='no_save'):
            if(not os.path.isdir(self.data_path)):
                os.mkdir(self.data_path)
            else:
                self.data_path = self.data_path+f'_{time.time()}'
                os.mkdir(self.data_path)
        self.latest_imgs = [] # useful for saving
        return

    def init_camera(self, cam_trigger):
        self.sdk = atmcd("")  # Load the atmcd library
        self.sdk_codes = atmcd_codes
        if self.sdk.GetStatus()[0] == 20075:
            ret = self.sdk.Initialize("")  # Initialize camera
            print("Function Initialize returned {}".format(ret))
        self.sdk.SetVSSpeed(3)
        self.sdk.SetHSSpeed(0,0) 
        self.sdk.SetAcquisitionMode(self.sdk_codes.Acquisition_Mode.KINETICS) #Taking a series of pulses
        self.sdk.SetReadMode(self.sdk_codes.Read_Mode.IMAGE) #reading pixel-by-pixel with no binning
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            self.sdk.SetTriggerMode(self.sdk_codes.Trigger_Mode.EXTERNAL_EXPOSURE_BULB)
            self.trigger_time = self.exp_time
            if self.readout_time<0.059 * 1e9:
                print('WARNING readout time should be at least 59 ms in pulse-length-exposure mode')
        elif cam_trigger == 'EXTERNAL_FT':
            self.sdk.SetTriggerMode(self.sdk_codes.Trigger_Mode.EXTERNAL) 
            # exposure_min = 0.046611 * 1e9 # hardware limited minimum exposure in FT mode
            # if self.exp_time < exposure_min:
            #     print(f'exposure must be at least {exposure_min*1000} ms.')
            #     raise Exception()
            if self.exp_time < self.trigger_time:
                print(f'WARNING exposure time {self.exp_time/1e6} ms is less than trigger time {self.trigger_time/1e6} ms. This may cause issues due to coding. Need to understand minimum trigger length.')
                raise Exception()
            elif self.exp_time + self.readout_time < 0.08 * 1e9:
                print('WARNING May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            if self.readout_time<0.005 * 1e9:
                print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
            self.sdk.SetExposureTime(self.exp_time / 1e9) 
            self.sdk.SetFrameTransferMode(1) 

        (ret, xpixels, ypixels) = self.sdk.GetDetector()
        self.sdk.SetImage(1, 1, 1, xpixels, 1, ypixels) #defining image
        #self.sdk.SetBaselineClamp(1)
        self.sdk.SetShutter(1,self.sdk_codes.Shutter_Mode.PERMANENTLY_OPEN,27,27) #Open Shutter
        return
    ## Process Functions (functional)
    def cool_loop(self, camera, temp):
        ret = camera.SetTemperature(temp)
        print(f"Function SetTemperature returned {ret} target temperature {temp}")
        print('Input "c" to continue without waiting for stabilization. Input "r" or anything else to refresh. ' \
        'Input "X" to exit. Input "A" to auto-wait for stabilization.')
        ret = camera.CoolerON()
        ct = 0
        inp = ''
        while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED and inp != 'c':
            ct = ct%3
            (ret, temperature) = camera.GetTemperature()
            if inp != 'A':
                inp = input("Function GetTemperature returned {}, current temperature = {}".format(
                    ret, temperature))
            elif inp == 'X':
                raise Exception('Exiting per user request during cooldown')
            else: 
                time.sleep(5)
                print("Function GetTemperature returned {}, current temperature = {}{}".format(
                ret, temperature, '.'*(ct+1)+ ' '*3), end='\r')
            ct+=1
        return
    ###########################################################################################################################

    def initialize(self, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, ROI_xy, decay_routine, alt_label, alt_sleep_time, trackpy_params, focus_bool,
                   data_path, save_image, data_download, shutdown, verbose, window_params, Misc
                   ):
        
        # print('Initializing EXPERIMENT')
        
        # #### General Param Formatting: ###############################################
        # ## Runtime
        # self.t0 = time.time()
        # self.Misc = eval(Misc)  # Must always be initialized as one of first variables, since other variables can check Misc for overrides. Any self.Misc.get('var', default) is a 
        #                         # hardcoded value that can be overridden by the user through the Misc dict in the params.
        # self.verbose = verbose
        # self.debug = self.Misc.get('DEBUG', False)
        # ## Camera Timings
        # self.set_pulse_self_params(exp_time, readout_time, self.Misc.get('trigger_time', 0.010), self.Misc.get('buffer_time', 0.005)) # self.exp_time | self.readout_time | self.trigger_time | self.buffer_time | self.pulse_len
        # ## Windowing
        # self.set_windowing_self_params(window_params) # self.window_interval | self.ct_for_window | self.window | self.all_ROI | self.r_display
        # ## NDs
        # self.set_ND_self_params(ROI_xy, self.Misc.get('r_track', 10), self.Misc.get('r_targ', 7)) #  self.ND_List | self.r_track | self.r_targ | self.z_pos
        # ## Labelling
        # self.set_label_self_params(label, alt_label) # self.label | self.label_inv | self.full_label
        # ## Timeout
        # self.set_timeout_param() # self.timeout_limit
        # ## Routine
        # freqs = np.linspace(eval(frequencies)[0], eval(frequencies)[1], eval(frequencies)[2], endpoint = True)
        # self.sg_freqs = Q_(freqs,'Hz')
        # ## Trackpy 
        # self.trackpy_params = eval(trackpy_params)
        # #### SG init ########################################################################
        # self.init_sg(rf_amplitude) # self.sg | self.rf_toggle | self.rf_amplitude | self.sg.mod_toggle | self.sg.mod_function | self.sg.mod_type | self.sg.AM_mod_depth
        # #### Cam init ########################################################################
        # self.init_camera(cam_trigger) # self.sdk | self.sdk_codes | camera initialized and ready to acquire
        # #### Seq init ########################################################################
        # self.init_seq(alt_label) # self.seq_key | self.alt_key (if alt_label) | self.gain_key | sequences initialized and ready to acquire
        # #### Experiment Specific Init #####################################################################
        # #### Cooldown if necessary ########################################################################
        # do_cool, temp = eval(cooler)
        # if do_cool: self.cool_loop(self.sdk, temp)
        # #### Checks for validity ################################################
        # # Dependent on protocol
        # #### Data formatting, pickle prep ###############################################
        # self.init_data_saving(data_path, data_download, save_image) # self.data_path | self.latest_imgs

        print('Initialization finished')
    
    #### MAIN HELPER FUNCTIONS ###############################################################################################
    ## Initialization Functions (set up devices and more complex variables) and Param Setting Functions
    def init_gain(self, gain, gain_setting, ideal_pixel_range, max_checks, max_gain, gain_wait_time, img_cycles_no_gain_optimization, save = 'no_save'):
        '''
        gain: initial gain to start optimization at, or gain to set if not optimizing.
        gain_setting: 'optimize' or 'override'. Whether to optimize gain or just set it to the input value. 'preset' uses whatever gain value is currently set. 'override' will not truly override if gain is already at input value.
        ideal_pixel_range: tuple of (min, max) pixel values to aim for during optimization. If max pixel value is below min, gain will be raised. If above max, gain will be lowered.
        max_checks: maximum number of times to check the gain during optimization before giving up and moving on with the current gain value.
        max_gain: maximum gain value to allow during optimization before giving up and moving on with the current gain value. Should be set based on experience with the camera and the sample, to avoid setting a gain that is too high and could damage the camera or give unusable images.
        gain_wait_time: time to wait after setting gain before acquiring image to check gain, in seconds. Should be long enough to allow camera to get ready to acquire again.
        img_cycles_no_gain_optimization: number of image acquisition cycles to run if not optimizing gain, to reset camera dynamics. Should be at least 2 to reset camera dynamics.
        
        
        '''

        ## Process
        self.sdk.SetNumberKinetics(self.n_gain)
        max_value = 0
        ct = 0
        if gain_setting == 'optimize':
            self.gain = gain
            self.sdk.SetEMCCDGain(self.gain)
            print('Optimizing gain...')
            while (max_value < ideal_pixel_range[0] or max_value > ideal_pixel_range[1]) and ct < max_checks:
                ct += 1
                representative_img = self.img_1D_to_2D(self.GetPicSimple(self.gain_key, self.n_gain)[-1], 1024, 1024) # Acquire data, keep last image as representative of gain setting
                max_value = np.max(representative_img)
                if max_value <= ideal_pixel_range[0]:
                    print(f'max pixel value: {max_value} low, raising gain: {self.gain} > {self.gain+1}')
                    self.gain+=1
                elif max_value >= ideal_pixel_range[1]:
                    print(f'max pixel value: {max_value} high, lowering gain: {self.gain} > {self.gain-1}')
                    self.gain-=1
                self.sdk.SetEMCCDGain(self.gain)
                if self.gain >= max_gain:
                    print(f"WARNING: gain at value {self.gain} higher than recommended max. Something is probably wrong with the experiment. To override, set Misc 'max_gain' to something else (default is 140).")
                    break
                if self.window: self.acquire({'window': self.format_windows(representative_img, focus_bool = False), 'time': time.time() - self.t0, 'autofocus_z': self.z_pos}) # dicey but I'm pretty sure format_windows runs first to update self.z_pos. Bad coding practice, though.
                else: self.acquire({})
                time.sleep(gain_wait_time)
            if ct == max_checks:
                print(f"Max checks reached without finding optimal gain. Either adjust starting guess, or alter 'max_checks' in Misc (default 20)")
        else:
            current_gain = self.sdk.GetEMCCDGain()[1]
            self.gain = current_gain
            if gain_setting == 'override':
                if current_gain != gain:
                    self.sdk.SetEMCCDGain(gain)
                    print('Overriding gain, setting gain to user input value: ', gain)
                    self.gain = gain
                else: 
                    print('Gain already at user input value: ', gain)
            print('Checking gain...')
            for i in range(img_cycles_no_gain_optimization):
                representative_img = self.img_1D_to_2D(self.GetPicSimple(self.gain_key, self.n_gain)[-1], 1024, 1024) # Acquire data, keep last image as representative of gain setting
                max_value = np.max(representative_img)
                if max_value <= ideal_pixel_range[0]:
                    print(f'max pixel value: {max_value} low')
                elif max_value >= ideal_pixel_range[1]:
                    print(f'max pixel value: {max_value} high')
                if self.window: self.acquire({'window': self.format_windows(representative_img, focus_bool = False), 'time': time.time() - self.t0, 'autofocus_z': self.z_pos})
                else: self.acquire({}) 
                time.sleep(gain_wait_time)
        if save == 'tracking':
            with open(self.data_path+f'\\Full_s{0}.pkl', 'wb') as file:
                pickle.dump(representative_img, file)
        return self.gain, max_value, representative_img

    def set_trackpy_params(self):
        do_trackpy = self.trackpy_params.get('trackpy', False) # Whether to use trackpy for ND detection and tracking, or to use a simpler method based on local maxima. Trackpy is more robust and better at handling changes in the number of visible NDs, but is also slower, so the option is there to turn it off if speed is a concern and the simpler method is sufficient.
        r = self.trackpy_params.get('r_ND', 7)                      # radius in pixels (use existing r if present)
        thresh_sigma = self.trackpy_params.get('sigma', 1.2)        # threshold = mean + thresh_sigma * std
        min_distance = self.trackpy_params.get('min_dist', 8)       # minimum distance between peaks
        buffer = self.trackpy_params.get('buffer', 35)              # buffer from edge of image to ignore when auto-detecting features, in pixels
        bg_pts = self.trackpy_params.get('bg_pts', [])          # list of background points to include in tracking, in format [(x1,y1), (x2,y2), ...]
        return do_trackpy, r, thresh_sigma, min_distance, buffer, bg_pts
    ## Picture Functions (take pictures)
    def GetPicSimple(self, seq_key, n_pic, im_size = 1024**2, no_window = False):
        '''
        Runs an acquisition of n pictures over a given sequence, returns pictures as a parsed list of 1D arrays of length 'im_size'.
        Automatically coordinates self.window. 

        Note: this method does not touch the sg
        '''
        ## Prep
        if not no_window:
            self.window = self.window_interval>0 and self.ct_for_window%self.window_interval == 0
            self.ct_for_window += 1
        acq_sleep = self.Misc.get('acq_sleep', 0.2) # Hardcoded | Time to wait after starting acquisition before sending pulses, in seconds
        ## Start 
        self.sdk.StartAcquisition()
        ret = self.sdk.GetStatus()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            raise Exception()
        time.sleep(acq_sleep) #Give time to start acquisition
        ## Go
        self.psWF.stream(seq_key, 1, mode = 'AM')
        timeout_counter = 0
        while(self.sdk.GetTotalNumberImagesAcquired()[1]<n_pic and timeout_counter<=self.timeout_limit):
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1
            if timeout_counter == self.timeout_limit:
                print(f'timeout with {self.sdk.GetTotalNumberImagesAcquired()[1]} pictures.')
        (ret, all_data, _, _) = self.sdk.GetImages16(1,n_pic,n_pic * 1024**2)
        ## Done 
        parsed_data = [all_data[i*im_size:i*im_size+im_size] for i in range(int(len(all_data)/im_size))]
        return parsed_data
    
    def GetPic(self, seq_key, n_pic, im_size = 1024**2, saving = 'no_save', no_window = False):
        '''
        Runs an acquisition of n pictures over a given sequence, returns pictures as a parsed list of 1D arrays of length 'im_size'.
        Automatically coordinates self.window. 
        Additionally, during wait time after starting acquisition, attempts to save any images in self.unsaved_imgs.

        Note: this method does not touch the sg
        '''
        ## Prep
        intermediate_save = saving == 'raw_images'
        if not no_window:
            self.window = self.window_interval>0 and self.ct_for_window%self.window_interval == 0
            self.ct_for_window += 1
        acq_sleep = self.Misc.get('acq_sleep', 0.2) # Hardcoded | Time to wait after starting acquisition before sending pulses, in seconds
        ## Start 
        self.sdk.StartAcquisition()
        ret = self.sdk.GetStatus()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            raise Exception()
        time.sleep(acq_sleep) #Give time to start acquisition
        ## Go
        self.psWF.stream(seq_key, 1, mode = 'AM')
        timeout_counter = 0
        if self.debug or self.verbose: t_prestream = time.time()
        if intermediate_save:
            if self.debug or self.verbose: t_presave = time.time()
            self.save_pics()
            if self.debug or self.verbose: print(f'Image saving took {time.time() - t_presave} seconds.')
        while(self.sdk.GetTotalNumberImagesAcquired()[1]<n_pic and timeout_counter<=self.timeout_limit):
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1
            if timeout_counter == self.timeout_limit:
                print(f'timeout with {self.sdk.GetTotalNumberImagesAcquired()[1]} pictures.')
        if self.debug or self.verbose: print(f'Acquisition took {time.time() - t_prestream} seconds after streaming started.')
        (ret, all_data, _, _) = self.sdk.GetImages16(1,n_pic,n_pic * 1024**2)
        ## Done 
        parsed_data = [all_data[i*im_size:i*im_size+im_size] for i in range(int(len(all_data)/im_size))]
        return parsed_data
    
    def GetPic_Alternating(self, seq_key, alt_key, n_pic, alt_sleep_time, im_size = 1024**2, saving = 'no_save'):
        '''
        Runs an acquisition of n pictures over a given sequence, and its alternate, returns pictures as a parsed list of 1D arrays of length 'im_size'.
        Automatically coordinates self.window. 

        Note: this method does not touch the sg
        '''
        data = self.GetPic(seq_key, n_pic, im_size, saving = saving)
        time.sleep(alt_sleep_time) # Time to wait between two acquisitions, in seconds. Should be long enough to allow camera to recover
        data_alt = self.GetPic(alt_key, n_pic, im_size, saving = saving, no_window = True)
        return data + data_alt
    ## Process Functions
    def init_ND_list(self, representative_img):
        ## Params
        do_trackpy, r, thresh_sigma, min_distance, buffer, bg_pts = self.set_trackpy_params() # self.bg_pts | extracts trackpy variables, with defaults if not present in input
        if do_trackpy:
            ## Prep
            if representative_img is None: # Shouldn't happen, but for the sake of robust code...
                print('No representative image found from gain optimization, acquiring new image for trackpy prep...')
                self.sdk.SetNumberKinetics(self.n_gain)
                representative_img = self.img_1D_to_2D(self.GetPicSimple(self.gain_key, self.n_gain)[-1], 1024, 1024) # Acquire data, keep last image as representative.
            img = representative_img.copy().astype(float) # use existing img_data (1024x1024)
            
            ## Process
            discovered_ROI_list = self.identify_NDs(img, r, thresh_sigma, min_distance, buffer)
            ND_list = self.ND_list + discovered_ROI_list 
            self.ND_list = self.filter_duplicate_NDs(ND_list, min_distance) # Filter out any duplicate NDs that may have been detected from the original list and the trackpy list
        self.ND_list = self.ND_list + bg_pts # Add any user-input background points to the ND list 
        self.ND_iter = range(len(self.ND_list))
        print(self.ND_list[:5])
        print(f'---------------------------------\n Total {len(self.ND_list)} ROIs \n---------------------------------')
        return len(bg_pts) # Return number of background points for later use in analysis

    def init_main_loop(self): # TEMPLATE
        ## Prepare camera
        self.sdk.SetNumberKinetics(len(self.label))
        ## Prepare SG, ps
        # Q_set = -1 if mode == 'AM' else 0 # ODMR ONLY
        self.psWF.Pulser.constant(([6],...,0.0)) #set pulser to safe output
        self.sg.rf_toggle = True 
        raise NotImplementedError('main loop initialization is highly dependent on the experiment and protocol. Please implement this function.')
    ## Analysis Functions (data formatting, analysis)
    def img_1D_to_2D(self,img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, not snake-like formatting.
        '''
        arr = np.asarray(img_1D, dtype=int)
        return arr.reshape((y_len, x_len))
    
    def format_windows(self, img, focus_bool = False):
        '''
        formats an image into a list of ROIs around each ND of size self.r_display*2 by self.r_display*2, to be sent as part of acquire when self.window is True. 
        If self.all_ROI is True, formats a window around each ND in self.ND_List, otherwise just the first one (which is set to be the autofocus ND if focus_bool is True). 
        If focus_bool is True, also runs autofocus on the first ROI and updates self.z_pos accordingly. Returns a list of images for 2D plotting.
        '''
        windows = []
        if self.all_ROI:
            imgs_to_acquire = range(len(self.ND_list))
        else:
            imgs_to_acquire = [0] 
        for ND in imgs_to_acquire:
            loc = self.ND_list[ND]
            px_x = loc[0]
            px_y = loc[1]

            ROI = img[px_y-self.r_display:px_y+self.r_display,px_x-self.r_display:px_x+self.r_display]
            if ND==0 and focus_bool:
                self.z_pos = self.autofocus(ROI, self.r_display)
            #make sure ROI is a list of lists of ints for nspyre compatibility:
            ROI = ROI.astype(int).tolist()
            windows.append(ROI)
        return windows
    
    def autofocus(self, temp_image, ROI_rad): 
        z_pos = self.urixyz.daq_controller.position['z'].to('um').m
        x_pos = self.urixyz.daq_controller.position['x'].to('um').m
        y_pos = self.urixyz.daq_controller.position['y'].to('um').m
        y_sum = np.sum(temp_image, axis=0)
        x_sum = np.sum(temp_image, axis=1)
        x_line = np.sum(x_sum[ROI_rad-2:ROI_rad+2] )
        y_line = np.sum(y_sum[ROI_rad-2:ROI_rad+2] )
        if x_line < 1.05 * y_line:
            if y_line < 1.05 * x_line:
                if self.verbose: print('focus complete')
            else: 
                if self.verbose: print('raising z')
                z_pos+=0.05
        else:
            if self.verbose: print('lowering z')
            z_pos-=0.05
        self.urixyz.daq_controller.move({'x': Q_(x_pos,'um'), 'y': Q_(y_pos,'um'), 'z': Q_(z_pos,'um')})
        return z_pos

    def identify_NDs(self, img, r, thresh_sigma, min_distance, buffer):
            '''
            auto-detect bright-spot ROIs in img and create ROI_list. r is the expected radius of the NDs in pixels, used for blob detection. thresh_sigma is the number of standard deviations above the mean to set as threshold for feature detection. 
            min_distance is the minimum distance between detected features, in pixels. buffer is the distance from the edge of the image to ignore when detecting features, in pixels. If bg_pt is True, will add points from ROI_xy to ND_List and 
            count them as background points (not tracked, but used for normalization). 
            outputs: ROI_list (list of (x,y) tuples)
            '''
            #compute smoothed image and threshold
            img_smooth = gaussian_filter(img, sigma=1.0)
            threshold = img_smooth.mean() + thresh_sigma * img_smooth.std()

            coords = []

            # try trackpy first, then skimage, then simple local-max approach
            try:
                # trackpy expects bright features: diameter ~ 2*r+1
                f = tp.locate(img_smooth, diameter=max(3, 2*r+1), minmass=threshold*(2*r+1)**2/10)
                coords = [(int(x), int(y)) for x, y in zip(f['x'], f['y'])]
            except Exception:
                if self.verbose: print('Trackpy failed to find features, trying blob_log...')
                try:
                    blobs = blob_log(img_smooth, min_sigma=1, max_sigma=r, num_sigma=10, threshold=threshold/np.max(img_smooth))
                    # blob_log returns (y, x, sigma)
                    coords = [(int(b[1]), int(b[0])) for b in blobs]
                except Exception:
                    if self.verbose: print('blob_log also failed, falling back to local maxima approach...')
                    # fallback: local maxima using maximum_filter
                    neighborhood = maximum_filter(img_smooth, size=2*min_distance+1)
                    peaks = (img_smooth == neighborhood) & (img_smooth > threshold)
                    labeled, n_peaks = label(peaks)
                    slices = find_objects(labeled)
                    for s in slices:
                        if s is None:
                            continue
                        y = (s[0].start + s[0].stop - 1) // 2
                        x = (s[1].start + s[1].stop - 1) // 2
                        coords.append((int(x), int(y)))
            discovered_ROI_list = np.array(coords) if coords else np.empty((0,2), dtype=int)
            # remove points too close to edge
            discovered_ROI_list = [loc for loc in discovered_ROI_list if buffer <= loc[0] < img.shape[1]-buffer and buffer <= loc[1] < img.shape[0]-buffer]
            return discovered_ROI_list
    
    def filter_duplicate_NDs(self, coords_arr, min_distance):
        # remove duplicates / too-close points. Input np.array() with shape (n,2) or list of n (x,y) tuples. Output list of (x,y) tuples.
        kept = []
        for c in coords_arr:
            if not any(np.hypot(c[0]-kc[0], c[1]-kc[1]) < (min_distance) for kc in kept):
                kept.append(tuple(int(v) for v in c))
        return kept  # assign so cells below can use this variable

    def save_pics(self, n = -1):
        '''saves n pictures from self.unsaved_imgs, if n = -1 saves all. Clears saved pics from self.unsaved_imgs.'''
        ct = 0
        if n == -1:
            n = len(self.unsaved_imgs)
        elif n > len(self.unsaved_imgs):
            if self.verbose:
                print(f'Only {len(self.unsaved_imgs)} unsaved images available, saving all of them.')
            n = len(self.unsaved_imgs)
        for im_name, img in list(self.unsaved_imgs.items())[:n]:
            with open(self.data_path+f'\\{im_name}.pkl', 'wb') as file:
                pickle.dump(img, file)
            ct += 1
            del self.unsaved_imgs[im_name]
        if self.verbose: print(f'Saved {ct} images, {len(self.unsaved_imgs)} remaining unsaved.')

    def save_after_sweep(self, img, save_image, sweep):
        if save_image == 'raw_images' : self.save_pics() # Save any remaining unsaved images for this sweep
        elif save_image == 'tracking':
            with open(self.data_path+f'\\Full_s{sweep + 1}.pkl', 'wb') as file:
                pickle.dump(img, file)

    def track_NDs(self, ND_List, pic, r_search = 10, number_bg_pts = 0):
        '''
        Not intended for the cellular environment: intended for more or less stationary diamonds which will not appear/disappear. More planning will be needed for celluluar environment.

        given a set of ROI [(x,y), ...] and a picture, relocates the ROI to the brightest spot within r_search, returning the updated 
        ROI list, as well as an array of the max brightnesses for tracking purposes (can determine if ND lost).
        Only searches points that are not bg_pts.
        '''
        ls_mx = []
        ls_ROI = []
        for i in range(len(ND_List)-number_bg_pts):
            px_x = ND_List[i][0]
            px_y = ND_List[i][1]
            ROI_search = pic[px_y - r_search: px_y + r_search, px_x - r_search: px_x + r_search]
            px_max = np.argmax(ROI_search)
            ls_mx.append(np.max(ROI_search))
            temp_y = int(px_max/(r_search*2)) + px_y - r_search
            temp_x = px_max%(r_search*2) + px_x - r_search
            ls_ROI.append((temp_x, temp_y))
        for i in range(number_bg_pts):
            ls_ROI.append(ND_List[-(i+1)])
        return ls_ROI, ls_mx

    def img_to_sig(self, ND_List, pic, r_ROI = 7):
        ''' 
        Given an ND_List, a picture, and an ROI radius, extracts a signal and outputs it as an array sig[ND]
        '''
        sig = []
        for i in range(len(ND_List)):
            px_x = ND_List[i][0]
            px_y = ND_List[i][1]
            ROI = pic[px_y - r_ROI: px_y + r_ROI, px_x - r_ROI: px_x + r_ROI]
            sig.append(sum(sum(ROI)))
        return sig
    
    def analyze_sig(self, data): # TEMPLATE
        '''
        An example signal analysis. Should be redefined for an experiment.
        '''
        # dependent on process. Roughly this will consist of:
        # Define for each sig a list, by ND, and allowing for multiple entries due to multiple runs.
        sig1 = [[] for i in self.ND_iter]
        bg1 = [[] for i in self.ND_iter]
        # Define sig all of the signals for this run, for all NDs, to be added to the acquisition dict regardless of protocol, for maximum flexibility in post-processing.
        sig_all = [[] for i in self.ND_iter] # For collecting all signals.

        # begin processing images:
        for i in range(len(data)):
            extracted_sig = self.img_to_sig(self.ND_list, data[i], r_ROI = self.r_targ) #array of [ND] signals from a given image.
            for ND in self.ND_iter: sig_all[ND].append(extracted_sig[ND])
            # BEGIN PROCESS MOST DEPENDENT ON PROTOCOL FOR PROCESSING IMAGES, MATCHING IMAGES. EXAMPLE:
            if self.full_label_filtered[i] == 1:
                for ND in self.ND_iter: sig1[ND].append(extracted_sig[ND])
            elif self.full_label_filtered[i] == 0:
                for ND in self.ND_iter: bg1[ND].append(extracted_sig[ND])
        ls_sig1 = [np.mean(sig1[ND]) for ND in range(len(self.ND_list))]
        ls_bg1 = [np.mean(bg1[ND]) for ND in range(len(self.ND_list))]
        output = {'sig1': sig1, 'bg1': bg1, 'sig_all': sig_all}
        raise NotImplementedError('analyze_sig is highly dependent on the experiment and protocol. Please implement this function according to the needs of your experiment. sig1, bg1, and sig_all are just examples of how to structure the output, but can be redefined as needed. The important thing is that the output is a dictionary of whatever values you want to acquire, which will be added to the acquisition dict in the main loop and saved for post-processing.')
        return output
    ###########################################################################################################################

    #TEMPLATE: commented out to prevent accidentally thinking this is complete and editing it instead of the spyrelet implementing it.

    def main(self, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, ROI_xy, decay_routine, alt_label, alt_sleep_time, trackpy_params, focus_bool,
                   data_path, save_image, data_download, shutdown, verbose, window_params, Misc
                   ):

    #     representative_img = None # useful for saving and windowing, a running representative image.
    #     #### Optimize gain/ take images to reset camera dynamics #################################################
    #     self.gain, max_value, representative_img = self.init_gain(gain, gain_setting, self.Misc.get('ideal_pixel_range', (2.1e4,2.9e4)), 
    #                                                               self.Misc.get('max_checks', 20), self.Misc.get('max_gain', 140), self.Misc.get('gain_wait_time', 0.5),
    #                                                               self.Misc.get('img_cycles_no_gain_optimization', 2), save = save_image ) # runs self.acquire several times. 
    #     print(f'gain: {self.gain}, giving max pixel value of roughly {max_value}')

    #     #### Trackpy #################################################################################################################
    #     n_bg_pts = self.init_ND_list(representative_img) # self.ND_list | self.ND_iter | some print statements | runs trackpy if necessary to find NDs. 

    #     #### Begin Experiment ################################################################################################################
    #     self.init_main_loop() # Any experiment-specific initialization before main loop, such as defining sequences, running initial sequences, etc.

    #     for sweep in self.progress(range(sweeps)):
    #         ## main loop ################################################################################################################
    #         self.unsaved_imgs = {} # dict to hold unsaved images for this sweep, key is img name, value is img to save.
    #         for i,f in enumerate(self.sg_freqs):
    #             if verbose: print("frequency: ", f)
    #             self.sg.frequency = f 
    #             if alt_label:
    #                 data_1D = self.GetPic_Alternating(self.seq_key, self.alt_key, len(self.label), alt_sleep_time.m, saving = save_image ) # Get data as list of 1D arrays, alternating between two labels
    #             else:
    #                 data_1D = self.GetPic(self.seq_key, len(self.label), saving = save_image ) # Get data as list of 1D arrays, saving any images during wait if all images are to be saved
    #             # Go through the new data and format it. Add it to unsaved imgs.
    #             data = []

    #             for j, img_1D in enumerate(data_1D):
    #                 if self.full_label[j] != 't':
    #                     img = self.img_1D_to_2D(img_1D, 1024, 1024)
    #                     data.append(img)
    #                     im_name = f'{self.seq_key}_s{sweep+1}_f{i}_{j}'
    #                     self.unsaved_imgs[im_name] = img

    #             ## Track NDs
    #             self.ND_list, ls_mx = self.track_NDs(self.ND_list, data[-1], r_search = self.r_track, number_bg_pts= n_bg_pts)

    #             ## ANALYSIS
    #             output_dict = self.analyze_sig(data)
                
    #             ## Acquire.
    #             # dependent on process. Example of an acquisition dict. 
    #             acq_dict = {
    #                 'sweep_idx': sweep,                         # sweep idx
    #                 'f': f,                            # any frequency info
    #                 'time': time.time() - self.t0,                   # time since start of experiment
    #                 'z_pos': self.z_pos                     # z position
    #             }
    #             acq_dict.update(output_dict) # add whatever values were output from the analysis to the acquisition dict
    #             if self.window:
    #                 acq_dict['window'] = self.format_windows(data[-1], focus_bool= focus_bool)
    #             self.acquire(acq_dict)
    #         ########################################################################### 
    #         representative_img = img
    #         self.save_after_sweep(img, save_image, sweep)
    #         print(f'Finished sweep {sweep+1}/{sweeps}, time elapsed: {time.time() - self.t0} seconds.')
        print('main finished')

    #### FINALIZE HELPER FUNCTIONS ###############################################################################################
    def finalize_sg(self):
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.psWF.Pulser.reset()
        return
    
    def finalize_camera(self, shutdown):
        ret = self.sdk.SetShutter(1,self.sdk_codes.Shutter_Mode.PERMANENTLY_CLOSED,27,27)
        print("Function SetShutter returned {}".format(ret))
        if shutdown:
            ret = self.sdk.ShutDown()
            print("SDK shutdown ", ret == 20002)
        return
    
    def save_config(self, data_download, sweeps, alt_label, rf_amplitude, frequencies, gain, exp_time, readout_time, ROI_xy):
        total_time = time.time() - self.t0
        if data_download:
            config = {'VERSION': 2, 'label': self.label, 'gain': self.gain, 'sweeps': sweeps, 'alt_label': alt_label, 'rf': rf_amplitude,'NDs_input': eval(ROI_xy),
                      'NDs': self.ND_list, 'n_ND': len(self.ND_list),'freqs': frequencies, 'exp_time': exp_time.m, 'readout_time': readout_time.m, 'total_time': total_time} 
            os.mkdir(self.data_path+'\\data')
            with open(self.data_path+f'\\data\\config.pkl', 'wb') as file: 
                pickle.dump(config, file)
            with open(self.data_path+f'\\data\\config.txt', "w") as file:
                file.write(str(config))
        raise NotImplementedError('save_config should be rewritten to include any additional parameters that should be saved.')
        return total_time
    ###########################################################################################################################
    def finalize(self, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, ROI_xy, decay_routine, alt_label, alt_sleep_time, trackpy_params, focus_bool,
                   data_path, save_image, data_download, shutdown, verbose, window_params, Misc
                   ):
        # #### SG off ###############################################################################################
        # self.finalize_sg()
        # #### Cam close ###############################################################################################
        # self.finalize_camera(shutdown)
        # #### Additional Analysis ###############################################################################################
        # # Ex. Quasilinear slope extraction, fitting, etc.
        # #### Data saving ###############################################################################################
        # total_time = self.save_config(data_download, sweeps, alt_label, rf_amplitude, frequencies, gain, exp_time, readout_time, ROI_xy)
        # #### Final Print Statements ###############################################################################################
        # first_10_ROI = self.ND_list[:10]
        # print(f'The updated ND locations: {first_10_ROI}... ({len(first_10_ROI)} of {len(self.ND_list)} shown)')
        # print(f"Finalizing finished, total time: {total_time} seconds")
        return



