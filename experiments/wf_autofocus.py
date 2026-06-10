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
from nspyre.misc.pint import Q_
import numpy as np
from experiments.picture import Pictures
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class WFAutofocus(Pictures):
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



    def autofocus(self, coordinates: str='[512, 512, 16]', dataset: str='picture'):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """
        with InstrumentManager() as mgr:  # +1 to account for signal being a difference of counts
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return
            mgr.Camera.start_acquisition()
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return

            self.coords = eval(coordinates)  # Expecting a string like "((x_start, x_end), (y_start, y_end))"
            radius=self.coords[2]
            z_pos=mgr.DAQcontrol.position['z']
            img=self.take_picture(zoom=True, zoom_coordinates=self.coords, picture=dataset, single_picture=True)
            x_line, y_line, max_index_x, max_index_y = self.focus_data_process(img, radius)
            print(f'ND center: ({self.coords[0]}, {self.coords[1]})')
            for i in range(30):
                img = self.take_picture(zoom=True, zoom_coordinates=self.coords, picture=dataset, single_picture=True)

                x_line, y_line, _, _ = self.focus_data_process(img, radius)
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
                mgr.DAQcontrol.move({'z': z_pos})

                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                # the GUI has asked us nicely to exit
                    return
            
    # ==== HELPER FUNCTION ==============

    def focus_data_process(self, img, r):
        y_sum = np.sum(img, axis=0)
        x_sum = np.sum(img, axis=1)
        max_y, max_x = np.unravel_index(np.argmax(img), img.shape)
        self.coords[1]=+max_y-r
        self.coords[0]=+max_x-r
        if max_x >0 :
            if max_x< len(x_sum)-1:
                x_line = np.sum(x_sum[max_x-1:max_x+2] )
            else: 
                x_line = np.sum(x_sum[max_x-2:max_x+1] )
        else:
            x_line = np.sum(x_sum[max_x:max_x+3] )
        if max_y >0 :
            if max_y< len(y_sum)-1:
                y_line = np.sum(y_sum[max_y-1:max_y+2] )
            else:
                y_line = np.sum(y_sum[max_y-2:max_y+1] )
        else:
            y_line = np.sum(y_sum[max_y:max_y+3])
        return x_line, y_line, max_x, max_y







    


