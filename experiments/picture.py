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

    def take_picture(self, readout_time=15e-3, trigger_time=10e-3, buffer_time=5e-3, picture: str=None,):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """

        with InstrumentManager() as mgr, DataSource(picture) as picture_data:  # +1 to account for signal being a difference of counts
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print(f"GetStatus failed with code {ret}. Check camera status.")
                return
            # if zoom:
            #     if type(zoom_coordinates) == str:
            #         zoom_coords = eval(zoom_coordinates)  # Expecting a string like "((x_start, x_end), (y_start, y_end))"
            #     zoom_x_start, zoom_x_end = zoom_coords[0]-zoom_coords[2], zoom_coords[0]+zoom_coords[2]+1
            #     zoom_y_start, zoom_y_end = zoom_coords[1]-zoom_coords[2], zoom_coords[1]+zoom_coords[2]+1

            ### WARNING (Ramon): There might be some issues with confusing the x and y lengths with width vs height. Need to confirm that the x_len and y_len are correct for the img_1D_to_2D function and that they correspond to the correct dimensions of the image. 
            x_len=mgr.Camera.x_len
            y_len=mgr.Camera.y_len
            self.trigger_mode=mgr.Camera.trigger_mode
            
            if self.trigger_mode == 'Internal':
                
                mgr.Pulser.set_state([3])
                mgr.Camera.start_acquisition()
                ret, _ = mgr.Camera.get_status()
                if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                    print(f"GetStatus failed with code {ret}. Check camera status.")
                    return
                

                time.sleep(0.1)  # wait for the camera to acquire some data
                ret=mgr.Camera.wait_for_acquisition_timeout(timeout_seconds=1)
                mgr.Pulser.set_state_off()
                _, number_images_acquired = mgr.Camera.get_total_number_images_acquired() 
                data_dic={}

                for i in range(1, number_images_acquired+1):

                    ret, data, _, _ = mgr.Camera.get_images_16(i, i, 1024**2)
                    temp_image=self.img_1D_to_2D(data,x_len,y_len)
                    
                    # if zoom:
                    #     temp_image = temp_image[zoom_y_start:zoom_y_end, zoom_x_start:zoom_x_end]
                    #     temp_image=np.asarray(temp_image)
                    data_dic[f'image_{i}'] = temp_image
                data_dic['latest_image']=temp_image


                
            elif self.trigger_mode == 'External' or self.trigger_mode == 'External Exposure (Bulb)':
                self.acquisition_mode=mgr.Camera.acquisition_mode
                if self.acquisition_mode == 'Kinetics' or self.acquisition_mode == 'Fast Kinetics':
                    self.num_pictures=int(mgr.Camera.number_kinetics)
                elif self.acquisition_mode == 'Single Scan':
                    self.num_pictures=1
                elif self.acquisition_mode == 'Run Till Abort':
                    print('WARNING: This function is not implemented for Run Till Abort mode.')
                    return
                elif self.acquisition_mode == "Accumulate":
                    self.num_pictures=int(mgr.Camera.number_accumulations) # Untested
                self.exp_time=int(mgr.Camera.exposure_time*1e9)
                self.readout_time=int(readout_time*1e9)
                self.trigger_time=int(trigger_time*1e9)
                self.buffer_time=int(buffer_time*1e9)
                if self.trigger_mode == 'External':
                    self.trigger_time = self.exp_time
                    if self.readout_time<0.059 * 1e9:
                        print('WARNING readout time should be at least 59 ms in pulse-length-exposure mode')
                else: 
                    if self.exp_time < self.trigger_time:
                        print(f'WARNING exposure time {self.exp_time/1e6} ms is less than trigger time {self.trigger_time/1e6} ms. This may cause issues due to coding. Need to understand minimum trigger length.')
                        raise Exception()
                    elif self.exp_time + self.readout_time < 0.08 * 1e9:
                        print('WARNING May experience failure from exposure + readout < 80 ms due to pulses being missed.')
                    if self.readout_time<0.005 * 1e9:
                        print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
                self.pic_seq=mgr.Pulser.WF_prep_gain_seq(n=self.num_pictures, exp=self.exp_time, read=self.readout_time, trig=self.trigger_time, buff=self.buffer_time)
                data_1D=self.GetPicBare(mgr, self.pic_seq, self.num_pictures)
                print(len(data_1D))
                data_dic={}
                for i, img_1D in enumerate(data_1D):
                    img_data=self.img_1D_to_2D(img_1D, x_len, y_len)
                    data_dic[f'image_{i}'] = img_data
                    # if zoom:
                    #     data_dic[f'image_{i}'] = data_dic[f'image_{i}'][zoom_y_start:zoom_y_end, zoom_x_start:zoom_x_end]
                data_dic['latest_image']=img_data
            picture_data.push({
                                'title': 'Picture',
                                'xlabel': 'Pixels',
                                'ylabel': 'Pixels',
                                'xs': np.asarray(range(x_len)),
                                'ys': np.asarray(range(y_len)),
                                'datasets': data_dic
            })
            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
            # the GUI has asked us nicely to exit
                return temp_image

                





    #### INITIALIZATION METHODS

 

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))

    #### FINALIZATION METHODS

    


