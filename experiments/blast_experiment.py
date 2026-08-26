#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import pickle, os
import numpy as np
import time


from experiments.spatialfb import SpatialFeedback
from experiments.confocalODMR import ConfocalODMR
from experiments.i1i2 import I1I2
from nspyre import DataSink
from nspyre.data.save import save_json

####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)


class BlastExperiment():

    """
    We run two windows: one with our MW on and the other with the MW off.
    We read the start of these 50us windows, and we do this 10,000 times. So,
    we have a time per point of 1s.
    We set a timeout for the general sample clock, 
    we can repeat x sweeps every y minutes per z repetitions.
    We sweep our microwave window over frequencies, generally 30 steps.
    Note: probe_time is the laser_on_per_window,
    rf_amplitude is the signal generator's power,
    clockpulse_duration sets the width of the pulse that clocks eery 50ns.
        set it to 10ns or so.
    """
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
        _logger.info('Created BlastExperiment instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed BlastExperiment instance.')

    def blast_experiment(
            self,
            feedback_params_path: str = None,
            I1I2_params_path: str = None,
            ODMR_params_path: str = None,
            autosave_folder: str = None, # The general experiment folder (ex. ...\data\260812\ND1)
            autosave_labels: str = "['baseline']", # The labels for the specific experiment (ex. ['baseline']) which is then saved into subfolders 'baseline', 'baseline_1', for each iter. 
            iters: int = 3, # The number of times to repeat the experiment
            first_fb: str = 'skip', # Whether to run the first feedback ('skip', 'run', 'special')
            rf_override: int = -18,
            laser_base_power: int = 2,
            laser_blast_power: int = 100,
            duration: float = 2.0, # The duration (s) to blast at each location.
            final_duration: float = 2.0, # The duration (s) to blast for the final blast at each location. Set to duration by default, but can be set to a different value for the final blast.
    ):
        '''
        An experiment for performing in sequence a spatial feedback, an I1I2 measurement, and a confocal ODMR measurement. Will save data according to set structure, and print key values along the way.
        '''
        try:
            ## DEBUG VARS
            do_verbose_override = False
            ## VARS
            self.time_start = time.time()
            self.log = []
            self.FEEDBACK_SAVE_NAME = 'feedback'
            self.I1I2_SAVE_NAME = 'I1I2'
            self.ODMR_SAVE_NAME = 'ODMR'

            self.autosave_labels = eval(autosave_labels)

            self.fluorescence_estimate = None
            self.estimate_threshold = 0.1 # The threshold for determining if the fluorescence has changed significantly
            self.z_estimate = None
            self.z_kick = 1 # The amount to kick the z position
            ## LOAD PARAMS & OVERRIDE
            with open(feedback_params_path, 'rb') as f:
                feedback_params = pickle.load(f)
            with open(I1I2_params_path, 'rb') as f:
                I1I2_params = pickle.load(f)
            with open(ODMR_params_path, 'rb') as f:
                ODMR_params = pickle.load(f)
            I1I2_params['rf_amplitude'] = rf_override
            ODMR_params['rf_amplitude'] = rf_override
            if do_verbose_override:
                feedback_params['verbose'] = True
                ODMR_params['verbose'] = True
            # TODO Can make more efficient by streamlining initialize, defining versions of confocal and I1I2 that don't standalone. 
            ## BEGIN EXPERIMENT
            # TODO  increased control over ODMR

            self.params = {
                    'feedback_params_path': feedback_params_path,
                    'I1I2_params_path': I1I2_params_path,
                    'ODMR_params_path': ODMR_params_path,
                    'autosave_folder': autosave_folder,
                    'autosave_labels': autosave_labels,
                    'iters': iters,
                    'first_fb': first_fb,
                    'rf_override': rf_override,
                    'laser_base_power': laser_base_power,
                    'laser_blast_power': laser_blast_power,
                    'duration': duration,
                    'final_duration': final_duration #overrides the duration for the final blast.
                    }

            for j,autosave_label in enumerate(self.autosave_labels):
                self.print_log(f'\n Starting experiment with label: {autosave_label} ({time.time() - self.time_start:.2f}s) \n')
                for i in range(iters):
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        # the GUI has asked us nicely to exit
                        raise SystemExit("stop")
                    self.print_log(f'\n Iteration {i+1} of {iters} ({time.time() - self.time_start:.2f}s) \n')
                    autosave_path = os.path.join(autosave_folder, autosave_label)
                    if iters > 1:
                        autosave_path = os.path.join(autosave_folder, f'{autosave_label}_{i+1}')
                    # Check if folder exists, if it does, append a number to the end of the folder name to avoid overwriting previous data
                    if os.path.exists(autosave_path):
                        count = 1
                        new_autosave_path = autosave_path + f'_{count}'
                        while os.path.exists(new_autosave_path):
                            count += 1
                            new_autosave_path = autosave_path + f'_{count}'
                        autosave_path = new_autosave_path
                    os.makedirs(autosave_path, exist_ok=True)
                    if i == 0:
                        if first_fb == 'run':
                            data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override)
                            self.fluorescence_estimate, self.z_estimate = self.analyze_fluor(data)
                            self.print_log(f"\n Current estimates: Fluorescence = {self.fluorescence_estimate}, Z = {self.z_estimate} \n")
                        elif j!= 0:
                            data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override)
                            f_final, z_final = self.analyze_fluor(data)
                            if f_final < self.fluorescence_estimate * (1 - self.estimate_threshold):
                                self.print_log(f"\n WARNING: Fluorescence decreased to {(self.fluorescence_estimate - f_final)/self.fluorescence_estimate * 100:.2f}% from previous label. \n")
                            self.print_log(f"\n Current estimates: Fluorescence = {self.fluorescence_estimate}, Z = {self.z_estimate} \n")
                        elif first_fb == 'special':
                            data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override, save = False)
                            f_final, z_final = self.analyze_fluor(data)
                            self.fluorescence_estimate = f_final
                            self.z_estimate = z_final
                            count = 0
                            max_iterations = 3
                            while count < max_iterations:
                                count += 1
                                self.print_log(f"\n Current estimates: Fluorescence = {self.fluorescence_estimate}, Z = {self.z_estimate} \n")
                                with InstrumentManager() as mgr:
                                    mgr.DAQcontrol.move({'x': mgr.DAQcontrol.get_position()['x'], 'y': mgr.DAQcontrol.get_position()['y'], 'z': mgr.DAQcontrol.get_position()['z'] + self.z_kick})
                                data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override, save = False)
                                f_final, z_final = self.analyze_fluor(data)
                                if z_final < self.z_estimate + self.z_kick * (1-self.estimate_threshold) and f_final >= self.fluorescence_estimate * (1 - self.estimate_threshold):
                                    self.print_log("Case: Fluorescence within threshold, not increased by kicking z. Proceeding.")
                                    break
                                elif z_final >= self.z_estimate + self.z_kick * (1-self.estimate_threshold) and f_final >= self.fluorescence_estimate * (1 - self.estimate_threshold):
                                    self.print_log("Case: Fluorescence within threshold, increased by kicking z. Updating estimates and kicking again.")
                                    self.fluorescence_estimate = f_final
                                    self.z_estimate = z_final
                                elif f_final < self.fluorescence_estimate * (1 - self.estimate_threshold):
                                    self.print_log("Case: Fluorescence decreased by kicking z. Reverting to previous estimates and proceeding.")
                                    with InstrumentManager() as mgr:
                                        mgr.DAQcontrol.move({'x': mgr.DAQcontrol.get_position()['x'], 'y': mgr.DAQcontrol.get_position()['y'], 'z': self.z_estimate})
                                    break
                            self.print_log(f"\n Final estimates: Fluorescence = {self.fluorescence_estimate}, Z = {self.z_estimate} \n")
                            data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override)
                            self.fluorescence_estimate, self.z_estimate = self.analyze_fluor(data)
                        self.run_I1I2(I1I2_params, autosave_path=autosave_path, verbose=do_verbose_override)
                        self.run_ODMR(ODMR_params, autosave_path=autosave_path, verbose=do_verbose_override)
                    else:
                        autosave_path = os.path.join(autosave_folder, f'{autosave_label}_{i+1}')
                        data = self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override)
                        self.fluorescence_estimate, self.z_estimate = self.analyze_fluor(data)
                        self.print_log(f"\n Current estimates: Fluorescence = {self.fluorescence_estimate}, Z = {self.z_estimate} \n")
                        self.run_I1I2(I1I2_params, autosave_path=autosave_path, verbose=do_verbose_override)
                self.print_log(f'\n Finished all iterations for label: {autosave_label}. Pre-blast localization... \n')
                autosave_path = os.path.join(autosave_folder, f'{autosave_label}_preblast')
                os.makedirs(autosave_path, exist_ok=True)
                self.run_feedback(feedback_params, autosave_path=autosave_path, verbose=do_verbose_override)
                if j < len(self.autosave_labels) - 2: # not last blast:
                    self.print_log(f'\n Finished all iterations for label: {autosave_label}. Blasting {duration} s @ {laser_blast_power} mW... ({time.time() - self.time_start:.2f}s)\n')
                    self.run_blast(laser_base_power, laser_blast_power, duration, verbose=do_verbose_override)
                elif (j == len(self.autosave_labels) - 2): # last blast
                    self.print_log(f'\n Finished all iterations for label: {autosave_label}. Beginning final blast: Blasting {final_duration} s @ {laser_blast_power} mW... ({time.time() - self.time_start:.2f}s)\n')
                    self.run_blast(laser_base_power, laser_blast_power, final_duration, verbose=do_verbose_override)
                self.print_log(f'Finished blast ({time.time() - self.time_start:.2f}s)')

            self.print_log('\n Blast Experiment Complete \n')   
        except SystemExit as e:
            self.finalize()
            return str(e)
        except Exception as e:
            self.finalize()
            raise e
        else:
            self.finalize()
            return 'end'
        
        
    def run_feedback(self, feedback_params: dict, autosave_path: str = None, verbose: bool = False, save: bool = True, label_override: str = None):
        """
        Run the spatial feedback experiment and save the data.

        Args:
            feedback_params: A dictionary containing the parameters for the spatial feedback experiment.
            autosave_path: The path where the data will be saved.
            verbose: Whether to print verbose output.
            save: Whether to save the data.
            label_override: The label to use for the saved data.
        """
        if label_override is None:
            label_override = self.FEEDBACK_SAVE_NAME
        self.print_log(f'\n Running Spatial Feedback... ({time.time() - self.time_start:.2f}s) \n')
        if verbose:
            print(f"Feedback params: {feedback_params}")  # DEBUG
        res = SpatialFeedback(queue_to_exp=self.queue_to_exp, queue_from_exp=self.queue_from_exp).spatial_feedback(**feedback_params)
        ## Autosave Feedback:
        if save:
            print('\n Saving Spatial Feedback... \n')
        dataset = feedback_params['dataset']
        filename = os.path.join(autosave_path, f'{label_override}.json')
        with DataSink(dataset) as sink:
            # get the data from the dataserver
            sink.pop(timeout=10)
            if save:
                save_json(filename, sink.data)
            data = sink.data['datasets'] # can also get params via 'params'
        if experiment_widget_process_queue(self.queue_to_exp) == 'stop' or res == 'stop':
            # the GUI has asked us nicely to exit
            raise SystemExit("stop")
        return data  # Return the data for further processing if needed

    def run_I1I2(self, I1I2_params: dict, autosave_path: str = None, verbose: bool = False, label_override: str = None):
        """
        Run the I1I2 experiment and save the data.

        Args:
            I1I2_params: A dictionary containing the parameters for the I1I2 experiment.
            autosave_path: The path where the data will be saved.
        """
        if label_override is None:
            label_override = self.I1I2_SAVE_NAME
        self.print_log(f'\n Running I1I2... ({time.time() - self.time_start:.2f}s) \n')
        if verbose:
            print(f"I1I2 params: {I1I2_params}")  # DEBUG
        res = I1I2(queue_to_exp=self.queue_to_exp, queue_from_exp=self.queue_from_exp).i1i2(**I1I2_params)
        ## Autosave I1I2:
        print('\n Saving I1I2... \n')
        dataset = I1I2_params['dataset']
        filename = os.path.join(autosave_path, f'{label_override}.json')
        with DataSink(dataset) as sink:
            # get the data from the dataserver
            sink.pop(timeout=10)
            save_json(filename, sink.data)
        if experiment_widget_process_queue(self.queue_to_exp) == 'stop' or res == 'stop':
            # the GUI has asked us nicely to exit
            raise SystemExit("stop")

    def run_ODMR(self, ODMR_params: dict, autosave_path: str = None, verbose: bool = False, label_override: str = None):
        """
        Run the confocal ODMR experiment and save the data.

        Args:
            ODMR_params: A dictionary containing the parameters for the confocal ODMR experiment.
            autosave_path: The path where the data will be saved.
        """
        if label_override is None:
            label_override = self.ODMR_SAVE_NAME
        self.print_log(f'\n Running Confocal ODMR... ({time.time() - self.time_start:.2f}s) \n')
        if verbose:
            print(f"ODMR params: {ODMR_params}")  # DEBUG
        res = ConfocalODMR(queue_to_exp=self.queue_to_exp, queue_from_exp=self.queue_from_exp).confocal_odmr(**ODMR_params)
        ## Autosave ODMR:
        print('\n Saving Confocal ODMR... \n')
        dataset = ODMR_params['dataset']
        filename = os.path.join(autosave_path, f'{label_override}.json')
        with DataSink(dataset) as sink:
            # get the data from the dataserver
            sink.pop(timeout=10)
            save_json(filename, sink.data)
        if experiment_widget_process_queue(self.queue_to_exp) == 'stop' or res == 'stop':
            # the GUI has asked us nicely to exit
            raise SystemExit("stop")
        
    def run_blast(self, laser_base_power: int, laser_blast_power: int, duration: float, verbose: bool = False):
        with InstrumentManager() as mgr:
            self.blast_seq = mgr.Pulser.laser_blast(duration*1e9)  # Convert duration from seconds to nanoseconds
            mgr.DLnsec.set_power(laser_blast_power)
            mgr.Pulser.stream_sequence(self.blast_seq)
            t_start_wait = time.time()
            while time.time() - t_start_wait < duration:
                time.sleep(1)
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    mgr.DLnsec.set_power(laser_base_power) 
                    raise SystemExit("stop")
            mgr.DLnsec.set_power(laser_base_power)
            

    def analyze_fluor(self, data):
        fluor_data = data['total_fluor'] # list of pairs [t, fluor]
        fluor = np.array(fluor_data)[:,1] # extract the fluorescence values
        z_data = data['z_pos'] # list of pairs [t, [z]]
        z = np.array(z_data)[:,1] # extract the z values
        f_final = np.mean(fluor[-5:])  # Average of the last 5 points
        z_final = z[0]  # Last point
        return f_final, z_final

    def print_log(self, message: str):
        """Print a message to the log and the console."""
        self.log.append(message)
        print(message)

    def finalize(self):
        self.print_log(f'\n Finalizing Blast Experiment... ({time.time() - self.time_start:.2f}s) \n')
        autosave_folder = self.params['autosave_folder']
        params_path = os.path.join(autosave_folder, 'blast_experiment_params.pkl')
        log_path = os.path.join(autosave_folder, 'blast_experiment_log.txt')
        counter = 1
        while os.path.exists(params_path) or os.path.exists(log_path):
            # If the files already exist, try to rename with a counter to avoid overwriting
            params_path = os.path.join(autosave_folder, f'blast_experiment_params_{counter}.pkl')
            log_path = os.path.join(autosave_folder, f'blast_experiment_log_{counter}.txt')
            counter += 1
        with open(params_path, 'wb') as f:
            pickle.dump(self.params, f)
        with open(log_path, 'w') as f:
            for message in self.log:
                f.write(message + '\n')
        return




















