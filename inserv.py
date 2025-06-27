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

from instrument_activation import xyz_activation_boolean, pulser_activation_boolean, sg_activation_boolean, dlnsec_activation_boolean


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

# create a new instrument server
with InstrumentServer() as inserv:
   # add signal generator driver
   # 'sg' will be an instance of the class 'SG396' in the file ./drivers/sg.py. The class __init__ will be run with the given args. 
   if sg_activation_boolean:
      inserv.add(name = 'sg', 
               class_path= _HERE / 'drivers' / 'dr_sg396.py', 
               class_name= 'SG396',
               args = ['TCPIP::10.135.70.67::inst0::INSTR'])
   
   # REQUIRED IMPORT: pyserial
   if dlnsec_activation_boolean:
      inserv.add(name = 'DLnsec', 
                  class_path= _HERE / 'drivers' / 'dr_dlnsec.py', 
                  class_name= 'DLnsec',
                  args= ['COM9'])

   #REQUIRED IMPORT: pulsestreamer

   if pulser_activation_boolean:
      inserv.add(name = 'Pulser',
                  class_path= _HERE / 'drivers' / 'dr_pulse.py',
                  class_name= 'PulserClass',
                  args= []

               )
      
      #REQUIRED IMPORT: lantz-drivers
   if xyz_activation_boolean:
      

      inserv.add(name = 'XYZcontrol',
               class_path= _HERE / 'drivers' / 'dr_xyz_controls.py',
               class_name= 'XYZSetup',
               args= ['Dev1/ao0', 'Dev1/ao1', 'Dev1/ao2', 'Dev1/ctr1']
               )

      inserv.add(name = 'DAQCounter',
            class_path= _HERE / 'drivers' / 'dr_DAQ_counter.py',
            class_name= 'DAQCounter',
            args= ['Dev1'],
            kwargs={'clk_pfi': 'PFI0', 'ctr_pfi': 'PFI3'}
            )

   # run a CLI (command-line interface) that allows the user to enter
   # commands to control the server
   serve_instrument_server_cli(inserv)

   