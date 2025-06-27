from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

class Camera():
    def __init__(self):
        self.sdk=atmcd("")
        self.codes=atmcd_codes

    def initialize(self):
        ret=self.sdk.Initialize("")
        print("Function Initialize returned {}".format(ret))