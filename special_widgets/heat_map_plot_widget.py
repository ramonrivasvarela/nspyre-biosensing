import logging
import time
from typing import Callable
from typing import Optional

import numpy as np
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtWidgets

from nspyre import DataSink
from nspyre import QThreadSafeObject
from nspyre.gui.widgets.layout import tree_layout
from nspyre import HeatMapWidget

from pyqtgraph.Qt import QtGui

_logger = logging.getLogger(__name__)

import pyqtgraph as pg


class _HeatMapSeriesSettings:
    def __init__(
        self,
        series: str,
        hidden: bool = False,
    ):
        self.series = series
        self.hidden = hidden

class _HeatMapSettings(QThreadSafeObject):
    def __init__(self):
        self.series_settings = {}
        self.sink = None
        self.sink_mutex = QtCore.QMutex()
        self.force_update = False
        super().__init__()

    def get_settings(self, name: str, callback=None):
        with QtCore.QMutexLocker(self.mutex):
            settings = self.series_settings[name]
            if callback is not None:
                self.run_main(callback, name, settings, blocking=True)
    
    def new_heatmap(
        self,
        name: str,
        series: str,
        hidden: bool,
        callback: Optional[Callable]=None,
    ):
        with QtCore.QMutexLocker(self.mutex):
            if name in self.series_settings:
                _logger.info(
                    f'A plot with the name [{name}] already exists. Ignoring add_plot '
                    'request.'
                )
                return
            self.series_settings[name] = _HeatMapSeriesSettings(
                series=series,
                hidden=hidden,
            )
            self.force_update = True
            if callback is not None:
                self.run_main(callback, name, blocking=True)
    
    def remove_heatmap(self, name: str, callback: Optional[Callable]=None):
<<<<<<< Updated upstream
        with QtCore.QMutexLocker(self.mutex): 
=======
        with QtCore.QMutexLocker(self.mutex):
>>>>>>> Stashed changes
            if name not in self.series_settings:
                _logger.info(
                    f'No plot with the name [{name}] exists. Ignoring remove_plot '
                    'request.'
                )
                return
            
            if callback is not None:
                self.run_main(callback, name, blocking=True)

            del self.series_settings[name]

    def hide_heatmap(self, name: str, callback: Optional[Callable]=None):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'No plot with the name [{name}] exists. Ignoring hide_plot '
                    'request.'
                )
                return
            if self.series_settings[name].hidden:
                _logger.info(
                    f'Plot with the name [{name}] is already hidden. Ignoring hide_plot '
                    'request.'
                )
                return
            self.series_settings[name].hidden = True
            if callback is not None:
                self.run_main(callback, name, blocking=True)
    
    def show_heatmap(self, name: str, callback: Optional[Callable]=None):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'No plot with the name [{name}] exists. Ignoring show_plot '
                    'request.'
                )
                return
            if not self.series_settings[name].hidden:
                _logger.info(
                    f'Plot with the name [{name}] is already visible. Ignoring show_plot '
                    'request.'
                )
                return
            self.series_settings[name].hidden = False
            if callback is not None:
                self.run_main(callback, name, blocking=True)
    
    def update_settings(
        self,
        name: str,
        series: str,
    ):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'No plot with the name [{name}] exists. Ignoring update_plot '
                    'request.'
                )
                return
            self.series_settings[name].series = series
            self.force_update = True



