from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
import time
import numpy as np
import pickle
import ctypes
import ctypes

class Camera():
    def __init__(self):
        self.sdk=atmcd("")
        self.errors=atmcd_errors
        self.exposure_time=0.075
        self.trigger_mode="Internal"
        
        self.temperature=20
        self.emccdgain=1
        self.shutter="Auto"
        self.cooler_on=False
        self.temperature_goal=18

        self.read_mode="Image"
        self.frame_transfer_mode="Conventional"
        self.acquisition_mode="Kinetics"
        self.number_accumulations=1
        self.number_kinetics=1

        

    def initialize(self):
        ret=self.sdk.Initialize("")
        if ret==self.errors.Error_Codes.DRV_SUCCESS:
            print("Camera is initalized.")
            return True

        else:
            print("Camera is not initialized.")
            print(f"Error code: {ret}")
            return False
        
        

    def check_Error_Codes(self, code, function_name="Function"):
        if code==self.errors.Error_Codes.DRV_SUCCESS:
            return f"{function_name} succeeded."
        elif code==self.errors.Error_Codes.DRV_NOT_INITIALIZED:
            raise RuntimeError(f"{function_name} failed. Camera is not initialized. Error code: {code}.")
        elif code==self.errors.Error_Codes.DRV_ACQUIRING:
            raise RuntimeError(f"{function_name} failed. Camera is currently acquiring. Error code: {code}.")
        elif code==self.errors.Error_Codes.DRV_ERROR_ACK:
            raise RuntimeError(f"{function_name} failed. Unable to communicate with card. Error code: {code}.")
        else:
            raise RuntimeError(f"{function_name} failed due to other error. Error code: {code}. Consult function in https://andor.oxinst.com/downloads/uploads/Software%20Development%20Kit.pdf .")

    def set_trigger_mode(self, trigger_mode:str):
        if trigger_mode=="Internal":
            ret=self.sdk.SetTriggerMode(0)
            if ret==20002:
                self.trigger_mode="Internal"
                print("Trigger mode set to Internal.")
            return ret
        elif trigger_mode=="External":
            ret=self.sdk.SetTriggerMode(1)
            if ret==20002:
                self.trigger_mode="External"
                print("Trigger mode set to External.")
            return ret
        elif trigger_mode=="External Exposure Bulb":
            ret=self.sdk.SetTriggerMode(6)
            if ret==20002:
                self.trigger_mode="External Exposure Bulb"
                print("Trigger mode set to External Exposure Bulb.")
            return ret
        else:
            raise ValueError("Trigger mode must be set to 'Internal', 'External', or 'External Exposure Bulb'.")

    def set_temperature(self, temp_value:int):
        ret=self.sdk.SetTemperature(temp_value)
        if ret==20002:
            self.temperature_goal=temp_value
        return ret

    def cool(self):
        ret=self.sdk.CoolerON()
        return ret
    
    def stop_cooling(self):
        ret=self.sdk.CoolerOFF()
        return ret

    def get_temperature_status(self):
        err, temp = self.sdk.GetTemperatureF()
        return err, temp

 

    def start_acquisition(self):
        ret=self.sdk.StartAcquisition()
        return ret
        
    def prepare_acquisition(self):
        ret=self.sdk.PrepareAcquisition()
        return ret
    
    def get_total_number_images_acquired(self):
        # Call the SDK; wrapper gives (ret_code, total_images)
        ret, total = self.sdk.GetTotalNumberImagesAcquired()

        if ret == self.errors.Error_Codes.DRV_SUCCESS:
            return ret, total
        else:
            # Surface the driver error for easier debugging
            raise RuntimeError(f"GetTotalNumberImagesAcquired failed (code {ret})")

    def set_emccdgain(self, gain:int):
        ret=self.sdk.SetEMCCDGain(gain)
        if ret==20002:
            self.emccdgain=gain
        return ret

    def get_emccdgain(self):
        ret, gain = self.sdk.GetEMCCDGain()
        if ret == self.errors.Error_Codes.DRV_SUCCESS:
            self.emccdgain = gain
            return ret, gain



    def get_status(self):

        # Call GetStatus; this will return DRV_NOT_INITIALIZED if Initialize() was never called
        ret, state = self.sdk.GetStatus()

        return ret

    def cool_old(self, temp_value):
        ret = self.set_temperature(temp_value)
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            raise RuntimeError(f"SetTemperature({temp_value}) failed (code {ret})")
        else:
            self.temperature_goal = temp_value
        print(f"SetTemperature returned {ret}, target = {temp_value}°C")


        ret = self.sdk.CoolerON()
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            raise RuntimeError(f"CoolerON() failed (code {ret})")
        print("CoolerON returned DRV_SUCCESS; waiting for stabilization…")


        # while True:
        #     status, current = self.get_temperature_status()  # returns (status_code, temperature)
        #     if status == self.errors.Error_Codes.DRV_TEMP_STABILIZED:
        #         print(f"\nTemperature stabilized at {current}°C.")
        #         break

        #     # still on the way to set-point
        #     print(f"\rStatus={status}; current={current}°C", end="")
        #     time.sleep(5)
        return ret

    def set_exposure_time(self, exp_time:float):
        ret=self.sdk.SetExposureTime(exp_time)
        if ret==20002:
            self.exposure_time=exp_time
            print(f"Exposure time set to {exp_time} seconds.")

    def get_images_16(self, first, last, size):
        ret, all_data, validfirst, validlast=self.sdk.GetImages16(first, last, size)
        self.check_Error_Codes
        return ret, all_data, validfirst, validlast

    def shutdown(self):
        ret=self.sdk.ShutDown()

    def set_shutter(self, mode:str):
        if mode=="Auto":
            ret=self.sdk.SetShutter(0, 0, 27, 27)
            self.shutter="Auto"
        elif mode=="Open":
            ret=self.sdk.SetShutter(0, 1, 27, 27)
            self.shutter="Open"
        elif mode=="Closed":
            ret=self.sdk.SetShutter(0, 2, 27, 27)
            self.shutter="Closed"
        return ret
    
    def is_cooler_on(self):
        """
        Check if the cooler is on.
        """
        ret, status = self.sdk.IsCoolerOn()
        return status
    
    def cooler_on(self):
        """
        Turn the cooler on.
        """
        ret = self.sdk.CoolerON()
        return ret

    def cooler_off(self):
        """
        Turn the cooler off.
        """
        ret = self.sdk.CoolerOFF()
        return ret
    
    def get_total_number_images_acquired(self):
        """
        Get the total number of images acquired.
        """
        ret, total = self.sdk.GetTotalNumberImagesAcquired()
        return ret, total

    def set_read_mode(self, mode:str):
        """
        Set the read mode of the camera.
        """
        if mode=="Full Vertical Binning":
            ret=self.sdk.SetReadMode(0)
        elif mode=="Multi-Track":
            ret=self.sdk.SetReadMode(1)
        elif mode=="Random-Track":
            ret=self.sdk.SetReadMode(2)
        elif mode=="Single-Track":
            ret=self.sdk.SetReadMode(3)
        elif mode=="Image":
            ret=self.sdk.SetReadMode(4)
        try:
            if ret==20002:
                self.read_mode = mode
                print(f"Read mode set to {mode}.")
                return ret
        except Exception as e:
            print(f"Error setting read mode: {e}")
    
    def set_frame_transfer_mode(self, mode:str):
        """
        Set the frame transfer mode of the camera.
        """
        if mode=="Frame Transfer":
            ret=self.sdk.SetFrameTransferMode(0)
        elif mode=="Conventional":
            ret=self.sdk.SetFrameTransferMode(1)
        try:
            if ret==20002:
                self.frame_transfer_mode = mode
                print(f"Frame transfer mode set to {mode}.")
                return ret
        except Exception as e:
            print(f"Error setting frame transfer mode: {e}")

    def set_acquisition_mode(self, mode:str):
        """
        Set the acquisition mode of the camera.
        """
        if mode=="Single Scan":
            ret=self.sdk.SetAcquisitionMode(1)
        elif mode=="Accumulate":
            ret=self.sdk.SetAcquisitionMode(2)
        elif mode=="Kinetics":
            ret=self.sdk.SetAcquisitionMode(3)
        elif mode=="Fast Kinetics":
            ret=self.sdk.SetAcquisitionMode(4)
        elif mode=="Run Till Abort":
            ret=self.sdk.SetAcquisitionMode(5)
        try:
            if ret==20002:
                print(f"Acquisition mode set to {mode}.")
                self.acquisition_mode=mode
                return ret
        except Exception as e:
            print(f"Error setting acquisition mode: {e}")

    def set_number_accumulations(self, number:int):
        """
        Set the number of accumulations for the camera.
        """
        ret=self.sdk.SetNumberAccumulations(number)
        if ret==20002:
            self.number_accumulations=number
            print(f"Number of accumulations set to {number}.")
        return ret
    
    def set_number_kinetics(self, number:int):
        """
        Set the number of kinetics for the camera.
        """
        ret=self.sdk.SetNumberKinetics(number)
        if ret==20002:
            self.number_kinetics=number
            print(f"Number of kinetics set to {number}.")
        return ret
        
    