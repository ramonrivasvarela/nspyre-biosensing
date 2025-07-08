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
        
        self.temperature=-70
        self.gain=1
        self.shutter="Open"

        

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
        elif trigger_mode=="External":
            ret=self.sdk.SetTriggerMode(1)
            
        elif trigger_mode=="External Exposure Bulb":
            ret=self.sdk.SetTriggerMode(6)
        else:
            raise ValueError("Trigger mode must be set to 'Internal', 'External', or 'External Exposure Bulb'.")
        self.check_Error_Codes(ret, "SetTriggerMode")


    def set_temperature(self, temp_value:int):
        ret=self.sdk.SetTemperature(temp_value)
        if ret == self.errors.Error_Codes.DRV_SUCCESS:
            return True 
        else:
            return False
        

    def get_temperature(self):
        ret, temp = self.sdk.GetTemperature()
        return ret, temp

 

    def start_acquisition(self):
        ret=self.sdk.StartAcquisition()
        
    def prepare_acquisition(self):
        ret=self.sdk.PrepareAcquisition()

    def get_total_number_images_acquired(self):
        # Call the SDK; wrapper gives (ret_code, total_images)
        ret, total = self.sdk.GetTotalNumberImagesAcquired()

        if ret == self.errors.Error_Codes.DRV_SUCCESS:
            return ret, total
        else:
            # Surface the driver error for easier debugging
            raise RuntimeError(f"GetTotalNumberImagesAcquired failed (code {ret})")
    
    def set_gain(self, gain:int):
        ret=self.sdk.SetEMCCDGain(gain)
        self.check_Error_Codes(ret, "SetGain")

    def get_gain(self):
        ret, gain = self.sdk.GetEMCCDGain()
        if ret == self.errors.Error_Codes.DRV_SUCCESS:
            return ret, gain
        else:
            raise RuntimeError(f"GetEMCCDGain failed (code {ret})")



    def get_status(self):

        # Call GetStatus; this will return DRV_NOT_INITIALIZED if Initialize() was never called
        ret, state = self.sdk.GetStatus()

        return ret == self.errors.Error_Codes.DRV_SUCCESS

    def cool(self, temp_value):
        ret = self.set_temperature(temp_value)
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            raise RuntimeError(f"SetTemperature({temp_value}) failed (code {ret})")
        print(f"SetTemperature returned {ret}, target = {temp_value}°C")


        ret = self.sdk.CoolerON()
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            raise RuntimeError(f"CoolerON() failed (code {ret})")
        print("CoolerON returned DRV_SUCCESS; waiting for stabilization…")


        while True:
            status, current = self.get_temperature()  # returns (status_code, temperature)
            if status == self.errors.Error_Codes.DRV_TEMP_STABILIZED:
                print(f"\nTemperature stabilized at {current}°C.")
                break

            # still on the way to set-point
            print(f"\rStatus={status}; current={current}°C", end="")
            time.sleep(5)

    def set_exposure_time(self, exp_time:float):
        ret=self.sdk.SetExposureTime(exp_time)
        self.check_Error_Codes(ret, "SetExposureTime")

    def get_images_16(self, first, last, size):
        ret, all_data, validfirst, validlast=self.sdk.GetImages16(first, last, size)
        self.check_Error_Codes
        return ret, all_data, validfirst, validlast

    def shutdown(self):
        ret=self.sdk.ShutDown()

    def set_shutter(self, mode:str):
        ret=self.sdk.SetShutter()