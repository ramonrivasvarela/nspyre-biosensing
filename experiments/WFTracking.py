'''
Widefield Routine for Multi-ND ZFS Sensing using a Two-Point Measurement
'''

#### IMPORTS
## Standard
import numpy as np
import time
from scipy.optimize import curve_fit
import trackpy as tp


import pickle
import os
from collections import deque 

from experiments.camera_settings_tasks.gain_optimization import get_gain

## Nidaqmx




from nspyre import InstrumentManager, DataSource

## Cam SDK

import logging
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

#### Spyrelet
class WFODMRTrack():
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
        _logger.info('Created WFTracking instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed WFTracking instance.')
    # VERSION = '1.0' #to keep track of how to parse apart data, in case output style changes. 

    def wftracking(self, 
                   device:str='Dev1',
                   exp_time:float= 75e-3, # seconds
                   readout_time:float= 15e-3, # seconds
                   cam_trigger:str='EXTERNAL_FT', # 'EXTERNAL_FT' or 'EXTERNAL_EXPOSURE'
                   gain:int=2, # EM gain for camera, goes from 1-272
                   routine:str='[2,3,100,0,-1]', # runs, sweeps, two-pt interval, two-pt averaging, total reps
                   wait_interval:str='(0,10)', # wait interval, of form (points-between-wait, wait time (s)), where <1 means no waiting
                   end_ODMR:bool=False, # if True, will finalize the ODMR at the end of the routine
                   frequency:str='[2.84e9, 2.90e9, 30]', # [start, end, num_points]
                   label:str='[t, 1, 0, 2, 0, 1, 0, 2, 0]', # labels for the two-point measurement
                   rf_amplitude:int=-15, # RF amplitude in dBm
                   mode:str='AM', # 'AM' or 'SWITCH'
                   ROI_xy:str='[(512,512)]', # list of (x,y) tuples for the regions of interest
                   ZFS:float=2.868780e9, # Zero-field splitting in Hz
                   sideband:float=12e6, # Sideband in Hz
                   QLS:str='[-5e-9]', # Quantum-limited sensitivity in Hz
                   alt_label:bool=False, # Alternate label to get more balanced results
                   PID:str="{'Kp':0.03, 'Ki': 0.005, 'Kd':0.01, 'Mem': 15, 'Mem_decay': 2.0}", # PID parameters
                   data_path:str='Z:\\biosensing_setup\\data\\WFODMR_images_test', # Path to save data
                   save_image:bool=False, # Save full images
                   data_download:bool=False, # Save just raw data [sig, bg, ...]
                   window:bool=True, # Show sample at intermittent points (every sub_interval points)
                   optimize_gain:bool=False,# Optimize gain at the start
                   data_source:str='wftrack', # Data source name
                   Misc:str="{'DEBUG':False}"): # Miscellaneous parameters

        ## Optimize Gain ##########
        self.initialize(self, mgr, exp_time, readout_time,cam_trigger,gain,routine, wait_interval, end_ODMR,frequency,label,rf_amplitude,mode,ROI_xy,
                   alt_label, PID,data_path,save_image,data_download, window, Misc)
        print('Optimizing gain...')
        with InstrumentManager() as mgr, DataSource(data_source) as source:
            get_gain(mgr, optimize_gain, gain, frequency, self.runs, mode, self.ns_exp_time, self.ns_readout_time)


            #### Experiment Loop ##########
            mgr.sg.set_rf_toggle(True)

            self.t_rep = [time.time()]
            rep = 0
            ZFS_setpt = ZFS
            sb_setpt = sideband
            ls_QLS = eval(QLS)
            ls_ZFS = [ZFS] * len(self.ND_List)
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
                    ZFS_setpt = ZFS_avg
                    sb_setpt = np.mean([z for z in ls_sb if z != 0])
                    self.dt_ls_ZFS.append(ls_ZFS)
                    for i in range(len(ls_ZFS)):
                        if ls_ZFS[i] == 0:
                            ls_ZFS[i] = ZFS_avg

                    ls_dZFS_PID = [(ls_ZFS[ND] - ZFS_setpt) for ND in self.ND_iter] #make sure it shouldn't be the opposite way around... ZFS_setpt.m - ls_ZFS
                else:
                    ls_dZFS_PID = [0 for ND in self.ND_iter]

                e_arr = []
                for ND in self.ND_iter:
                    e_arr.append(deque())
                    e_arr[ND].appendleft(0)

                print(f'ZFS set to {ZFS_setpt/1e9} GHz, sb set to {sb_setpt/1e6} MHz')
                self.dt_sg_setpt.append((ZFS_setpt, sb_setpt))

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

                mgr.sg.set_mod_type("FM")
                mgr.sg.set_FM_mod_dev(sb_setpt)
                mgr.sg.set_frequency(ZFS_setpt)
                mgr.Camera.set_number_kinetics(n_pic)


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
                        ls_fullZFS.append(ls_dZFS[ND] + ZFS_setpt)
                        ls_fullZFS_averaged.append(ls_dZFS_averaged[ND] + ZFS_setpt.m)
                        ls_fullZFS_PID.append(ls_dZFS_PID[ND] + ZFS_setpt)
                    


                    if (self.sub_interval >= 1 and s%self.sub_interval==self.sub_interval-1):
                        source.push({
                            'params':{
                                'device':device,
                                'exp_time': exp_time, # seconds
                                'readout_time': readout_time, # seconds
                                'cam_trigger':cam_trigger, # 'EXTERNAL_FT' or 'EXTERNAL_EXPOSURE'
                                'gain':gain, # EM gain for camera, goes from 1-272
                                'routine':routine, # runs, sweeps, two-pt interval, two-pt averaging, total reps
                                'wait_interval':wait_interval, # wait interval, of form (points-between-wait, wait time (s)), where <1 means no waiting
                                'end_ODMR':end_ODMR, # if True, will finalize the ODMR at the end of the routine
                                'frequency':frequency, # [start, end, num_points]
                                'label':label, # labels for the two-point measurement
                                'rf_amplitude':rf_amplitude, # RF amplitude in dBm
                                'mode':mode, # 'AM' or 'SWITCH'
                                'ROI_xy':ROI_xy, # list of (x,y) tuples for the regions of interest
                                'ZFS':ZFS, # Zero-field splitting in Hz
                                'sideband':sideband, # Sideband in Hz
                                'QLS':QLS, # Quantum-limited sensitivity in Hz
                                'alt_label':alt_label, # Alternate label to get more balanced results
                                'PID':PID, # PID parameters
                                'data_path':data_path, # Path to save data
                                'save_image':save_image, # Save full images
                                'data_download':data_download, # Save just raw data [sig, bg, ...]
                                'window':window, # Show sample at intermittent points (every sub_interval points)
                                'optimize_gain':optimize_gain,# Optimize gain at the start
                                'data_source':data_source, # Data source name
                                'Misc':Misc
                            },
                    # Miscellaneous parameters
                            'rep_idx': rep,
                            'sweep_idx': s,
                            't': t_pt,
                            'dZFS': ls_fullZFS, #ls_dZFS for values relative to 0. Currently including setpoint.
                            'ZFS_setpt' : ZFS_setpt, 
                            'total_fluorescence': total_fluorescence,
                            'dZFS_averaged' : ls_fullZFS_averaged,
                            'dZFS_PID' : ls_fullZFS_PID,
                            'img': im,
                            'dtype': 'I1I2',
                            })
                        ls_dZFS_averaged = [0] * len(self.ND_List)

                    else:
                        source.push({
                            'rep_idx': rep,
                            'sweep_idx': s,
                            't': t_pt,
                            'dZFS': ls_fullZFS,
                            'dZFS_PID' : ls_fullZFS_PID,
                            'ZFS_setpt' : ZFS_setpt, 
                            'total_fluorescence': total_fluorescence,
                            'dtype': 'I1I2',
                            })
                    s+=1
                    if self.wait_interval[0] > 0 and s%self.wait_interval[0] == 0:
                        mgr.sg.set_rf_toggle(False)
                        # print(f'waiting {self.wait_interval[1]} seconds...')
                        time.sleep(self.wait_interval[1])     
                        mgr.sg.set_rf_toggle(True)
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            self.finalize(self, mgr, routine, wait_interval, ROI_xy,
                            alt_label, PID,save_image,data_download)
                            return                    
                rep+=1
                self.t_rep.append(round(time.time(),3) )
            
            if self.end_ODMR:
                print('final ODMR')
                self.run_ODMR(self.reps+1,save_image)
        self.finalize(self, mgr, routine, wait_interval, ROI_xy,
                      alt_label, PID,save_image,data_download)

    def initialize(self, mgr, exp_time, readout_time,cam_trigger,gain,routine, wait_interval, end_ODMR,frequency,label,rf_amplitude,mode,ROI_xy,
                   alt_label, PID,data_path,save_image,data_download, window, Misc):
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
        self.exp_time = exp_time # seconds
        self.ns_exp_time = exp_time * 1e9 # nanoseconds
        self.readout_time = readout_time # seconds
        self.ns_readout_time = readout_time * 1e9 # nanoseconds
        self.trigger_time = 0.010 # seconds             #(Hardcoded)
        self.ns_trigger_time = self.trigger_time * 1e9 # nanoseconds
        self.buffer_time = 0.005 # seconds              #(Hardcoded)
        self.ns_buffer_time = self.buffer_time * 1e9 # nanoseconds

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
        self.frequency = freq
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
        
        mgr.sg.set_mode_toggle(True)
        mgr.sg.set_mode_function('external')
        mgr.sg.set_mode_amplitude(rf_amplitude) #set amplitude in dBm

        ## Seq init ##########
        bool_FT = (cam_trigger=='EXTERNAL_FT')
        ### Important: CONVERT TO NANOSECONDS
        self.ODMR_seq = mgr.Pulser.WFODMR(self.runs, self.ns_exp_time, self.ns_readout_time, trig = self.ns_trigger_time, buff = self.ns_buffer_time, mode = mode
            , FT = bool_FT) 
        self.gain_seq = mgr.Pulser.gain_seq(self.ns_exp_time, self.ns_readout_time, FT = bool_FT)
        self.ZFS_seq = mgr.Pulser.I1I2(self.ns_exp_time, self.ns_readout_time, self.ns_trigger_time, self.ns_buffer_time, self.label_base, FT = bool_FT)
        self.ZFS_seq_inv = mgr.Pulser.I1I2(self.ns_exp_time, self.ns_readout_time, self.ns_trigger_time, self.ns_buffer_time, self.label_inv, FT = bool_FT)

        self.I1I2_seqs = [self.ZFS_seq, self.ZFS_seq]
        if alt_label:
            self.I1I2_seqs[1] = self.ZFS_seq_inv

        ## Cam init ##########
        if mgr.Camera.get_status()[0] == 20075:
            ret = mgr.Camera.initialize  # Initialize camera
            print("Function Initialize returned {}".format(ret))

        mgr.Camera.set_acquisition_mode("Kinetics") #Taking a series of pulses
        mgr.Camera.set_read_mode("Image") #reading pixel-by-pixel with no binning
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            mgr.Camera.set_trigger_mode("External Exposure Bulb")
            if self.readout_time<0.059:
                print('WARNING readout time should be at least 59 ms in pulse-length-exposure mode')
        else:
            mgr.Camera.set_trigger_mode("External")
            exposure_min = 0.046611 # hardware limited minimum exposure in FT mode
            if self.exp_time < exposure_min:
                print(f'exposure must be at least {exposure_min*1000} ms.')
                return
            elif self.exp_time + self.readout_time < 0.08:
                print('WARNING May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            if self.readout_time<0.005:
                print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
            mgr.Camera.set_exposure_time(self.exp_time) 
            mgr.Camera.set_frame_transfer_mode("conventional") 

        ret, _, _ = mgr.Camera.get_detector()
        mgr.Camera.set_image() #defining image
        #self.sdk.SetBaselineClamp(1)
        mgr.Camera.set_gain(self.gain) #setting Electron Multiplier Gain
        mgr.Camera.set_shutter("Open") #Open Shutter

        self.t_init = round(time.time(),3)
        self.t_cool = self.t_init
        self.t_gain = self.t_init
        self.t_rep = [self.t_init]

        

        print('Initialization finished')

        

    def finalize(self, mgr, routine, wait_interval, ROI_xy,
        alt_label, PID,save_image,data_download):

        if self.finalize_ODMR:
            print('final ODMR')
            self.run_ODMR(self.reps+1,save_image, do_acquire = False)
            print('final ODMR finished')
        
        mgr.sg.set_rf_toggle(False) #turn off RF
        mgr.sg.set_mod_toggle(False) #turn off modulation

        ## cam end ##########
        ret = mgr.Camera.set_shutter("Closed")
        if(ret==20002):
            print("Shutter closed successfully")
        else:
            print("WARNING: Trouble closing shutter")

        

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
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))

    def GetPictures(self, mgr, seq, n_pic,do_save = False, last_pics = [], im_labels = [], im_size = 1024**2):
        '''
        Runs an acquisition of n pictures over a given sequence, returns pictures as a parsed list of 1D arrays or length 'im_size'
        Allows for efficient saving via do_save, labels which contain n_pic different labels which are strings


        Warning: this method does not touch the sg
        Warning: do_save does not check for save_img. save_img must be factored in beforehand
        '''
        acq_sleep = 0.1
        timeout_limit = n_pic * 20

        # self.sdk.SetNumberKinetics(n_pic)
        mgr.Camera.start_acquisition()
        ret = mgr.Camera.get_status()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            return
        time.sleep(acq_sleep) #Give time to start acquisition
        mgr.Pulser.stream_umOFF(seq, 1, AM_mode = True) #0 since only one seq in my seq array.
        timeout_counter = 0
        if do_save: self.save_pics(last_pics, im_labels)
        while(mgr.Camera.get_total_number_images_acquired()[1]<n_pic and timeout_counter<=timeout_limit):
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1 
            if timeout_counter == timeout_limit:
                print(f'timeout with {mgr.Camera.get_total_number_images_acquired()[1]} pictures.')
        ret, all_data, _, _ = mgr.Camera.get_images(1,n_pic,n_pic * 1024**2) #cut out first image here
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

    def run_ODMR(self, mgr, rep, save_image, do_acquire = True):
        for ND in self.ND_iter:
            self.dt_ODMR_raw[ND].append([])#creates dt_ODMR_raw[ND][rep] for each ND
            self.dt_ODMR_ref[ND].append([])#creates dt_ODMR_ref[ND][rep] for each ND

        ## Run ODMR, Collect Params Per ND, Diagnostic
        n_pic = self.runs*2+1
        mgr.sg.set_mod_type('AM') #set modulation type to AM
        mgr.sg.set_AM_mod_depth(100)

        mgr.Camera.set_number_kinetics(n_pic)
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
                mgr.set_frequency(freq) #set frequency
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
