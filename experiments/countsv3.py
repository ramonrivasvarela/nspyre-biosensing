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
        with InstrumentManager() as mgr, DataSource(dataset) as counts_data:  # +1 to account for signal being a difference of counts
            self.initialize(mgr)
            seq = self.create_sequence(mgr)
            start_t = time.time()
            while True:
                ## Start, Stream, Read. Data will be in the buffer.
                # mgr.Pulser.stream_sequence(seq)
                self.start_stream_read(mgr, seq, timeout=100)
                data = self.buffer_to_data(mgr)


                APD_counts.append(np.array([np.array([time.time()-start_t]),np.array([data])]))
                # TODO: experiment with making the above line of code less disgusting. Depends on how particular NSpyre is about having np.arrays.
                APD_counts.updated_item(-1)
                print("Running well.")

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
        mgr.Pulser.set_state([7],0.0,0.0)
         # +1 to account for signal being a difference of counts
        mgr.DAQCounter.intialize(self.n_points+1)  # +1 to account for signal being a difference of counts
        mgr.DAQ



    def create_sequence(self, mgr):
        seq = mgr.Pulser.create_sequence()
        clock_pulse = [(self.clock_time,1),(self.probe_time-self.clock_time,0)] ##ensure clock_time in nanoseconds
        clock = clock_pulse * (self.n_points+1)
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        return seq

    #### EXPERIMENTAL LOOP METHODS

    def buffer_to_data(self, mgr):
        """ Convert the buffer to data. Not particularly interesting here, but more relevant for more complex experiments."""
        if mgr.DAQCounter.buffer is None:
            raise ValueError("Buffer is not initialized.")
        # Convert the buffer to a numpy array
        all_data = mgr.DAQCounter.buffer[1:] - mgr.DAQCounter.buffer[0:-1]
        data = np.sum(all_data)/ (self.probe_time * self.n_points)  #counts per second
        return data

    #### FINALIZATION METHODS

    def finalize(self, mgr):
        """Finalize the experiment."""
        mgr.Pulser.set_state_off()
        mgr.XYZcontrol.end_task()

    def start_stream_read(self, mgr, sequence, timeout = 10):
        """
        start, stream, and read from a single method by passing in the pulse streamer and all of its arguments.
        pulses: PulseStreamer instance
        sequence: Sequence object to stream
        n_runs: number of runs to stream, to pass to the PulseStreamer
        timeout: timeout for reading samples
        """
        # if mgr.DAQCounter.buffer is None:
        #     raise RuntimeError("Buffer not created. Call create_buffer() before starting the stream read.")

        if mgr.DAQCounter.buffer is None:
            mgr.DAQCounter.create_buffer(self.n_points+1)  # +1 to account for signal being a difference of counts

        if mgr.DAQCounter.read_task is not None:
            mgr.DAQCounter.read_task.start()

        mgr.Pulser.stream_sequence(sequence)

        num_samps = mgr.DAQCounter.reader.read_many_sample_uint32(
            mgr.DAQCounter.buffer,
            number_of_samples_per_channel= mgr.DAQCounter.n_samples,
            timeout= timeout
        )

        if num_samps < mgr.DAQCounter.n_samples:
            raise RuntimeError('Something went wrong: buffer issue, not enough samples read.')
        mgr.DAQCounter.read_task.stop() 
        return 






if __name__ == '__main__':
    print('Hello World')