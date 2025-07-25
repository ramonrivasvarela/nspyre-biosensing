"""
experiment to determine counts, iterated through time.

Written by David Ovetsky
Written on 6/12/2025

"""

#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import time
import numpy as np
import nidaqmx
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

    def take_picture(self, picture: str):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """
        with InstrumentManager() as mgr, DataSource(picture) as picture_data:  # +1 to account for signal being a difference of counts
            ret, state=mgr.Camera.get_status()
            if ret != 20002:
                raise RuntimeError(f"Camera not ready, status code: {ret}")


            elif state==20072:
                mgr.Camera.abort_acquisition()
            _, width, height=mgr.Camera.get_detector()  # Get the detector size
            mgr.Camera.set_image()
            mgr.Pulser.stream([(1000000000, [3])])
            time.sleep(0.1)  # Give time to start acquisition
            mgr.Camera.start_acquisition()
            ret, _ = mgr.Camera.get_status()
            print(f"Start Acquisition returned {ret}")
            if not ret == 20002:
                print('Starting Acquisition Failed, ending process...')
                return
            #print('Starting Acquisition', ret)
            time.sleep(0.1) #Give time to start acquisition
            #mgr.Pulser.stream_umOFF([3], 1) 
            if mgr.Camera.trigger_mode != "internal":
                mgr.Pulser.stream([(1000000000, [3])])  # Start the pulser to trigger the camera
                mgr.Pulser.stream([(100000000, [1]), (1000000000, [3])])
            timeout_counter = 0
            while(mgr.Camera.get_total_number_images_acquired()[1]<mgr.Camera.number_kinetics and timeout_counter<=100): #20 second hard-coded limit!
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1
            mgr.Camera.abort_acquisition()
            ret, data, _, _ = mgr.Camera.get_images_16(1,1,1024**2) #cut out first image here
            #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
            # temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
            temp_image = self.img_1D_to_2D(data, 1024, 1024)
            # TODO: experiment with making the above line of code less disgusting. Depends on how particular NSpyre is about having np.arrays.
            
            print("Running well.")
            print(temp_image)
            print(temp_image.shape)
            temp_image=np.asarray(temp_image)
            print(type(temp_image))
            print(type(temp_image[0]))

            picture_data.push({
                            'title': 'Picture',
                            'xlabel': 'Pixels',
                            'ylabel': 'Pixels',
                            'xs': np.asarray(range(width)),
                            'ys': np.asarray(range(height)),
                            'datasets': {'picture' : temp_image,
                                        }
            })


            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                # the GUI has asked us nicely to exit

                return


    #### INITIALIZATION METHODS

 

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))

    #### FINALIZATION METHODS

    





if __name__ == '__main__':
    print('Hello World')