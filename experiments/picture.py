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

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class Pictures:
    """Pictures experiments."""

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
        _logger.info('Created Pictures instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Pictures instance.')

    def take_picture(self, zoom: bool=False, zoom_coordinates: str=None, picture: str=None, single_picture: bool=False):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """
        with InstrumentManager() as mgr, DataSource(picture) as picture_data:  # +1 to account for signal being a difference of counts
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return
            mgr.Pulses.set_state([7])
            mgr.Camera.start_acquisition()
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return
            x_len=mgr.Camera.x_len
            y_len=mgr.Camera.y_len
            if zoom:
                if zoom_coordinates is None:
                    print("Zoom coordinates not provided. Cannot zoom.")
                    return
                zoom_coords = eval(zoom_coordinates)  # Expecting a string like "((x_start, x_end), (y_start, y_end))"
                zoom_x_start, zoom_x_end = zoom_coords[0]-zoom_coords[2], zoom_coords[0]+zoom_coords[2]
                zoom_y_start, zoom_y_end = zoom_coords[1]-zoom_coords[2], zoom_coords[1]+zoom_coords[2]

            time.sleep(0.1)  # wait for the camera to acquire some data
            ret=mgr.Camera.wait_for_acquisition_timeout(timeout_seconds=1)
            mgr.Pulses.set_state_off()
            _, number_images_acquired = mgr.Camera.get_total_number_images_acquired() 
            data_dic={}
            if single_picture:
                ret, data, _, _ = mgr.Camera.get_images_16(1, 1, 1024**2)
                temp_image=self.img_1D_to_2D(data,x_len,y_len)
                
                if zoom:
                    temp_image = temp_image[zoom_y_start:zoom_y_end, zoom_x_start:zoom_x_end]
                data_dic[f'latest_image'] = temp_image
            else:
                for i in range(number_images_acquired):

                    ret, data, _, _ = mgr.Camera.get_images_16(i, i, 1024**2)
                    temp_image=self.img_1D_to_2D(data,x_len,y_len)
                    
                    if zoom:
                        temp_image = temp_image[zoom_y_start:zoom_y_end, zoom_x_start:zoom_x_end]
                    data_dic[f'image_{i}'] = temp_image
                data_dic['latest']=temp_image


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

    


