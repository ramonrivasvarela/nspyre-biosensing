"""
experiment to determine counts, iterated through time.

Written by David Ovetsky
Written on 6/12/2025

"""

#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import time
import numpy as np
####
from experiments.wfExperiment import WFSpyrelet

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class Pictures(WFSpyrelet):
    """Pictures experiments."""

    def __init__(self, queue_to_exp=None, queue_from_exp=None):
        """
        Args:
            queue_to_exp: A multiprocessing Queue object used to send messages
                to the experiment from the GUI.
            queue_from_exp: A multiprocessing Queue object used to send messages
                to the GUI from the experiment.
        """
        super().__init__(queue_to_exp, queue_from_exp)

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
        _logger.info('Created Pictures instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Pictures instance.')

    def take_picture(self, readout_time=15e-3, trigger_time=10e-3, buffer_time=5e-3,
                      routine = 'Full Picture', ROI='[(512, 512)]', window_size=16, picture: str=None,):
        """
        A program for low-level camera operation
        """

        with InstrumentManager() as mgr, DataSource(picture) as picture_data:  # +1 to account for signal being a difference of counts
            ## INIT
            self.verbose = True
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print(f"GetStatus failed with code {ret}. Check camera status.")
                return
            x_len=mgr.Camera.x_len
            y_len=mgr.Camera.y_len
            trigger_mode=mgr.Camera.trigger_mode
            mgr.Camera.set_shutter("Open") # Open shutter for picture taking
            n_pics = mgr.Camera.number_kinetics
            if n_pics > 2 and routine == 'Full Picture':
                print('WARNING: Due to NSpyre DataSink limitations, can only have at most 2 images of full size')
                n_pics = 2
                mgr.Camera.set_number_kinetics(n_pics)
            self.z_pos = mgr.DAQcontrol.position['z']
            # if zoom:
            #     if type(zoom_coordinates) == str:
            #         zoom_coords = eval(zoom_coordinates)  # Expecting a string like "((x_start, x_end), (y_start, y_end))"
            #     zoom_x_start, zoom_x_end = zoom_coords[0]-zoom_coords[2], zoom_coords[0]+zoom_coords[2]+1
            #     zoom_y_start, zoom_y_end = zoom_coords[1]-zoom_coords[2], zoom_coords[1]+zoom_coords[2]+1
            ### WARNING (Ramon): There might be some issues with confusing the x and y lengths with width vs height. Need to confirm that the x_len and y_len are correct for the img_1D_to_2D function and that they correspond to the correct dimensions of the image. 
            
            if routine == 'ROI Pictures' or routine == 'Autofocus':
                if type(ROI) == str:
                    self.ND_list = eval(ROI) # Expecting a string like "[(x1, y1), (x2, y2), ...]"
                else:
                    self.ND_list = [ROI]
                self.r_display = int(window_size)
                self.all_ROI = True
                if len(self.ND_list) == 0:
                    print('No ROIs provided. Please provide at least one ROI.')
                    return
                elif len(self.ND_list) > 1:
                    print('Multiple ROIs not yet implemented. Selecting the first.')
                    self.ND_list = [self.ND_list[0]]
                px_x = int(self.ND_list[0][0])
                px_y = int(self.ND_list[0][1])
            x_img = np.array(range(x_len)) if routine == 'Full Picture' else np.array(range(px_x-self.r_display, px_x + self.r_display))
            y_img = np.array(range(y_len)) if routine == 'Full Picture' else np.array(range(px_y-self.r_display, px_y + self.r_display))

            self.data_dict = {}
            ## Get Picture, looping for autofocus if necessary:
            autofocus_bool = (routine == 'Autofocus')
            
            self.last_pic_n = 0
            while (not autofocus_bool and self.last_pic_n == 0) or autofocus_bool:
                prev_z_pos = self.z_pos
                data_1D = self.get_images(mgr, trigger_mode, readout_time, trigger_time, buffer_time, n_pics)
                #### ANALYZE DATA ######################################################
                print(f'Number of images acquired: {len(data_1D)} / {n_pics}')
                for i,img in enumerate(data_1D):
                    img_data = self.img_1D_to_2D(img, x_len, y_len)
                    if routine == 'ROI Pictures' or routine == 'Autofocus':
                        windows = self.format_windows(mgr, img_data, focus_bool = (routine == 'Autofocus' and i == len(data_1D)-1)) #only autofocus using last image
                        img_data = windows[0] # Need to implement multiple ROIs
                    self.data_dict[f'image_{self.last_pic_n}'] = img_data
                    self.last_pic_n += 1
                self.data_dict['window'] = img_data    
                picture_data.push({
                                    'title': 'Picture',
                                    'xlabel': 'Pixels',
                                    'ylabel': 'Pixels',
                                    'xs': x_img,
                                    'ys': y_img,
                                    'datasets': self.data_dict
                })
                autofocus_bool = not prev_z_pos == self.z_pos and autofocus_bool
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    mgr.Camera.set_shutter("Closed") # Close shutter for picture taking
                    return 
            mgr.Camera.set_shutter("Closed") # Close shutter for picture taking
    
    #### MAIN METHODS
    def get_images(self, mgr, trigger_mode, readout_time, trigger_time, buffer_time, n_pics):
        #### INTERNAL MODE ########################################################
        if trigger_mode == 'Internal':
            if mgr.Camera.number_kinetics > 1:
                print('WARNING: Internal trigger mode kinetic mode not working properly. Taking multiple single images.')  
            data_1D = []
            ## Get picture INTERNAL
            mgr.Pulser.set_state([3])
            for i in range(n_pics):
                mgr.Camera.start_acquisition()
                ret, _ = mgr.Camera.get_status()
                if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                    print(f"GetStatus failed with code {ret}. Check camera status.")
                    mgr.Pulser.set_state_off()
                    return
                time.sleep(0.1)  # wait for the camera to acquire some data
                ret=mgr.Camera.wait_for_acquisition_timeout(timeout_seconds=1)
                mgr.Pulser.set_state_off()
                _, number_images_acquired = mgr.Camera.get_total_number_images_acquired() 
                (ret, all_data, _, _) = mgr.Camera.get_images_16(1, 1, 1024**2)
                data_1D.append(all_data)
        #### EXTERNAL MODE ########################################################
        elif trigger_mode == 'External' or trigger_mode == 'External Exposure (Bulb)':
            ## Prepare Acquisition Mode
            acquisition_mode=mgr.Camera.acquisition_mode
            if acquisition_mode == 'Kinetics' or acquisition_mode == 'Fast Kinetics':
                pass # already set the right amount of n_pics
            elif acquisition_mode == 'Single Scan':
                n_pics = 1
            elif acquisition_mode == 'Run Till Abort':
                print('WARNING: This function is not implemented for Run Till Abort mode.')
                return
            elif acquisition_mode == "Accumulate":
                print('WARNING: This function is not implemented for Accumulate mode.')
                return
            ## Prepare Timings
            ns_exp_time=int(mgr.Camera.exposure_time*1e9)
            ns_readout_time=int(readout_time*1e9)
            ns_trigger_time=int(trigger_time*1e9)
            ns_buffer_time=int(buffer_time*1e9)
            ## Prepare Exposure Type
            if trigger_mode == 'External Exposure (Bulb)':
                ns_trigger_time = ns_exp_time
            ## Verify
            if ns_readout_time<0.059 * 1e9 and mgr.Camera.frame_transfer_mode == 'OFF':
                    print('WARNING readout time should be at least 59 ms in pulse-length-exposure mode')
            if ns_exp_time < ns_trigger_time and trigger_mode != 'External Exposure (Bulb)':
                print(f'WARNING exposure time {ns_exp_time/1e6} ms is less than trigger time {ns_trigger_time/1e6} ms. This may cause issues due to coding. Need to understand minimum trigger length.')
                raise Exception()
            elif ns_exp_time + ns_readout_time < 0.08 * 1e9 and mgr.Camera.frame_transfer_mode == 'ON':
                print('WARNING May experience failure from exposure + readout < 80 ms due to pulses being missed.')
            if ns_readout_time<0.005 * 1e9:
                print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
            ## Set Up            
            self.pic_seq=mgr.Pulser.WF_prep_gain_seq(n=n_pics, exp=ns_exp_time, read=ns_readout_time, trig=ns_trigger_time, buff=ns_buffer_time)
            data_1D=self.GetPicBare(mgr, self.pic_seq, n_pics)
        return data_1D

            

    def format_windows(self, mgr, img, focus_bool = False):
            '''
            From WFSpyrelet

            formats an image into a list of ROIs around each ND of size self.r_display*2 by self.r_display*2, 
            Autofocuses using the first ND. 
            If focus_bool is True, also runs autofocus on the first ROI and updates self.z_pos accordingly. Returns a list of images for 2D plotting.
            '''
            windows = []
            imgs_to_acquire = range(len(self.ND_list))
            for ND in imgs_to_acquire:
                loc = self.ND_list[ND]
                px_x = int(loc[0])
                px_y = int(loc[1])
                ROI = img[px_y-self.r_display:px_y+self.r_display,px_x-self.r_display:px_x+self.r_display]
                if ND==0 and focus_bool:
                    self.z_pos = self.autofocus(mgr, ROI, self.r_display)
                #make sure ROI is a list of lists of ints for nspyre compatibility:
                ROI = ROI.astype(int).tolist()
                windows.append(ROI)
            return windows
    
    def autofocus(self, mgr, temp_image, ROI_rad):
            '''
            From WFSpyrelet. 
            Checks picture aberration to determine focus (setup dependent, but reliable for us)
            and moves one step to correct z direction. Returns new z position.
            ''' 
            z_pos = float(mgr.DAQcontrol.position['z'])
            x_pos = float(mgr.DAQcontrol.position['x'])
            y_pos = float(mgr.DAQcontrol.position['y'])
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
            mgr.DAQcontrol.move({'x': x_pos, 'y': y_pos, 'z': z_pos})
            return z_pos



    #### INITIALIZATION METHODS

 

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))

    #### FINALIZATION METHODS

    


