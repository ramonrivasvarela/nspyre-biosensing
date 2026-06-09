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



    def autofocus(self, coordinates: str='(512, 512, 16)', dataset: str='picture'):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """
        with InstrumentManager() as mgr, DataSource(dataset) as picture_data:  # +1 to account for signal being a difference of counts
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return
            mgr.Camera.start_acquisition()
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:  # 20002 means "Camera is currently acquiring data"
                print("Camera is not acquiring data. Check camera status.")
                return

            coords = eval(coordinates)  # Expecting a string like "((x_start, x_end), (y_start, y_end))"
            z_pos=mgr.DAQcontrol.position['z']
            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
            # the GUI has asked us nicely to exit
                return
            







    


