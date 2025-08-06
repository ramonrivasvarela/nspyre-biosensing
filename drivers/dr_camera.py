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
        self.frame_transfer_mode="OFF"
        self.acquisition_mode="Kinetics"
        self.number_accumulations=1
        self.number_kinetics=1
        self.width=None
        self.height=None
        

        

    def initialize(self):
        ret=self.sdk.Initialize("")
        return ret
        
        
    def set_trigger_mode(self, trigger_mode):
        if type(trigger_mode) is str:
            mode = trigger_mode.lower().replace("-", " ").replace("(", "").replace(")", "")
        if mode == "internal" or mode == 0:
            mode="Internal"
            ret = self.sdk.SetTriggerMode(0)
        elif mode == "external" or mode == 1:
            mode="External"
            ret = self.sdk.SetTriggerMode(1)

        elif mode == "external exposure bulb" or mode == 7:
            mode="External Exposure (Bulb)"
            ret = self.sdk.SetTriggerMode(7)
        else:
            raise ValueError("Trigger mode must be 'internal', 'external', or 'external exposure bulb'.")
        if ret == 20002:
            self.trigger_mode = mode
            print(f"Trigger mode set to {mode}.")


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

    def set_number_kinetics(self, number_kinetics:int): 
        ret = self.sdk.SetNumberKinetics(number_kinetics)
        if ret == 20002:
            self.number_kinetics = number_kinetics
            print(f"Number of kinetics set to {number_kinetics}.")
            return ret
        else:
            raise RuntimeError(f"SetNumberKinetics failed with error code {ret}.")
    
    def set_number_accumulations(self, number_accumulations:int):
        ret = self.sdk.SetNumberAccumulations(number_accumulations) 
        if ret == 20002:
            self.number_accumulations = number_accumulations
            print(f"Number of accumulations set to {number_accumulations}.")
            return ret
        else:
            raise RuntimeError(f"SetNumberAccumulations failed with error code {ret}.")

    def set_shutter(self, mode):
        if type(mode) is str:
            mode = mode.lower().replace("-", " ")
        if mode == "auto" or mode=="automatic" or mode == 0:
            ret = self.sdk.SetShutter(0, 0, 27, 27)
            mode = "Automatic"
        elif mode == "open" or mode == 1:
            ret = self.sdk.SetShutter(0, 1, 27, 27)
            mode = "Open"
        elif mode == "closed" or mode == 2:
            ret = self.sdk.SetShutter(0, 2, 27, 27)
            mode= "Closed"
        else:
            raise ValueError("Shutter mode must be 'auto', 'open', or 'closed'.")
        if ret == 20002:
            self.shutter = mode
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

    def set_read_mode(self, mode):
        if type(mode) is str:
            mode = mode.lower().replace("-", " ")
        if mode == "full vertical binning" or mode == 0:
            mode = "Full Vertical Binning"
            ret = self.sdk.SetReadMode(0)  
        elif mode == "multi track" or mode == 1:
            mode = "Multi-Track"
            ret = self.sdk.SetReadMode(1)
        elif mode == "random track" or mode == 2:
            mode = "Random-Track"
            ret = self.sdk.SetReadMode(2)
        elif mode == "single track" or mode == 3:
            mode = "Single-Track"
            ret = self.sdk.SetReadMode(3)
        elif mode == "image" or mode == 4:
            mode= "Image"
            ret = self.sdk.SetReadMode(4)
        else:
            raise ValueError("Read mode must be one of: full vertical binning, multi track, random track, single track, image.")
        if ret == 20002:
            self.read_mode= mode
            print(f"Read mode set to {mode}.")
            return ret

    def set_frame_transfer_mode(self, mode):
        if type(mode) is str:
            mode = mode.lower().replace("-", " ")
        if mode == "off" or mode == 0:
            mode = "OFF"
            ret = self.sdk.SetFrameTransferMode(0)
        elif mode == "ON" or mode == 1:
            mode = "ON"
            ret = self.sdk.SetFrameTransferMode(1)
        else:
            raise ValueError("Frame transfer mode must be 'frame transfer' or 'conventional'.")
        if ret == 20002:
            self.frame_transfer_mode = mode
            print(f"Frame transfer mode set to {mode}.")
            return ret

    def set_acquisition_mode(self, mode):
        if type(mode) is str:
            mode = mode.lower().replace("-", " ")
        if mode == "single scan" or mode == 1:
            mode = "Single Scan"
            ret = self.sdk.SetAcquisitionMode(1)
        elif mode == "accumulate" or mode == 2:
            mode = "Accumulate"
            ret = self.sdk.SetAcquisitionMode(2)
        elif mode == "kinetics" or mode == 3:
            mode = "Kinetics"
            ret = self.sdk.SetAcquisitionMode(3)
        elif mode == "fast kinetics" or mode == 4:
            mode = "Fast Kinetics"
            ret = self.sdk.SetAcquisitionMode(4)
        elif mode == "run till abort" or mode == 5:
            mode = "Run till Abort"
            ret = self.sdk.SetAcquisitionMode(5)
        else:
            raise ValueError("Acquisition mode must be one of: single scan, accumulate, kinetics, fast kinetics, run till abort.")
        if ret == 20002:
            self.acquisition_mode = mode
            print(f"Acquisition mode set to {mode}.")
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
        ret = self.sdk.SetImage(1, 1, 1, self.width, 1, self.height)
        if ret == 20002:
            print("Image set successfully.")
            return ret
        else:
            raise RuntimeError(f"SetImage failed with error code {ret}.")
        

    def get_acquisition_timings(self):
        """
        Get the acquisition timings.
        """
        ret, exp_time, acc_time, kin_time = self.sdk.GetAcquisitionTimings()
        if ret == 20002:
            self.exposure_time = exp_time
            self.accumulation_time = acc_time
            self.kinetic_time = kin_time
            return ret, exp_time, acc_time, kin_time
        else:
            raise RuntimeError(f"GetAcquisitionTimings failed with error code {ret}.")