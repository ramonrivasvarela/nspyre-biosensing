# std
import numpy as np
import time
import logging
from math import ceil
from nspyre import InstrumentManager, StreamingList, DataSource
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader

# Other Spyrelets to Use
from experiments.spatialfb import SpatialFeedback

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class MultiBlast(SpatialFeedback):
    """
    A class for moving to several locations and blasting using a controlled power (%) for a specified
    duration (s). The locations are specified in a list of tuples, where each tuple contains the x, and y
    coordinates of the location to blast. 
    """
    ## STANDARD DEFINITIONS #############################################################

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
        _logger.info('Created SpatialFeedback instance.')
    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed SpatialFeedback instance.')

    ## MAIN EXPERIMENT METHOD ##########################################################

    def multi_blast(self, locations, blast_power, duration, feedback, do_z, xyz_step, 
                    shrink_every_x_iter, probe_time, n_points,  total_fb_time, verbose, dataset):
        """
        Move to several locations and blast using a controlled power (%) for a specified duration (s).
        The locations are specified in a list of tuples, where each tuple contains the x, and y
        coordinates of the location to blast. 

        Args:
            locations: A list of tuples containing the x and y coordinates of the locations to blast.
              If None, blasts at the current location.
            power: The power (%) to use for blasting.
            duration: The duration (s) to blast at each location.
            feedback: Whether to use feedback during blasting.
            feedback_cap: The maximum number of feedback iterations to perform.
            do_z: Whether to perform z feedback during blasting.
            xyz_step: The step size (um) for xyz feedback.
            shrink_every_x_iter: How often to shrink the step size during feedback.
            starting_point: The starting point for feedback ('default' or 'current').
            probe_time: The time (s) to probe at each location before blasting.
            initial_position: The initial position (x,y,z) to move to before starting the experiment.
            n_points: The number of points for feedback at a different location
            total_fb_time: The total time (s) to perform feedback before blasting (default 0.0).
        """
        params={'locations': locations,
                    'blast_power': blast_power,
                    'duration': duration,
                    'feedback': feedback,
                    'do_z':do_z,
                    'xyz_step':xyz_step,
                    'shrink_every_x_iter': shrink_every_x_iter,
                    'probe_time':probe_time,
                    'n_points': n_points,
                    'total_fb_time': total_fb_time,
                    'verbose': verbose
                    }
        self.verbose = verbose
        
        X_pos=StreamingList()
        Y_pos=StreamingList()
        Z_pos=StreamingList()
        fluorescence=StreamingList()
        

        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            base_power = mgr.DLnsec.get_power()
            _logger.info(f"Base power: {base_power}%")
            locations = eval(locations)
            cur_loc = mgr.DAQcontrol.get_position()
            if locations is None or len(locations) == 0:
                locations = [(cur_loc['x'], cur_loc['y'])]
            self.initialize(mgr, n_points=n_points, probe_time=probe_time, duration=duration)
            super().data_update(X_pos, Y_pos, Z_pos, fluorescence, 0, mgr.DAQcontrol.get_position(), 0, params, ds) # Add (0,0) to create a break 
            for i,loc in enumerate(locations):
                x, y = loc
                print(f"\nMoving to location {i+1}/{len(locations)}: ({x}, {y})") # DEBUG
                mgr.DAQcontrol.move({'x': x, 'y': y, 'z': mgr.DAQcontrol.get_position()['z']})
                print(f"Current position: {mgr.DAQcontrol.get_position()}") # DEBUG
                if feedback:
                    _logger.info(f"Performing feedback at location ({x}, {y})...")
                    quit_exp = super().spatial_feedback_integrated(X_pos, Y_pos, Z_pos, fluorescence, mgr, ds, do_z=do_z, xyz_step=xyz_step, shrink_every_x_iter=shrink_every_x_iter, probe_time=probe_time, n_points=n_points, total_fb_time=total_fb_time)
                    if quit_exp: return
                    super().data_update(X_pos, Y_pos, Z_pos, fluorescence, 0, mgr.DAQcontrol.get_position(), 0, params, ds) # Add (0,0) to create a break for processing
                else:
                    _logger.info(f"Skipping feedback at location ({x}, {y})... Running quick probe instead.")
                    fluorData = self.read(mgr, self.pulse_sequence, probe_time * n_points)
                    super().data_update(X_pos, Y_pos, Z_pos, fluorescence, 0, mgr.DAQcontrol.get_position(), fluorData, params, ds) # Add (0,fluorData) 
                _logger.info(f"Blasting at location ({x}, {y}) with power {blast_power}% for {duration}s...")
                mgr.DLnsec.set_power(blast_power)
                mgr.Pulser.stream_sequence(self.blast_seq)
                t_start_wait = time.time()
                while time.time() - t_start_wait < duration:
                    time.sleep(1)
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        # the GUI has asked us nicely to exit
                        mgr.DLnsec.set_power(base_power) 
                        self.finalize(mgr)
                        return
                mgr.DLnsec.set_power(base_power) 
                print(f"final position {i+1}/{len(locations)}: ", mgr.DAQcontrol.get_position())
            self.finalize(mgr)
            return


    ## INITIALIZATION AND FINALIZATION
    def initialize(self, mgr, n_points, probe_time, duration):
        #Define self.init_position, self.pulse_sequence
        super().initialize(mgr, "", "current", False, n_points, probe_time)
        self.blast_seq = mgr.Pulser.laser_blast(duration*1e9)  # Convert duration from seconds to nanoseconds

    def finalize(self, mgr): 
        super().finalize(mgr, False)

    

    

