###########################
# imports
###########################

# std
import numpy as np
import time
import math
from itertools import cycle
import logging
from scipy.optimize import curve_fit
from scipy import signal #Unused?
import datetime as Dt
import trackpy as tp
import pims
from pims import Frame, FramesSequence
#from skimage.io import imsave, imread #Not working?
from PIL import Image
import pickle #Delete later

# importing the sys module
import sys, os

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

#importing sdk
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

###########################
# classes
###########################

#spyrelet
class WFODMRSwabianSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',
    ]

    '''
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    '''
    """
    We run two windows: one with our MW on and the other with the MW off.
    We read the start of these 50us windows, and we do this 10,000 times. So,
    we have a time per point of 1s.
    we can repeat x sweeps every y minutes per z repetitions.
    We sweep our microwave window over frequencies, generally 30 steps.
    Note: probe_time is the laser_on_per_window,
    rf_amplitude is the signal generator's power,

    During each MW period, we take n_acc image (16 bit) accumulations
    (~50? ~10 for real time?) (calculated in pulse streamer based on exp time and
    collect time)- 50 times within one MW period (?) --> "average" 32 bit signal
    image containing 2 * f_step * (f_end - f_start)
    Frequency step of 1 MHz (?)
    10 electron multiplication gain (?)
    """

    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },

        'exp_time':{ #this represents the exposure time per frame
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 75e-3,
        },
        'cam_trigger':{'type': list,'items': ['EXTERNAL_EXPOSURE','EXTERNAL_FT'], 'default': 'EXTERNAL_FT'},

        'readout_time':{ #this represents the total time per frame (including exposure and readout time)- greater than or equal to exp_time + 39 ms
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 15e-3,
        },
 

        'gain':{ #EM gain for camera, goes from 1-272
            'type':int,
            'default': 2,
            'positive': True

        },
        'repeat_every_x_minutes':{
            'type': float,
            'default': 0,
            'positive': True
        },

        'runs_sweeps_reps':{'type': str, 'default': '[1,1,1]'},
        'frequency': {
            'type': str,
            'default': '[2.85e9, 2.89e9, 30]',
        },
        'rf_amplitude':{
            'type': float,
            'default': -15,
        },
        'mw_duty':{
            'type': float,
            'default': 1,
        },
        'mw_rep':{
            'type': int,
            'default': 50,
        },
        'probe_time':{ #total amount of time the microwave is pulsed (on or off)
            'type': float,
            'default': 160e-3,
            'suffix': 's',
            'units': 's'
        },

        'laser_lag': {
            'type': float,
            'default': 0.07,
            'suffix' : ' s',
            'units': 's'
        },
            'leave_laser_on':{ #leaves laser on when switching frequencies.
            'type': bool,
            'default': False
        },
            'optimize_gain':{ #Optimize gain before beginning WFODMR. Better for lower exposure times.
            'type': bool,
            'default': True # once it works, change to True
        },

        'sleep_time': { #accounts for some overhead time
            'type': float,
            'default': 0,
            'suffix': 's',
            'units': 's'
        },

        'data_path': { #where the raw images are saved if data_download is true
            'type': str,
            'default': 'Z:\\biosensing_setup\\data\\WFODMR_images_test'
        },

        #trackpy parameters

        # 'radius': { #maximum radius of ROIs
        #     'type': int,
        #     'default': 9 #must be odd integer
        # },

        # 'threshold': { #minimum brightness
        #     'type': int,
        #     'default': 36420
        # },

        # 'minmass': { #minimum integrated "mass" of ROIs- mostly use this for further tweaking
        #     'type': int,
        #     'default': 0
        # },

        # 'link_radius': { #maximum search radius for determining trajectory of ROIs
        #     'type': int,
        #     'default': 20
        # },
        # 'microns_per_pixel': { #microns per pixel in images- used for calculating displacements using trackpy
        #     'type': float,
        #     'default': 0.068
        # },
        'save_image': {
            'type': bool,
            'default': False
        },
        'ROI_xyr':{'type': str, 'default': '[(512,512,16,7)]'},

        'data_download':{
            'type': bool,
        },
        'cooler':{
            'type': bool,
            'default': False
        },
        'Temp':{ #number of pulse sequences per frequency point
            'type': int,
            'default': 20,
        },
        'protected_readout':{ #determines whether light shuts off during readout (after exposure) or not
        'type': bool,
        'default': False
        },
        'mode':{'type': list,'items': ['QAM','AM','SWITCH'], 'default': 'QAM'},
        'trackpy':{
            'type': bool,
            'default': False
        },
        'trackpy_params': {
            'type': str,
            'default': '(False, 40, 800)' #default values for invert, threshold, and minmass respectively
        },
        'Misc': {
            'type': str,
            'default': "{'DEBUG':False, 'DEBUG_FM': False, 'shutdown': False}" #default values for invert, threshold, and minmass respectively
        }

    }
    def initialize(self, device, PS_clk_channel, exp_time,cam_trigger,readout_time, gain, optimize_gain,runs_sweeps_reps, frequency, rf_amplitude, mw_duty, mw_rep,
                        laser_lag,leave_laser_on, probe_time, repeat_every_x_minutes, data_download, 
                        data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,mode, trackpy, trackpy_params, Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,
        self.t0 = time.time()    

        self.misc = eval(Misc)
        self.ROI_xyr = eval(ROI_xyr)
        self.sig_data = []
        self.bg_data = []
        self.ODMR_data = []
        self.frequency = Q_(np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True),'Hz')
        for ND in range(len(self.ROI_xyr)):
            self.sig_data.append(np.zeros(len(self.frequency)))
            self.bg_data.append(np.zeros(len(self.frequency)))
            self.ODMR_data.append(np.zeros(len(self.frequency)))
        

        self.trackpy_params = trackpy_params
        
        self.gain_string = ''
        ## create self parameters ------------------------------
        print('Initializing WFODMR_New')
        #initialize experiment params---------------------------------------
        #self.sequence = sequence #type of ODMR sequence from the list
        self.index = 0

        self.repetitions = eval(runs_sweeps_reps)[2]
        self.runs = eval(runs_sweeps_reps)[0] #let's have a sacrificial set of images! Toss the first run because that point is always strange

        #self.channel = channel1 #reading channel
        self.sg.rf_amplitude = rf_amplitude ## set SG paramaters: running this spyrelet with IQ inputs
        self.probe_time = int(round(probe_time.to("ns").m)) #laser time per window
        self.point_num = len(frequency)
        self.sweeps = eval(runs_sweeps_reps)[1]
        self.sleep_time = sleep_time
        self.mw_duty = mw_duty
        self.mw_rep = mw_rep


        #initialize trackpy params --------------------------------------
        # self.data_path = data_path #where to save the trajectories if data_download is true
        # self.radius = radius #radius of desired ROIs (in pixels)
        # self.threshold = threshold #clips below specified bandpass (usually in 100s)
        # self.minmass = minmass #minimum integrated brightness (recommended value: 100)
        # self.link_radius = link_radius #search radius for finding trajectories between frames (in pixels)
        # self.microns_per_pixel = microns_per_pixel #conversion factor between microns and pixels

        self.data_path = data_path
        self.data_download = data_download
        self.save_image = save_image
        if(data_download or save_image):
            if(not os.path.isdir(self.data_path)):
                os.mkdir(self.data_path)
            else:
                self.data_path = self.data_path+f'_{time.time()}'
                os.mkdir(self.data_path)

        self.sdk = atmcd("")  # Load the atmcd library
        self.codes = atmcd_codes
        ret = self.sdk.Initialize("")  # Initialize camera
        print("Function Initialize returned {}".format(ret)) #returns 20002 if successful

        #Can probably get rid of 'ret' but not important...
        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.KINETICS) #Taking a series of pulses
        self.sdk.SetReadMode(self.codes.Read_Mode.IMAGE) #reading pixel-by-pixel with no binning
        '''
        For some reason if you move SetTriggerMode to a later line the camera seems to go to internal or something?
        '''
 
        self.exp_time = exp_time.to('ns').m 
        self.readout_time = readout_time.to('ns').m
        self.laser_lag = int(round(laser_lag.to("ns").m))
        self.collect_time = self.exp_time+self.readout_time

        if cam_trigger == 'EXTERNAL_EXPOSURE':
            self.sdk.SetTriggerMode(self.codes.Trigger_Mode.EXTERNAL_EXPOSURE_BULB) #Pulse  length controls exposure
            if self.laser_lag < self.readout_time+10000000:
                print('laser lag must be larger than readout_time + 10 ms for camera initialization.')
                return
            elif self.laser_lag > self.readout_time + 1.5 * self.exp_time:
                print('risk of over-exposing during initialization! laser lag too high.')
                return
        else:
            '''
            exposure min is 46.611 ms. The set exposure time is done in excess of this s.t. exp_time = 0 corresponds to 46.611 ms exposure.
            The pulse streamer will trigger the camera by sending pulses of 10ms, and the rest of the exposure time plus any set readout time will be 
            sent to the pulse streamer as readout time
            '''
            self.sdk.SetTriggerMode(self.codes.Trigger_Mode.EXTERNAL) #Pulse  length controls exposure
            # self.sdk.SetFastExtTrigger(0)
            #### camera-ended stuff
            exposure_min = 0.046611e9
            if self.exp_time < exposure_min:
                print(f'exposure must be at least {exposure_min*1000} ms.')
            elif self.exp_time + self.readout_time < 80000000:
                print('May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            self.sdk.SetExposureTime(self.exp_time*1e-9) 
            #### ps-ended stuff
            self.sdk.SetFrameTransferMode(1) 
            print('frame transfer mode on')

        if self.readout_time<5000000:
            print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
        if self.collect_time >= self.probe_time:
            print('WARNING probe time cannot be less than or equal to collect time!')
            

        (ret, xpixels, ypixels) = self.sdk.GetDetector()
        self.sdk.SetImage(1, 1, 1, xpixels, 1, ypixels) #defining image
        # if self.misc['clamp']:
        #     self.sdk.SetBaselineClamp(1)
        #     print('set baseline clamp to 1')

        self.sdk.SetEMCCDGain(gain) #setting Electron Multiplier Gain
        self.sdk.SetNumberAccumulations(int((self.probe_time - (self.probe_time%self.collect_time)) / self.collect_time)) #more explanation 
        self.sdk.SetNumberKinetics(self.runs * 2 + 1)
        self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_OPEN,27,27) #Open Shutter


        #connect to pulse sequence------------------------------------------
        self.seqs = []
        

        if mode == 'QAM':
            self.sg.mod_type = 'QAM'
            self.AM_mode = False
            self.switch_mode = False
        elif mode == 'AM':
            self.sg.mod_type = 'AM'
            self.sg.AM_mod_depth = Q_(100, 'pc')
            self.switch_mode = False
            self.AM_mode = True
        elif mode == 'SWITCH':
            self.sg.mod_type = 'AM'
            self.sg.AM_mod_depth = Q_(100, 'pc')
            self.switch_mode = True
            self.AM_mode = True
        self.pulse_setup(self.probe_time, self.collect_time, self.exp_time, self.runs,protected_readout, mode,cam_trigger)

        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'

        # ret = self.sdk.GetKeepCleanTime()
        # print(f'Keep Clean Time is {ret[1]}')
        self.t_init = time.time()  


    def main(self, device, PS_clk_channel, exp_time,cam_trigger,readout_time, gain, optimize_gain,runs_sweeps_reps, frequency, rf_amplitude, mw_duty, mw_rep,
                    laser_lag,leave_laser_on, probe_time, repeat_every_x_minutes, data_download, 
                    data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,mode, trackpy, trackpy_params, Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,
        self.t_cool = self.t_init
        if(cooler):
            ret = self.sdk.SetTemperature(Temp)
            print(f"Function SetTemperature returned {ret} target temperature {Temp}")
            ret = self.sdk.CoolerON()
            while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
                time.sleep(5)
                (ret, temperature) = self.sdk.GetTemperature()
                print("Function GetTemperature returned {} current temperature = {} ".format(
                    ret, temperature), end='\r')
            self.t_cool = time.time()

        if(optimize_gain):
            self.gain = gain
            print('optimizing gain...')
            mx = 0
            while(mx<=2.0e4 or mx>=2.9e4):
                self.sdk.StartAcquisition()
                ret = self.sdk.GetStatus()
                if not ret[0] == 20002:
                    print('Starting Acquisition Failed, ending process...')
                    return
                #print('Starting Acquisition', ret)
                time.sleep(0.1) #Give time to start acquisition
                self.sg.frequency = self.frequency[0] ## make sure the sg frequency is set! (overhead of <1ms)
                self.pulses.stream_umOFF(self.seqs[0], 1, AM = self.AM_mode, SWITCH = self.switch_mode) #0 since only one seq in my seq array.
                timeout_counter = 0
                while(self.sdk.GetTotalNumberImagesAcquired()[1]<2 and timeout_counter<=2000): #20 second hard-coded limit!
                    time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                    timeout_counter+=1 
                (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(2,2,1024**2) #cut out first image here
                #print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
                temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
                mx = np.max(temp_image)
                print(f'gain of {self.gain}, mx is {mx}')
                if(mx<=1.0e4):
                    print('signal really low, raising gain +3')
                    self.gain+=3
                elif mx<=2.0e4:
                    print('raising gain +1')
                    self.gain+=1
                elif mx>=3.2e4:
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')
                    self.gain-=5
                elif mx>=2.9e4: 
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
                    self.gain-=2
                if self.gain <= 0:
                    self.gain = 1
                self.sdk.SetEMCCDGain(self.gain) #setting Electron Multiplier Gain
                self.sdk.PrepareAcquisition()
                ret = self.sdk.GetEMCCDGain()
                if self.gain>=150:
                    print('Warning! Gain too high! Re-adjust experiment parameters, or turn off optimize_gain, or edit the limit in the spyrelet code. Aborting...')
                    return
                time.sleep(0.6)
            self.gain_string = f'optimum gain determined to be {self.gain}, giving max pixel value of roughly {mx}'
            print(self.gain_string)
        else:
            self.gain = gain
            print('Initial capture to counteract camera dynamics...')
            mx = 0
            self.sdk.StartAcquisition()
            ret = self.sdk.GetStatus()
            if not ret[0] == 20002:
                print('Starting Acquisition Failed, ending process...')
                return
            time.sleep(0.1) #Give time to start acquisition
            self.sg.frequency = self.frequency[0] ## make sure the sg frequency is set! (overhead of <1ms)
            self.pulses.stream_umOFF(self.seqs[0], 1,AM = self.AM_mode, SWITCH = self.switch_mode) 
            timeout_counter = 0
            while(self.sdk.GetTotalNumberImagesAcquired()[1]<2 and timeout_counter<=400): #20 second hard-coded limit!
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1 
            (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(2,2,1024**2) #cut out first image here
            #print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
            temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
            mx = np.max(temp_image)
            if(mx<=1.0e4):
                print(mx, 'signal really low')
            elif mx<=2.0e4:
                print(mx, 'signal low')
            elif mx>=2.7e4: 
                print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
            print(f'gain of {self.gain}, mx is {mx}')
            self.gain_string = f'gain was set to {self.gain}, giving max pixel value of roughly {mx}'
            print(self.gain_string)

        self.t_gain = time.time()


        for rep in range(self.repetitions):
            for sweep in self.progress(range(self.sweeps)):
                count = 0
                for f in self.frequency:
                    print("frequency: ", f)

                    #import pdb;pdb.set_trace()
                    self.sdk.StartAcquisition()
                    ret = self.sdk.GetStatus()
                    if not ret[0] == 20002:
                        print('Starting Acquisition Failed, ending process...')
                        return
                    print('Starting Acquisition', ret)
                    time.sleep(0.1) #Give time to start acquisition, not optimized
                    self.sg.set_frequency(f) ## make sure the sg frequency is set! (overhead of <1ms)
                    self.pulses.stream_umOFF(self.seqs[0], 1, AM = self.AM_mode, SWITCH = self.switch_mode)
                    timeout_counter = 0

                    #### Need to wait to get data
                    while(self.sdk.GetTotalNumberImagesAcquired()[1]<self.runs*2+1 and timeout_counter<=100): #Should timeout counter be controlled better
                        time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                        timeout_counter+=1 #ends up being ~0.4ms
                    

                    (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,self.runs*2+1, (1+self.runs*2)*1024**2) #keep bad image, want to read it out
                    print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])

                    if(save_image and count==0):
                        self.sdk.SaveAsSif(self.data_path+'\\Characteristic_Image.sif')#Saves both mw-on and mw-off images as SIF

                    ## TRACKPY ###############################################################################################################
                    if trackpy and count == 0 and sweep == 0: #WE need to make sure this only happens on the first run of the first sweep
                        rng = range(1,self.runs*2+1)
                        for i in rng: #cut buffer data into individual image arrays: [ [img], [img], ...]
                            temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                        #tp_params = eval(trackpy_params)
                        #temp_frame = [Frame(temp_image.astype('int32'), frame_no = 0)]
                        temp_frame = [Frame(temp_image, frame_no = 0)]
                        loc0 = self.ROI_xyr[0] #trackpy param? loc0[2] needs to be odd.

                        if(self.save_image):
                            with open(self.data_path+f'\\temp_image.pkl', 'wb') as file:
                                pickle.dump(temp_image, file)
                            with open(self.data_path+f'\\temp_frame.pkl', 'wb') as file:
                                pickle.dump(temp_frame, file)
                            with open(self.data_path+f'\\trackpy_params', 'wb') as file:
                                pickle.dump(trackpy_params, file)
                            with open(self.data_path+f'\\loc0', 'wb') as file:
                                pickle.dump(loc0, file)

                        print(tp)

                        import pdb; pdb.set_trace()

                        f0 = tp.locate(temp_frame[0], self.closest_odd(loc0[2]), minmass=eval(trackpy_params)[1], threshold=eval(trackpy_params)[2], invert=eval(trackpy_params)[0])
                        if(self.save_image):
                            with open(self.data_path+f'\\f0.pkl', 'wb') as file:
                                pickle.dump(f0, file)

                        locs_tp = []
                        for i in range(len(f0)):
                            locs_tp.append(tuple((int(f0.iloc[i]['x']), int(f0.iloc[i]['y']), loc0[2], int(2 * f0.iloc[i]['size']))))
                        self.ROI_xyr = locs_tp
                    ###########################################################################################################################
                        
                    sigs = []
                    bgs = []
                    for ND in range(len(self.ROI_xyr)):
                        loc = self.ROI_xyr[ND]
                        sig, bg, loc = self.analyze(loc,(count == 0 and sweep == 0),sweep, count) #Figure out a way to move this into the waiting part of the program above, to maximize time usage, without messing up acquire cycle.
                        self.ROI_xyr[ND] = loc
                        sigs.append(sig)
                        bgs.append(bg)
                        self.sig_data[ND][count] +=(sig)
                        self.bg_data[ND][count] += (bg)
                        self.ODMR_data[ND][count] += (sig/bg)

                    while len(sigs)<5:
                        sigs.append(0)
                        bgs.append(0)

                    ## acquire the following
                    self.acquire({ ##TODO: figure out how to acquire lists
                        'rep_idx': rep,
                        'sweep_idx': sweep,
                        'f': f,
                        'runs': self.runs,
                        'probe_time': self.probe_time,
                        'rf_power': rf_amplitude,
                        'repetitions': self.repetitions,
                        'repeat_every_x_minutes': repeat_every_x_minutes,
                        'bg': bgs[0],
                        'sig': sigs[0],
                        'bg1': bgs[1],
                        'sig1': sigs[1],
                        'bg2': bgs[2],
                        'sig2': sigs[2],
                        'bg3': bgs[3],
                        'sig3': sigs[3],
                        'bg4': bgs[4],
                        'sig4': sigs[4],
                    }) 
                    count +=1


                    #mysterious overhead time
                    print("sleep time (s): ", sleep_time.m) #maybe move this
                    time.sleep(sleep_time.m)


            time.sleep(repeat_every_x_minutes * 60)

            self.t_exp = time.time()

            #### 
            self.t_db = 0
            self.t_db_setup = 0
            if self.misc['DEBUG_FM']:
                '''
                Misc arguments: sweeps, save

                '''
                print('DEBUG_FM')
                # if self.misc['pdb']:
                #     import pdb;pdb.set_trace()

                self.ODMR_data = np.divide(self.ODMR_data,self.sweeps)
                self.freq_data = np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True)

                f_start = self.freq_data[0]
                f_end = self.freq_data[-1]

                ## Determine ZFS to be in the middle, sb to be equivalent to regular ODMR range
                ZFS = (f_start + f_end)/2
                sb = np.abs(f_start - f_end)/2

                self.ODMR_data = np.multiply(self.ODMR_data,self.sweeps)
                '''
                TODO: Switch sg to FM mode, run two point odmr N times, and save data.
                '''
                self.sg.mod_type = 'FM'
                self.sg.FM_mod_setter = Q_(sb,'Hz')
                self.sg.frequency = Q_(ZFS, 'Hz')
                FM_seqs, kin_cycle, kin_leftovers = self.pulses.FM_WFODMR(self.exp_time,self.readout_time,10000000,5000000,self.runs,f_start,f_end,len(self.freq_data))

                self.t_db_setup = time.time()

                for s in range(self.misc['sweeps']):
                    self.sdk.SetNumberKinetics(kin_cycle)
                    raw_data = []
                    for ND in range(len(self.ROI_xyr)):
                        raw_data.append([])

                    for c in range(len(FM_seqs)-1):
                        ## ROBUST ACQUISITION OF IMAGES
                        acq_img = 0
                        timeout = 0
                        while acq_img < kin_cycle:
                            self.sdk.StartAcquisition()
                            ret = self.sdk.GetStatus()
                            if not ret[0] == 20002:
                                print('Starting Acquisition Failed, ending process...')
                                return
                            print('Starting Acquisition', ret)
                            time.sleep(0.1 * (timeout+1)) #Give time to start acquisition, not optimized
                            self.pulses.stream(FM_seqs[c], 1)
                            #### Need to wait to get data
                            while(self.sdk.GetTotalNumberImagesAcquired()[1]<kin_cycle and timeout_counter<=2000): #Should timeout counter be controlled better
                                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                                timeout_counter+=1 #ends up being ~0.4ms
                                if timeout_counter == 2000:                           
                                    print('timeout')
                            print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
                            acq_img = self.sdk.GetTotalNumberImagesAcquired()[1]
                            if acq_img < kin_cycle:
                                print('Not all images taken. Waiting and trying again...')
                                self.sdk.AbortAcquisition()
                                self.sdk.FreeInternalMemory()
                                timeout+=1
                                if timeout == 5:
                                    return #fail if can't get proper amount of images 3 times in a row
                                time.sleep(2**timeout)
                            else:
                                timeout = 0

                        (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,kin_cycle, kin_cycle*1024**2) #keep bad image, want to read it out

                        for ND in range(len(self.ROI_xyr)):
                            loc = self.ROI_xyr[ND]
                            raw_data[ND].append([])


                            for i in range(1,kin_cycle): #cut buffer data into individual image arrays: [ [img], [img], ...]
                                temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                                if(self.save_image and self.misc['save']):
                                    with open(self.data_path+f'\\FMODMR_c{c}_{i}.pkl', 'wb') as file:
                                        pickle.dump(temp_image, file)

                                #### LOCATION ######################################################################################################
                                px_x = loc[0]
                                px_y = loc[1]
                                ROI_rad = loc[2]
                                r_targ = loc[3]
                                ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad] #HAVE ROI_XYR UPDATE, more important for longer term though

                                if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                                    px_max = np.argmax(ROI)
                                    temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                                    temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                                    threshold_change = 10 #4?
                                    if (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change): 
                                        print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                                    else:
                                        px_y = temp_y
                                        px_x = temp_x
                                        loc = (px_x,px_y,ROI_rad,r_targ)
                                        # print((self.mx_x,self.mx_y))
                                ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
                                raw_data[ND][c].append(sum(sum(ROI)))

                    ## Now do leftover seq
                    self.sdk.SetNumberKinetics(kin_leftovers)
                    acq_img = 0
                    timeout = 0
                    while acq_img < kin_leftovers:
                        self.sdk.StartAcquisition()
                        ret = self.sdk.GetStatus()
                        if not ret[0] == 20002:
                            print('Starting Acquisition Failed, ending process...')
                            return
                        print('Starting Acquisition', ret)
                        time.sleep(0.1 * (timeout+1)) #Give time to start acquisition, not optimized
                        self.pulses.stream(FM_seqs[-1], 1)
                        #### Need to wait to get data
                        while(self.sdk.GetTotalNumberImagesAcquired()[1]<kin_leftovers and timeout_counter<=2000): #Should timeout counter be controlled better
                            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                            timeout_counter+=1 #ends up being ~0.4ms
                            if timeout_counter == 2000:                           
                                print('timeout')
                        print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
                        acq_img = self.sdk.GetTotalNumberImagesAcquired()[1]
                        if acq_img < kin_leftovers:
                            print('Not all images taken. Waiting and trying again...')
                            self.sdk.AbortAcquisition()
                            self.sdk.FreeInternalMemory()
                            timeout+=1
                            if timeout == 5:
                                return #fail if can't get proper amount of images 3 times in a row
                            time.sleep(2**timeout)
                        else:
                            timeout = 0

                    (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,kin_leftovers, kin_leftovers*1024**2) #keep bad image, want to read it out

                    for ND in range(len(self.ROI_xyr)):
                        loc = self.ROI_xyr[ND]
                        raw_data[ND].append([])


                        for i in range(1,kin_leftovers): #cut buffer data into individual image arrays: [ [img], [img], ...]
                            temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                            if(self.save_image and self.misc['save']):
                                with open(self.data_path+f'\\FMODMR_c{len(FM_seqs)}_{i}.pkl', 'wb') as file:
                                    pickle.dump(temp_image, file)

                            #### LOCATION ######################################################################################################
                            px_x = loc[0]
                            px_y = loc[1]
                            ROI_rad = loc[2]
                            r_targ = loc[3]
                            ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad] #HAVE ROI_XYR UPDATE, more important for longer term though

                            if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                                px_max = np.argmax(ROI)
                                temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                                temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                                threshold_change = 10 #4?
                                if (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change): 
                                    print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                                else:
                                    px_y = temp_y
                                    px_x = temp_x
                                    loc = (px_x,px_y,ROI_rad,r_targ)
                                    # print((self.mx_x,self.mx_y))
                            ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
                            raw_data[ND][-1].append(sum(sum(ROI)))


                    if(self.data_download):
                        with open(self.data_path+f'\\raw_data_{s}.pkl', 'wb') as file: 
                            pickle.dump(raw_data, file)
                self.t_db = time.time()


