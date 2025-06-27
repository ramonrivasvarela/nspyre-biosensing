
import numpy as np
import time
import pickle


def get_gain(mgr, camera, optimize_gain, gain, frequency, seqs, AM_mode, switch_mode):
    if(optimize_gain):

        print('optimizing gain...')
        mx = 0
        while(mx<=2.0e4 or mx>=2.9e4):
            camera.start_acquisition()
            ret = camera.get_status()
            if not ret == 1:
                print('Starting Acquisition Failed, ending process...')
                return
            #print('Starting Acquisition', ret)
            time.sleep(0.1) #Give time to start acquisition
            mgr.sg.set_frequency(frequency[0]) ## make sure the sg frequency is set! (overhead of <1ms)
            mgr.Pulser.stream_umOFF(seqs[0], 1, AM = AM_mode, SWITCH = switch_mode) #0 since only one seq in my seq array.
            timeout_counter = 0
            while(camera.get_total_number_images_aquired()[1]<2 and timeout_counter<=2000): #20 second hard-coded limit!
                time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                timeout_counter+=1 
            (ret, all_data, validfirst, validlast) = camera.sdk.GetImages16(2,2,1024**2) #cut out first image here
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
            camera.set_gain(gain)#setting Electron Multiplier Gain
            camera.prepare_acquisition()
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
        camera.start_acquisition()
        ret = camera.get_status()
        if not ret == 1:
            print('Starting Acquisition Failed, ending process...')
            return
        time.sleep(0.1) #Give time to start acquisition
        mgr.sg.set_frequency(frequency[0]) ## make sure the sg frequency is set! (overhead of <1ms)
        mgr.Pulser.stream_umOFF(seqs[0], 1,AM = AM_mode, SWITCH = switch_mode) 
        timeout_counter = 0
        while(camera.get_total_number_images_aquired()[1]<2 and timeout_counter<=400): #20 second hard-coded limit!
            time.sleep(0.05)#Might want to base wait time on pulse streamer signal
            timeout_counter+=1 
        (ret, all_data, validfirst, validlast) = camera.sdk.GetImages16(2,2,1024**2) #cut out first image here
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
    img = np.zeros((x_len,y_len), dtype='int')
    for j in range(y_len):
        img[j,:] = img_1D[x_len*j:x_len*(j+1)] #np arrays count down first, then horizontally. That is, my image is saved as an array of rows, not an array of columns
    return img

def analyze(self,loc,first_sig,sweep,count):
    bg = 0
    sig = 0
    rng = range(1,self.runs*2+1)
    for i in rng: #cut buffer data into individual image arrays: [ [img], [img], ...]
        temp_image = img_1D_to_2D(self.all_data[i*1024**2:(i+1)*1024**2],1024,1024)
        if(self.save_image):
            with open(self.data_path+f'\\Full_s{sweep + 1}_f{count}_{i-1}.pkl', 'wb') as file: #saving for each nanodiamond. That's not good
                pickle.dump(temp_image, file)
        mx = np.max(temp_image)
        # if mx>=2.7e4:
        #     print(f'Warning, risk of saturation! Max pixel value {mx} detected')
        # else:
        #     print(mx)  
        #### LOCATION ######################################################################################################
        px_x = loc[0]
        px_y = loc[1]
        ROI_rad = loc[2]
        r_targ = loc[3]
        ROI = temp_image[px_y-ROI_rad:px_y+ROI_rad,px_x-ROI_rad:px_x+ROI_rad]

        if i==1: #no need to really do it more than once within a run. If in a cell and it moves on that timescale, then can change later via boolean param
            px_max = np.argmax(ROI)
            temp_y = int(px_max/(ROI_rad*2)) + px_y - ROI_rad
            temp_x = px_max%(ROI_rad*2) + px_x - ROI_rad
            threshold_change = 10 #4?
            if (not first_sig and (np.abs(px_x-temp_x) + np.abs(px_y-temp_y) > threshold_change)): 
                print('Warning! Sudden discontinuity detected!') #don't want to suddenly jump to another bright spot in the image. If this keeps up, need to re-run ODMR
            else:
                px_y = temp_y
                px_x = temp_x
                loc = (px_x,px_y,ROI_rad,r_targ)
                # print((self.mx_x,self.mx_y))
        ROI = temp_image[px_y-r_targ:px_y+r_targ,px_x-r_targ:px_x+r_targ]
        #####################################################################################################################
        if i%2==0: #dark: offset by one due to initial throwaway pulse
            bg += sum(sum(ROI))
        else: #bright
            sig += sum(sum(ROI))
    return sig, bg, loc

