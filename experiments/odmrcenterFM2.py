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

    def main(self, runs, initial_odmr, odmr_span, sweep_time, PID, probe_time, clock_time, laser_pause, timeout_counter, rf_amplitude, mode, drift, xy_pid, z_pid, dataset):
        params={'runs':runs, 
                'initial_odmr':initial_odmr, 
                'odmr_span':odmr_span, 
                'sweep_time':sweep_time, 
                'PID':PID, 
                'probe_time':probe_time, 
                'clock_time':clock_time, 
                'laser_pause':laser_pause, 
                'timeout_counter':timeout_counter, 
                'rf_amplitude':rf_amplitude,
                'mode':mode,
                'dataset':dataset}
        kp, ki, kd=eval(PID)

        drift=eval(drift)
        xy_pid=eval(xy_pid)
        z_pid=eval(z_pid)
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            counter=0
            odmr_freq=initial_odmr
            self.initialize(mgr, runs, odmr_span, sweep_time, probe_time, clock_time, laser_pause, mode, rf_amplitude)
            current_pos=mgr.DAQcontrol.position
            x=current_pos['x']
            y=current_pos['y']
            z=current_pos['z']
            pos=[x, y, z]
            count_array=np.zeros(8)
            x_counts_error_last=0
            y_counts_error_last=0
            z_counts_error_last=0
            x_counts_sum=0
            y_counts_sum=0
            z_counts_sum=0
            left_background_t=0
            left_signal_t=0
            right_background_t=0
            right_signal_t=0

            mgr.sg.set_frequency(odmr_freq)
            while counter<timeout_counter:
                
                if counter%8<4:
                    pos[0]=x+drift[0]/2
                else:
                    pos[0]=x-drift[0]/2
                if counter%4<2:
                    pos[1]=y+drift[1]/2
                else:
                    pos[1]=y-drift[1]/2
                if counter%2<1:
                    pos[2]=z+drift[2]/2
                else:
                    pos[2]=z-drift[2]/2
                mgr.DAQcontrol.move({'x':pos[0],'y':pos[1],'z':pos[2]})
                mgr.DAQcontrol.start_counter()
                mgr.Pulser.stream_sequence(self.sequence, runs)
                data = rpyc.utils.classic.obtain(mgr.DAQcontrol.read_to_data_array())

                
                left_background, left_signal, right_background, right_signal = self.process_data(runs, data)
                count_array[counter%8]=left_background+right_background

                left_background_t+=left_background
                left_signal_t+=left_signal
                right_background_t+=right_background
                right_signal_t+=right_signal
                 # Update search value based on adjustment magnitude
                
                
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return self.finalize(mgr)
                if counter!=0 and counter%8==0:
                    x_counts_up=np.sum(count_array[:4])
                    x_counts_down=np.sum(count_array[4:])
                    x_counts_diff=(x_counts_up - x_counts_down)/(x_counts_up + x_counts_down)
                    x_change, x_counts_error_last, x_counts_sum=self.xyz_pid(xy_pid, x_counts_diff, x_counts_error_last, x_counts_sum)
                    x+=x_change
                    y_counts_up=count_array[0]+count_array[1]+count_array[4]+count_array[5]
                    y_counts_down=count_array[2]+count_array[3]+count_array[6]+count_array[7]
                    y_counts_diff=(y_counts_up - y_counts_down)/(y_counts_up + y_counts_down)
                    y_change, y_counts_error_last, y_counts_sum=self.xyz_pid(xy_pid, y_counts_diff, y_counts_error_last, y_counts_sum) 
                    y+=y_change
                    z_counts_up=count_array[::2]
                    z_counts_down=count_array[1::2]
                    z_counts_diff=(np.sum(z_counts_up) - np.sum(z_counts_down))/(np.sum(z_counts_up) + np.sum(z_counts_down))
                    z_change, z_counts_error_last, z_counts_sum=self.xyz_pid(z_pid, z_counts_diff, z_counts_error_last, z_counts_sum)
                    z+=z_change

                    left_contrast=(left_background_t-left_signal_t)/left_background_t
                    right_contrast=(right_background_t-right_signal_t)/right_background_t
                    left_background_t=0
                    left_signal_t=0
                    right_background_t=0
                    right_signal_t=0
                    print(f"Left contrast: {left_contrast}, Right contrast: {right_contrast}")
                    
                    # PID control to adjust ODMR frequency
                    frequency_adjustment = self.pid_control(left_contrast, right_contrast, kp, ki, kd)
                    odmr_freq += frequency_adjustment
                    mgr.sg.set_frequency(odmr_freq)
                    print(f"Frequency adjustment: {frequency_adjustment:.6f} Hz, New ODMR freq: {odmr_freq:.6f} Hz")
                    ds.push({'params': params,
                            'left_contrast': left_contrast,
                            'right_contrast': right_contrast,
                            'odmr_freq': odmr_freq
                    })
                counter+=1
            return self.finalize(mgr)

    def initialize(self, mgr, runs,odmr_span, sweep_time, probe_time, clock_time, laser_pause, mode, rf_amplitude):
        # n_points=int(sweep_time/probe_time)
        # odmr_span=int(odmr_span/probe_time)*probe_time
        # sg_span=(odmr_span/sweep_time)*(sweep_time+laser_pause)
        

        self.sequence=self.create_sequence(mgr, odmr_span,sweep_time, clock_time, probe_time, laser_pause)
        import pickle, os
        print(f'saving sequence to seq.pkl in {os.getcwd()}')
        pickle.dump(self.sequence, open('seq.pkl', 'wb'))
        mgr.DAQcontrol.create_counter()
        print("buffer size:", (2*self.n_points+2)*runs)
        mgr.DAQcontrol.prepare_counting(2/probe_time, (2*self.n_points+2)*runs-1)
        print(len(mgr.DAQcontrol.ctr_buffer))

        # SG settings: 
        mgr.sg.set_rf_amplitude(rf_amplitude) 
        mgr.sg.set_mod_toggle(True)
        if mode == 'QAM':
            mgr.sg.set_mod_type('QAM')
            mgr.sg.set_mod_function('QAM', 'external')
        elif mode == 'AM' or mode == 'NoMod':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_mod_function('AM', 'external')
            mgr.sg.set_AM_mod_depth(100)
        mgr.sg.set_rf_toggle(True)

        return
    
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

    def finalize(self, mgr):
        # Reset PID variables
        self.previous_error = 0
        self.integral = 0
        mgr.DAQcontrol.finalize_counter()
        return

    def create_sequence(self, mgr, odmr_span,sweep_time, clock_time, probe_time, laser_pause):
        clock_time_ns=int(clock_time*1e9)
        IQleft=[0.355, 0.348]
        IQright=[0.357, 0.350]
        # Ensure probe_time_ns is a multiple of 8
        number_bins=(int(probe_time*1e9) + 4) // 8
        probe_time_ns = (number_bins) * 8
        self.n_points=int(sweep_time//(probe_time_ns*1e-9))
        print('type n_points', type(self.n_points), self.n_points)
        print('type n_bins', type(number_bins), number_bins)
        sweep_time_ns=probe_time_ns*self.n_points
        f_values=np.linspace(0, odmr_span*1e-9, self.n_points*number_bins)
        laser_pause_ns=int(laser_pause*1e9)
        
        clock_pulse = [(clock_time_ns,1),(probe_time_ns-clock_time_ns,0)] ##ensure clock_time in nanoseconds
        laser=4*[(sweep_time_ns+clock_time_ns,1), (laser_pause_ns,0)]
        clock =4*(clock_pulse * (self.n_points)+[(clock_time_ns, 1), (laser_pause_ns,0)])
        switch=2*[(sweep_time_ns+clock_time_ns, 1), (laser_pause_ns,0), (sweep_time_ns+clock_time_ns, 0), (laser_pause_ns,0)]
        i_left=[]
        i_right=[]
        q_left=[]
        q_right=[]
        phi=0
        for f in f_values:
            phi+=2*np.pi*f*8
            i_left.append((8, IQleft[1]*np.cos(phi)))
            i_right.append((8, IQright[1]*np.cos(phi)))
            q_left.append((8, -IQleft[0]*np.sin(phi)))
            q_right.append((8, IQright[0]*np.sin(phi)))
        i=[(laser_pause_ns+clock_time_ns+sweep_time_ns,IQleft[1])]+i_left+[(2*laser_pause_ns+2*clock_time_ns+sweep_time_ns,IQright[1])]+i_right+[(laser_pause_ns+clock_time_ns,IQright[1])]
        q=[(laser_pause_ns+clock_time_ns+sweep_time_ns,0)]+q_left+[(2*laser_pause_ns+2*clock_time_ns+sweep_time_ns,0)]+q_right+[(laser_pause_ns+clock_time_ns,0)]
        print('clock', clock)
        print('laser', laser)
        print('switch', switch)
        print('i', i)
        print('q', q)
        seq = mgr.Pulser.create_sequence()
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        seq.setDigital(mgr.Pulser.channel_dict['laser'], laser)
        seq.setDigital(mgr.Pulser.channel_dict['switch'], switch)
        seq.setAnalog(mgr.Pulser.channel_dict['I'], i)
        seq.setAnalog(mgr.Pulser.channel_dict['Q'], q)
        return seq
    
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
    
    def xyz_pid(self, pid, error, last, sum):
        kp, ki, kd=pid
        proportional=kp*error
        sum+=error
        integral=ki*sum
        derivative=kd*(error - last)
        output=proportional+integral+derivative
        last=error
        return output, last, sum