class HeatMapPlotWidget(QtWidgets.QWidget):
    """Qt widget for flexible plotting of 1D user data.
    It connects to an arbitrary data set stored in the
    :py:class:`~nspyre.data.server.DataServer`, collects and processes the data, and
    offers a variety of user-controlled plotting options.

    The user should push a dictionary containing the following key/value pairs
    to the corresponding :py:class:`~nspyre.data.source.DataSource`
    object sourcing data to the :py:class:`~nspyre.data.server.DataServer`:

    - key: :code:`title`, value: Plot title string
    - key: :code:`xlabel`, value: X label string
    - key: :code:`ylabel`, value: Y label string
    - key: :code:`datasets`, value: Dictionary where keys are a data series \
        name, and values are data as a list of 2D numpy arrays of shape (2, n). \
        The two rows represent the x and y axes, respectively, of the plot, and \
        the n columns each represent a data point.

    You may use np.NaN values in the data arrays to represent invalid entries,
    which won't contribute to the data averaging. An example is given below:

    .. code-block:: python

        from nspyre import DataSource, StreamingList

        with DataSource('my_dataset') as ds:
            channel_1_data = StreamingList([np.array([[1, 2, 3], [12, 12.5, 12.25]]), \
np.array([[4, 5, 6], [12.6, 13, 11.2]])])
            channel_2_data = StreamingList([np.array([[1, 2, 3], [3, 3.3, 3.1]]), \
np.array([[4, 5, 6], [3.4, 3.6, 3.5]])])
            my_plot_data = {
                'title': 'MyVoltagePlot',
                'xlabel': 'Time (s)',
                'ylabel': 'Amplitude (V)',
                'datasets': {
                    'channel_1': channel_1_data
                    'channel_2': channel_2_data
                }
            }
            ds.push(my_plot_data)

    """

    def __init__(
        self, timeout: float = 1, data_processing_func: Optional[Callable] = None
    ):
        """
        Args:
            timeout: Timeout for :py:meth:`~nspyre.data.sink.DataSink.pop`.
            data_processing_func: Function to do any post-processing of the data
                popped by the :py:class:`~nspyre.data.sink.DataSink`. Takes one
                argument, which is the :py:class:`~nspyre.data.sink.DataSink`.
        """
        super().__init__()

        self.heat_map = _HeatMapPlotWidget(
            timeout=timeout, data_processing_func=data_processing_func 
        )
        
        

        """Underlying LinePlotWidget."""

        # data source lineedit
        self.datasource_lineedit = QtWidgets.QLineEdit()

        # data source connect button
        connect_button = QtWidgets.QPushButton('Connect')
        connect_button.clicked.connect(self._update_source_clicked)

        # heatmap settings
        heat_map_settings_label= QtWidgets.QLabel('Heat Map Settings')
        heat_map_settings_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.heat_map_name_lineedit = QtWidgets.QLineEdit("heatmap")
        self.heat_map_series_lineedit = QtWidgets.QLineEdit("heatmap")

        show_button= QtWidgets.QPushButton('Show')
        show_button.clicked.connect(self._show_button_clicked)

        hide_button = QtWidgets.QPushButton('Hide')
        hide_button.clicked.connect(self._heat_map_selection_changed)

        update_button = QtWidgets.QPushButton('Update')
        update_button.clicked.connect(self._update_button_clicked)    

        
        # add button
        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(self._add_button_clicked)

        remove_button = QtWidgets.QPushButton('Remove')
        remove_button.clicked.connect(self._remove_button_clicked)

        heat_maps_label=QtWidgets.QLabel('Heat Maps')
        heat_maps_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.heat_maps_list_widget = QtWidgets.QListWidget()
        self.heat_maps_list_widget.currentItemChanged.connect(self._heat_map_selection_changed)

        # spacer
        fixed_spacer = QtWidgets.QLabel('')
        fixed_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
        )

        # spacer
        expanding_spacer = QtWidgets.QLabel('')
        expanding_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        # layout
        settings_layout_config = {
            'type': QtWidgets.QVBoxLayout,
            'data_source': {
                'type': QtWidgets.QHBoxLayout,
                'label': QtWidgets.QLabel('Data Set'),
                'edit': self.datasource_lineedit,
                'button': connect_button,
            },
            'config': {
                'type': QtWidgets.QHBoxLayout,
                'plot': {
                    'type': QtWidgets.QVBoxLayout,
                    'label': heat_map_settings_label,
                    'settings': {
                        'type': QtWidgets.QVBoxLayout,
                        'name': {
                            'type': QtWidgets.QHBoxLayout,
                            'label': QtWidgets.QLabel('Plot Name'),
                            'edit': self.heat_map_name_lineedit,
                        },
                        'series': {
                            'type': QtWidgets.QHBoxLayout,
                            'label': QtWidgets.QLabel('Data Series'),
                            'edit': self.heat_map_series_lineedit,
                        },
                        'spacer': expanding_spacer,
                    },
                },
                'settings_buttons': {
                    'type': QtWidgets.QVBoxLayout,
                    'spacer_t': fixed_spacer,
                    'update': update_button,
                    'add': add_button,
                    'remove': remove_button,
                    'spacer_b': expanding_spacer,
                },
                'plots': {
                    'type': QtWidgets.QVBoxLayout,
                    'label': heat_maps_label,
                    'list': self.heat_maps_list_widget,
                },
                'list_buttons': {
                    'type': QtWidgets.QVBoxLayout,
                    'spacer_t': fixed_spacer,
                    'show': show_button,
                    'hide': hide_button,
                    'spacer_b': expanding_spacer,
                },
            },

        
        }
        self.layout_tree = tree_layout(settings_layout_config)
        # make the plots list (index=2) take up all extra space (stretch=1)

        # splitter
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.heat_map)
        layout_container = QtWidgets.QWidget()
        layout_container.setLayout(self.layout_tree.layout)
        splitter.addWidget(layout_container)

        # main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(splitter)

        self.setLayout(layout)

    def _heat_map_selection_changed(self):
        selected_item = self.heat_maps_list_widget.currentItem()
        if selected_item is not None:
            return
        name = selected_item.text()
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.get_settings,
            name,
            callback=self._heat_map_selection_changed_callback,
        )

    def _heat_map_selection_changed_callback(self, name:str, settings:_HeatMapSeriesSettings):
        """Callback for when the heat map selection changes."""
        self.heat_map_name_lineedit.setText(name)
        self.heat_map_series_lineedit.setText(settings.series)

    def _get_heat_map_settings(self):
        name=self.heat_map_name_lineedit.text()
        series=self.heat_map_series_lineedit.text()
        return name, series

    def _update_button_clicked(self):
        """Called when the user clicks the update button."""
        name, series = self._get_heat_map_settings()
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.update_settings,
            name,
            series,
        )
    
    def _add_button_clicked(self):
        """Called when the user clicks the add button."""
        name, series = self._get_heat_map_settings()
        self.add_heat_map(name, series)

    def add_heat_map(self, name: str, series: str):
        """Add a new heat map plot.

        Args:
            name: Name of the new heat map plot.
            series: Data series to plot.
        """
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.add_plot,
            name,
            series,
            callback=self._add_heat_map_callback,
        )

    def _add_heat_map_callback(self, name: str):
        """Callback for when a new heat map plot is added."""
        self.heat_maps_list_widget.addItem(name)
        self.heat_map.add_heat_map(name)

    def _find_heat_map_item(self, name: str):
        """Find the heat map item with the given name."""
        list_widget_index=None
        for i in range(self.heat_maps_list_widget.count()):
            if self.heat_maps_list_widget.item(i).text() == name:
                list_widget_index = i
                break
        if list_widget_index is None:
            raise RuntimeError(
                f'Internal error: heat map [{name}] not found in list widget.'
            )

        return list_widget_index
    
    def _remove_button_clicked(self):
        """Called when the user clicks the remove button."""
        selected_item = self.heat_maps_list_widget.currentItem()
        if selected_item is None:
            _logger.warning('No heat map selected to remove.')
            return
        name = selected_item.text()
        self.remove_heat_map(name)


    def remove_heat_map(self, name: str):
        """Remove a heat map plot.

        Args:
            name: Name of the heat map plot to remove.
        """
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.remove_plot,
            name,
            callback=self._remove_heat_map_callback,
        )

    def _remove_heat_map_callback(self, name: str):
        """Callback for when a heat map plot is removed."""
        self.heat_maps_list_widget.takeItem(
            self._find_heat_map_item(name)
        )
        self.heat_map.remove_heat_map(name)

    def _show_button_clicked(self):
        """Called when the user clicks the show button."""
        selected_item = self.heat_maps_list_widget.currentItem()
        if selected_item is not None:
            name = selected_item.text()
            self.show_heat_map(name)


    def show_heat_map(self, name: str):
        """Show a heat map plot.

        Args:
            name: Name of the heat map plot to show.
        """
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.show_heatmap,
            name,
            callback=self._show_heat_map_callback,
        )


    def _show_heat_map_callback(self, name: str, settings: _HeatMapSeriesSettings):
        """Callback for when the show button is clicked."""
        self.heat_map.show_plot(name)
        idx = self._find_heat_map_item(name)
        normal_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        normal_bg_color = self.palette().color(QtGui.QPalette.ColorRole.Base)
        self.heat_maps_list_widget.item(idx).setForeground(normal_text_color)
        self.heat_maps_list_widget.item(idx).setBackground(normal_bg_color)

    def _hide_button_clicked(self):
        """Called when the user clicks the hide button."""
        selected_item = self.heat_maps_list_widget.currentItem()
        if selected_item is not None:
            name = selected_item.text()
            self.hide_heat_map(name)

    def hide_heat_map(self, name: str):
        """Hide a heat map plot.

        Args:
            name: Name of the heat map plot to hide.
        """
        self.heat_map.heat_map_settings.run_safe(
            self.heat_map.heat_map_settings.hide_heatmap,
            name,
            callback=self._hide_heat_map_callback,
        )





    def _hide_heat_map_callback(self, name: str, settings: _HeatMapSeriesSettings):
        """Callback for when the hide button is clicked."""
        self.heat_map.hide_plot(name)
        # also remove the item from the list widget
        list_widget_index = self._find_heat_map_item(name)
        self.heat_maps_list_widget.item(list_widget_index).setForeground(QtCore.Qt.GlobalColor.gray)
        self.heat_maps_list_widget.item(list_widget_index).setBackground(
            self.palette().color(QtGui.QPalette.ColorRole.Mid)
        )


    def _update_source_clicked(self):
        """Called when the user clicks the connect button."""
        self.heat_map.new_source(self.datasource_lineedit.text())


