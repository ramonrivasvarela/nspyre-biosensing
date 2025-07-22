
import numpy as np
import time
import pickle


def get_gain(mgr, optimize_gain, gain, frequency, runs, mode, ns_exp_time, ns_readout_time):
    ret=mgr.Camera.get_status()
    if not ret==20002:
        print('Camera not initialized, ending process...')
        return
    if mgr.Camera.number_kinetics<=1:
        mgr.Camera.set_number_kinetics(2) #set to 2 to get a dark and bright image
    mgr.Camera.set_emccdgain(gain) 
    if(optimize_gain):

        print('optimizing gain...')
        
        mx = 0
        while(mx<=2.0e4 or mx>=2.9e4):
            mgr.Camera.start_acquisition()
            ret = mgr.Camera.get_status()
            if not ret == 1:
                print('Starting Acquisition Failed, ending process...')
                return
            #print('Starting Acquisition', ret)
            time.sleep(0.1) #Give time to start acquisition
            mgr.sg.set_frequency(frequency[0]) ## make sure the sg frequency is set! (overhead of <1ms)
            mgr.Pulser.pulse_for_widefield(runs, mode, mgr.Camera.trigger_mode, ns_exp_time, ns_readout_time, AM_mode = True, switch_mode = True)
            timeout_counter = 0
            while(mgr.Camera.get_total_number_images_aquired()[1]<2 and timeout_counter<=2000): #20 second hard-coded limit!
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1 
            ret, all_data, _, _ = mgr.Camera.get_images_16(2,2,1024**2) #cut out first image here
            #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
            temp_image = img_1D_to_2D(all_data[:1024**2],1024,1024) 
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
        ret = mgr.Camera.get_status()
        if not ret == 1:
            print('Starting Acquisition Failed, ending process...')
            return
        time.sleep(0.1) #Give time to start acquisition
        mgr.sg.set_frequency(frequency[0]) ## make sure the sg frequency is set! (overhead of <1ms)
        mgr.Pulser.pulse_for_widefield(runs, mode, mgr.Camera.trigger_mode, ns_exp_time, ns_readout_time, AM_mode = True, switch_mode = True) 
        timeout_counter = 0
        while(mgr.Camera.get_total_number_images_aquired()[1]<2 and timeout_counter<=400): #20 second hard-coded limit!
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1 
        ret, all_data, _, _ = mgr.Camera.get_images_16(2,2,1024**2) #cut out first image here
        #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
        temp_image = img_1D_to_2D(all_data[:1024**2],1024,1024) 
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
