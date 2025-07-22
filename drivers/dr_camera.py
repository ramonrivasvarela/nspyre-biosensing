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
        self.accumulation_time=None
        self.kinetic_time=None
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
        self.width=None
        self.height=None
        

        

    def initialize(self):
        ret=self.sdk.Initialize("")
        return ret
        
        

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

    def set_trigger_mode(self, trigger_mode: str):
        mode_processed = trigger_mode.lower().replace("-", " ")
        if mode_processed == "internal":
            ret = self.sdk.SetTriggerMode(0)
            if ret == 20002:
                self.trigger_mode = "Internal"
                print("Trigger mode set to internal.")
            return ret
        elif mode_processed == "external":
            ret = self.sdk.SetTriggerMode(1)
            if ret == 20002:
                self.trigger_mode = "External"
                print("Trigger mode set to external.")
            return ret
        elif mode_processed == "external exposure bulb":
            ret = self.sdk.SetTriggerMode(6)
            if ret == 20002:
                self.trigger_mode = "External Exposure Bulb"
                print("Trigger mode set to external exposure bulb.")
            return ret
        else:
            raise ValueError("Trigger mode must be 'internal', 'external', or 'external exposure bulb'.")

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
    
    def abort_acquisition(self):
        ret=self.sdk.AbortAcquisition()
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

        return ret, state

    def cool_old(self, temp_value):
        ret = self.set_temperature(temp_value)
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            print(f"SetTemperature({temp_value}) failed (code {ret})")
            return
        else:
            self.temperature_goal = temp_value
        print(f"SetTemperature returned {ret}, target = {temp_value}°C")


        ret = self.sdk.CoolerON()
        if ret != self.errors.Error_Codes.DRV_SUCCESS:
            print(f"CoolerON() failed (code {ret})")
            return
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
        return ret, all_data, validfirst, validlast
    
    def get_images(self, first, last, size):
        ret, all_data, validfirst, validlast=self.sdk.GetImages(first, last, size)
        return ret, all_data, validfirst, validlast
    
    def shutdown(self):
        ret=self.sdk.ShutDown()
        return ret

    def set_shutter(self, mode: str):
        mode_processed = mode.lower().replace("-", " ")
        if mode_processed == "auto":
            ret = self.sdk.SetShutter(0, 0, 27, 27)
        elif mode_processed == "open":
            ret = self.sdk.SetShutter(0, 1, 27, 27)
        elif mode_processed == "closed":
            ret = self.sdk.SetShutter(0, 2, 27, 27)
        else:
            raise ValueError("Shutter mode must be 'auto', 'open', or 'closed'.")
        if ret == 20002:
            self.shutter = mode_processed
            print(f"Shutter set to {self.shutter}.")
            return ret
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

    def set_read_mode(self, mode: str):
        mode_processed = mode.lower().replace("-", " ")
        if mode_processed == "full vertical binning":
            ret = self.sdk.SetReadMode(0)  
        elif mode_processed == "multi track":
            ret = self.sdk.SetReadMode(1)
        elif mode_processed == "random track":
            ret = self.sdk.SetReadMode(2)
        elif mode_processed == "single track":
            ret = self.sdk.SetReadMode(3)
        elif mode_processed == "image":
            ret = self.sdk.SetReadMode(4)
        else:
            raise ValueError("Read mode must be one of: full vertical binning, multi track, random track, single track, image.")
        if ret == 20002:
            self.read_mode= mode_processed
            print(f"Read mode set to {self.read_mode}.")
            return ret

    def set_frame_transfer_mode(self, mode: str):
        mode_processed = mode.lower().replace("-", " ")
        if mode_processed == "frame transfer":
            ret = self.sdk.SetFrameTransferMode(0)
        elif mode_processed == "conventional":
            ret = self.sdk.SetFrameTransferMode(1)
        else:
            raise ValueError("Frame transfer mode must be 'frame transfer' or 'conventional'.")
        if ret == 20002:
            self.frame_transfer_mode = mode_processed
            print(f"Frame transfer mode set to {mode_processed}.")
            return ret

    def set_acquisition_mode(self, mode: str):
        mode_processed = mode.lower().replace("-", " ")
        if mode_processed == "single scan":
            ret = self.sdk.SetAcquisitionMode(1)
        elif mode_processed == "accumulate":
            ret = self.sdk.SetAcquisitionMode(2)
        elif mode_processed == "kinetics":
            ret = self.sdk.SetAcquisitionMode(3)
        elif mode_processed == "fast kinetics":
            ret = self.sdk.SetAcquisitionMode(4)
        elif mode_processed == "run till abort":
            ret = self.sdk.SetAcquisitionMode(5)
        else:
            raise ValueError("Acquisition mode must be one of: single scan, accumulate, kinetics, fast kinetics, run till abort.")
        if ret == 20002:
            self.acquisition_mode = mode_processed
            print(f"Acquisition mode set to {mode_processed}.")
            return ret

    def get_detector(self):
        """
        Get the detector size.
        """
        ret, width, height = self.sdk.GetDetector()
        if ret == 20002:
            self.width = width
            self.height = height
            return ret, width, height
        else:
            raise RuntimeError(f"GetDetector failed with error code {ret}.")
        
    def set_image(self, width=None, height=None):
        """
        Set the image.
        """
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        if self.width is None or self.height is None:
            raise ValueError("Width and height must be set before calling set_image.")
        ret = self.sdk.SetImage(1, 1, self.width, self.height)
        if ret == 20002:
            print("Image set successfully.")
            return ret
        else:
            raise RuntimeError(f"SetImage failed with error code {ret}.")