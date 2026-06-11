"""Written by Ramon Rivas
Based on Andor's SDK documentation and example code, as well as the pyAndorSDK2 wrapper."""

from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
import time
import numpy as np
import pickle
import ctypes
import ctypes

class Camera():
    def __init__(self):
        self.sdk=None
        self.errors=atmcd_errors
        self.exposure_time=0.075
        self.accumulation_time=None
        self.kinetic_time=None
        self.trigger_mode="Internal"
        
        self.temperature=20
        self.emccdgain=2
        self.shutter="Auto"
        self.cooler_on=False
        self.temperature_goal=18

        self.read_mode="Image"
        self.frame_transfer_mode="OFF"
        self.acquisition_mode="Kinetics"
        self.number_accumulations=1
        self.number_kinetics=1
        self.x_len=None
        self.y_len=None

        self.vs_speed=3
        self.hs_speed=0
        
    # ========= String conversion function =======

    def convert_string(self, input_string):
        """
        Convert a string to the format expected by the SDK functions.
        This involves converting to lowercase and replacing certain characters.
        """
        return input_string.lower().replace("-", " ").replace("_", " ").replace("(", "").replace(")", "")
        

    def initialize(self):
        self.sdk=atmcd("")
        ret=self.sdk.Initialize("")
        if ret == 20002:
            self.set_acquisition_mode(self.acquisition_mode)
            self.set_read_mode(self.read_mode)
            self.set_trigger_mode(self.trigger_mode)
            (ret, xpixels, ypixels) = self.get_detector()
            self.set_image(xpixels, ypixels)
            self.x_len = xpixels
            self.y_len = ypixels
            self.set_exposure_time(self.exposure_time)
            self.set_emccdgain(self.emccdgain)
            self.set_shutter(self.shutter)
        return ret
        
    ### WARNING (Ramon): I don't love my conventions for storing camera settings in the Camera class. It might be nice to replace strings with enums or something more robust, and to have a more systematic way of keeping track of the current settings.
    def set_trigger_mode(self, trigger_mode):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change trigger mode while camera is not idle.")

        if type(trigger_mode) is str:
            mode = self.convert_string(trigger_mode)
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
        if not self.sdk:
            return 20000 # Not initialized
        ret=self.sdk.SetTemperature(temp_value)
        if ret==20002:
            self.temperature_goal=temp_value
        return ret

    def cool(self):
        if not self.sdk:
            return 20000  # Not initialized
        ret=self.sdk.CoolerON()
        return ret
    
    def stop_cooling(self):
        if not self.sdk:
            return 20000  # Not initialized
        ret=self.sdk.CoolerOFF()
        return ret

    def get_temperature_status(self):
        if not self.sdk:
            return 20000, None  # Not initialized

        err, temp = self.sdk.GetTemperatureF()
        return err, temp

 

    def start_acquisition(self):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot start acquisition while camera is not idle.")

        ret=self.sdk.StartAcquisition()
        return ret
        
    def prepare_acquisition(self):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot prepare acquisition while camera is not idle.")

        ret=self.sdk.PrepareAcquisition()
        return ret
    
    def abort_acquisition(self):
        if not self.sdk:
            return 20000
        ret=self.sdk.AbortAcquisition()
        return ret
    
    def get_total_number_images_acquired(self):
        # Call the SDK; wrapper gives (ret_code, total_images)
        if self.sdk is None:
            return 20000, None  # Not initialized
        ret, total = self.sdk.GetTotalNumberImagesAcquired()

        if ret == 20002:
            return ret, total
        else:
            # Surface the driver error for easier debugging
            raise RuntimeError(f"GetTotalNumberImagesAcquired failed (code {ret})")

    def set_emccdgain(self, gain:int):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change EMCCD gain while camera is not idle.")
        ret=self.sdk.SetEMCCDGain(gain)
        if ret==20002:
            self.emccdgain=gain
        return ret

    def get_emccdgain(self):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot get EMCCD gain while camera is not idle.")
        if self.sdk is None:
            return 20000, None  # Not initialized
        ret, gain = self.sdk.GetEMCCDGain()
        if ret == 20002:
            self.emccdgain = gain
            return ret, gain



    def get_status(self):
        if not self.sdk:
            return 20000, None
        # Call GetStatus; this will return DRV_NOT_INITIALIZED if Initialize() was never called
        ret, state = self.sdk.GetStatus()

        return ret, state

    def is_camera_idle(self):
        """
        Check if the camera is ready for acquisition.
        """
        if self.sdk is None:
            return False  # Not initialized
        ret, state = self.get_status()
        if ret != 20002:
            print(f"GetStatus() failed (code {ret})")
            return False
        return state == 20073

    def cool_old(self, temp_value):
        if not self.sdk:
            return 20000        
        ret = self.set_temperature(temp_value)
        if ret != 20002:
            print(f"SetTemperature({temp_value}) failed (code {ret})")
            return ret
        else:
            self.temperature_goal = temp_value
        print(f"SetTemperature returned {ret}, target = {temp_value}°C")


        ret = self.sdk.CoolerON()
        if ret != 20002:
            print(f"CoolerON() failed (code {ret})")
            return ret
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
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change exposure time while camera is not idle.")
        if self.sdk is None:
            return 20000  # Not initialized
        ret=self.sdk.SetExposureTime(exp_time)
        if ret==20002:
            self.exposure_time=exp_time
            print(f"Exposure time set to {exp_time} seconds.")

    def wait_for_acquisition_timeout(self, timeout_seconds:int):
        """
        Wait for acquisition to complete, with a timeout.

        Args:
            timeout_seconds: Maximum time to wait for acquisition to complete, in seconds.
        Returns:
            True if acquisition completed within the timeout, False if timeout was reached.
        """
        if self.sdk is None:
            raise RuntimeError("Camera SDK not initialized.")
        ret=self.sdk.WaitForAcquisitionTimeOut(timeout_seconds*1000)  # SDK expects milliseconds
        return ret == 20002
    
    def get_images_16(self, first, last, size):
        if self.sdk is None:
            return 20000, None, None, None  # Not initialized
        ret, all_data, validfirst, validlast=self.sdk.GetImages16(first, last, size)
        return ret, all_data, validfirst, validlast
    
    def get_images(self, first, last, size):
        if not self.sdk:
            return 20000, None, None, None  # Not initialized
        ret, all_data, validfirst, validlast=self.sdk.GetImages(first, last, size)
        return ret, all_data, validfirst, validlast
    
    def shutdown(self):
        if self.sdk is None:
            return 20000  # Not initialized
        ret=self.sdk.ShutDown()
        self.sdk=None
        return ret

    def set_number_kinetics(self, number_kinetics:int): 
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change number of kinetics while camera is not idle.")
        ret = self.sdk.SetNumberKinetics(number_kinetics)
        if ret == 20002:
            self.number_kinetics = number_kinetics
            print(f"Number of kinetics set to {number_kinetics}.")
            return ret
        else:
            raise RuntimeError(f"SetNumberKinetics failed with error code {ret}.")
    
    def set_number_accumulations(self, number_accumulations:int):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change number of accumulations while camera is not idle.")
        ret = self.sdk.SetNumberAccumulations(number_accumulations) 
        if ret == 20002:
            self.number_accumulations = number_accumulations
            print(f"Number of accumulations set to {number_accumulations}.")
            return ret
        else:
            raise RuntimeError(f"SetNumberAccumulations failed with error code {ret}.")

    def set_shutter(self, mode):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change shutter mode while camera is not idle.")
        if self.sdk is None:
            return 20000  # Not initialized
        if type(mode) is str:
            mode = self.convert_string(mode)
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
        if self.sdk is None:
            return 20000, None  # Not initialized
        ret, status = self.sdk.IsCoolerOn()
        return status
    
    def cooler_on(self):
        """
        Turn the cooler on.
        """
        if self.sdk is None:
            return 20000  # Not initialized
        ret = self.sdk.CoolerON()
        return ret

    def cooler_off(self):
        """
        Turn the cooler off.
        """
        if self.sdk is None:
            return 20000  # Not initialized
        ret = self.sdk.CoolerOFF()
        return ret
    
    def get_total_number_images_acquired(self):
        """
        Get the total number of images acquired.
        """
        if self.sdk is None:
            return 20000, None  # Not initialized
        ret, total = self.sdk.GetTotalNumberImagesAcquired()
        return ret, total

    def set_read_mode(self, mode):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change read mode while camera is not idle.")
        if type(mode) is str:
            mode = self.convert_string(mode)
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
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change frame transfer mode while camera is not idle.")
        if type(mode) is str:
            mode = self.convert_string(mode)
        if mode == "off" or mode=="conventional" or mode == 0:
            mode = "OFF"
            ret = self.sdk.SetFrameTransferMode(0)
        elif mode == "on" or mode=="frame transfer" or mode == 1:
            mode = "ON"
            ret = self.sdk.SetFrameTransferMode(1)
        else:
            raise ValueError("Frame transfer mode must be 'ON' or 'OFF'.")
        if ret == 20002:
            self.frame_transfer_mode = mode
            print(f"Frame transfer mode set to {mode}.")
            return ret

    def set_acquisition_mode(self, mode):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change acquisition mode while camera is not idle.")
        if type(mode) is str:
            mode = self.convert_string(mode)
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
        if not self.is_camera_idle():
            raise RuntimeError("Cannot get detector size while camera is not idle.")
        ret, width, height = self.sdk.GetDetector()
        if ret == 20002:
            self.x_len = width
            self.y_len = height
            return ret, width, height
        else:
            raise RuntimeError(f"GetDetector failed with error code {ret}.")
        
    def set_image(self, width=None, height=None):
        """
        Set the image.
        """
        if not self.is_camera_idle():
            raise RuntimeError("Cannot set image while camera is not idle.")
        if width is not None:
            self.x_len = width
        if height is not None:
            self.y_len = height
        if self.x_len is None or self.y_len is None:
            raise ValueError("Width and height must be set before calling set_image.")
        ret = self.sdk.SetImage(1, 1, 1, self.x_len, 1, self.y_len)
        if ret == 20002:
            print("Image set successfully.")
            return ret
        else:
            raise RuntimeError(f"SetImage failed with error code {ret}.")
        

    def get_acquisition_timings(self):
        """
        Get the acquisition timings.
        """
        if not self.is_camera_idle():
            raise RuntimeError("Cannot get acquisition timings while camera is not idle.")
        ret, exp_time, acc_time, kin_time = self.sdk.GetAcquisitionTimings()
        if ret == 20002:
            self.exposure_time = exp_time
            self.accumulation_time = acc_time
            self.kinetic_time = kin_time
            return ret, exp_time, acc_time, kin_time
        else:
            raise RuntimeError(f"GetAcquisitionTimings failed with error code {ret}.")
        

    def set_VS_speed(self, speed:int):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change vertical shift speed while camera is not idle.")
        ret = self.sdk.SetVSSpeed(speed)
        if ret == 20002:
            self.vs_speed = speed
            print(f"Vertical shift speed set to {speed}.")
            return ret
        else:
            raise RuntimeError(f"SetVSSpeed failed with error code {ret}.")
        
    def set_HS_speed(self, speed:int):
        if not self.is_camera_idle():
            raise RuntimeError("Cannot change horizontal shift speed while camera is not idle.")
        ret = self.sdk.SetHSSpeed(0, speed)
        if ret == 20002:
            self.hs_speed = speed
            print(f"Horizontal shift speed set to {speed}.")
            return ret
        else:
            raise RuntimeError(f"SetHSSpeed failed with error code {ret}.")