#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import datetime as Dt
import numpy as np
from scipy import optimize

from rpyc.utils.classic import obtain

from experiments.spatialfb import SpatialFeedback
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class PulsedODMR():

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
        _logger.info('Created PulsedODMR instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed PulsedODMR instance.')

    def pulesed_ODMR(self,
        dataset: str = 'pulsed_odmr',
        n_points: int = 10000
        sweeps: int = 100,
        mode: str = 'sweep', # what the heck does this do
        frequencies: str = '(2.8e9, 2.94e9, 49)',
        rf_amplitude: float = -20,
        pi_time: float = 5e-6,
        probe_time: float = 3.5e-6,
        readout_time: float = 4e-6,
        wait_buffer_time: float = 800e-6,
        singlet_decay: float = 6e-6,
        clock_duration: float = 10e-9,
        timeout: int = 300,
        aom_lag: float = 0.026e-6,
        buffer_time: float = 0.1e-6,
        feedback: bool = False,
        dozfb: bool = True,
        sweeps_till_fb: int = 10,
        xyz_step: float = 60e-9,
        count_step_shrink: int = 2,
        starting_point: str = 'current position (ignore input)',
        verbose: bool = True # from confocal_odmr.py, not yet sure what for
    ):

