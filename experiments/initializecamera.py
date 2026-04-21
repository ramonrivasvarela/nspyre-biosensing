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

class CameraInitialization:
    """Camera initialization experiments."""

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
        _logger.info('Created Camera Initialization instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Camera Initialization instance.')

    def initialize_camera(self, optimize_gain: bool = True, 
                          cam_trigger: str = 'EXTERNAL_EXPOSURE', 
                          ns_probe_time: float = 1e8,
                          ns_exp_time: float = 1e8, 
                          ns_readout_time: float = 0.05e9, 
                          ns_laser_lag: float = 0.02e9, 
                          gain: int = 1, 
                          mode: str = 'AM',
                          runs: int = 1):
        """
        Initialize the camera and optionally optimize gain.

        Args:
            optimize_gain: If True, optimize the camera gain.
        """
        with InstrumentManager() as mgr:
            ret = mgr.Camera.initialize()  # Initialize camera
            print("Function Initialize returned {}".format(ret)) #returns 20002 if successful
            ret, _ = mgr.Camera.get_status()
            if ret != 20002:
                print('Camera initialization failed, ending process...')
                return
            #Can probably get rid of 'ret' but not important...
            mgr.Camera.set_acquisition_mode("Kinetics") #Taking a series of pulses
            mgr.Camera.set_read_mode("Image") #reading pixel-by-pixel with no binning
            '''
            For some reason if you move SetTriggerMode to a later line the camera seems to go to internal or something?
            '''
    
            ns_collect_time = ns_exp_time+ns_readout_time

            if cam_trigger == 'EXTERNAL_EXPOSURE':
                mgr.Camera.set_trigger_mode("External Exposure (Bulb)") #Pulse  length controls exposure
                if ns_laser_lag < ns_readout_time+10000000:
                    print('laser lag must be larger than readout_time + 10 ms for camera initialization.')
                    return
                elif ns_laser_lag > ns_readout_time + 1.5 * ns_exp_time:
                    print('risk of over-exposing during initialization! laser lag too high.')
                    return
            else:
                '''
                exposure min is 46.611 ms. The set exposure time is done in excess of this s.t. exp_time = 0 corresponds to 46.611 ms exposure.
                The pulse streamer will trigger the camera by sending pulses of 10ms, and the rest of the exposure time plus any set readout time will be 
                sent to the pulse streamer as readout time
                '''
                mgr.Camera.set_trigger_mode("External") #Pulse  length controls exposure
                exposure_min = 0.046611e9*1e9
                if ns_exp_time < exposure_min:
                    print(f'exposure must be at least {exposure_min*1000} ms.')
                elif ns_exp_time + ns_readout_time < 80000000:
                    print('May experience failure from exposure + readout < 80 ms due to pulses being missed.')
                mgr.Camera.set_exposure_time(ns_exp_time*1e-9) 
                #### ps-ended stuff
                mgr.Camera.set_frame_transfer_mode("ON") #frame transfer mode
                print('frame transfer mode on')

            if ns_readout_time<5000000:
                print('WARNING readout time should be at least 5 ms even with frame transfer, experiment may fail ')
            if ns_collect_time >= ns_probe_time:
                print('WARNING probe time cannot be less than or equal to collect time!')


            (ret, xpixels, ypixels) = mgr.Camera.get_detector()
            mgr.Camera.set_image()

            mgr.Camera.set_emccdgain(gain) #setting Electron Multiplier Gain
            mgr.Camera.set_number_accumulations(int((ns_probe_time - (ns_probe_time%ns_collect_time)) / ns_collect_time)) #more explanation
            mgr.Camera.set_number_kinetics(runs * 2 + 1)
            mgr.Camera.set_shutter("Open") #Open Shutter


            mgr.Camera.set_emccdgain(gain) 
            if(optimize_gain):

                print('optimizing gain...')
                
                mx = 0
                safety_counter = 0
                while(mx<=2.0e4 or mx>=2.9e4) and safety_counter < 15:
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        print("Ending process due to stop command from GUI.")
                        return
                    safety_counter += 1
                    mgr.Camera.start_acquisition()
                    ret, _ = mgr.Camera.get_status()
                    if not ret == 20002:
                        print('Starting Acquisition Failed, ending process... status code:', ret)
                        return
                    #print('Starting Acquisition', ret)
                    time.sleep(0.1) #Give time to start acquisition
                    ## make sure the sg frequency is set! (overhead of <1ms)
                    mgr.Pulser.pulse_for_widefield(runs, mode, mgr.Camera.trigger_mode, ns_exp_time, ns_readout_time, AM_mode = True, switch_mode = True)
                    timeout_counter = 0
                    while(mgr.Camera.get_total_number_images_acquired()[1]<2 and timeout_counter<=2000): #20 second hard-coded limit!
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            print("Ending process due to stop command from GUI.")
                            return
                        time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                        timeout_counter+=1 
                    ret, all_data, _, _ = mgr.Camera.get_images_16(2,2,1024**2) #cut out first image here
                    #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
                    temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
                    mx = np.max(temp_image)
                    print(f'gain of {gain}, mx is {mx}')
                    if(mx<=1.0e4):
                        print('signal really low, raising gain +3')
                        gain+=3
                    elif mx<=2.0e4:
                        print('raising gain +1')
                        gain+=1
                    elif mx>=3.2e4:
                        print(f'Warning, risk of saturation! Max pixel value {mx} detected')
                        gain-=5
                    elif mx>=2.9e4: 
                        print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
                        gain-=2
                    if gain <= 0:
                        gain = 1
                    mgr.Camera.set_emccdgain(gain)#setting Electron Multiplier Gain
                    mgr.Camera.prepare_acquisition()
                    if gain>=150:
                        print('Warning! Gain too high! Re-adjust experiment parameters, or turn off optimize_gain, or edit the limit in the spyrelet code. Aborting...')
                        return
                    time.sleep(0.6)
                gain_string = f'optimum gain determined to be {gain}, giving max pixel value of roughly {mx}'
                print(gain_string)
            else:
                gain = gain
                print('Initial capture to counteract camera dynamics...')
                mx = 0
                mgr.Camera.start_acquisition()
                ret, _ = mgr.Camera.get_status()
                if not ret == 20002:
                    print('Starting Acquisition Failed, ending process... status code:', ret)
                    return
                time.sleep(0.1) #Give time to start acquisition
                ## make sure the sg frequency is set! (overhead of <1ms)
                mgr.Pulser.pulse_for_widefield(runs, mode, mgr.Camera.trigger_mode, ns_exp_time, ns_readout_time, AM_mode = True, switch_mode = True) 
                timeout_counter = 0
                while(mgr.Camera.get_total_number_images_acquired()[1]<2 and timeout_counter<=400): #20 second hard-coded limit!
                    time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                    timeout_counter+=1 
                ret, all_data, _, _ = mgr.Camera.get_images_16(2,2,1024**2) #cut out first image here
                #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
                temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
                mx = np.max(temp_image)
                if(mx<=1.0e4):
                    print(mx, 'signal really low')
                elif mx<=2.0e4:
                    print(mx, 'signal low')
                elif mx>=2.7e4: 
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
                print(f'gain of {gain}, mx is {mx}')
                gain_string = f'gain was set to {gain}, giving max pixel value of roughly {mx}'
                print(gain_string)
            return gain 

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)

        return arr.reshape((y_len, x_len))