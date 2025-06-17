'''
Widefield Routine for Multi-ND ZFS Sensing using a Two-Point Measurement
'''

#### IMPORTS
## Standard
import numpy as np
import time
from scipy.optimize import curve_fit
import trackpy as tp
import pims
from pims import Frame, FramesSequence
from PIL import Image
import pickle
import sys, os
from collections import deque 

## Nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
from nidaqmx.stream_readers import CounterReader

## Nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_
from nspyre.gui.colors import cyclic_colors, colors

## Cam SDK
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

#### Spyrelet
class WFODMRSwabianSpyrelet(Spyrelet):

    # VERSION = '1.0' #to keep track of how to parse apart data, in case output style changes. 

    REQUIRED_DEVICES = ['sg','pulses', ]#'urixyz',
    PARAMS = {
        ## Standard
        'device':{'type': str,'default': 'Dev1',},
        ## Timings
        'exp_time':{ #this represents the exposure time per frame
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 75e-3,
        },
        'readout_time':{ 
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 15e-3,
        },
        # 'trigger_time':{'type':float,'units':'s','suffix': 's','default': 10e-3,},
        # 'buffer_time':{'type':float,'units':'s','suffix': 's','default': 5e-3,},

        ## Cam settings
        'cam_trigger':{'type': list,'items': ['EXTERNAL_EXPOSURE','EXTERNAL_FT'], 'default': 'EXTERNAL_FT'},
        'gain':{'type':int,'default': 2,'positive': True,}, #EM gain for camera, goes from 1-272
        'cooler':{'type': str, 'default': '(False, 20)'},

        ## Routine structure
        'routine':{'type': str, 'default': '[2,3,100,0,-1]'}, #runs, sweeps, two-pt interval, two-pt averaging, total reps
        'wait_interval':{'type': str, 'default': '(0,10)'}, #wait interval, of form (points-between-wait, wait time (s)), where <1 means no waiting
        'end_ODMR':{'type': bool, 'default': False},
        'frequency': {'type': str,'default': '[2.84e9, 2.90e9, 30]',},
        'label':{'type': str, 'default': '[t, 1, 0, 2, 0, 1, 0, 2, 0]'},

        ## SG
        'rf_amplitude':{'type': float,'default': -15,},
        'mode':{'type': list,'items': ['AM','SWITCH'], 'default': 'AM'},

        ## Data
        'ROI_xy':{'type': str, 'default': '[(512,512)]'},
        'ZFS':{ 
            'type':float,
            'units':'Hz',
            'suffix': 'Hz',
            'default': 2.868780e9,
        },
        'sideband':{ 
            'type':float,
            'units':'Hz',
            'suffix': 'Hz',
            'default': 12e6,
        },
        'QLS':{ 
            'type':str,
            'default': '[-5e-9]',
        },
        'alt_label': {'type': bool,'default': False}, # Alternate label to get more balanced results
        'PID': {'type': str, 'default': "{'Kp':0.03, 'Ki': 0.005, 'Kd':0.01, 'Mem': 15, 'Mem_decay': 2.0}"},


        'data_path': {'type': str,'default': 'Z:\\biosensing_setup\\data\\WFODMR_images_test'},
        'save_image': {'type': bool,'default': False}, # Saving full images
        'data_download':{'type': bool,'default': False}, #Saving just raw data [sig, bg, ...]
        'window':{'type': bool,'default': True}, #Show sample at intermitent points (every sub_interval points)


        'trackpy':{
            'type': bool,
            'default': False
        },
        'trackpy_params': {
            'type': str,
            'default': '(False, 40, 800)' #default values for invert, threshold, and minmass respectively
        },
        'shutdown':{'type': bool,'default': True},
        'Misc': {
            'type': str,
            'default': "{'DEBUG':False}" #default values for invert, threshold, and minmass respectively
        }

    }

    def initialize(self, device, exp_time, readout_time,cam_trigger,gain,cooler,routine, wait_interval, end_ODMR,frequency,label,rf_amplitude,mode,ROI_xy,
        ZFS,sideband,QLS,alt_label, PID,data_path,save_image,data_download, window, trackpy,trackpy_params, shutdown, Misc):
        '''
        Define a class variable for all params that:
            (1) Need to be "formatted" in terms of extracting unitless value, or adding units
            (2) Have a chance to be changed, with the change needing to be propagated to main()/finalize()

        Define the arrays that will hold the outputs to be saved

        Initialize SG somewhat, allow switching between AM/FM mode to be controlled by main()

        Initialize all necessary pulse sequences for ps. 

        Initialize camera, if necessary

        Cooldown, if necessary
        '''
        print('\nINITIALIZING WF_TRACK')
        self.t_0 = round(time.time(),3)
        self.Misc = eval(Misc)

        ## Param formatting ##########
        self.exp_time = exp_time.m # seconds
        self.readout_time = readout_time.m # seconds
        self.trigger_time = 0.010 # seconds             #(Hardcoded)
        self.buffer_time = 0.005 # seconds              #(Hardcoded)

        self.gain = gain #adjusted in optimize

        self.ND_List = eval(ROI_xy)
        self.ND_iter = range(len(self.ND_List))
        self.r = 16                                     #(Hardcoded)
        self.r_targ = 7                                 #(Hardcoded)

        self.PID = eval(PID)

        self.ODMR_timings = []
        rt = eval(routine)

        try:
            if self.Misc['preset']=='ODMR1':
                rt = [2,3,0,5,1]
        except: 
            pass

        self.runs = rt[0]
        self.sweeps = rt[1]
        self.interval = rt[2]
        self.sub_interval = rt[3]
        if (self.interval >= 1 and self.sub_interval >= 1 and self.interval % self.sub_interval != 0):
            self.interval += self.interval % self.sub_interval
            print(f'warning, interval must be a multiple of avg_interval. Extending interval so that it is now {self.interval}.')
        if self.sub_interval%2 != 0 and alt_label:
            self.sub_interval += 1
            print(f'warning, avg_interval must be even if alt_label is used. Setting sub_interval to the next even number {self.sub_interval}')
        self.reps = rt[4]
        self.window = window




        if end_ODMR and self.interval == -1:
            self.finalize_ODMR = True
            self.end_ODMR = False
        else:
            self.finalize_ODMR = False
            self.end_ODMR = end_ODMR
        self.wait_interval = eval(wait_interval)


        t = 't'
        self.label_base = eval(label)
        self.label_inv = []
        for pulse in self.label_base:
            if pulse == '1' or pulse == 1:
                self.label_inv.append(2)
            elif pulse == '2' or pulse == 2:
                self.label_inv.append(1)
            else:
                self.label_inv.append(pulse)

        self.I1I2_labels = [self.label_base, self.label_base]
        if alt_label:  
            self.I1I2_labels[1] = self.label_inv

        freq = np.linspace(eval(frequency)[0], eval(frequency)[1], eval(frequency)[2], endpoint = True)
        self.frequency = Q_(freq,'Hz')
        self.data_path = data_path
        if(data_download or save_image):
            if(not os.path.isdir(self.data_path)):
                os.mkdir(self.data_path)
            else:
                self.data_path = self.data_path+f'_{time.time()}'
                os.mkdir(self.data_path)

        ## Data formatting, pickle prep ##########
        self.dt_freq = freq #frequency of ODMR spectra

        self.dt_ODMR_raw = [[] for i in range(len(self.ND_List))] #dt_ODMR_raw[ND][rep][sweep][freq][count] > yields the raw data to build an ODMR for each sweep
        self.dt_ODMR_ref = [[] for i in range(len(self.ND_List))] #dt_ODMR_ref[ND][rep][sweep][freq] > yields the combined ODMR from all of the sweeps for a rep
        self.dt_I1I2_raw = [[] for i in range(len(self.ND_List))] #dt_I1I2_raw[ND][rep][set][count] > yields the raw data for I1I2 measurements
        self.dt_I1_ref = [[] for i in range(len(self.ND_List))] #dt_I1_ref[ND][rep][set][count_norm] > yields the normalized data for I1 measurements
        self.dt_I2_ref = [[] for i in range(len(self.ND_List))] #dt_I2_ref[ND][rep][set][count_norm] > yields the normalized data for I2 measurements
        self.dt_dZFS =  [[] for i in range(len(self.ND_List))] #dt_dZFS[ND][rep][set] > yields the ZFS estimate
        self.dt_dZFS_PID = [[] for i in range(len(self.ND_List))]
        self.dt_fluorescence = [[] for i in range(len(self.ND_List))]

        self.dt_ls_ZFS = []

        self.dt_times = [] #times for each entry in I1I2_raw
        self.dt_sg_setpt = []#an array of (ZFS,sb) setpoints for each rep

        self.latest_ims = []
        

        ## SG init ##########
        self.sg.mod_toggle = True
        self.sg.mod_function = 'external'
        self.sg.rf_amplitude = rf_amplitude
        #Modulation handled in main

        ## Seq init ##########
        bool_FT = (cam_trigger=='EXTERNAL_FT')
        self.ODMR_seq = self.pulses.WFODMR(self.runs, exp_time.to('ns').m, readout_time.to('ns').m, trig = self.trigger_time * 1e9, buff = self.buffer_time * 1e9, mode = mode
            , FT = bool_FT) 
        self.gain_seq = self.pulses.gain_seq(exp_time.to('ns').m, readout_time.to('ns').m, FT = bool_FT)
        self.ZFS_seq = self.pulses.I1I2(exp_time.to('ns').m, readout_time.to('ns').m, self.trigger_time * 1e9, self.buffer_time * 1e9, self.label_base, FT = bool_FT)
        self.ZFS_seq_inv = self.pulses.I1I2(exp_time.to('ns').m, readout_time.to('ns').m, self.trigger_time * 1e9, self.buffer_time * 1e9, self.label_inv, FT = bool_FT)

        self.I1I2_seqs = [self.ZFS_seq, self.ZFS_seq]
        if alt_label:
            self.I1I2_seqs[1] = self.ZFS_seq_inv

        ## Cam init ##########
        self.sdk = atmcd("")  # Load the atmcd library
        self.codes = atmcd_codes
        if self.sdk.GetStatus()[0] == 20075:
            ret = self.sdk.Initialize("")  # Initialize camera
            print("Function Initialize returned {}".format(ret))

        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.KINETICS) #Taking a series of pulses
        self.sdk.SetReadMode(self.codes.Read_Mode.IMAGE) #reading pixel-by-pixel with no binning
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            self.sdk.SetTriggerMode(self.codes.Trigger_Mode.EXTERNAL_EXPOSURE_BULB)
            if self.readout_time<0.059:
                print('WARNING readout time should be at least 59 ms in pulse-length-exposure mode')
        else:
            self.sdk.SetTriggerMode(self.codes.Trigger_Mode.EXTERNAL) 
            exposure_min = 0.046611 # hardware limited minimum exposure in FT mode
            if self.exp_time < exposure_min:
                print(f'exposure must be at least {exposure_min*1000} ms.')
                return
            elif self.exp_time + self.readout_time < 0.08:
                print('WARNING May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            if self.readout_time<0.005:
                print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
            self.sdk.SetExposureTime(self.exp_time) 
            self.sdk.SetFrameTransferMode(1) 

        (ret, xpixels, ypixels) = self.sdk.GetDetector()
        self.sdk.SetImage(1, 1, 1, xpixels, 1, ypixels) #defining image
        #self.sdk.SetBaselineClamp(1)
        self.sdk.SetEMCCDGain(self.gain) #setting Electron Multiplier Gain 
        self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_OPEN,27,27) #Open Shutter

        self.t_init = round(time.time(),3)
        self.t_cool = self.t_init
        self.t_gain = self.t_init
        self.t_rep = [self.t_init]

        ## Cooldown if necessary ##########
        cool = eval(cooler)[0]
        Temp = eval(cooler)[1]
        if(cool):
            ret = self.sdk.SetTemperature(Temp)
            print(f"Function SetTemperature returned {ret} target temperature {Temp}")
            ret = self.sdk.CoolerON()
            ct = 0
            while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
                ct = ct%3
                my_str = '.'*ct + '.' + ' '*3 
                time.sleep(5)
                (ret, temperature) = self.sdk.GetTemperature()
                print("Function GetTemperature returned {}, current temperature = {}{}".format(
                    ret, temperature, my_str), end='\r')
                ct+=1
        self.t_cool = round(time.time(),3) 

        print('Initialization finished')


    def main(self, device, exp_time, readout_time,cam_trigger,gain,cooler,routine, wait_interval, end_ODMR,frequency,label,rf_amplitude,mode,ROI_xy,
        ZFS,sideband,QLS,alt_label, PID, data_path,save_image,data_download, window, trackpy,trackpy_params,shutdown,Misc):


        ## Optimize Gain ##########
        print('Optimizing gain...')
        mx = 0
        max_pixel_tolerance = (2.0e4,2.9e4,4e4) #consider if this can be raised without meaningful distortion
        self.sdk.SetNumberKinetics(2)
        while mx <= max_pixel_tolerance[0] or mx >= max_pixel_tolerance[1]:
            all_data = self.GetPictures(self.gain_seq,2)[1]
            mx = np.max(all_data)
            if mx <= max_pixel_tolerance[0]:
                print(f'mx: {mx} low, raising gain: {self.gain} > {self.gain+1}')
                self.gain+=1
            elif mx >= max_pixel_tolerance[2]:
                print(f'mx: {mx} dangerously high, lowering gain: {self.gain} > {self.gain-3}')
                self.gain-=3
            elif mx >= max_pixel_tolerance[1]:
                print(f'mx: {mx} high, lowering gain: {self.gain} > {self.gain-1}')
                self.gain-=1
            self.sdk.SetEMCCDGain(self.gain)
            if self.gain >= 200:
                print('WARNING: gain too high')
                return
            if self.window:
                img = self.img_1D_to_2D(all_data, 1024, 1024)
                # self.save_pics([img], [str(mx)])
                self.acquire({
                    'rep_idx': -1,
                    'dtype':'bg',
                    'img': img[512-128:512+128, 512-128:512+128]})
            else:
                self.acquire({}) #Allows exit using spyrelet 'Stop' key. 
        self.gain_string = f'optimum gain determined to be {self.gain}, giving max pixel value of roughly {mx}'
        print(self.gain_string)
        self.t_gain = round(time.time(),3) 



        #### Experiment Loop ##########
        self.sg.rf_toggle = True

        self.t_rep = [time.time()]
        rep = 0
        ZFS_setpt = ZFS
        sb_setpt = sideband
        ls_QLS = eval(QLS)
        ls_ZFS = [ZFS.m] * len(self.ND_List)
        while(self.reps == -1 or rep < self.reps):
            print(f'rep: {rep}')

            ## Run ODMR

            self.run_ODMR(rep, save_image)

            ## Determine the best ZFS, sb, and get a list of QLS

            if self.sweeps!= 0: #case of skipped ODMR
                ODMR_by_ND = self.build_ODMR(self.dt_ODMR_ref, only_final_rep=True)
                ls_ZFS_new, ls_sb, ls_QLS = self.ODMR_stats(self.dt_freq, ODMR_by_ND)
                for ND in self.ND_iter:
                    if ls_ZFS_new[ND] != 0:
                        ls_ZFS[ND] = ls_ZFS_new[ND]
                ZFS_avg = np.mean(ls_ZFS)
                ZFS_setpt = Q_(ZFS_avg, 'Hz')
                sb_setpt = Q_(np.mean([z for z in ls_sb if z != 0]), 'Hz')
                self.dt_ls_ZFS.append(ls_ZFS)
                for i in range(len(ls_ZFS)):
                    if ls_ZFS[i] == 0:
                        ls_ZFS[i] = ZFS_avg

                ls_dZFS_PID = [(ls_ZFS[ND] - ZFS_setpt.m) for ND in self.ND_iter] #make sure it shouldn't be the opposite way around... ZFS_setpt.m - ls_ZFS
            else:
                ls_dZFS_PID = [0 for ND in self.ND_iter]

            e_arr = []
            for ND in self.ND_iter:
                e_arr.append(deque())
                e_arr[ND].appendleft(0)

            print(f'ZFS set to {ZFS_setpt.m/1e9} GHz, sb set to {sb_setpt.m/1e6} MHz')
            self.dt_sg_setpt.append((ZFS_setpt.m, sb_setpt.m))

            ##  Run I1I2 Measurement Loop for a certain amount of iteration ##########
            self.dt_times.append([])
            for ND in self.ND_iter:
                self.dt_I1I2_raw[ND].append([])#creates dt_I1I2_raw[ND][rep] for each ND
                self.dt_I1_ref[ND].append([]) #creates dt_I1_ref[ND][rep] for each ND
                self.dt_I2_ref[ND].append([]) #creates dt_I2_ref[ND][rep] for each ND
                self.dt_dZFS[ND].append([])
                self.dt_fluorescence[ND].append([])
                self.dt_dZFS_PID[ND].append([])

            n_pic = len(self.label_base)
            n_throwaway = self.label_base.count('t')

            self.sg.mod_type = 'FM'
            self.sg.FM_mod_setter = Q_(sb_setpt,'Hz')
            self.sg.frequency = Q_(ZFS_setpt, 'Hz')
            self.sdk.SetNumberKinetics(n_pic)


            ls_dZFS_averaged = [0] * len(self.ND_List)
            s = 0
            while self.interval == -1 or s < self.interval:

                #TODO: include option to alternate label using self.label_inv

                first_pic = s==0 
                last_pic = s== self.interval-1

                if first_pic:
                    data_1D = self.GetPictures(self.I1I2_seqs[s%2], n_pic)
                else:
                    data_1D = self.GetPictures(self.I1I2_seqs[s%2],n_pic, do_save= save_image, last_pics = data, im_labels = im_labels)
                self.latest_ims = [self.img_1D_to_2D(data_1D[i], 1024, 1024) for i in range(n_throwaway,n_pic)] # The set of pics as 2D arrays, w/o throwaway
                data = self.latest_ims
                im_labels = [f'I1I2_r{rep}_s{s}_{i}' for i in range(n_pic-n_throwaway)]
                if last_pic and save_image: 
                    self.save_pics(data,im_labels) # Save last pics
                ## track NDs
                self.ND_List, ls_mx = self.ROI_loc(self.ND_List, data[0], r_search = 8)

                #normalized I1, I2 lists for a given set. averaged and compared to derive ZFS.
                dt_I1 = [[] for i in range(len(self.ND_List))] 
                dt_I2 = [[] for i in range(len(self.ND_List))]
                total_fluorescence = [0] * len(self.ND_List)

                ## Sort data
                ## To sort data properly, independently of label, build up I1_buff, I2_buff, bg_buff with one data point at a time, when bg and (I1 or I2) are filled, pop the value. If I1 and I2 full before bg, label is invalid (no clear denomination of bg)                                              
                I1_buff = []
                I2_buff = []
                bg_buff = []
                
                try:
                    if self.Misc['pdb']:
                        import pdb;pdb.set_trace()
                except:
                    pass


                for i in range(len(data)):
                    dt_raw = self.ROI_analyze(self.ND_List,data[i], r_ROI = 7) #array of [ND] signals from a given image.
                    total_fluorescence = list(np.add(total_fluorescence, dt_raw))
                    total_fluorescence = [int(val) for val in total_fluorescence]
                    [self.dt_I1I2_raw[ND][-1].append(dt_raw[ND]) for ND in range(len(self.ND_List))]
                    if self.I1I2_labels[s%2][n_throwaway + i] == 1:
                        I1_buff = dt_raw
                    elif self.I1I2_labels[s%2][n_throwaway + i] == 2:
                        I2_buff = dt_raw
                    elif self.I1I2_labels[s%2][n_throwaway + i] == 0:
                        bg_buff = dt_raw
                    if bg_buff != []: 
                        if I1_buff != []:
                            [dt_I1[ND].append(I1_buff[ND]/bg_buff[ND]) for ND in range(len(self.ND_List))]
                            bg_buff = []
                            I1_buff = []
                        elif I2_buff != []:
                            [dt_I2[ND].append(I2_buff[ND]/bg_buff[ND]) for ND in range(len(self.ND_List))]
                            bg_buff = []
                            I2_buff = []

                ls_dZFS = []

                Kp = self.PID['Kp']
                Ki = self.PID['Ki']
                Kd = self.PID['Kd']
                Mem = self.PID['Mem']
                Mem_decay = self.PID['Mem_decay']



                for ND in range(len(self.ND_List)):  
                    self.dt_I1_ref[ND][-1].append(dt_I1[ND])
                    self.dt_I2_ref[ND][-1].append(dt_I2[ND]) 

                    dZFS = (np.mean(dt_I2[ND]) - np.mean(dt_I1[ND]))/ls_QLS[ND]
                    ls_dZFS.append(dZFS)
                    if self.sub_interval>=1:
                        ls_dZFS_averaged[ND] += int(dZFS/self.sub_interval)
                    else:
                        ls_dZFS_averaged[ND] += dZFS

                    self.dt_dZFS[ND][-1].append(dZFS)
                    self.dt_fluorescence[ND][-1].append(total_fluorescence[ND])
                    e_arr[ND].appendleft(ls_dZFS[ND]-ls_dZFS_PID[ND])
                    if len(e_arr[ND]) > Mem: e_arr[ND].pop()

                ls_u = self.PID_update(e_arr,Kp,Ki,Kd,Mem_decay)
                for ND in self.ND_iter:
                    ls_dZFS_PID[ND] += ls_u[ND]
                    self.dt_dZFS_PID[ND][-1].append(ls_dZFS_PID[ND])

            

                t_pt = time.time()-self.t_gain
                self.dt_times[-1].append(t_pt)

                if self.window:
                    im = data[0][self.ND_List[0][1] - 12: self.ND_List[0][1] + 12, self.ND_List[0][0] - 12: self.ND_List[0][0]+12]
                else:
                    im = []


                ls_fullZFS = []
                ls_fullZFS_averaged = []
                ls_fullZFS_PID = []
                for ND in self.ND_iter:
                    ls_fullZFS.append(ls_dZFS[ND] + ZFS_setpt.m)
                    ls_fullZFS_averaged.append(ls_dZFS_averaged[ND] + ZFS_setpt.m)
                    ls_fullZFS_PID.append(ls_dZFS_PID[ND] + ZFS_setpt.m)
                


                if (self.sub_interval >= 1 and s%self.sub_interval==self.sub_interval-1):
                    self.acquire({
                        'rep_idx': rep,
                        'sweep_idx': s,
                        't': t_pt,
                        'dZFS': ls_fullZFS, #ls_dZFS for values relative to 0. Currently including setpoint.
                        'ZFS_setpt' : ZFS_setpt.m, 
                        'total_fluorescence': total_fluorescence,
                        'dZFS_averaged' : ls_fullZFS_averaged,
                        'dZFS_PID' : ls_fullZFS_PID,
                        'img': im,
                        'dtype': 'I1I2',
                        })
                    ls_dZFS_averaged = [0] * len(self.ND_List)

                else:
                    self.acquire({
                        'rep_idx': rep,
                        'sweep_idx': s,
                        't': t_pt,
                        'dZFS': ls_fullZFS,
                        'dZFS_PID' : ls_fullZFS_PID,
                        'ZFS_setpt' : ZFS_setpt.m, 
                        'total_fluorescence': total_fluorescence,
                        'dtype': 'I1I2',
                        })
                s+=1
                if self.wait_interval[0] > 0 and s%self.wait_interval[0] == 0:
                    self.sg.rf_toggle = False
                    # print(f'waiting {self.wait_interval[1]} seconds...')
                    time.sleep(self.wait_interval[1])     
                    self.sg.rf_toggle = True
            rep+=1
            self.t_rep.append(round(time.time(),3) )
        
        if self.end_ODMR:
            print('final ODMR')
            self.run_ODMR(self.reps+1,save_image)

    def finalize(self, device, exp_time, readout_time,cam_trigger,gain,cooler,routine, wait_interval, end_ODMR,frequency,label,rf_amplitude,mode,ROI_xy,
        ZFS,sideband,QLS,alt_label, PID, data_path,save_image,data_download, window, trackpy,trackpy_params,shutdown,Misc):

        if self.finalize_ODMR:
            print('final ODMR')
            self.run_ODMR(self.reps+1,save_image, do_acquire = False)
            print('final ODMR finished')

        ## sg end ##########
        self.sg.rf_toggle = False
        self.sg.mod_toggle = False

        ## cam end ##########
        ret = self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_CLOSED,27,27)
        if(ret==20002):
            print("Shutter closed successfully")
        else:
            print("WARNING: Trouble closing shutter")

        try:
            if(shutdown):
                ret = self.sdk.ShutDown()
                print("SDK shutdown ")
                print(ret) ##returns 20002 if successful
        except:
            pass

        print(f'Final ROI loc: {self.ND_List}')


        # TODO: Ensure all saved data is necessary, and actually saved.

        if(data_download):
            config = {'VERSION': 1, 'label': self.label_base, 'gain': self.gain, 'routine': eval(routine), 'alt_label': alt_label, 'NDs': eval(ROI_xy), 'PID_params':PID, 'ODMR_timings':self.ODMR_timings, 'wait_interval': eval(wait_interval)} 

            os.mkdir(self.data_path+'\\data')
            with open(self.data_path+f'\\data\\config.pkl', 'wb') as file: 
                pickle.dump(config, file)
            with open(self.data_path+f'\\data\\dt_freq.pkl', 'wb') as file: 
                pickle.dump(self.dt_freq, file)
            with open(self.data_path+f'\\data\\dt_ODMR_raw.pkl', 'wb') as file: 
                pickle.dump(self.dt_ODMR_raw, file)
            with open(self.data_path+f'\\data\\dt_ODMR_ref.pkl', 'wb') as file: 
                pickle.dump(self.dt_ODMR_ref, file)
            with open(self.data_path+f'\\data\\dt_I1I2_raw.pkl', 'wb') as file: 
                pickle.dump(self.dt_I1I2_raw, file)
            with open(self.data_path+f'\\data\\dt_I1_ref.pkl', 'wb') as file: 
                pickle.dump(self.dt_I1_ref, file)
            with open(self.data_path+f'\\data\\dt_I2_ref.pkl', 'wb') as file: 
                pickle.dump(self.dt_I2_ref, file)
            with open(self.data_path+f'\\data\\dt_dZFS.pkl', 'wb') as file: 
                pickle.dump(self.dt_dZFS, file)
            with open(self.data_path+f'\\data\\dt_fluorescence.pkl', 'wb') as file: 
                pickle.dump(self.dt_fluorescence, file)
            with open(self.data_path+f'\\data\\dt_ls_ZFS.pkl', 'wb') as file: 
                pickle.dump(self.dt_ls_ZFS, file)
            with open(self.data_path+f'\\data\\dt_dZFS_PID.pkl', 'wb') as file: 
                pickle.dump(self.dt_dZFS_PID, file)
            with open(self.data_path+f'\\data\\dt_times.pkl', 'wb') as file: 
                pickle.dump(self.dt_times, file)
            with open(self.data_path+f'\\data\\dt_sg_setpt.pkl', 'wb') as file: 
                pickle.dump(self.dt_sg_setpt, file)
            with open(self.data_path+f'\\data\\img.pkl', 'wb') as file: 
                pickle.dump(self.latest_ims[-1], file)

            #TODO: pickle a config file

        self.t_fin = round(time.time(),3) 
        ## final diagnostics ##########

        # TODO: separate ODMR and I1I2 timings

        ## times: t_0, t_init, t_cool, t_gain, t_rep[...], 
        t_ = f'Initialization: {round(self.t_init-self.t_0,3)} seconds, '
        t_+= f'Cooldown: {round(self.t_cool - self.t_init,3)} seconds, '
        t_ +=f'Gain Optimization: {round(self.t_gain - self.t_cool,3)} seconds, '
        t_ +=f'Experiment: {round(self.t_rep[-1] - self.t_gain,3)} seconds, ' 
        t_ +=f'Finalze: {round(self.t_fin - self.t_rep[-1],3)} seconds.'
        print(t_)    
        t_tot = round(self.t_fin - self.t_0,3)
        print(f'TOTAL TIME: {t_tot}')

        print('FINALIZED')
        # import pdb;pdb.set_trace()




    ################################################################################################################################################
    #### HELPER FUNCTIONS
    def img_1D_to_2D(self,img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        img = np.zeros((x_len,y_len), dtype='int')
        for j in range(y_len):
            img[j,:] = img_1D[x_len*j:x_len*(j+1)] #np arrays count down first, then horizontally. That is, my image is saved as an array of rows, not an array of columns
        return img

    def GetPictures(self, seq, n_pic,do_save = False, last_pics = [], im_labels = [], im_size = 1024**2):
        '''
        Runs an acquisition of n pictures over a given sequence, returns pictures as a parsed list of 1D arrays or length 'im_size'
        Allows for efficient saving via do_save, labels which contain n_pic different labels which are strings


        Warning: this method does not touch the sg
        Warning: do_save does not check for save_img. save_img must be factored in beforehand
        '''
        acq_sleep = 0.1
        timeout_limit = n_pic * 20

        # self.sdk.SetNumberKinetics(n_pic)
        self.sdk.StartAcquisition()
        ret = self.sdk.GetStatus()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            return
        time.sleep(acq_sleep) #Give time to start acquisition
        self.pulses.stream_umOFF(seq, 1, AM_mode = True) #0 since only one seq in my seq array.
        timeout_counter = 0
        if do_save: self.save_pics(last_pics, im_labels)
        while(self.sdk.GetTotalNumberImagesAcquired()[1]<n_pic and timeout_counter<=timeout_limit):
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1 
            if timeout_counter == timeout_limit:
                print(f'timeout with {self.sdk.GetTotalNumberImagesAcquired()[1]} pictures.')
        (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(1,n_pic,n_pic * 1024**2) #cut out first image here
        parsed_data = [all_data[i*im_size:i*im_size+im_size] for i in range(int(len(all_data)/im_size))]

        return parsed_data

    def save_pics(self, pics, im_labels, convert = False):
        '''
        given an array of pics, already parsed apart, and labels by which to save them, saves them
        As a standard, pic inputs are saved in 2D. Convert determines whether to run the pics through img_1D_to_2D
        Does not check if save_images is true. 

        type: WFODMR, I1I2, general
        label: string 
        '''
        if len(pics) != len(im_labels):
            print('WARNING: label mismatch in saving')

        for i in range(len(pics)):
            pic = pics[i]
            if convert:
                pic = self.img_1D_to_2D(pic, 1024, 1024)
            with open(self.data_path+f'\\{im_labels[i]}.pkl', 'wb') as file: #saving for each nanodiamond. That's not good
                pickle.dump(pic, file)

    def ROI_loc(self, ND_List, pic, r_search = 10):
        '''
        Not intended for the cellular environment: intended for more or less stationary diamonds which will not appear/disappear.
        In order to better deal w/ cellular environment, need trackpy, AI, or at least some sort of brightness tracking

        given a set of ROI [(x,y), ...] and a picture, relocates the ROI to the brightest spot within r_search, returning the updated
        ROI list, as well as an array of the max brightnesses for tracking purposes (can determine if ND lost)
        '''
        ls_mx = []
        ls_ROI = []
        for i in range(len(ND_List)):
            px_x = ND_List[i][0]
            px_y = ND_List[i][1]
            ROI_search = pic[px_y - r_search: px_y + r_search, px_x - r_search: px_x + r_search]
            px_max = np.argmax(ROI_search)
            ls_mx.append(np.max(ROI_search))
            temp_y = int(px_max/(r_search*2)) + px_y - r_search
            temp_x = px_max%(r_search*2) + px_x - r_search
            ls_ROI.append((temp_x, temp_y))
        return ls_ROI, ls_mx

    def ROI_analyze(self, ND_List, pic, r_ROI = 7):
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


    def build_ODMR(self,ODMR_ref,only_final_rep = False):
        '''
        Converts a ref ODMR of structure ODMR_ref[ND][rep][sweep][freq]
        into a collapsed ODMR of structure ODMR_ref[ND]([rep])

        '''
        ODMR = []
        for ND in range(len(ODMR_ref)):
            ODMR.append([])
            if only_final_rep:
                for freq in range(len(ODMR_ref[-1][-1][-1])):
                    ls_val = []
                    for sweep in range(len(ODMR_ref[-1][-1])):
                        ls_val.append(ODMR_ref[ND][-1][sweep][freq])
                    val = np.mean(ls_val)
                    ODMR[ND].append(val)
            else:
                for rep in range(len(ODMR_ref[-1])):
                    ODMR[ND].append([])
                    for freq in range(len(ODMR_ref[-1][-1][-1])):
                        ls_val = []
                        for sweep in range(len(ODMR_ref[-1][-1])):
                            ls_val.append(ODMR_ref[ND][rep][sweep][freq])
                        val = np.mean(ls_val)
                        ODMR[ND][-1].append(val)
        return ODMR

    def ODMR_stats(self, freq, ODMRs):
        '''
        ODMRs > [ZFS], [sb], [QLS]
        '''
        ZFS = []
        sb = []
        QLS = []

        for ODMR in ODMRs:
            try:
                p,pcov = curve_fit(self.fit_func,freq,ODMR, [-0.02,-0.02,10e6,10e6,2.865e9,2.875e9,1])
                ZFS.append((p[4]+p[5])/2) 
                sb.append((np.abs(p[4]-p[5]) + (p[2]+p[3])/(2*np.sqrt(3)))/2)
                QLS.append(3*np.sqrt(3)/4 * (p[0]/p[2] + p[1]/p[3]))
            except:
                try:
                    p,pcov = curve_fit(self.fit_func_2,freq,ODMR, [-0.02,10e6,2.87e9,1])
                    ZFS.append(p[2]) 
                    sb.append(p[1]/(2*np.sqrt(3)))
                    QLS.append(3*np.sqrt(3)/2 * (p[0]/p[1]))
                except:
                    ZFS.append(0)
                    sb.append(0)
                    QLS.append(-5e-9) # hard-coded default
        return ZFS,sb,QLS

    def run_ODMR(self, rep, save_image, do_acquire = True):
        for ND in self.ND_iter:
            self.dt_ODMR_raw[ND].append([])#creates dt_ODMR_raw[ND][rep] for each ND
            self.dt_ODMR_ref[ND].append([])#creates dt_ODMR_ref[ND][rep] for each ND

        ## Run ODMR, Collect Params Per ND, Diagnostic
        n_pic = self.runs*2+1

        self.sg.mod_type = 'AM'
        self.sg.AM_mod_depth = Q_(100, 'pc')
        self.sdk.SetNumberKinetics(n_pic)
        self.ODMR_timings.append(time.time())
        for s in range(self.sweeps):
            for ND in range(len(self.ND_List)):
                self.dt_ODMR_raw[ND][-1].append([])  #creates dt_ODMR_raw[ND][rep][sweep] for each ND, the latest rep
                self.dt_ODMR_ref[ND][-1].append([]) #creates dt_ODMR_raw[ND][rep][sweep] for each ND, the latest rep
            for f in range(len(self.frequency)):
                [self.dt_ODMR_raw[ND][-1][-1].append([]) for ND in range(len(self.ND_List))] #creates dt_ODMR_raw[ND][rep][sweep][freq] for each ND, the latest rep, sweep
                freq = self.frequency[f]
                first_pic = s==0 and f==0 
                last_pic = s==self.sweeps-1 and f==len(self.frequency)-1

                self.sg.frequency = freq
                if first_pic:
                    data_1D = self.GetPictures(self.ODMR_seq, n_pic)
                else:
                    data_1D = self.GetPictures(self.ODMR_seq,n_pic, do_save= save_image, last_pics = data, im_labels = im_labels)
                self.latest_ims = [self.img_1D_to_2D(data_1D[i], 1024, 1024) for i in range(1,n_pic)] # The set of pics as 2D arrays, w/o throwaway
                data = self.latest_ims
                im_labels = [f'ODMR_r{rep}_s{s}_f{f}_{i}' for i in range(n_pic-1)]
                if last_pic and save_image: 
                    self.save_pics(data,im_labels) # Save last pics
                ## track NDs
                self.ND_List, ls_mx = self.ROI_loc(self.ND_List, data[0], r_search = 8) 
                ## analyze ROI & append data
                dt_sig = [] #a list of totaled sig by ND
                dt_bg = [] #a list of totaled bg by ND
                [dt_sig.append(0) for ND in range(len(self.ND_List))] 
                [dt_bg.append(0) for ND in range(len(self.ND_List))]
                for i in range(len(data)):
                    dt_raw = self.ROI_analyze(self.ND_List,data[i], r_ROI = 7) #array of [ND] signals from a given image
                    [self.dt_ODMR_raw[ND][-1][-1][-1].append(dt_raw[ND]) for ND in range(len(self.ND_List))] #creates dt_ODMR_raw[ND][rep][sweep][freq][count]
                    if i%2 == 0:
                        dt_sig = [dt_sig[ND] + int(dt_raw[ND]) for ND in range(len(self.ND_List))] 
                    else:
                        dt_bg = [dt_bg[ND] + int(dt_raw[ND]) for ND in range(len(self.ND_List))]
                [self.dt_ODMR_ref[ND][-1][-1].append(dt_sig[ND]/dt_bg[ND]) for ND in range(len(self.ND_List))] # should correspond to the latest shown ODMR

                if self.window:
                    im = data[0][self.ND_List[0][1] - 12: self.ND_List[0][1] + 12, self.ND_List[0][0] - 12: self.ND_List[0][0]+12]
                else:
                    im = []
                if do_acquire:
                    if (self.sub_interval >= 1 and f%self.sub_interval==0):
                        self.acquire(
                            {
                            'rep_idx': rep,
                            'sweep_idx': s,
                            'f': freq,
                            'bg': list(dt_sig), 
                            'sig': list(dt_bg),
                            'ODMR' : list([self.dt_ODMR_ref[ND][-1][-1][f] for ND in range(len(self.ND_List))]), 
                            'dtype': 'ODMR',
                            'img': im
                            })
                    else:
                        self.acquire(
                            {
                            'rep_idx': rep,
                            'sweep_idx': s,
                            'f': freq,
                            'bg': list(dt_sig), 
                            'sig': list(dt_bg),
                            'ODMR' : list([self.dt_ODMR_ref[ND][-1][-1][f] for ND in range(len(self.ND_List))]), 
                            'dtype': 'ODMR',
                            })      
                else:
                    print(f'sweep {s+1}/{self.sweeps}, freq {f+1}/{len(self.frequency)}    ', end='\r')
        self.ODMR_timings[-1] = time.time() - self.ODMR_timings[-1]

    ################################################################################################################################################

    def fit_func(self, xs, A=-0.02, A2 = -0.02, gamma=10e6, gamma2=10e6, x0=2.865e9, x02=2.875e9, y0=1):
        return A/(1+(2*(xs-x0)/gamma)**2)+ A2/(1+(2*(xs-x02)/gamma2)**2)+y0

    def fit_func_2(self, xs, A=-0.02,  gamma=10e6, x0=2.865e9, y0=1):
        return A/(1+(2*(xs-x0)/gamma)**2)+y0

    def PID_update(self, e_arr, Kp, Ki, Kd, dec):
        '''
        PID averaging technique to decrease noise. 
        output an array of values that can be applied to dZFS_PID to get a new estimate (ls_u)
        '''
        ls_u = []
        for ND in self.ND_iter:
            u = 0
            u+= Kp * e_arr[ND][0]
            integral = 0 #weighted integral
            for j in range(len(e_arr[ND])):
                integral += e_arr[ND][j] / (dec**j)
            u+= integral * Ki
            u+= Kd * (e_arr[ND][0] - e_arr[ND][1])
            ls_u.append(u)
        return ls_u

    ################################################################################################################################################

    ## Plot a picture to give window into the routine
    @Plot2D
    def window(df, cache):
        latest_image = df['img'].dropna().iloc[-1]
        return latest_image


    @Plot1D
    def sig_plot(df, cache):
        '''
        graph sig/bg for ND across latest rep, averaging across sweeps.
        '''
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'ODMR')] #filters only ODMR data of latest rep
        grouped = rep_df.groupby('f') #creates groupby object, df with key defined by 'f', and grouped rows as values
        sigs = grouped['sig'] #also returns  groupby object, still with 'f' as the index, but with only sigs associated. A list of sigs (which is itself a list)
        bgs = grouped['bg']

        #the following code transforms the groupby object into a series which can be treated like a list. Groupby is just a lazy way for 
        #pandas to instead just store theoretical instructions on how things are grouped that don't apply until you do something material like .mean.
        # Then replace each list with the NDth item, then average the subsequent list per f in series. End with a series.
        sigs_averaged = sigs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        bgs_averaged = bgs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)

        return {'sig': [sigs_averaged.index, sigs_averaged],
                'bg': [bgs_averaged.index, bgs_averaged]}

    @Plot1D
    def ODMR_plot(df, cache):
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'ODMR')] #filters only ODMR data of latest rep
        grouped = rep_df.groupby('f') #creates groupby object, df with key defined by 'f', and grouped rows as values

        ODMR = grouped['ODMR']
        ODMR_averaged = ODMR.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        return {'ODMR': [ODMR_averaged.index, ODMR_averaged]}

    @Plot1D
    def I1I2_plot(df, cache):
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'I1I2')] #filters only ODMR data of latest rep
        grouped = rep_df.groupby('t') #creates groupby object, df with key defined by 'f', and grouped rows as values

        I1I2 = grouped['dZFS']
        I1I2_averaged = I1I2.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        return {'I1I2': [I1I2_averaged.index, I1I2_averaged]}

    @Plot1D
    def I1I2_averaged_plot(df, cache):
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'I1I2')].dropna(subset=['dZFS_averaged']) #filters only ODMR data of latest rep
        grouped = rep_df.groupby('t') #creates groupby object, df with key defined by 'f', and grouped rows as values

        I1I2 = grouped['dZFS_averaged']
        I1I2_averaged = I1I2.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        return {'I1I2_averaged': [I1I2_averaged.index, I1I2_averaged]}

    @Plot1D
    def I1I2_PID(df, cache):
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'I1I2')] #filters only ODMR data of latest rep
        grouped = rep_df.groupby('t') #creates groupby object, df with key defined by 'f', and grouped rows as values

        I1I2 = grouped['dZFS_PID']
        I1I2_averaged = I1I2.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        return {'I1I2_PID': [I1I2_averaged.index, I1I2_averaged]}

    @Plot1D
    def fluorescence_plot(df, cache):
        ND = 0

        rep_df = df[(df.rep_idx == df.rep_idx.max()) & (df.dtype == 'I1I2')] #filters only ODMR data of latest rep
        grouped = rep_df.groupby('t') #creates groupby object, df with key defined by 'f', and grouped rows as values

        fluor = grouped['total_fluorescence']
        fluor_averaged = fluor.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
        return {'fluorescence': [fluor_averaged.index, fluor_averaged]}


