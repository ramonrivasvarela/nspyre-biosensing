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
from nidaqmx.constants import Edge, CountDirection
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

    def confocal_counts_time(self, dataset: str, n_points: int, probe_time: float, clock_time: float):
        """
        confocal counts vs time experiment that is static (does not track), under constant illumination.

        Args:
            dataset: name of the dataset to push data to
            time_per_point: time in seconds t
            
        """
        ## Set up experiment parameters
        self.n_points = n_points
        self.probe_time = probe_time
        self.clock_time = clock_time

        # connect to the instrument server
        # connect to the data server and create a data set, or connect to an
        # existing one with the same name if it was created earlier.
        APD_counts = StreamingList()
        with InstrumentManager() as mgr, DataSource(dataset) as counts_data:
            self.initialize(mgr)
            start_t = time.time()
            while True:
                ## Start, Stream, Read. Data will be in the buffer.
                ctrs_start = self.read_task.read()
                time.sleep(self.probe_time)
                ctrs_end = self.read_task.read()
                dctrs = ctrs_end - ctrs_start
                ctrs_rate = dctrs / self.probe_time

                APD_counts.append(np.array([np.array([time.time()-start_t]),np.array([ctrs_rate])]))
                # TODO: experiment with making the above line of code less disgusting. Depends on how particular NSpyre is about having np.arrays.
                APD_counts.updated_item(-1)

                counts_data.push({'params': {'n_points': n_points, 'probe_time': probe_time, 'clock_time': clock_time},
                                'title': 'Counts vs Time (Confocal)',
                                'xlabel': 'Time (s)',
                                'ylabel': 'Counts (/s)',
                                'datasets': {'counts' : APD_counts,
                                            }
                })


                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr)
                    return

    #### INITIALIZATION METHODS

    def initialize(self, mgr):
        """Initialize the experiment."""
        mgr.XYZcontrol.finalize()  # Ensure XYZ control is finalized before starting the experiment
        mgr.Pulser.set_state([7],0.0,0.0)
        dev_channel = 'Dev1/ctr1'
        self.read_task = nidaqmx.Task()
        self.read_task.ci_channels.add_ci_count_edges_chan(
                                dev_channel,
                                edge=Edge.RISING,
                                initial_count=0,
                                count_direction=CountDirection.COUNT_UP
        )

        
        self.read_task.start()
        self.read_task.read()

    def create_sequence(self, mgr):
        seq = mgr.Pulser.create_sequence()
        clock_pulse = [(self.clock_time,1),(self.probe_time-self.clock_time,0)] ##ensure clock_time in nanoseconds
        clock = clock_pulse * (self.n_points+1)
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        return seq

    #### EXPERIMENTAL LOOP METHODS

    def buffer_to_data(self):
        """ Convert the buffer to data. Not particularly interesting here, but more relevant for more complex experiments."""
        if self.buffer is None:
            raise ValueError("Buffer is not initialized.")
        # Convert the buffer to a numpy array
        all_data = self.buffer[1:] - self.buffer[0:-1]
        data = np.sum(all_data)/ (self.probe_time * self.n_points)  #counts per second
        return data

    #### FINALIZATION METHODS

    def finalize(self, mgr):
        """Finalize the experiment."""
        mgr.Pulser.set_state_off()
        self.read_task.stop()
        self.read_task.close()
        mgr.XYZcontrol.initialize()






if __name__ == '__main__':
    print('Hello World')