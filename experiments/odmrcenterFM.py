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
import rpyc.utils.classic
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)



class ODMRCenter:
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
        # PID variables
        self.previous_error = 0
        self.integral = 0

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
        _logger.info('Created Experiment instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Experiment instance.')

    def main(self, runs, n_steps, initial_odmr, odmr_span, sweep_time, PID, probe_time, clock_time, laser_pause, timeout_counter, rf_amplitude,  dataset):
        params={'runs':runs, 
                'n_steps':n_steps,
                'initial_odmr':initial_odmr, 
                'odmr_span':odmr_span, 
                'sweep_time':sweep_time, 
                'PID':PID, 
                'probe_time':probe_time, 
                'clock_time':clock_time, 
                'laser_pause':laser_pause, 
                'timeout_counter':timeout_counter, 
                'rf_amplitude':rf_amplitude,
                'dataset':dataset}
        kp, ki, kd=eval(PID)
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            counter=0
            left_bg_sweeps=StreamingList()
            right_bg_sweeps=StreamingList()
            left_sg_sweeps=StreamingList()
            right_sg_sweeps=StreamingList()

            odmr_freq=initial_odmr
            mgr.sg.set_frequency(odmr_freq)
            self.initialize(mgr, runs, n_steps, odmr_span, sweep_time, probe_time, clock_time, laser_pause, rf_amplitude)
            while counter<timeout_counter:
                
                

                counter+=1
                
                mgr.DAQcontrol.start_counter()
                time.sleep(0.01)  # Small delay after starting
                mgr.Pulser.stream_sequence(self.sequence, runs)
                # mgr.Pulser.set_state_off()
                # data = rpyc.utils.classic.obtain(mgr.DAQcontrol.read_to_data_array())

                try:
                    left_background_r, left_signal_r, right_background_r, right_signal_r = rpyc.utils.classic.obtain(mgr.DAQcontrol.odmr_center_read_process_data(n_steps, runs, timeout=self.reader_timeout))
                except Exception as e:
                    print("Error during data acquisition or processing:", e)
                    print(mgr.DAQcontrol.ctr_buffer)
                    self.finalize(mgr)
                    return
                #Ramon: IMPORTANT: convert to float to avoid overflow issues
                print('len(left_background_r):', len(left_background_r))
                left_bg_sweeps.append(np.stack([np.linspace(0, -1, n_steps), left_background_r]))
                left_bg_sweeps.updated_item(-1)
                right_bg_sweeps.append(np.stack([np.linspace(0, 1, n_steps), right_background_r]))
                right_bg_sweeps.updated_item(-1)
                left_sg_sweeps.append(np.stack([np.linspace(0, -1, n_steps), left_signal_r]))
                left_sg_sweeps.updated_item(-1)
                right_sg_sweeps.append(np.stack([np.linspace(0, 1, n_steps), right_signal_r]))
                right_sg_sweeps.updated_item(-1)
                left_background=float(np.sum(left_background_r))
                left_signal=float(np.sum(left_signal_r))
                right_background=float(np.sum(right_background_r))
                right_signal=float(np.sum(right_signal_r))
                print(f"Left background: {left_background}, Left signal: {left_signal}, Right background: {right_background}, Right signal: {right_signal}")
                left_contrast=(left_background-left_signal)/left_background
                right_contrast=(right_background-right_signal)/right_background
                print(f"Left contrast: {left_contrast}, Right contrast: {right_contrast}")
                
                # PID control to adjust ODMR frequency
                frequency_adjustment = self.pid_control(left_contrast, right_contrast, kp, ki, kd)
                odmr_freq += frequency_adjustment
                search = abs(frequency_adjustment)  # Update search value based on adjustment magnitude
                
                print(f"Frequency adjustment: {frequency_adjustment:.6f} Hz, New ODMR freq: {odmr_freq:.6f} Hz")
                ds.push({'params': params,
                         'datasets':{
                            'left_sg': left_sg_sweeps,
                            'left_bg': left_bg_sweeps,
                            'right_bg': right_bg_sweeps,
                            'right_sg': right_sg_sweeps,
                         },
                         'odmr_freq': odmr_freq
                })
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return self.finalize(mgr)
            return self.finalize(mgr)

    def initialize(self, mgr, runs,n_steps, odmr_span, sweep_time, probe_time, clock_time, laser_pause,  rf_amplitude):
        # n_points=int(sweep_time/probe_time)
        # odmr_span=int(odmr_span/probe_time)*probe_time
        # sg_span=(odmr_span/sweep_time)*(sweep_time+laser_pause)
        
        print("Creating sequence")
        self.sequence, probe_time_ns=mgr.Pulser.odmr_center_create_sequence_FM(n_steps, runs, clock_time, probe_time)
        import pickle, os
        print(f'saving sequence to seq.pkl in {os.getcwd()}')
        pickle.dump(self.sequence, open('seq.pkl', 'wb'))
        print("sequence created")
        # import pickle, os
        # print(f'saving sequence to seq.pkl in {os.getcwd()}')
        # pickle.dump(self.sequence, open('seq.pkl', 'wb'))
        new_probe_time=probe_time_ns*1e-9
        self.reader_timeout=new_probe_time* (4*n_steps*runs+1)*1.5
        mgr.DAQcontrol.create_counter()
        print("buffer size:", (4*n_steps*runs+1))
        print("new probe time:", new_probe_time)
        mgr.DAQcontrol.prepare_counting(2/new_probe_time, (4*n_steps*runs+1)-1)
        print(len(mgr.DAQcontrol.ctr_buffer))

        # SG settings: 
         
        mgr.sg.set_mod_toggle(True)
        mgr.sg.set_rf_amplitude(rf_amplitude)
        mgr.sg.set_mod_type('FM')
        mgr.sg.set_mod_function('FM', 'external')
        
        
        mgr.sg.set_FM_mod_dev(odmr_span)
        mgr.sg.set_rf_toggle(True)
        return
    
    def finalize(self, mgr):
        # Reset PID variables
        self.previous_error = 0
        self.integral = 0
        mgr.DAQcontrol.finalize_counter()
        mgr.sg.set_mod_toggle(False)
        mgr.sg.set_rf_toggle(False)
        return

    
    def pid_control(self, left_contrast, right_contrast, kp, ki, kd):
        """
        PID controller to determine frequency adjustment based on contrast difference.
        Target is to make left_contrast == right_contrast.
        """
        error = left_contrast - right_contrast
        
        # Proportional term
        proportional = kp * error
        
        # Integral term
        self.integral += error
        integral_term = ki * self.integral
        
        # Derivative term
        derivative = kd * (error - self.previous_error)
        
        # PID output
        output = proportional + integral_term + derivative
        
        # Update previous error for next iteration
        self.previous_error = error
        
        return output

