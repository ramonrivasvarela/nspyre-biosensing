###########################
# imports
###########################

# std
import numpy as np
import time
from itertools import cycle
import logging
from scipy.optimize import curve_fit
from scipy import signal #Unused?
import datetime as Dt
import pims
from pims import Frame, FramesSequence
#from skimage.io import imsave, imread #Not working?
from PIL import Image
import pickle #Delete later
import trackpy as tp

# importing the sys module
import sys, os

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader

# nspyre

from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue
from nspyre import InstrumentManager, DataSource, StreamingList
from pathlib import Path

from experiments.camera_settings_tasks.gain_optimization import get_gain
from experiments.initializecamera import CameraInitialization

#from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence


# for data download


#importing sdk
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

###########################
# classes
###########################

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

#spyrelet
class WideFieldODMR():
 
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

    def widefield(self, dataset, 
                  exp_time:float=75e-3, 
                  cam_trigger:str='EXTERNAL_FT', 
                  readout_time:float=15e-3, 
                  gain:int=2, 
                  optimize_gain:bool=True, 
                  runs_sweeps_reps:str='(1,1,1)',
                  frequency:tuple='(2.85e9, 2.89e9, 30)', 
                  rf_amplitude:float=-15, 
                  mw_duty:float=1, 
                  mw_rep:int=50,
                  laser_lag:float=0.07, 
                  probe_time:float=160e-3, 
                  repeat_every_x_minutes:float=0, 
                  data_download:bool=False,
                  data_path:str='Z:\\biosensing_setup\\data\\WFODMR_images_test', 
                  sleep_time:float=0, 
                  save_image:bool=False, 
                  trackpy:bool=False,
                  trackpy_params:str="(False, 40, 800)",
                  ROI_xyr:str='[(512,512,16,7)]', 
                  protected_readout:bool=False, 
                
                #   cooler:bool=False, 
                #   Temp:int=20, 
                  mode:str='QAM', 
                  Misc:str="{'DEBUG':False, 'DEBUG_FM': False, 'shutdown': False}"): 
        
        ### WARNING!!!! probe_time, exp_time, laser_lag, readout_time are all in NANOSECONDS

        # radius, threshold, minmass, link_radius, microns_per_pixel,
        with InstrumentManager() as mgr, DataSource(dataset) as data_source:
            self.initialize(mgr, exp_time,cam_trigger,readout_time, gain, runs_sweeps_reps, frequency, rf_amplitude, mw_duty, mw_rep,
                            laser_lag, probe_time, data_download, 
                            data_path, sleep_time, save_image,ROI_xyr,protected_readout,mode, Misc)
            self.t_cool = self.t_init
            # if(cooler):
            #     mgr.Camera.
            #     self.t_cool = time.time()
            self.gain=get_gain(mgr, optimize_gain, gain, self.runs, mode, self.ns_exp_time, self.ns_readout_time)
            self.t_gain = time.time()
            plots={}
            for nd in range(len(self.ROI_xyr)):
                plots[f"signal_{nd+1}"]=StreamingList()
                plots[f"background_{nd+1}"]=StreamingList()
            for rep in range(self.repetitions):
                for sweep in range(self.sweeps):
                    counts_list=np.empty(len(self.frequencies))
                    counts_list[:] = np.nan
                    for nd in range(len(self.ROI_xyr)):
                        plots[f"signal_{nd+1}"].append(np.stack([self.frequencies/1e9, counts_list]))
                        plots[f"background_{nd+1}"].append(np.stack([self.frequencies/1e9, counts_list]))
                    count = 0
                    for f, freq in enumerate(self.frequencies):
                        print("frequency: ", freq)

                        #import pdb;pdb.set_trace()
                        mgr.Camera.start_acquisition()
                        ret, _ = mgr.Camera.get_status()
                        if not ret == 20002:
                            print('Starting Acquisition Failed, ending process...')
                            return
                        print('Starting Acquisition', ret)
                        time.sleep(0.1) #Give time to start acquisition, not optimized
                        mgr.sg.set_frequency(freq) ## make sure the sg frequency is set! (overhead of <1ms)
                        mgr.Pulser.stream_umOFF(self.seqs[0], 1, AM = self.AM_mode, SWITCH = self.switch_mode)
                        timeout_counter = 0

                        #### Need to wait to get data
                        while(mgr.Camera.get_total_number_images_acquired()[1]<self.runs*2+1 and timeout_counter<=100): #Should timeout counter be controlled better
                            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                            timeout_counter+=1 #ends up being ~0.4ms
                        

                        ret, self.all_data, _, _ = mgr.Camera.get_images_16(1,self.runs*2+1, (1+self.runs*2)*1024**2) #keep bad image, want to read it out
                        print("Number of images collected in current acquisition: ", mgr.Camera.get_total_number_images_acquired()[1])

                        if(save_image and count==0):
                            mgr.Camera.save_as_sif(self.data_path+'\\Characteristic_Image.sif')#Saves both mw-on and mw-off images as SIF
   
                        ### Trackpy section

                        if trackpy and count == 0 and sweep == 0: #WE need to make sure this only happens on the first run of the first sweep
                            rng = range(1,self.runs*2+1)
                            for i in rng: #cut buffer data into individual image arrays: [ [img], [img], ...]
                                temp_image = self.img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
                            #tp_params = eval(trackpy_params)
                            #temp_frame = [Frame(temp_image.astype('int32'), frame_no = 0)]
                            temp_frame = [Frame(temp_image, frame_no = 0)]
                            try:
                                loc0 = self.ROI_xyr[0] #trackpy param? loc0[2] needs to be odd.
                            except:
                                raise ValueError(f'ROI_xyr is {self.ROI_xyr}')
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

                            f0 = tp.locate(temp_frame[0], self.closest_odd(loc0[2]), minmass=eval(trackpy_params)[1], threshold=eval(trackpy_params)[2], invert=eval(trackpy_params)[0])
                            if(self.save_image):
                                with open(self.data_path+f'\\f0.pkl', 'wb') as file:
                                    pickle.dump(f0, file)

                            locs_tp = []
                            for i in range(len(f0)):
                                locs_tp.append(tuple((int(f0.iloc[i]['x']), int(f0.iloc[i]['y']), loc0[2], int(2 * f0.iloc[i]['size']))))
                            self.ROI_xyr = locs_tp

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
                            plots[f"signal_{ND+1}"][-1][1][f] = sig
                            plots[f"signal_{ND+1}"].updated_item(-1)
                            plots[f"background_{ND+1}"][-1][1][f] = bg
                            plots[f"background_{ND+1}"].updated_item(-1)

                        while len(sigs)<5:
                            sigs.append(0)
                            bgs.append(0)

                    
                        print(plots)
                        ## acquire the following
                        data_source.push({
                            'params':{
                                'exp_time':exp_time,
                                'cam_trigger':cam_trigger,
                                'readout_time':readout_time,
                                'gain':self.gain,
                                'repeat_every_x_minutes':repeat_every_x_minutes,
                                'runs_sweeps_reps': runs_sweeps_reps,
                                'ROI_xyr': ROI_xyr,
                                'frequency': frequency,
                                'rf_amplitude':rf_amplitude,
                                'mw_duty':self.mw_duty,
                                'mw_rep':self.mw_rep,
                                'probe_time': probe_time,
                                'laser_lag':laser_lag,
                                'optimize_gain': optimize_gain,
                                'sleep_time':self.sleep_time,
                                'data_path':self.data_path
                                
                            },
                            'title': 'Counts vs Time (Confocal)',
                            'xlabel': 'Time (s)',
                            'ylabel': 'Counts',
                            'datasets': plots
                        })
                        

                        
                        #mysterious overhead time
                        print("sleep time (s): ", sleep_time) #maybe move this
                        time.sleep(sleep_time)
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            self.finalize(mgr, exp_time, readout_time, frequency, sleep_time)
                            return





                
                time.sleep(repeat_every_x_minutes * 60)
                
                
                        

            self.finalize(mgr, exp_time, readout_time, frequency, sleep_time, ended=True) #radius, threshold, minmass, link_radius, microns_per_pixel,



    

    def initialize(self, mgr, exp_time, cam_trigger, readout_time, gain, runs_sweeps_reps, frequency, rf_amplitude, mw_duty, mw_rep,
                   laser_lag, probe_time, data_download,
                   data_path, sleep_time, save_image, ROI_xyr, protected_readout, mode, Misc):  # radius, threshold, minmass, link_radius, microns_per_pixel,
        self.t0 = time.time()

        self.misc = eval(Misc)
        self.ROI_xyr = eval(ROI_xyr)
        eval_frequency = eval(frequency)
        self.frequencies = np.linspace(eval_frequency[0], eval_frequency[1], eval_frequency[2], endpoint=True)

        self.t_gain = None

        self.sig_data = []
        self.bg_data = []
        self.ODMR_data = []
        for ND in range(len(self.ROI_xyr)):
            self.sig_data.append(np.zeros(len(self.frequencies)))
            self.bg_data.append(np.zeros(len(self.frequencies)))
            self.ODMR_data.append(np.zeros(len(self.frequencies)))
        self.gain_string = ''
        ## create self parameters ------------------------------
        print('Initializing WFODMR_New')
        #initialize experiment params---------------------------------------
        #self.sequence = sequence #type of ODMR sequence from the list
        self.index = 0
        eval_runs_sweeps_reps = eval(runs_sweeps_reps)
        self.repetitions = eval_runs_sweeps_reps[2]
        self.runs = eval_runs_sweeps_reps[0] #let's have a sacrificial set of images! Toss the first run because that point is always strange

        #self.channel = channel1 #reading channel
        mgr.sg.set_rf_amplitude(rf_amplitude) ## set SG paramaters: running this spyrelet with IQ inputs
        self.ns_probe_time = int(round(probe_time*1e9)) #laser time per window
        self.point_num = len(frequency)
        self.sweeps = eval_runs_sweeps_reps[1]
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

        ret = mgr.Camera.initialize()  # Initialize camera
        print("Function Initialize returned {}".format(ret)) #returns 20002 if successful

        #Can probably get rid of 'ret' but not important...
        mgr.Camera.set_acquisition_mode("Kinetics") #Taking a series of pulses
        mgr.Camera.set_read_mode("Image") #reading pixel-by-pixel with no binning
        '''
        For some reason if you move SetTriggerMode to a later line the camera seems to go to internal or something?
        '''
 
        self.ns_exp_time = exp_time*1e9
        self.ns_readout_time = readout_time*1e9
        self.ns_laser_lag = int(round(laser_lag*1e9))
        self.ns_collect_time = self.ns_exp_time+self.ns_readout_time

        if cam_trigger == 'EXTERNAL_EXPOSURE':
            mgr.Camera.set_trigger_mode("External Exposure (Bulb)") #Pulse  length controls exposure
            if self.ns_laser_lag < self.ns_readout_time+10000000:
                print('laser lag must be larger than readout_time + 10 ms for camera initialization.')
                return
            elif self.ns_laser_lag > self.ns_readout_time + 1.5 * self.ns_exp_time:
                print('risk of over-exposing during initialization! laser lag too high.')
                return
        else:
            '''
            exposure min is 46.611 ms. The set exposure time is done in excess of this s.t. exp_time = 0 corresponds to 46.611 ms exposure.
            The pulse streamer will trigger the camera by sending pulses of 10ms, and the rest of the exposure time plus any set readout time will be 
            sent to the pulse streamer as readout time
            '''
            mgr.Camera.set_trigger_mode("External") #Pulse  length controls exposure
            exposure_min = 0.046611e9
            if self.ns_exp_time < exposure_min:
                print(f'exposure must be at least {exposure_min*1000} ms.')
            elif self.ns_exp_time + self.ns_readout_time < 80000000:
                print('May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            mgr.Camera.set_exposure_time(self.ns_exp_time*1e-9) 
            #### ps-ended stuff
            mgr.Camera.set_frame_transfer_mode("Conventional") #conventional frame transfer mode
            print('frame transfer mode on')

        if self.ns_readout_time<5000000:
            print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
        if self.ns_collect_time >= self.ns_probe_time:
            print('WARNING probe time cannot be less than or equal to collect time!')
            

        (ret, xpixels, ypixels) = mgr.Camera.get_detector()
        mgr.Camera.set_image()

        mgr.Camera.set_emccdgain(gain) #setting Electron Multiplier Gain
        mgr.Camera.set_number_accumulations(int((self.ns_probe_time - (self.ns_probe_time%self.ns_collect_time)) / self.ns_collect_time)) #more explanation
        mgr.Camera.set_number_kinetics(self.runs * 2 + 1)
        mgr.Camera.set_shutter("Open") #Open Shutter


        #connect to pulse sequence------------------------------------------

        self.seqs=[]

        if mode == 'QAM':
            mgr.sg.set_mod_type('QAM')
            self.AM_mode = False
            self.switch_mode = False
        elif mode == 'AM':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_AM_mod_depth(100)
            self.switch_mode = False
            self.AM_mode = True
        elif mode == 'SWITCH':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_AM_mod_depth(100)
            self.switch_mode = True
            self.AM_mode = True
        self.seqs=mgr.Pulser.pulse_setup(self.runs, mode,cam_trigger, self.ns_exp_time, self.ns_readout_time)

        mgr.sg.set_rf_toggle(1)
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_mod_function(mode, 'external')

        self.t_init = time.time() 

    def finalize(self, mgr, exp_time, readout_time, frequency, sleep_time, ended=False): #radius, threshold, minmass, link_radius, microns_per_pixel,
        self.t_exp = time.time()
        # mgr.Camera.abort_acquisition() #stop acquisition
        self.sig_data = np.divide(self.sig_data,self.sweeps)
        self.bg_data = np.divide(self.bg_data,self.sweeps)
        self.ODMR_data = np.divide(self.ODMR_data,self.sweeps)
        

        ret = mgr.Camera.set_shutter("Closed")
        print("Function SetShutter returned {}".format(ret))
        ## turns off instruments, close shutter
        mgr.sg.set_rf_toggle(0)
        mgr.sg.set_mod_toggle(False)
        mgr.Pulser.reset()

        if(self.misc['shutdown']):
            ret = mgr.Camera.shutdown() #Shuts down the camera
            print("SDK shutdown ")
            print(ret) ##returns 20002 if successful

        print(self.gain_string)
        self.freq_data = self.frequencies
        if ended:
            for i in range(len(self.ODMR_data)):
                try:
                    p,pcov = curve_fit(self.fit_func, self.freq_data,self.ODMR_data[i], [-0.02,-0.02,10e6,10e6,2.865e9,2.875e9,1])
                    ZFS = (p[4]+p[5])/2
                    HWHM = ((max(p[4],p[5])-min(p[4],p[5]))+p[2]/2+p[3]/2)/2
                    Contrast = max(np.abs(p[0]),np.abs(p[1]))
                    print(self.ROI_xyr[i],ZFS,HWHM,Contrast)
                except Exception as e:
                    print(f"Error occurred while fitting curve for ROI {self.ROI_xyr[i]}: {e}")

        print(f'The updated ND locations: {self.ROI_xyr}')
        self.t_fin = time.time()

        signal_time = exp_time * len(self.freq_data) * self.runs * self.sweeps * self.repetitions
        cam_down_time = readout_time * len(self.freq_data) * self.runs * self.sweeps * self.repetitions + (sleep_time+0.1) * len(self.freq_data) + self.sweeps * self.repetitions + (exp_time + readout_time)* len(self.freq_data) * self.sweeps * self.repetitions


        print(f'TOTAL EXPOSURE TIME was {signal_time} (seconds) and TOTAL CAM DOWN TIME was {cam_down_time}') #cam_down_time includes sleep and 0.1 second rest before acquisition, as well as readout, as well as throwaway
        
        t_ = f'Initialization: {self.t_init-self.t0} seconds, '
        t_+= f'Cooldown: {self.t_cool - self.t_init} seconds, '
        if self.t_gain is not None:
            t_ +=f'Gain Optimization: {self.t_gain - self.t_cool} seconds, '
            t_ +=f'Experiment: {self.t_exp - self.t_gain} seconds, ' 

        print(t_)    
        t_tot = self.t_fin - self.t0
        print(f'TOTAL TIME: {t_tot}')

        print("FINALIZE")

        return

    def fit_func(self, xs, A=-0.02, A2 = -0.02, gamma=10e6, gamma2=10e6, x0=2.865e9, x02=2.875e9, y0=1):
        return A/(1+(2*(xs-x0)/gamma)**2)+ A2/(1+(2*(xs-x02)/gamma2)**2)+y0
            
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

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))
        
    
    def pulse_setup(self, runs,mode, cam_trigger, probe_time,  exp_time):
        #print('\n using sequence without wait time')
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            self.seqs.append(self.pulses.WFODMR(runs, exp_time, probe_time,mode = mode, FT = False, mw_duty = self.mw_duty, mw_rep = self.mw_rep))
        else:
            self.seqs.append(self.pulses.WFODMR(runs, exp_time, probe_time,10000000,5000000,mode, mw_duty = self.mw_duty, mw_rep = self.mw_rep))

    def closest_odd(self, num):
        if num%2 == 0:
            return num + 1
        else:
            return num