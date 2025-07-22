#!/usr/bin/env python
"""
This is an example script that demonstrates the basic functionality of nspyre.
"""
import logging
from pathlib import Path

import nspyre.gui.widgets.save
import nspyre.gui.widgets.load
import nspyre.gui.widgets.flex_line_plot
import nspyre.gui.widgets.subsystem
from nspyre import MainWidget
from nspyre import MainWidgetItem
from nspyre import nspyre_init_logger
from nspyre import nspyreApp
# in order for dynamic reloading of code to work, you must pass the specifc
# module containing your class to MainWidgetItem, since the python reload()
# function does not recursively reload modules


from gui_widgets import laser_gui
from gui_widgets import instrument_gui
from gui_widgets import experiment_gui
from gui_widgets import camera_gui

from drivers.insmgr import MyInstrumentManager
from nspyre import InstrumentManager


from instrument_activation import xyz_activation_boolean, pulser_activation_boolean, sg_activation_boolean, dlnsec_activation_boolean, camera_activation_boolean


_HERE = Path(__file__).parent

def main():
    # Log to the console as well as a file inside the logs folder.
    nspyre_init_logger(
        log_level=logging.INFO,
        log_path=_HERE / '../logs',
        log_path_level=None,
        prefix=Path(__file__).stem,
        file_size=10_000_000,
    )

    with InstrumentManager() as mgr:
        app = nspyreApp()
        if xyz_activation_boolean:
            mgr.XYZcontrol.initialize()
            print("Initialized XYZ control.")
        def app_close_event():
            print("Application is closing...")
            if xyz_activation_boolean:
                try:
                    mgr.XYZcontrol.reset_and_finalize()
                except Exception as e:
                    print(f"Error finalizing XYZ control: {e}")
            if pulser_activation_boolean:
                mgr.Pulser.set_state_off()
            if sg_activation_boolean:
                mgr.sg.set_rf_toggle(0)
            if camera_activation_boolean:
                mgr.Camera.shutdown()

            print("Cleanup complete.")

        # Connect the close event to the app
        app.aboutToQuit.connect(app_close_event)

        # Create the GUI.
        main_widget = MainWidget(
            {   'Instruments' : {
                'Lasers': MainWidgetItem(laser_gui, 'InstWidget', stretch=(1, 1)),
                'SG & XYZ': MainWidgetItem(instrument_gui, 'InstWidgetV2', stretch=(1, 1)),
                'Camera': MainWidgetItem(camera_gui, 'CameraWidget', stretch=(1, 1)),
                },
                'Save': MainWidgetItem(nspyre.gui.widgets.save, 'SaveWidget', stretch=(1, 1)),
                'Load': MainWidgetItem(nspyre.gui.widgets.load, 'LoadWidget', stretch=(1, 1)),
                'Experiments': {
                    'Counts vs Time' : MainWidgetItem(experiment_gui, 'CountsWidget', stretch=(1, 1)),
                    'Planescan' : MainWidgetItem(experiment_gui, 'PlaneScanWidget', stretch=(1, 1)),
                    'Wide Field ODMR': MainWidgetItem(experiment_gui, 'WideFieldWidget', stretch=(1, 1)),
                    'Spatial Feedback': MainWidgetItem(experiment_gui, 'SpatialFeedbackWidget', stretch=(1, 1)),
                    'Pictures': MainWidgetItem(experiment_gui, 'PicturesWidget', stretch=(1, 1)),
                    },
                
                'Plotting' : {
                    'Flex Line Plot': MainWidgetItem(experiment_gui, 'CountsPlotWidget', stretch=(1, 1)),
                    'Heat Map': MainWidgetItem(experiment_gui, 'PlaneScanHeatMapWidget', stretch=(1, 1)),
                }
            }
        )


        main_widget.show()

        # Run the GUI event loop.
        app.exec()


# if using the nspyre ProcessRunner, the main code must be guarded with if __name__ == '__main__':
# see https
#//docs.python.org/2/library/multiprocessing.html#windows
if __name__ == '__main__':
    main()