class _HeatMapPlotWidget(HeatMapWidget):
    """See HeatMapPlotWidget."""

    def __init__(self, timeout: float, colormap=pg.colormap.get('viridis')):
        """
        Args:
            timeout: see :py:class:`HeatMapPlotWidget`.
            data_processing_func: see :py:class:`HeatMapPlotWidget`.
        """
        self.timeout = timeout
        # protect access to the sink
        self.heat_map_settings = _HeatMapSettings()
        self.heat_map_settings.start()
        super().__init__(colormap=colormap)

    def _stop(self):
        self.heat_map_settings.stop()
        super()._stop()

    def new_source(self, data_set_name: str):
        """Connect to a new data set on the data server.

        Args:
            data_set_name: Name of the new data set.
        """
        # run on the plot_settings thread since we'll need to acquire mutexes
        self._new_source(data_set_name)

    def _new_source(self, data_set_name: str):
        # connect to a new data set
        with QtCore.QMutexLocker(self.sink_mutex):
            try:
                # connect to the new data source
                self.sink = DataSink(data_set_name)
                self.sink.start()

                # try to get the plot title and x/y labels
                self.sink.pop(timeout=self.timeout)

                # set title
                try:
                    title = self.sink.title
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "title" '
                        'attribute. Not setting the plot title...'
                    )
                    title = None

                # set xlabel
                try:
                    xlabel = self.sink.xlabel
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "xlabel" '
                        'attribute. Not setting the plot x-axis label...'
                    )
                    xlabel = None

                # set ylabel
                try:
                    ylabel = self.sink.ylabel
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "ylabel" '
                        'attribute. Not setting the plot y-axis label...'
                    )
                    ylabel = None

                

                # set the new title/labels in the main thread

                self._new_source_callback(title, xlabel, ylabel, blocking=True)



                # force plot the data since we used the first pop() to extract the
                # plot info
                self.force_update = True
            except (TimeoutError, RuntimeError) as err:
                self.teardown()
                raise RuntimeError(
                    f'Could not connect to new data source [{data_set_name}]'
                ) from err

    def _new_source_callback(self, title, xlabel, ylabel):
        """Callback for when a new data source connects."""
        if title is not None:
            self.plot_item.setTitle(title)
        if xlabel is not None:
            self.btm_axis.setLabel(text=xlabel)
        if ylabel is not None:
            self.lft_axis.setLabel(text=ylabel)

    def teardown(self):
        """Clean up."""
        # run on the plot_settings thread since we'll need to acquire mutexes
        self._close_source()

    def _close_source(self):
        """Disconnect from the data source."""
        with QtCore.QMutexLocker(self.sink_mutex):
            if self.sink is not None:
                self.sink.stop()
                self.sink = None

    def update(self):
        """Update the plot if there is new data available."""
        with QtCore.QMutexLocker(self.sink_mutex):
            if self.sink is None:
                # rate limit how often update() runs if there is no sink connected
                time.sleep(0.1)
                return

            if self.force_update:
                self.force_update = False
            else:
                try:
                    # wait for new data to be available from the sink
                    self.sink.pop(timeout=self.timeout)
                except TimeoutError:
                    return


            with QtCore.QMutexLocker(self.sink_mutex):

                try: 
                    xs = self.sink.xs
                except KeyError:
                    _logger.error(f'Data source has no "xs" attribute.')
                    xs= np.arange(0, 100)
                try:
                    ys = self.sink.ys
                except KeyError:
                    _logger.error(f'Data source has no "ys" attribute.')
                    ys = np.arange(0, 100)
                # pick out the particular data series
                try:
                    data = self.sink.datasets["heatmap"]
                except KeyError:
                    _logger.error(f'Data series [heatmap] does not exist.')
                    data= np.zeros((len(ys), len(xs)))

                if not isinstance(data, list):
                    raise ValueError(
                        f'Data series [heatmap] must be a list of numpy arrays, '
                        f'but has type [{type(data)}].'
                    )

                else:
                    # check for numpy array
                    if not isinstance(data[0], np.ndarray):
                        raise ValueError(
                            f'Data series [heatmap] must be a list of numpy '
                            'arrays, but the first list element has type '
                            f'[{type(data[0])}].'
                        )
                    # check numpy array shape
                    if data.shape[0] != len(ys) or data.shape[1] != len(xs):
                        raise ValueError(
                            f'Data series does not match the x and y axes '
                            f'shapes: {data.shape}, {ys.shape}, {xs.shape}'
                        )


                # update the plot
                self.set_data(xs, ys, data)
