###########################
# imports
###########################

# std
import numpy as np
import time
import math
from itertools import cycle
import logging
import scipy as sp #Unused?
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
        'device':{'type': str,'default': 'Dev1',},
        'PS_clk_channel':{'type': str,'default': 'PFI0',},
        'exp_time':{'type':float,'units':'s','suffix': 's','default': 100e-3,},

        'readout_time':{ #this represents the readout time. cannot be lower than 30MHz
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 59e-3,
        },
 

        'gain':{ #EM gain for camera, goes from 1-272
            'type':int,
            'default': 1,
            'positive': True

        },
        'repeat_every_x_minutes':{
            'type': float,
            'default': .1,
            'positive': True
        },

        'sweeps_reps':{'type': str, 'default': '[1,1]'},
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
            'type': float,
            'units':'Hz',
            'suffix': 'Hz',
            'default': 14e6,
        },
        'rf_amplitude':{
            'type': float,
            'default': -15,
        },
        # 'probe_time':{ #total amount of time the microwave is pulsed (on or off)
        #     'type': float,
        #     'default': 160e-3,
        #     'suffix': 's',
        #     'units': 's'
        # },

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
            'default': True
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
        'ROI_xyr':{'type': str, 'default': ' (512,512,16,7)'},

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
        'default': True
        },
        'Misc':{'type': str, 'default': '[True]',} #a parameter to allow for quickly testing functionalities
    }
    
    def initialize(self, device, PS_clk_channel, exp_time,readout_time, gain, optimize_gain,sweeps_reps, frequencies,slope_range,sideband_frequency, rf_amplitude,
                        laser_lag,leave_laser_on, repeat_every_x_minutes, data_download, 
                        data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,
        self.sb = sideband_frequency.m
        self.frequency = Q_(np.linspace(eval(frequencies)[0], eval(frequencies)[1], eval(frequencies)[2], endpoint = True),'Hz')

        self.ROI_xyr = eval(ROI_xyr)
        
        ## Tracking
        self.mx_x = -1
        self.mx_y = -1
        ## create self parameters ------------------------------
        print('Initializing Two-Point WFODMR')
        ##Protocol
        self.gain_string = ''
        self.t_start = time.time()
        self.repetitions = eval(sweeps_reps)[1]
        self.sweeps = eval(sweeps_reps)[0]
        self.data_path = data_path
        if(data_download or save_image):
            if(not os.path.isdir(self.data_path)):
                os.mkdir(self.data_path)
            else:
                self.data_path = self.data_path+f'_{time.time()}'
                os.mkdir(self.data_path)
        ##sg, ps params
        self.sg.rf_amplitude = rf_amplitude ## set SG paramaters: running this spyrelet with IQ inputs
        self.sg.mod_type = 'FM'
        self.sg.rf_toggle = True
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
        self.sg.FM_mod_setter = sideband_frequency

        self.laser_lag = int(round(laser_lag.to("ns").m))
        self.sleep_time = sleep_time
        self.exp_time = exp_time.to('ns').m #time of exposure
        self.readout_time = readout_time.to('ns').m
        self.collect_time = self.exp_time+self.readout_time #total "camera busy" time
        if self.laser_lag < 70000000:
            print('laser lag must be at least 70 ms for camera initialization.')
            return
        elif self.laser_lag > 70000000 + 1.5 * self.exp_time:
            print('risk of over-exposing during initialization! laser lag too high.')
            raise Exception()

        ##Camera setup
        self.sdk = atmcd("")  # Load the atmcd library
        self.codes = atmcd_codes
        ret = self.sdk.Initialize("")  # Initialize camera
        print("Function Initialize returned {}".format(ret)) #returns 20002 if successful
        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.KINETICS) #Taking a series of pulses
        self.sdk.SetReadMode(self.codes.Read_Mode.IMAGE) #reading pixel-by-pixel with no binning
        self.sdk.SetTriggerMode(self.codes.Trigger_Mode.EXTERNAL_EXPOSURE_BULB) #Pulse  length controls exposure
        (ret, xpixels, ypixels) = self.sdk.GetDetector()
        self.sdk.SetImage(1, 1, 1, xpixels, 1, ypixels) #defining image
        self.sdk.SetEMCCDGain(gain) #setting Electron Multiplier Gain

        self.test_bool = eval(Misc)[0]

        if (self.test_bool):
            self.n_pulse = 6
        else:
            self.n_pulse = 5

        self.sdk.SetNumberKinetics(self.n_pulse)


        self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_OPEN,27,27) #Open Shutter


        ##connect to pulse sequence------------------------------------------
        self.seqs = []
        # import pdb; pdb.set_trace()
        self.pulse_setup(self.laser_lag, self.exp_time,self.sb,self.readout_time,protected_readout) #5 exposures per run: 1 sacrificial and 4 sideband points, snaking 

    def pulse_setup(self, laser_lag, exp_time,sb_freq, readout_time, protected_readout):
        if protected_readout and self.test_bool:
            self.seqs.append(self.pulses.I1I2_double(exp_time, readout_time,sb_freq, laser_lag)) 
        elif protected_readout:
            self.seqs.append(self.pulses.I1I2(exp_time, readout_time,sb_freq, laser_lag)) 
        else:
            print('have not implemented quickpulse yet... will not work')
            return
            #self.seqs.append(self.pulses.WFODMR(self.exp_time, self.collect_time))#list of sequences to be compatible with read_odmr() and PulsedODMR class


    def main(self, device, PS_clk_channel, exp_time,readout_time, gain, optimize_gain,sweeps_reps, frequencies,slope_range,sideband_frequency, rf_amplitude, 
                    laser_lag,leave_laser_on, repeat_every_x_minutes, data_download, 
                    data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,
        ##Cool -------------------------------------------------------------------------
        if(cooler):
            ret = self.sdk.SetTemperature(Temp)
            print(f"Function SetTemperature returned {ret} target temperature {Temp}")
            ret = self.sdk.CoolerON()
            while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
                time.sleep(5)
                (ret, temperature) = self.sdk.GetTemperature()
                print("Function GetTemperature returned {} current temperature = {} ".format(
                    ret, temperature), end='\r')

        ## Optimize gain/ take first image to reset camera dynamics ------------------------------------------------------------------------
        '''
        Camera dynamics: the first image(s?) taken after the camera has been prepared for the first time each experiment are wildly off
        '''
        self.sdk.PrepareAcquisition()
        if(optimize_gain):
            t_gain_start = time.time()

            self.gain = gain
            print('optimizing gain...')
            mx = 0
            while(mx<=2.0e4 or mx>=2.7e4):
                self.sdk.StartAcquisition()
                ret = self.sdk.GetStatus()
                if not ret[0] == 20002:
                    print('Starting Acquisition Failed, ending process...')
                    return
                #print('Starting Acquisition', ret)
                time.sleep(0.1) #Give time to start acquisition
                #import pdb; pdb.set_trace()
                self.sg.frequency = self.frequency[0] ## make sure the sg frequency is set! (overhead of <1ms)
                self.pulses.stream(self.seqs[0], 1) #0 since only one seq in my seq array.
                timeout_counter = 0
                while(self.sdk.GetTotalNumberImagesAcquired()[1]<3 and timeout_counter<=400): #20 second hard-coded limit!
                    time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                    timeout_counter+=1 
                (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(3,3,1024**2) #cut out first image here
                #print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])
                temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
                mx = np.max(temp_image)
                print(f'gain of {self.gain}, mx is {mx}')
                if(mx<=1.0e4):
                    print('signal really low, raising gain +5')
                    self.gain+=5
                elif mx<=2.0e4:
                    print('raising gain +1')
                    self.gain+=1
                elif mx>=3.2e4:
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')
                    self.gain-=5
                elif mx>=2.7e4: 
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
                    self.gain-=2
                if self.gain <= 0:
                    self.gain = 1
                self.sdk.SetEMCCDGain(self.gain) #setting Electron Multiplier Gain
                self.sdk.PrepareAcquisition()
                ret = self.sdk.GetEMCCDGain()
                if self.gain>=80:
                    print('Warning! Gain too high! Re-adjust experiment parameters, or turn off optimize_gain, or edit the limit in the spyrelet code. Aborting...')
                    return
                time.sleep(0.6)
            self.gain_string = f'optimum gain determined to be {self.gain}, giving max pixel value of roughly {mx}'
            print(self.gain_string)
            t_gain_end = time.time()
            self.t_gain = t_gain_end -t_gain_start
        else:
            self.gain = gain
            t_gain_start = time.time()
            print('Initial capture to counteract camera dynamics...')
            mx = 0
            self.sdk.StartAcquisition()
            ret = self.sdk.GetStatus()
            if not ret[0] == 20002:
                print('Starting Acquisition Failed, ending process...')
                return
            time.sleep(0.1) #Give time to start acquisition
            self.sg.frequency = frequency[0] ## make sure the sg frequency is set! (overhead of <1ms)
            self.pulses.stream(self.seqs[0], 1) 
            timeout_counter = 0
            while(self.sdk.GetTotalNumberImagesAcquired()[1]<3 and timeout_counter<=400): #20 second hard-coded limit!
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1 
            (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(3,3,1024**2) #cut out first image here
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
            t_gain_end = time.time()
            self.t_gain = t_gain_end -t_gain_start

        ## Begin Experiment ################################################################################################################
        for rep in range(self.repetitions):
            for sweep in self.progress(range(self.sweeps)):
                count = 0
                for f in self.frequency:
                    print("frequency: ", f)
                    self.sdk.StartAcquisition()
                    ret = self.sdk.GetStatus()
                    if not ret[0] == 20002:
                        print('Starting Acquisition Failed, ending process...')
                        return
                    print('Starting Acquisition', ret)
                    time.sleep(0.1) #Give time to start acquisition, not optimized


                    self.sg.frequency = f 
                    self.t0= time.time()
                    if(leave_laser_on):
                        self.pulses.stream_LLO(self.seqs[0], 1)
                    else:
                        self.pulses.stream(self.seqs[0], 1)
                    timeout_counter = 0
                    while(self.sdk.GetTotalNumberImagesAcquired()[1]< self.n_pulse and timeout_counter<=250): #timeout counter should be controlled better
                        time.sleep(0.02)
                        timeout_counter+=1 
                    (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(1,self.n_pulse,self.n_pulse*1024**2) #keep bad image, want to read it out
                    print("Number of images collected in current acquisition: ", self.sdk.GetTotalNumberImagesAcquired()[1])

                    if(save_image and count==0):
                        self.sdk.SaveAsSif(self.data_path+'\\Characteristic_Image.sif')

                    ## ANALYSIS ####################################################################################################################
                    img_arr = []
                    I1 = 0
                    I2 = 0
                    rng = range(self.n_pulse-4,self.n_pulse)
                    for i in rng: #cut buffer data into individual image arrays: [ [img], [img], ...]

                        temp_image = self.img_1D_to_2D(all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                        mx = np.max(temp_image)
                        # if mx>=2.7e4:
                        #     print(f'Warning, risk of saturation! Max pixel value {mx} detected')
                        # else:
                        #     print(mx)  
                        if(data_download):
                            with open(self.data_path+f'\\Full_s{sweep+1}_f{count}_{i-1}.pkl', 'wb') as file: 
                                pickle.dump(temp_image, file)
                        
                        if self.mx_x == -1:
                            px_x = eval(ROI_xyr)[0]
                            px_y = eval(ROI_xyr)[1]
                        else:
                            px_x = self.mx_x
                            px_y = self.mx_y
                        ROI_rad = eval(ROI_xyr)[2]
                        r_targ = eval(ROI_xyr)[3]
                        ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad]
                        ## Tracking
                        if i==rng[0]: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
                            px_max = np.argmax(ROI)
                            temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
                            temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
                            threshold_change = 4
                            if (self.mx_x != -1 and (np.abs(self.mx_x-temp_x) + np.abs(self.mx_y-temp_y) > threshold_change)): 
                                print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
                            else:
                                self.mx_y = temp_y
                                self.mx_x = temp_x
                                print((self.mx_x,self.mx_y))
                        ROI = temp_image[self.mx_y-r_targ:self.mx_y+r_targ,self.mx_x-r_targ:self.mx_x+r_targ]

                        if(data_download and count == 0):
                            with open(self.data_path+f'\\ROI_s{sweep+1}_f{count}_{i-1}.pkl', 'wb') as file: 
                                pickle.dump(ROI, file)
                        print(sum(sum(ROI)))
                        if i==rng[0] or i==rng[-1]: 
                            I1 += sum(sum(ROI))
                        else: #bright
                            I2 += sum(sum(ROI))
                        # if i == rng[0]:
                        #     I1+= sum(sum(ROI))
                        # elif i == rng[1]:
                        #     I2+= sum(sum(ROI))
                    ######################################################################################
                        

                    ## acquire the following: return statement equivalent
                    self.acquire({
                        'sweep_idx': sweep,
                        'carrier_f': f,
                        'I1': I1,
                        'I2' : I2,
                        'w1' : f.m - self.sb,
                        'w2' : f.m + self.sb
                    }) 
                    count +=1


                    #mysterious overhead time
                    print("sleep time (s): ", sleep_time.m) #maybe move this
                    time.sleep(sleep_time.m)

            time.sleep(repeat_every_x_minutes * 60)

    def img_1D_to_2D(self,img_1D,x_len,y_len):
            '''
            turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
            '''
            img = np.zeros((x_len,y_len), dtype='int')
            for j in range(y_len):
                img[j,:] = img_1D[x_len*j:x_len*(j+1)] #np arrays count down first, then horizontally. That is, my image is saved as an array of rows, not an array of columns
            return img


    def finalize(self, device, PS_clk_channel, exp_time,readout_time, gain, optimize_gain,sweeps_reps, frequencies,slope_range,sideband_frequency, rf_amplitude, 
                        laser_lag,leave_laser_on, repeat_every_x_minutes, data_download, 
                        data_path, sleep_time, save_image,ROI_xyr,protected_readout,cooler,Temp,Misc): #radius, threshold, minmass, link_radius, microns_per_pixel,

        
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
        ret = self.sdk.ShutDown()
        print("SDK shutdown ")
        print(ret) ##returns 20002 if successful

        print(self.gain_string)
        self.t_end = time.time()
        print(f'Total time of experiment: {self.t_end - self.t_start}, including t_gain = {self.t_gain}')
        ## experiment finishes
        self.slope_range = slope_range
        quasilinear_calibration_slope, quasilinear_zero_field_splitting = self.quasilinear_slope_extraction()        
        print(str(quasilinear_calibration_slope) + 
              ' is the quasilinear slope between the frequency change and the fluorescence change. The zero field splitting is '
              + str(quasilinear_zero_field_splitting))
        print("FINALIZE")

        return


    def quasilinear_slope_extraction(self):
            df = self.data
            grouped = df.groupby('carrier_f')
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
            left_frequency_slope = eval(self.slope_range)[0] 
            right_frequency_slope = eval(self.slope_range)[1]

            index_left = np.abs(df.carrier_f - left_frequency_slope).idxmin()
            index_right = np.abs(df.carrier_f - right_frequency_slope).idxmin()

            x_values = x_values[index_left : index_right + 1]
            y_values = y_values[index_left : index_right + 1]

            linear_regression = np.polyfit(x_values, y_values, 1)

            # Shivam: Calculating the slope of the line and the y = 0 value (zero field splitting of ODMR)
            slope = linear_regression[0]
            odmr_zfs = -linear_regression[1] / linear_regression[0]
            print(slope)
            print(odmr_zfs)
            return slope, odmr_zfs
    

    @PlotFormatInit(LinePlotWidget, ['average','average_normalized','I2I1','I2I1_normalized'])
    def init_format(p):
        p.xlabel = 'frequency (GHz)'
        p.ylabel = 'PL (cts)'

    @Plot1D
    def average(df, cache):
        grouped = df.groupby('carrier_f')
        freq_left = grouped.w1
        freq_right = grouped.w2
        sigs_left = grouped.I1
        sigs_right = grouped.I2
    

        freq_left_mean = freq_left.mean()
        freq_right_mean = freq_right.mean()
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        return {'sig 1': [freq_left_mean, sigs_left_mean], 'sig 2': [freq_right_mean, sigs_right_mean]}
    ## add plot for tracking

    @Plot1D
    def average_normalized(df, cache):
        grouped = df.groupby('carrier_f')
        freq_left = grouped.w1
        freq_right = grouped.w2
        sigs_left = grouped.I1
        sigs_right = grouped.I2
    

        freq_left_mean = freq_left.mean()
        freq_right_mean = freq_right.mean()
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        norm = (sigs_left_mean+sigs_right_mean)/2

        return {'sig 1': [freq_left_mean, sigs_left_mean/norm], 'sig 2': [freq_right_mean, sigs_right_mean/norm]}

    @Plot1D
    def I2I1_normalized(df, cache):
        grouped = df.groupby('carrier_f')
        sigs_left = grouped.I1
        sigs_right = grouped.I2
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean
        norm = (sigs_left_mean+sigs_right_mean)/2
        sigs_norm = sigs_diff/norm

        return {'I2I1': [sigs_norm.index,sigs_norm]}

    @Plot1D
    def I2I1(df, cache):
        grouped = df.groupby('carrier_f')
        sigs_left = grouped.I1
        sigs_right = grouped.I2
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        sigs_diff = sigs_right_mean - sigs_left_mean
        norm = (sigs_left_mean+sigs_right_mean)/2

        return {'I2I1': [sigs_diff.index,sigs_diff]}

    @Plot1D
    def norm(df, cache):
        grouped = df.groupby('carrier_f')
        sigs_left = grouped.I1
        sigs_right = grouped.I2
        sigs_left_mean = sigs_left.mean()
        sigs_right_mean = sigs_right.mean()

        norm = (sigs_left_mean+sigs_right_mean)/2

        return {'norm': [norm.index,norm]}

