###########################
# imports
###########################

# std
import numpy as np
import time
import math
from itertools import cycle
import logging
import pims
from pims import Frame, FramesSequence
#from skimage.io import imsave, imread #Not working?
from PIL import Image
import pickle #Delete later

# importing the sys module
import sys, os


# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

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
    REQUIRED_DEVICES = ['pulses' ,'urixyz']


    PARAMS = {
        'exp_time':{ #this represents the exposure time per frame
            'type':float,
            'units':'s',
            'suffix': 's',
            'default': 100e-3,
        },
        'cam_trigger':{'type': list,'items': ['EXTERNAL_EXPOSURE','EXTERNAL_FT'], 'default': 'EXTERNAL_BULB'},

        'wait_time':{ #this represents the total time per frame (including exposure and readout time)- greater than or equal to exp_time + 39 ms
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
        'probe_time':{ #total amount of time the microwave is pulsed (on or off)
            'type': float,
            'default': 160e-3,
            'suffix': 's',
            'units': 's'
        },
        'data_path': { #where the raw images are saved if data_download is true
            'type': str,
            'default': 'Z:\\biosensing_setup\\data\\WFODMR_images_test'
        },

        'save_image': {
            'type': bool,
            'default': False
        },
        'ROI':{'type': str, 'default': '(512,512,64)'},

        'zoom':{
            'type': bool, 'default': False,
        },
        'cooler':{'type': str, 'default': '(False, 20)'},
        'Misc': {
            'type': str,
            'default': "{'DEBUG':False}" #default values for invert, threshold, and minmass respectively
        }

    }
    def initialize(self, exp_time,cam_trigger,wait_time, gain,probe_time, ROI, zoom, data_path, save_image,cooler, Misc): 
        self.misc = eval(Misc)
        self.wait_time = wait_time.m
        self.exp_time = exp_time.m
        self.gain = gain
    

        self.sdk = atmcd("")  # Load the atmcd library
        self.codes = atmcd_codes
        self.cam_on(self.exp_time, self.gain)

        ROI = eval(ROI)
        self.px_x = ROI[0]
        self.px_y = ROI[1]
        self.r = ROI[2]

        self.zoom = zoom

    def cam_on(self,exp_time,gain):
        ret = self.sdk.Initialize("")  # Initialize camera
        print("Function Initialize returned {}".format(ret)) #returns 20002 if successful
        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.SINGLE_SCAN) #Taking a series of pulses
        self.sdk.SetReadMode(self.codes.Read_Mode.IMAGE) #reading pixel-by-pixel with no binning
        self.sdk.SetTriggerMode(self.codes.Trigger_Mode.INTERNAL)
        (ret, xpixels, ypixels) = self.sdk.GetDetector()
        self.sdk.SetImage(1, 1, 1, xpixels, 1, ypixels) #defining image
        self.sdk.SetExposureTime(exp_time) 
        self.sdk.SetEMCCDGain(gain) #setting Electron Multiplier Gain
        self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_OPEN,27,27) #Open Shutter


    def main(self, exp_time,cam_trigger,wait_time, gain,probe_time, ROI, zoom, data_path, save_image,cooler, Misc): 
        commands = 'commands: \n -help: repeat commands \n -done: exit cam-control\n -on: initialize camera\n -off: shutdown camera\n -cool: initialize cooldown sequence (WARNING, CANNOT BE ABORTED)'
        commands += f'\n -gain: set gain\n -exp: set exp time\n -wait: set wait time\n -pic: take  single picture\n -stream: stream a picture every {self.exp_time + self.wait_time} seconds\n -series: kinetic series with acquisitions'
        commands += f'\n -pdb: use pdb to control fields/commands more directly, -save: save the last image taken to a pickle file to the data path\n -toggle_zoom: toggle zoom on/off'
        commands += f'\n -focus: focus at (x,y) with radius r'
            #add warmup
        #check camera is on
        ret = self.sdk.GetStatus()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            return
        print(commands)
        res = ''
        while(res != 'done'):
            res = input('command: ')
            if res == 'on':
                self.cam_on(self.exp_time, self.gain)
            elif res == 'off':
                self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_CLOSED,27,27)
                ret = self.sdk.ShutDown()
                print("SDK shutdown ")
                print(ret) ##returns 20002 if successful
            elif res == 'help':
                print(commands)
            elif res == 'pdb':
                import pdb;pdb.set_trace() #allows us to run our own code
            elif res == 'cool':
                t0 = time.time()
                Temp = input('set temp from -50 to 20: ')
                # Temp = eval(Temp)
                if Temp<-50 or Temp>20:
                    print('Temp not in range. Try again')
                    continue
                # confirm = input('Warning, cooldown cannot be aborted once started. Are you sure you want to proceed? (type "y" to proceed) ')
                confirm = 'y'
                if confirm == 'y':
                    ret = self.sdk.SetTemperature(Temp)
                    print(f"Function SetTemperature returned {ret} target temperature {Temp}")
                    print('Input "c" to continue without waiting for stabilization. Input anything else to refresh. ')
                    ret = self.sdk.CoolerON()
                    while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED and inp != 'c':
                        # time.sleep(5)
                        (ret, temperature) = self.sdk.GetTemperature()
                        inp = input("Function GetTemperature returned {} current temperature = {} ".format(
                            ret, temperature))
                    print(f'\n Temp Stabilized. Cooldown took {time.time()-t0}')

                else:
                    continue
            elif res == 'gain':
                self.gain = eval(input('gain set: '))
                self.sdk.SetEMCCDGain(self.gain)
                print(f'gain set to {self.gain}')
            elif res == 'exp':
                self.exp_time = eval(input('exp time set (s): '))
                self.sdk.SetExposureTime(self.exp_time) 
                print(f'exp_time set to {self.exp_time} (s)')
            elif res =='wait':
                self.wait_time = eval(input('wait time set (s): '))
                print(f'exp_time set to {self.wait_time} (s)')
            elif res =='pic':
                self.pulses.Pulser.constant(([3],0.0,0.0))
                img = self.pic()
                print(f'{self.sdk.GetTotalNumberImagesAcquired()[1]} images acquired')
                if self.zoom:
                    img = img[self.px_y - self.r: self.px_y+self.r, self.px_x - self.r: self.px_x+self.r]
                self.acquire({ 
                'img': img })
                self.pulses.Pulser.reset()
            elif res =='save':
                self.data_path = data_path+r'\imgs'
                if(not os.path.isdir(self.data_path)):
                    os.mkdir(self.data_path)
                with open(self.data_path+f'\\img_{time.time()}.pkl', 'wb') as file: 
                    pickle.dump(img, file)
            elif res == 'series':
                print('not fully implemented')
                img = self.series()
                print(f'{self.sdk.GetTotalNumberImagesAcquired()[1]} images acquired')
                self.acquire({ 
                'img': img }) 
            elif res =='stream':
                self.pulses.Pulser.constant(([3],0.0,0.0)) 
                #temporary solution, should figure out a better way of closing the stream
                res2 = input('how many seconds?: ')
                try:
                    n_imgs = 0
                    t0 = time.time()
                    t = t0
                    while t <= t0 + float(res2):
                        # self.clear_data()
                        img = self.pic()
                        if self.zoom:
                            img = img[self.px_y - self.r: self.px_y+self.r, self.px_x - self.r: self.px_x+self.r]
                        #print(t)
                        time.sleep(self.wait_time)
                        n_imgs += self.sdk.GetTotalNumberImagesAcquired()[1]
                        # print(f'{n_imgs} acquired',end = '\r')
                        
                        self.acquire({ 'img': img })
                        t = time.time()
                    print('done streaming')
                except ValueError:
                    print("invalid value for time")
                self.pulses.Pulser.reset()
            elif res == 'toggle_zoom':
                self.zoom = not self.zoom
                print(f'zoom set to {self.zoom}')

            elif res == 'focus':
                res2 = input('(x, y, r): ')
                res2 = eval(res2)
                if type(res2) is not tuple or len(res2) != 3:
                    print('invalid input, must be tuple (x,y,r)')
                    continue
                z_pos = self.urixyz.daq_controller.position['z'].to('um').m
                x_pos = self.urixyz.daq_controller.position['x'].to('um').m
                y_pos = self.urixyz.daq_controller.position['y'].to('um').m
                self.pulses.Pulser.constant(([3],0.0,0.0))
                img=self.pic()
                _, _, x_center, y_center = self.focus_data_process(img, res2[0], res2[1], res2[2])
                print(f'ND center: ({x_center}, {y_center})')
                for i in range(30):
                    img = self.pic()

                    x_line, y_line, _, _ = self.focus_data_process(img, x_center, y_center, res2[2])
                    print(f'x_line: {x_line}, y_line: {y_line}')
                    if x_line < 1.05 * y_line:
                        if y_line < 1.05 * x_line:
                            print('focus complete')
                            break
                        else: 
                            print('raising z')
                            z_pos += 0.05
                    else:
                        print('lowering z')
                        z_pos -= 0.05
                    self.urixyz.daq_controller.move({'x': Q_(x_pos,'um'), 'y': Q_(y_pos,'um'), 'z': Q_(z_pos,'um')})
                self.pulses.Pulser.reset()


    def img_1D_to_2D(self,img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        return np.asarray(img_1D, dtype='int').reshape((y_len, x_len))
    

    def pic(self):
        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.SINGLE_SCAN)
        self.sdk.StartAcquisition()
        ret = self.sdk.GetStatus()
        if not ret[0] == 20002:
            print('Starting Acquisition Failed, ending process...')
            return
        #print('Starting Acquisition', ret)
        time.sleep(0.1) #Give time to start acquisition

        ret = self.sdk.WaitForAcquisitionTimeOut(1000)

        (ret, all_data, validfirst, validlast) = self.sdk.GetImages16(1,1,1024**2) #cut out first image here
        temp_image = self.img_1D_to_2D(all_data,1024,1024) 
        return temp_image
        # temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 

    def focus_data_process(self, img, x_center, y_center, r):
        first_x_index = max(x_center - r,0)
        last_x_index = min(x_center + r+1, img.shape[0])
        first_y_index = max(y_center - r,0)
        last_y_index = min(y_center + r+1, img.shape[1])
        middle_x_index = x_center- first_x_index
        middle_y_index = y_center- first_y_index
        img_crop = img[first_y_index:last_y_index, first_x_index:last_x_index]
        self.acquire({ 'img': img_crop })
        y_sum = np.sum(img_crop, axis=0)
        x_sum = np.sum(img_crop, axis=1)
        max_row, max_col = np.unravel_index(np.argmax(img_crop), img_crop.shape)
        max_index_x = first_x_index + int(max_col)
        max_index_y = first_y_index + int(max_row)

        if middle_x_index >0 :
            if middle_x_index< len(x_sum)-1:
                x_line = np.sum(x_sum[middle_x_index-1:middle_x_index+2] )
            else: 
                x_line = np.sum(x_sum[middle_x_index-2:middle_x_index+1] )
        else:
            x_line = np.sum(x_sum[middle_x_index:middle_x_index+3] )
        if middle_y_index >0 :
            if middle_y_index< len(y_sum)-1:
                y_line = np.sum(y_sum[middle_y_index-1:middle_y_index+2] )
            else:
                y_line = np.sum(y_sum[middle_y_index-2:middle_y_index+1] )
        else:
            y_line = np.sum(y_sum[middle_y_index:middle_y_index+3])
        return x_line, y_line, max_index_x, max_index_y

    def series(self):
        self.sdk.SetAcquisitionMode(self.codes.Acquisition_Mode.KINETICS)
        for acq in self.sdk.acquire_series(2):
            print(f'acquiring {len(acq)}')

        (ret, all_data) = self.sdk.GetMostRecentImage(1024**2)
        temp_image = self.img_1D_to_2D(all_data,1024,1024) 
        return temp_image

    def finalize(self, exp_time,cam_trigger,wait_time, gain,probe_time, ROI, zoom, data_path, save_image,cooler, Misc): 

        ret = self.sdk.SetShutter(1,self.codes.Shutter_Mode.PERMANENTLY_CLOSED,27,27)
        print("Function SetShutter returned {}".format(ret))
        print("FINALIZE")

        return

    # @PlotFormatInit(LinePlotWidget, ['average_0'])
    # def init_format(p):
    #     p.xlabel = 'frequency (Hz)'
    #     p.ylabel = 'PL (cts)'


    ## this plots the running average of all sweeps.
    @Plot2D
    def picture(df, cache):
        latest_img = df['img'].iloc[-1]
        return latest_img
    
    # @Plot2D
    # def img_crop(df, cache):
    #     latest_img = df['img_crop'].iloc[-1]
    #     return latest_img

