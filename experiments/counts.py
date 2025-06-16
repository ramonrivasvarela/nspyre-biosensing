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
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class CountsTime:
    """counts vs time experiments."""

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
        _logger.info('Created CountsTime instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed CountsTime instance.')

    def confocal_counts_time(self, dataset: str, time_per_point: float):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            device: name of the APD device for connecting
            channel: name of the APD channel for connecting
            time_per_point: time in seconds t
            
        """
        # connect to the instrument server
        # connect to the data server and create a data set, or connect to an
        # existing one with the same name if it was created earlier.
        APD_counts = StreamingList()
        with InstrumentManager() as mgr, DataSource(dataset) as counts_data: 
            self.initialize(mgr)

            start_t = time.time()
            while True:
                val = mgr.DAQCounter.read(time_per_point)

                APD_counts.append(np.array([np.array([time.time()-start_t]),np.array([val])]))
                # TODO: experiment with making the above line of code less disgusting. Depends on how particular NSpyre is.
                APD_counts.updated_item(-1)

                counts_data.push({'params': {'time_per_point': time_per_point,},
                                'title': 'Counts vs Time (Confocal)',
                                'xlabel': 'Time (s)',
                                'ylabel': 'Counts',
                                'datasets': {'counts' : APD_counts,
                                            }
                })


                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr)
                    return



    def initialize(self, mgr):
        """Initialize the experiment."""
        mgr.Pulser.constant(([7],0.0,0.0))
        mgr.DAQCounter.initialize()
    
    def finalize(self, mgr):
        """Finalize the experiment."""
        mgr.Pulser.set_state_off()
        mgr.DAQCounter.finalize()






if __name__ == '__main__':
    print('Hello World')