### These functions are not executed in the experiment directly but in their respective drivers: 

    def process_data(self, runs, data):
        # Reshape data to separate runs

        points_per_run = 4 * self.n_points + 4  # (n_points+1) background + n_points signal
        data_reshaped = data.reshape(runs, points_per_run)
        # Separate background and signal for each run
        background_left_raw = data_reshaped[:, :self.n_points+1]  # First n_points+1 are background
        signal_left_raw = data_reshaped[:, self.n_points+1:2*self.n_points+2]  # Next n_points are signal
        background_right_raw = data_reshaped[:, 2*self.n_points+2:3*self.n_points+3]  # Next n_points are background
        signal_right_raw = data_reshaped[:, 3*self.n_points+3:4*self.n_points+4]  # Next n_points are signal

        # Apply buffer_to_data logic to each row and sum the differences
        background_left = np.average([np.sum(np.diff(row)) for row in background_left_raw])
        signal_left = np.average([np.sum(np.diff(row)) for row in signal_left_raw])
        background_right = np.average([np.sum(np.diff(row)) for row in background_right_raw])
        signal_right = np.average([np.sum(np.diff(row)) for row in signal_right_raw])
        return background_left, signal_left, background_right, signal_right


    def create_sequence(self, mgr, n_steps, odmr_span,sweep_time, clock_time, probe_time, laser_pause):
        DT_NS = max(8, int(sweep_time*1e9 // (n_steps)))
        
        print("DT_NS:", DT_NS)

        clock_time_ns = int(round(clock_time * 1e9))
        IQleft  = [0.355, 0.348]
        IQright = [0.357, 0.350]

        # probe_time rounded to a multiple of 8 ns
        number_bins   = max(1, int(round((probe_time * 1e9) / DT_NS)))

        probe_time_ns = number_bins * DT_NS
        self.probe_time=probe_time_ns*1e-9

        # total points
        n_points = int(sweep_time // (probe_time_ns * 1e-9))
        # sweep_time_ns = n_steps * DT_NS
        sweep_time_ns = probe_time_ns *n_points
        n_steps=int(sweep_time_ns//DT_NS)
        # n_points = sweep_time_ns // probe_time_ns

        # frequency values (GHz if odmr_span is in Hz; GHz*ns is unitless for phase)
        q_values_up = np.linspace(0, 1, n_steps, dtype=np.float64)
        q_values_down = np.linspace(0, -1, n_steps, dtype=np.float64)
        laser_pause_ns = int(round(laser_pause * 1e9))
        if laser_pause_ns < (probe_time_ns - clock_time_ns):
            # keep the warning but avoid printing in performance-critical paths if not needed
            print("Warning: laser pause time is less than probe_time - clock_time. "
                "Setting laser pause time to probe_time - clock_time")
            laser_pause_ns = probe_time_ns - clock_time_ns

        # ----- digital channels (lightweight list multiplications are fine) -----
        clock_pulse = [(clock_time_ns, 1), (probe_time_ns - clock_time_ns, 0)]  # one probe block
        laser = 4 * [(sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0)]
        clock = 4 * (clock_pulse * n_points + [(clock_time_ns, 1), (laser_pause_ns, 0)])
        switch = 2 * [
            (sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0),
            (sweep_time_ns + clock_time_ns, 0), (laser_pause_ns, 0)
        ]

        # ----- analog channels (vectorised) -----
        # Phase accumulates: phi_k = sum_{j<=k} 2π * f_j * DT_NS
        

        q_seq_up=[(DT_NS, q) for q in q_values_up]
        q_seq_down=[(DT_NS, q) for q in q_values_down]
        q_seq = [(sweep_time_ns+clock_time_ns+laser_pause_ns, 0)]+q_seq_up +[(clock_time_ns, 1), (2*laser_pause_ns+sweep_time_ns+clock_time_ns, 0)]+ q_seq_down+ [(clock_time_ns, -1), (laser_pause_ns, 0)]
        print('q=', q_seq)
        print('clock=', clock)
        print('laser=', laser)
        print('switch=', switch)
        # ----- build sequence -----
        seq = self.create_sequence()
        seq.setDigital(self.channel_dict['clock'], clock)
        seq.setDigital(self.channel_dict['laser'], laser)
        # seq.setDigital(self.channel_dict['switch'], switch)
        # seq.setAnalog(0, q_seq)

        return seq, n_points