#############################################################################################################################
            if self.misc['DEBUG']:
                '''
                # Misc arguments: n_pair, throwaway,bg,rev,ref,N
                '''
                print('DEBUG')
                # if self.misc['pdb']:
                #     import pdb;pdb.set_trace()

                self.ODMR_data = np.divide(self.ODMR_data,self.sweeps)
                self.freq_data = np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True)
                '''
                # TODO: quick stats on acquired ODMR_data in order to find the optimal points for modulation.
                # Need:
                # estimated ZFS, sideband freq
                '''
                p,pcov = curve_fit(self.fit_func, self.freq_data,self.ODMR_data[0], [-0.02,-0.02,10e6,10e6,2.865e9,2.875e9,1])
                ZFS = (p[4]+p[5])/2 
                sb = (np.abs(p[4]-p[5]) + (p[2]+p[3])/(2*np.sqrt(3)))/2
                QL_slope = 3*np.sqrt(3)/4 * (p[0]/p[2] + p[1]/p[3])

                print(f'ZFS: {ZFS/1e9} GHz')
                print(f'sb: {sb/1e6} MHz')
                print(f'QL: {QL_slope} s')

                self.ODMR_data = np.multiply(self.ODMR_data,self.sweeps)

                '''
                # TODO: Switch sg to FM mode, run two point odmr N times, and save data.
                '''
                self.sg.mod_type = 'FM'
                self.sg.FM_mod_setter = Q_(sb,'Hz')
                self.sg.frequency = Q_(ZFS, 'Hz')
                two_pt_seq = self.pulses.I1I2_FT(self.exp_time,self.readout_time,10000000,5000000,debug_flag_rev = self.misc['rev']
                    , n_pair = self.misc['n_pair'], throwaway = self.misc['throwaway'], ref = self.misc['ref'], bg = True)

                #how many images are there:
                n_pair = self.misc['n_pair']
                throwaway = self.misc['throwaway']

                n_img = n_pair*2*2
                if self.misc['ref']:
                    n_img*=2
                
                n_img += throwaway
                print(f'n_img: {n_img}')
                self.sdk.SetNumberKinetics(n_img)

                I1_data = []
                I2_data = []
                raw_data = []
                for ND in range(len(self.ROI_xyr)):
                    I1_data.append([])
                    I2_data.append([])
                    raw_data.append([])


                self.t_db_setup = time.time()
                for n in range(self.misc['N']):
                    acq_img = 0
                    timeout = 0
                    while acq_img < n_img:
                        self.sdk.StartAcquisition()
                        ret = self.sdk.GetStatus()
                        if not ret[0] == 20002:
                            print('Starting Acquisition Failed, ending process...')
                            return
                        print('Starting Acquisition', ret)
                        time.sleep(0.1 * (timeout+1)) #Give time to start acquisition, not optimized
                        self.pulses.stream(two_pt_seq, 1)
                        #### Need to wait to get data
                        while(self.sdk.GetTotalNumberImagesAcquired()[1]<n_img and timeout_counter<=200): #Should timeout counter be controlled better
                            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                            timeout_counter+=1 #ends up being ~0.4ms
                            if timeout_counter == 200:                           
                                print('timeout')
                        print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
                        acq_img = self.sdk.GetTotalNumberImagesAcquired()[1]
                        if acq_img < n_img:
                            print('Not all images taken. Waiting and trying again...')
                            self.sdk.AbortAcquisition()
                            self.sdk.FreeInternalMemory()
                            timeout+=1
                            if timeout == 5:
                                return #fail if can't get proper amount of images 3 times in a row
                            time.sleep(2**timeout)


                        else:
                            timeout = 0

                    (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,n_img, n_img*1024**2) #keep bad image, want to read it out

                    for ND in range(len(self.ROI_xyr)):
                        loc = self.ROI_xyr[ND]
                        raw_data[ND].append([])
                        I1 = 0
                        I2 = 0
                        #I1 will be even in i - (throwaway) until n_pair*2-1, odd afterward


                        for i in range(throwaway,n_img): #cut buffer data into individual image arrays: [ [img], [img], ...]
                            temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                            if(self.save_image):
                                with open(self.data_path+f'\\I1I2_{n}_{i}.pkl', 'wb') as file:
                                    pickle.dump(temp_image, file)

                            #### LOCATION ######################################################################################################
                            px_x = loc[0]
                            px_y = loc[1]
                            ROI_rad = loc[2]
                            r_targ = loc[3]
                            ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad] #HAVE ROI_XYR UPDATE, more important for longer term though

                            if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                                px_max = np.argmax(ROI)
                                temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                                temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                                threshold_change = 10 #4?
                                if (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change): 
                                    print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                                else:
                                    px_y = temp_y
                                    px_x = temp_x
                                    loc = (px_x,px_y,ROI_rad,r_targ)
                                    # print((self.mx_x,self.mx_y))
                            ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
                            #####################################################################################################################
                            # if not take_bg:
                            #     if ((i-throwaway)%2==0 and (i-throwaway)<(n_pair*2-1)) or ((i-throwaway)%2==1 and (i-throwaway)>(n_pair*2)) : 
                            #         if not debug_flag_rev:
                            #             I1 += sum(sum(ROI))
                            #         else:
                            #             I2 += sum(sum(ROI))
                            #     else: #bright
                            #         if not debug_flag_rev:
                            #             I2 += sum(sum(ROI))
                            #         else:
                            #             I1 += sum(sum(ROI))    
                            # else:
                            #     if ((i-throwaway)%2==0 and (i-throwaway)<(n_pair*2-1)) or ((i-throwaway)%2==1 and (i-throwaway)>(n_pair*2)): 
                            #         I2 += sum(sum(ROI))
                            #         
                            #     else: #bright
                            #         I1 += sum(sum(ROI))
                            #         
                            raw_data[ND][n].append(sum(sum(ROI)))


                        # I1_data[ND].append(I1)
                        # I2_data[ND].append(I2)
                        # print(f'({I1},{I2}: {I1-I2})')

                        if(self.data_download):
                            # with open(self.data_path+f'\\I1_data.pkl', 'wb') as file: 
                            #     pickle.dump(I1_data, file)
                            # with open(self.data_path+f'\\I2_data.pkl', 'wb') as file: 
                            #     pickle.dump(I2_data, file)
                            with open(self.data_path+f'\\raw_data.pkl', 'wb') as file: 
                                pickle.dump(raw_data, file)
                self.t_db = time.time()


    def img_1D_to_2D(self,img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        img = np.zeros((x_len,y_len), dtype='int')
        for j in range(y_len):
            img[j,:] = img_1D[x_len*j:x_len*(j+1)] #np arrays count down first, then horizontally. That is, my image is saved as an array of rows, not an array of columns
        return img

    def closest_odd(self, num):
        if num%2 == 0:
            return num + 1
        else:
            return num

    def analyze(self,loc,first_sig,sweep,count):
        bg = 0
        sig = 0
        rng = range(1,self.runs*2+1)
        for i in rng: #cut buffer data into individual image arrays: [ [img], [img], ...]
            temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
            if(self.save_image):
                with open(self.data_path+f'\\Full_s{sweep + 1}_f{count}_{i-1}.pkl', 'wb') as file: #saving for each nanodiamond. That's not good
                    pickle.dump(temp_image, file)
            mx = np.max(temp_image)
            # if mx>=2.7e4:
            #     print(f'Warning, risk of saturation! Max pixel value {mx} detected')
            # else:
            #     print(mx)  
            #### LOCATION ######################################################################################################
            px_x = loc[0]
            px_y = loc[1]
            ROI_rad = loc[2]
            r_targ = loc[3]
            ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad]

            if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                px_max = np.argmax(ROI)
                temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                threshold_change = 10 #4?
                if (not first_sig and (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change)): 
                    print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                else:
                    px_y = temp_y
                    px_x = temp_x
                    loc = (px_x,px_y,ROI_rad,r_targ)
                    # print((self.mx_x,self.mx_y))
            ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
            #####################################################################################################################
            if i%2==0: #dark: offset by one due to initial throwaway pulse
                bg += sum(sum(ROI))
            else: #bright
                sig += sum(sum(ROI))
        return sig, bg, loc

    def finalize(self, device, PS_clk_channel, exp_time,cam_trigger,readout_time, gain, optimize_gain,runs_sweeps_reps, frequency, rf_amplitude, mw_duty, mw_rep, 
                        laser_lag,leave_laser_on, probe_time, repeat_every_x_minutes, data_download, 
                        data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,mode, trackpy, trackpy_params, Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,


        self.sig_data = np.divide(self.sig_data,self.sweeps)
        self.bg_data = np.divide(self.bg_data,self.sweeps)
        self.ODMR_data = np.divide(self.ODMR_data,self.sweeps)
        self.freq_data = np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True)
        if(self.data_download):
            with open(self.data_path+f'\\sig_data.pkl', 'wb') as file: 
                pickle.dump(self.sig_data, file)
            with open(self.data_path+f'\\bg_data.pkl', 'wb') as file: 
                pickle.dump(self.bg_data, file)
            with open(self.data_path+f'\\ODMR_data.pkl', 'wb') as file: 
                pickle.dump(self.ODMR_data, file)
            with open(self.data_path+f'\\freq_data.pkl', 'wb') as file: 
                pickle.dump(self.freq_data, file)



        ret = self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_CLOSED,27,27)
        print("Function SetShutter returned {}".format(ret))
        ## turns off instruments, close shutter
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False
        self.pulses.Pulser.reset()

        ## saves the data to an excel sheet.
        # if data_download:
        #     time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        #     print("name of spyrelet is", self.name+time_string)
        #     save_excel(self.name)
        #     print('data downloaded')

        #shuts down sdk
        if(self.misc['shutdown']):
            ret = self.sdk.ShutDown()
            print("SDK shutdown ")
            print(ret) ##returns 20002 if successful

        print(self.gain_string)

        
        for i in range(len(self.ODMR_data)):
            p,pcov = curve_fit(self.fit_func, self.freq_data,self.ODMR_data[i], [-0.02,-0.02,10e6,10e6,2.865e9,2.875e9,1])
            ZFS = (p[4]+p[5])/2
            HWHM = ((max(p[4],p[5])-min(p[4],p[5]))+p[2]/2+p[3]/2)/2
            Contrast = max(np.abs(p[0]),np.abs(p[1]))
            print(self.ROI_xyr[i],ZFS,HWHM,Contrast)

        print(f'The updated ND locations: {self.ROI_xyr}')
        self.t_fin = time.time()

        signal_time = exp_time.to('s').m * len(self.freq_data) * self.runs * self.sweeps * self.repetitions
        cam_down_time = readout_time.to('s').m * len(self.freq_data) * self.runs * self.sweeps * self.repetitions + (sleep_time.m+0.1) * len(self.freq_data) + self.sweeps * self.repetitions + (exp_time.to('s').m + readout_time.to('s').m) * len(self.freq_data) * self.sweeps * self.repetitions


        print(f'TOTAL EXPOSURE TIME was {signal_time} (seconds) and TOTAL CAM DOWN TIME was {cam_down_time}') #cam_down_time includes sleep and 0.1 second rest before acquisition, as well as readout, as well as throwaway
        
        t_ = f'Initialization: {self.t_init-self.t0} seconds, '
        t_+= f'Cooldown: {self.t_cool - self.t_init} seconds, '
        t_ +=f'Gain Optimization: {self.t_gain - self.t_cool} seconds, '
        t_ +=f'Experiment: {self.t_exp - self.t_gain} seconds, ' 
        if self.misc['DEBUG'] or self.misc['DEBUG_FM']:
            t_ +=f'Debug Setup: {self.t_db_setup - self.t_exp} seconds, '
            t_ +=f'Debug: {self.t_db - self.t_db_setup} seconds, '
            t_ +=f'Finalize: {self.t_fin - self.t_db} seconds.'
            db_sig_time = exp_time.to('s').m * self.misc['N'] * self.misc['n_pair'] * 2
            db_down_time = readout_time.to('s').m * self.misc['N'] * self.misc['n_pair'] * 2
            if self.misc['ref']:
                db_sig_time *= 2
                db_down_time *= 2
            db_down_time += 0.1 * self.misc['N'] + (exp_time.to('s').m + readout_time.to('s').m) * self.misc['N'] * self.misc['throwaway']
            print(f'TOTAL DEBUG EXPOSURE: {db_sig_time} seconds, TOTAL DEBUG DOWNTIME: {db_down_time} seconds')
        else:
            t_ +=f'Finalze: {self.t_fin - self.t_exp} seconds.'

        print(t_)    
        t_tot = self.t_fin - self.t0
        print(f'TOTAL TIME: {t_tot}')

        print("FINALIZE")

        return

    def pulse_setup(self, probe_time, collect_time, exp_time,runs, protected_readout,mode,cam_trigger):
        #print('\n using sequence without wait time')
        self.pulses.laser_lag = self.laser_lag
        self.pulses.read_time = self.probe_time #laser time per window
        self.pulses.frame_time = self.collect_time
        self.pulses.exp_time = self.exp_time
        self.pulses.runs = runs #number of runs per point
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            self.seqs.append(self.pulses.WFODMR(runs, self.exp_time, self.readout_time,mode = mode, FT = False, mw_duty = self.mw_duty, mw_rep = self.mw_rep))
        else:
            self.seqs.append(self.pulses.WFODMR(runs, self.exp_time,self.readout_time,10000000,5000000,mode, mw_duty = self.mw_duty, mw_rep = self.mw_rep))

    def fit_func(self, xs, A=-0.02, A2 = -0.02, gamma=10e6, gamma2=10e6, x0=2.865e9, x02=2.875e9, y0=1):
        return A/(1+(2*(xs-x0)/gamma)**2)+ A2/(1+(2*(xs-x02)/gamma2)**2)+y0
            

    

    @PlotFormatInit(LinePlotWidget, ['average', 'average_diff','average_div_0'])
    def init_format(p):
        p.xlabel = 'frequency (Hz)'
        p.ylabel = 'PL (cts)'


    ## this plots the running average of all sweeps.
    @Plot1D
    def average_0(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'sig': [sigs_averaged.index, sigs_averaged],
                'bg': [bgs_averaged.index, bgs_averaged]}

    @Plot1D
    def avg_sig_0(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        sigs_averaged = sigs.mean()
        return {'sig': [sigs_averaged.index, sigs_averaged]}


    ## this plots the difference of the running averages of all sweeps
    @Plot1D
    def average_diff_0(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark-bright': [sigs_averaged.index, sigs_averaged-bgs_averaged]}

    ## this plots the division of the running averages of all sweeps
    @Plot1D
    def average_div_0(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig
        bgs = grouped.bg
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}

    @Plot1D
    def average_div_1(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig1
        bgs = grouped.bg1
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}

    @Plot1D
    def average_div_2(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig2
        bgs = grouped.bg2
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}

    @Plot1D
    def average_div_3(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig3
        bgs = grouped.bg3
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}

    @Plot1D
    def average_div_4(df, cache):
        rep_df = df[df.rep_idx == 0]
        grouped = rep_df.groupby('f')
        sigs = grouped.sig4
        bgs = grouped.bg4
        sigs_averaged = sigs.mean()
        bgs_averaged = bgs.mean()
        return {'dark/bright': [sigs_averaged.index, sigs_averaged/bgs_averaged]}



'''
Code archive:

DEBUG was used for testing FM two-point, with Frame Transfer

if self.misc['DEBUG']:
    print('DEBUG')
    # if self.misc['pdb']:
    #     import pdb;pdb.set_trace()

    self.ODMR_data = np.divide(self.ODMR_data,self.sweeps)
    self.freq_data = np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True)


    p,pcov = curve_fit(self.fit_func, self.freq_data,self.ODMR_data[0], [-0.02,-0.02,10e6,10e6,2.865e9,2.875e9,1])
    ZFS = (p[4]+p[5])/2 
    sb = (np.abs(p[4]-p[5]) + (p[2]+p[3])/(2*np.sqrt(3)))/2
    QL_slope = 3*np.sqrt(3)/4 * (p[0]/p[2] + p[1]/p[3])

    print(f'ZFS: {ZFS/1e9} GHz')
    print(f'sb: {sb/1e6} MHz')
    print(f'QL: {QL_slope} s')

    self.ODMR_data = np.multiply(self.ODMR_data,self.sweeps)

    self.sg.mod_type = 'FM'
    self.sg.FM_mod_setter = Q_(sb,'Hz')
    self.sg.frequency = Q_(ZFS, 'Hz')
    two_pt_seq = self.pulses.I1I2_FT(self.exp_time,self.readout_time,10000000,5000000,debug_flag_rev = self.misc['rev']
        , n_pair = self.misc['n_pair'], throwaway = self.misc['throwaway'], ref = self.misc['ref'], bg = self.misc['bg'])

    #how many images are there:
    n_pair = self.misc['n_pair']
    throwaway = self.misc['throwaway']
    take_bg = self.misc['bg']

    n_img = n_pair*2
    if self.misc['ref']:
        n_img*=2
    if take_bg:
        n_img*=2
    n_img += throwaway
    print(f'n_img: {n_img}')
    self.sdk.SetNumberKinetics(n_img)

    I1_data = []
    I2_data = []
    raw_data = []
    for ND in range(len(self.ROI_xyr)):
        I1_data.append([])
        I2_data.append([])
        raw_data.append([])


    for n in range(self.misc['N']):

        acq_img = 0
        timeout = 0
        while acq_img < n_img:
            self.sdk.StartAcquisition()
            ret = self.sdk.GetStatus()
            if not ret[0] == 20002:
                print('Starting Acquisition Failed, ending process...')
                return
            print('Starting Acquisition', ret)
            time.sleep(0.1 * (timeout+1)) #Give time to start acquisition, not optimized
            self.pulses.stream(two_pt_seq, 1)
            #### Need to wait to get data
            while(self.sdk.GetTotalNumberImagesAcquired()[1]<n_img and timeout_counter<=200): #Should timeout counter be controlled better
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1 #ends up being ~0.4ms
                if timeout_counter == 200:                           
                    print('timeout')
            print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
            acq_img = self.sdk.GetTotalNumberImagesAcquired()[1]
            if acq_img < n_img:
                print('Not all images taken. Waiting and trying again...')
                self.sdk.AbortAcquisition()
                self.sdk.FreeInternalMemory()
                timeout+=1
                if timeout == 5:
                    return #fail if can't get proper amount of images 3 times in a row
                time.sleep(2**timeout)


            else:
                timeout = 0

        (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,n_img, n_img*1024**2) #keep bad image, want to read it out

        for ND in range(len(self.ROI_xyr)):
            loc = self.ROI_xyr[ND]
            raw_data[ND].append([])
            I1 = 0
            I2 = 0
            #I1 will be even in i - (throwaway) until n_pair*2-1, odd afterward


            for i in range(throwaway,n_img): #cut buffer data into individual image arrays: [ [img], [img], ...]
                temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                if(self.save_image):
                    with open(self.data_path+f'\\I1I2_{n}_{i}.pkl', 'wb') as file:
                        pickle.dump(temp_image, file)

                #### LOCATION ######################################################################################################
                px_x = loc[0]
                px_y = loc[1]
                ROI_rad = loc[2]
                r_targ = loc[3]
                ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad] #HAVE ROI_XYR UPDATE, more important for longer term though

                if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                    px_max = np.argmax(ROI)
                    temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                    temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                    threshold_change = 10 #4?
                    if (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change): 
                        print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                    else:
                        px_y = temp_y
                        px_x = temp_x
                        loc = (px_x,px_y,ROI_rad,r_targ)
                        # print((self.mx_x,self.mx_y))
                ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
                #####################################################################################################################
                # if not take_bg:
                #     if ((i-throwaway)%2==0 and (i-throwaway)<(n_pair*2-1)) or ((i-throwaway)%2==1 and (i-throwaway)>(n_pair*2)) : 
                #         if not debug_flag_rev:
                #             I1 += sum(sum(ROI))
                #         else:
                #             I2 += sum(sum(ROI))
                #     else: #bright
                #         if not debug_flag_rev:
                #             I2 += sum(sum(ROI))
                #         else:
                #             I1 += sum(sum(ROI))    
                # else:
                #     if ((i-throwaway)%2==0 and (i-throwaway)<(n_pair*2-1)) or ((i-throwaway)%2==1 and (i-throwaway)>(n_pair*2)): 
                #         I2 += sum(sum(ROI))
                #         
                #     else: #bright
                #         I1 += sum(sum(ROI))
                #         
                raw_data[ND][n].append(sum(sum(ROI)))


            # I1_data[ND].append(I1)
            # I2_data[ND].append(I2)
            # print(f'({I1},{I2}: {I1-I2})')

            if(self.data_download):
                # with open(self.data_path+f'\\I1_data.pkl', 'wb') as file: 
                #     pickle.dump(I1_data, file)
                # with open(self.data_path+f'\\I2_data.pkl', 'wb') as file: 
                #     pickle.dump(I2_data, file)
                with open(self.data_path+f'\\raw_data.pkl', 'wb') as file: 
                    pickle.dump(raw_data, file)

############################################################################################################################################################################
DEBUG was used to figure out frame transfer


        if self.misc['DEBUG']:
            ####DEBUG
            print('DEBUG')
            count = 0
            # import pdb;pdb.set_trace()
            #include exp_buffer
            buff = self.misc['buff'] #in ns
            trig = self.misc['trig'] #in ns
            exp = exp_time.to('ns').m
            read = readout_time.to('ns').m
            self.sdk.SetExposureTime((exp+buff)/1000000000) #-exposure_min not necessary
            self.sdk.SetNumberKinetics(3)


            self.sdk.PrepareAcquisition()
            debug_seq = self.pulses.debug_cam_pulse(exp,read,trig,buff)
            self.sdk.StartAcquisition()
            ret = self.sdk.GetStatus()
            if not ret[0] == 20002:
                print('Starting Acquisition Failed, ending process...')
                return
            time.sleep(0.2)
            t0 = time.time()
            self.pulses.stream(debug_seq, 1)
            while(self.sdk.GetTotalNumberImagesAcquired()[1]<3 and count<=200):
                time.sleep(0.005)#Might want to base wait time on pulse streamer signal
                count += 1
                if count%100 == 0:
                    print(self.sdk.GetTotalNumberImagesAcquired()[1])
                if count==200:
                    print('timeout') 
            print(time.time()-t0)

            (ret, self.all_data, validfirst, validlast) = self.sdk.GetImages16(1,3, (3)*1024**2) #keep bad image, want to read it out
            for i in range(3):
                temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                if(self.save_image):
                    with open(self.data_path+f'\\img{i}.pkl', 'wb') as file:
                        pickle.dump(temp_image, file)
            print('ENDING DEBUG')
            return
            ####

'''