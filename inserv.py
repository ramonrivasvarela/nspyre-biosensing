# inserv.py

"""
David Ovetsky 4/1/2025

Based off of Evan Villafranca's code.

Start up an instrument server to host drivers. 
"""
import logging, os
logging.basicConfig(level=logging.INFO) 
from pathlib import Path
import logging

from nspyre import nspyre_init_logger


_HERE = Path(__file__).parent



nspyre_init_logger(
    logging.INFO,
    log_path=_HERE / '../logs',
    log_path_level=logging.DEBUG,
    prefix='local_inserv',
    file_size=10_000_000,
)

from nspyre import serve_instrument_server_cli
from nspyre import InstrumentServer
#import pdb; pdb.set_trace()
# create a new instrument server
with InstrumentServer() as inserv:
   # add signal generator driver
   # 'sg' will be an instance of the class 'SG396' in the file ./drivers/sg.py. The class __init__ will be run with the given args. 
   # inserv.add(name = 'sg', 
   #            class_path= _HERE / 'drivers' / 'dr_sg396.py', 
   #            class_name= 'SG396',
   #            args= '')
   
   # REQUIRED IMPORT: pyserial
#    inserv.add(name = 'DLnsec', 
#                 class_path= _HERE / 'drivers' / 'dr_dlnsec.py', 
#                 class_name= 'DLnsec',
#                 args= ['COM9'])

   #REQUIRED IMPORT: pulsestreamer
#    inserv.add(name = 'Pulser',
#                class_path= _HERE / 'drivers' / 'dr_pulse.py',
#                class_name= 'Pulses',
#                args= ['TCPIP::10.135.70.127::SOCKET']
#                )

#   inserv.add(name = 'XYZcontrols',
#               class_path= _HERE / 'drivers' / 'dr_xyz_controls.py',
#               class_name= 'XYZSetup',
#               args= ['Dev1/ao0', 'Dev1/ao1', 'Dev1/ao2', 'TCPIP::10.135.70.127::SOCKET']
#               )
   

   # run a CLI (command-line interface) that allows the user to enter
   # commands to control the server
   serve_instrument_server_cli(inserv)