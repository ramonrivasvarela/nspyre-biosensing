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
from pyqtgraph import InfiniteLine

_logger = logging.getLogger(__name__)

import pyqtgraph as pg


class _HeatMapSeriesSettings:
    def __init__(
        self,
        series: str,
        show: bool = False,
    ):
        self.series = series
        self.show = show

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
        callback: Optional[Callable]=None,
    ):
        with QtCore.QMutexLocker(self.mutex):
            if name in self.series_settings:
                _logger.info(
                    f'A heatmap with the name [{name}] already exists. Ignoring new_heatmap '
                    'request.'
                )
                return
            if not self.series_settings:
                self.series_settings[name] = _HeatMapSeriesSettings(
                    series=series,
                    show=True,
                )
            else: 
                self.series_settings[name] = _HeatMapSeriesSettings(
                    series=series,
                    show=False,
                )
            self.force_update = True
            if callback is not None:
                self.run_main(callback, name, blocking=True)
    
    def remove_heatmap(self, name, callback=None):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'A heatmap with the name [{name}] does not exist. Ignoring '
                    'remove_heatmap request.'
                )
                return

            if callback is not None:
                self.run_main(callback, name, blocking=True)
            # show_deleted=self.series_settings[name].show
            del self.series_settings[name]
            # if self.series_settings and show_deleted:
            #     self.series_settings[next(iter(self.series_settings))].show = True
            self.force_update = True


    def show_heatmap(self, name: str, callback: Optional[Callable]=None):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'No heatmap with the name [{name}] exists. Ignoring show_heatmap '
                    'request.'
                )
                return
            if self.series_settings[name].show:
                _logger.info(
                    f'Heatmap with the name [{name}] is already visible. Ignoring show_heatmap '
                    'request.'
                )
                return
            for current_name in self.series_settings:
                self.series_settings[current_name].show = False
            self.series_settings[name].show = True
            self.force_update = True
            if callback is not None:
                self.run_main(callback, name, blocking=True)
    
    def update_settings(
        self,
        name: str,
        series: str,
        shown: bool = False,
    ):
        with QtCore.QMutexLocker(self.mutex):
            if name not in self.series_settings:
                _logger.info(
                    f'No heatmap with the name [{name}] exists. Ignoring update_heatmap '
                    'request.'
                )
                return
            self.series_settings[name].series = series
            self.series_settings[name].show = shown
            self.force_update = True


class CrosshairManager(QtWidgets.QWidget):
    """Widget for managing multiple crosshairs."""
    
    delete_crosshair = QtCore.Signal(int)  # Signal emitted when crosshair should be deleted
    update_crosshair = QtCore.Signal(int, float, float)  # Signal emitted when crosshair position should be updated
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel("Crosshairs")
        title_label.setStyleSheet("font-weight: bold;")
        self.layout.addWidget(title_label)
        
        # Scrollable list area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.layout.addWidget(self.scroll_area)
        self.setLayout(self.layout)
        
        # Store crosshair item widgets and their line edits
        self.crosshair_items: dict[int, QtWidgets.QWidget] = {}
        self.crosshair_edits: dict[int, tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]] = {}
        
    def add_crosshair(self, crosshair_id: int, x: float, y: float):
        """Add a crosshair entry to the list."""
        item_widget = QtWidgets.QWidget()
        item_layout = QtWidgets.QHBoxLayout()
        item_layout.setContentsMargins(2, 2, 2, 2)
        
        # ID label
        id_label = QtWidgets.QLabel(f"#{crosshair_id}:")
        id_label.setMaximumWidth(30)
        item_layout.addWidget(id_label)
        
        # X coordinate edit
        x_label = QtWidgets.QLabel("X:")
        x_label.setMaximumWidth(15)
        item_layout.addWidget(x_label)
        
        x_edit = QtWidgets.QLineEdit(f"{x:.3f}")
        x_edit.setMinimumWidth(60)
        x_edit.setValidator(QtGui.QDoubleValidator())
        x_edit.editingFinished.connect(
            lambda: self._on_coordinate_changed(crosshair_id, x_edit, y_edit)
        )
        item_layout.addWidget(x_edit)
        
        # Y coordinate edit
        y_label = QtWidgets.QLabel("Y:")
        y_label.setMaximumWidth(15)
        item_layout.addWidget(y_label)
        
        y_edit = QtWidgets.QLineEdit(f"{y:.3f}")
        y_edit.setMinimumWidth(60)
        y_edit.setValidator(QtGui.QDoubleValidator())
        y_edit.editingFinished.connect(
            lambda: self._on_coordinate_changed(crosshair_id, x_edit, y_edit)
        )
        item_layout.addWidget(y_edit)
        
        # Delete button
        delete_btn = QtWidgets.QPushButton("Del")
        delete_btn.setMaximumWidth(40)
        delete_btn.clicked.connect(lambda: self.delete_crosshair.emit(crosshair_id))
        item_layout.addWidget(delete_btn)
        
        item_widget.setLayout(item_layout)
        
        # Insert before the stretch
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item_widget)
        self.crosshair_items[crosshair_id] = item_widget
        self.crosshair_edits[crosshair_id] = (x_edit, y_edit)
    
    def _on_coordinate_changed(self, crosshair_id: int, x_edit: QtWidgets.QLineEdit, y_edit: QtWidgets.QLineEdit):
        """Handle coordinate changes from line edits."""
        try:
            x = float(x_edit.text())
            y = float(y_edit.text())
            self.update_crosshair.emit(crosshair_id, x, y)
        except ValueError:
            # Invalid input, revert to previous values
            if crosshair_id in self.crosshair_edits:
                # Just keep the invalid text for now - it will be updated when the crosshair is updated
                pass
    
    def update_crosshair_display(self, crosshair_id: int, x: float, y: float):
        """Update the displayed coordinates for a crosshair."""
        if crosshair_id in self.crosshair_edits:
            x_edit, y_edit = self.crosshair_edits[crosshair_id]
            # Block signals to avoid triggering editingFinished during programmatic update
            x_edit.blockSignals(True)
            y_edit.blockSignals(True)
            x_edit.setText(f"{x:.3f}")
            y_edit.setText(f"{y:.3f}")
            x_edit.blockSignals(False)
            y_edit.blockSignals(False)
        
    def remove_crosshair(self, crosshair_id: int):
        """Remove a crosshair entry from the list."""
        if crosshair_id in self.crosshair_items:
            widget = self.crosshair_items[crosshair_id]
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()
            del self.crosshair_items[crosshair_id]
            del self.crosshair_edits[crosshair_id]
    
    def clear_all(self):
        """Remove all crosshair entries."""
        for crosshair_id in list(self.crosshair_items.keys()):
            self.remove_crosshair(crosshair_id)



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
                'title': 'MyVoltagePflot',
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
        self, timeout: float = 1, data_processing_func: Optional[Callable] = None, 
        crosshair_func=None
    ):
        """
        Args:
            timeout: Timeout for :py:meth:`~nspyre.data.sink.DataSink.pop`.
            data_processing_func: Function to do any post-processing of the data
                popped by the :py:class:`~nspyre.data.sink.DataSink`. Takes one
                argument, which is the :py:class:`~nspyre.data.sink.DataSink`.
        """
        super().__init__()
        self.crosshair_func=crosshair_func
        self.heatmap = _HeatMapPlotWidget(
            timeout=timeout, data_processing_func=data_processing_func 
        )
        
        

        """Underlying LinePlotWidget."""

        # data source lineedit
        self.datasource_lineedit = QtWidgets.QLineEdit()

        # data source connect button
        connect_button = QtWidgets.QPushButton('Connect')
        connect_button.clicked.connect(self._update_source_clicked)

        # heatmap settings
        heatmap_settings_label= QtWidgets.QLabel('Heat Map Settings')
        heatmap_settings_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.heatmap_name_lineedit = QtWidgets.QLineEdit("")
        self.heatmap_series_lineedit = QtWidgets.QLineEdit("")

        show_button= QtWidgets.QPushButton('Show')
        show_button.clicked.connect(self._show_button_clicked)

        update_button = QtWidgets.QPushButton('Update')
        update_button.clicked.connect(self._update_button_clicked)    

        remove_button = QtWidgets.QPushButton('Remove')
        remove_button.clicked.connect(self._remove_button_clicked)
        # add button
        add_button = QtWidgets.QPushButton('Add')
        add_button.clicked.connect(self._add_button_clicked)

        heatmaps_label=QtWidgets.QLabel('Heat Maps')
        heatmaps_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.heatmaps_list_widget = QtWidgets.QListWidget()
        self.heatmaps_list_widget.currentItemChanged.connect(self._heatmap_selection_changed)

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
                    'label': heatmap_settings_label,
                    'settings': {
                        'type': QtWidgets.QVBoxLayout,
                        'name': {
                            'type': QtWidgets.QHBoxLayout,
                            'label': QtWidgets.QLabel('Plot Name'),
                            'edit': self.heatmap_name_lineedit,
                        },
                        'series': {
                            'type': QtWidgets.QHBoxLayout,
                            'label': QtWidgets.QLabel('Data Series'),
                            'edit': self.heatmap_series_lineedit,
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
                    'label': heatmaps_label,
                    'list': self.heatmaps_list_widget,
                },
                'list_buttons': {
                    'type': QtWidgets.QVBoxLayout,
                    'spacer_t': fixed_spacer,
                    'show': show_button,
                    'spacer_b': expanding_spacer,
                },
            },

        
        }
        # Create crosshair controls AFTER defining the layout config
        # or use a regular layout instead of tree_layout

        # Option 1: Use regular layout (simpler and clearer)
        crosshair_top_widget = QtWidgets.QWidget()
        crosshair_top_layout = QtWidgets.QHBoxLayout()
        crosshair_top_layout.setContentsMargins(0, 0, 0, 0)
        crosshair_top_layout.setSpacing(4)

        self.crosshair_button = QtWidgets.QPushButton("Enable Crosshair")
        self.crosshair_button.setCheckable(True)
        self.crosshair_button.clicked.connect(self._toggle_crosshair)

        self.clear_all_button = QtWidgets.QPushButton("Clear All")
        self.clear_all_button.clicked.connect(self._clear_all_crosshairs)

        self.position_label = QtWidgets.QLabel("")
        self.position_label.setStyleSheet("background-color: rgba(255, 255, 255, 200); padding: 5px; border-radius: 3px;")
        self.position_label.hide()

        # Add all widgets to the layout
        crosshair_top_layout.addWidget(self.crosshair_button)
        crosshair_top_layout.addWidget(self.clear_all_button)
        crosshair_top_layout.addWidget(self.position_label)
        crosshair_top_layout.addStretch()  # Push widgets to the left

        crosshair_top_widget.setLayout(crosshair_top_layout)

        # Then later use it:
        # heatmap_with_crosshair_layout.addWidget(crosshair_top_widget)
        # Crosshair management
        self.crosshair_enabled = False

        self.crosshairs: dict[int, tuple[InfiniteLine, InfiniteLine]] = {}
        self.next_crosshair_id = 0
        
        # Temporary crosshair lines (shown during mouse movement)
        self.crosshair_v = InfiniteLine(angle=90, movable=False, pen='y')
        self.crosshair_h = InfiniteLine(angle=0, movable=False, pen='y')
        
        # Dragging state
        self.dragging_enabled=False
        self.dragging_crosshair_id = None
        self.drag_start_pos = None
        
        # Right side: crosshair manager panel
        self.crosshair_manager = CrosshairManager()
        self.crosshair_manager.delete_crosshair.connect(self._delete_crosshair)
        self.crosshair_manager.update_crosshair.connect(self._update_crosshair_position)
        
        self.layout_tree = tree_layout(settings_layout_config)
        # make the plots list (index=2) take up all extra space (stretch=1)
        heatmap_with_crosshair_layout=QtWidgets.QVBoxLayout()
        heatmap_with_crosshair_layout.setContentsMargins(0, 0, 0, 0)
        heatmap_with_crosshair_layout.setSpacing(2)
        heatmap_with_crosshair=QtWidgets.QWidget()

        crosshair_top_container=QtWidgets.QWidget()
        heatmap_with_crosshair_layout.addWidget(crosshair_top_widget)
        heatmap_with_crosshair_layout.addWidget(self.heatmap)
        heatmap_with_crosshair.setLayout(heatmap_with_crosshair_layout)
        self.crosshair_splitter = QtWidgets.QSplitter()
        self.crosshair_splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.crosshair_splitter.addWidget(heatmap_with_crosshair)
        self.crosshair_splitter.addWidget(self.crosshair_manager)
        self.crosshair_splitter.setCollapsible(0, False)
        self.crosshair_splitter.setCollapsible(1, True)
        self.crosshair_splitter.setSizes([1, 0])
        QtCore.QTimer.singleShot(
            0, lambda: self.crosshair_splitter.setSizes([1, 0])
        )
        # splitter
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.crosshair_splitter)
        layout_container = QtWidgets.QWidget()
        layout_container.setLayout(self.layout_tree.layout)
        splitter.addWidget(layout_container)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        bottom_min_height = max(1, layout_container.minimumSizeHint().height())

        def _maximize_heatmap_area():
            total_height = splitter.size().height()
            if total_height <= 0:
                splitter.setSizes([1, bottom_min_height])
                return
            splitter.setSizes([max(1, total_height - bottom_min_height), bottom_min_height])

        QtCore.QTimer.singleShot(0, _maximize_heatmap_area)

        # main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(splitter)

        self.setLayout(layout)

        # Enable keyboard focus to capture key events
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # Always connect mouse events for dragging (outside of crosshair placement mode)
        self.heatmap.plot_item.scene().sigMouseClicked.connect(self._on_click_drag)
        self.heatmap.plot_item.scene().sigMouseMoved.connect(self._on_mouse_move_drag)

    def _heatmap_selection_changed(self):
        selected_item = self.heatmaps_list_widget.currentItem()
        if selected_item is None:
            return
        name = selected_item.text()
        self.heatmap.heatmap_settings.run_safe(
            self.heatmap.heatmap_settings.get_settings,
            name,
            callback=self._heatmap_selection_changed_callback,
        )

    def _heatmap_selection_changed_callback(self, name:str, settings:_HeatMapSeriesSettings):
        """Callback for when the heat map selection changes."""
        self.heatmap_name_lineedit.setText(name)
        self.heatmap_series_lineedit.setText(settings.series)

    def _get_heatmap_settings(self):
        name=self.heatmap_name_lineedit.text()
        series=self.heatmap_series_lineedit.text()
        return name, series

    def _update_button_clicked(self):
        """Called when the user clicks the update button."""
        name, series = self._get_heatmap_settings()
        self.heatmap.heatmap_settings.run_safe(
            self.heatmap.heatmap_settings.update_settings,
            name,
            series,
        )
    
    def _add_button_clicked(self):
        """Called when the user clicks the add button."""
        name, series = self._get_heatmap_settings()
        self.add_heatmap(name, series)

    def add_heatmap(self, name: str, series: str):
        """Add a new heat map plot.

        Args:
            name: Name of the new heat map plot.
            series: Data series to plot.
        """
        self.heatmap.heatmap_settings.run_safe(
            self.heatmap.heatmap_settings.new_heatmap,
            name,
            series,
            callback=self._add_heatmap_callback,
        )
        

    def _add_heatmap_callback(self, name: str):
        """Callback for when a new heat map plot is added."""
        self.heatmaps_list_widget.addItem(name)


    def _find_heatmap_item(self, name: str):
        """Find the heat map item with the given name."""
        list_widget_index=None
        for i in range(self.heatmaps_list_widget.count()):
            if self.heatmaps_list_widget.item(i).text() == name:
                list_widget_index = i
                break
        if list_widget_index is None:
            raise RuntimeError(
                f'Internal error: heat map [{name}] not found in list widget.'
            )

        return list_widget_index
    
    def _remove_button_clicked(self):
        """Called when the user clicks the remove button."""
        # array of selected QListWidgetItems
        selected_item = self.heatmaps_list_widget.currentItem()
        if selected_item is not None:
            name = selected_item.text()
            self.remove_heatmap(name)

    def remove_heatmap(self, name: str):
        """Remove a heat map. Thread safe.

        Args:
            name: Name of the heat map.
        """
        # remove the plot settings
        self.heatmap.heatmap_settings.run_safe(
            self.heatmap.heatmap_settings.remove_heatmap,
            name,
            callback=self._remove_heatmap_callback,
        )
    

    def _remove_heatmap_callback(self, name: str):
        """Called in main thread after a heat map is removed."""
        # remove the heat map name from the list of heat maps
        self.heatmaps_list_widget.takeItem(self._find_heatmap_item(name))
        # remove the heat map from the pyqtgraph plotwidget
        self.heatmap.heatmap_settings.series_settings[name].show = False
        first_index=next(iter(self.heatmap.heatmap_settings.series_settings))

    def _show_button_clicked(self):
        """Called when the user clicks the show button."""
        selected_item = self.heatmaps_list_widget.currentItem()
        if selected_item is not None:
            name = selected_item.text()
            self.show_heatmap(name)


    def show_heatmap(self, name: str):
        """Show a heat map plot.

        Args:
            name: Name of the heat map plot to show.
        """
        self.heatmap.heatmap_settings.run_safe(
            self.heatmap.heatmap_settings.show_heatmap,
            name,
            callback=self._show_heatmap_callback,
        )


    def _show_heatmap_callback(self, name: str):
        """Callback for when the show button is clicked."""
        for series_name in self.heatmap.heatmap_settings.series_settings:
            self.heatmap.heatmap_settings.series_settings[series_name].show = False
        self.heatmap.heatmap_settings.series_settings[name].show = True
        idx = self._find_heatmap_item(name)
        normal_text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        normal_bg_color = self.palette().color(QtGui.QPalette.ColorRole.Base)
        self.heatmaps_list_widget.item(idx).setForeground(normal_text_color)
        self.heatmaps_list_widget.item(idx).setBackground(normal_bg_color)




    def _update_source_clicked(self):
        """Called when the user clicks the connect button."""
        self.heatmap.new_source(self.datasource_lineedit.text())

    # Crosshair functions 

    
    def _toggle_crosshair(self, checked):
        """Toggle crosshair mode on/off."""
        if checked:
            self.crosshair_button.setText("Disable Crosshair")
            self.crosshair_enabled = True
            # Show live position label
            self.position_label.show()
            # Add temporary crosshair lines to the plot
            self.heatmap.plot_item.addItem(self.crosshair_v)
            self.heatmap.plot_item.addItem(self.crosshair_h)
            # Connect mouse move and click events
            self.heatmap.plot_item.scene().sigMouseMoved.connect(self._on_mouse_move)
            self.heatmap.plot_item.scene().sigMouseClicked.connect(self._on_click)
        else:
            self.crosshair_button.setText("Enable Crosshair")
            self.crosshair_enabled = False
            # Hide live position label
            self.position_label.hide()
            # Remove temporary crosshair lines from the plot
            self.heatmap.plot_item.removeItem(self.crosshair_v)
            self.heatmap.plot_item.removeItem(self.crosshair_h)
            # Disconnect mouse events
            try:
                self.heatmap.plot_item.scene().sigMouseMoved.disconnect(self._on_mouse_move)
                self.heatmap.plot_item.scene().sigMouseClicked.disconnect(self._on_click)
            except TypeError:
                pass  # Already disconnected
    
    def _on_mouse_move(self, pos):
        """Update crosshair position when mouse moves."""
        if not self.crosshair_enabled:
            return
            
        # Convert scene coordinates to data coordinates
        if self.heatmap.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.heatmap.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            # Update temporary crosshair positions
            self.crosshair_v.setPos(x)
            self.crosshair_h.setPos(y)
            # Update live position label
            self.position_label.setText(f"Position: X={x:.3f}, Y={y:.3f}")
    
    def _find_nearest_crosshair(self, x: float, y: float, threshold: float = 0.05) -> int:
        """Find the nearest crosshair to the given position.
        
        Args:
            x: X coordinate in data space
            y: Y coordinate in data space
            threshold: Maximum distance (as fraction of axis range) to consider a crosshair as "near"
            
        Returns:
            Crosshair ID if found within threshold, None otherwise
        """
        if not self.crosshairs:
            return None
            
        # Get axis ranges for normalized distance calculation
        x_range = self.heatmap.plot_item.viewRange()[0]
        y_range = self.heatmap.plot_item.viewRange()[1]
        x_span = x_range[1] - x_range[0]
        y_span = y_range[1] - y_range[0]
        
        min_distance = float('inf')
        nearest_id = None
        
        for crosshair_id, (v_line, h_line) in self.crosshairs.items():
            cx = v_line.value()
            cy = h_line.value()
            
            # Normalized distance
            dx = (x - cx) / x_span if x_span != 0 else 0
            dy = (y - cy) / y_span if y_span != 0 else 0
            distance = (dx**2 + dy**2)**0.5
            
            if distance < min_distance and distance < threshold:
                min_distance = distance
                nearest_id = crosshair_id
        
        return nearest_id
    
    def _on_click_drag(self, event):
        """Handle mouse clicks for dragging crosshairs (when not in placement mode)."""
        if self.crosshair_enabled:
            return  # Let the placement handler deal with it
            
        if event.double():
            return  # Ignore double clicks
            
        # Get the click position
        scene_pos = event.scenePos()
        if self.heatmap.plot_item.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.heatmap.plot_item.vb.mapSceneToView(scene_pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                # If already dragging, stop dragging on next click
                if self.dragging_crosshair_id is not None:
                    print(f"Stopped dragging crosshair #{self.dragging_crosshair_id}")
                    self.dragging_crosshair_id = None
                    self.drag_start_pos = None
                else:
                    # Not dragging, check if clicked near a crosshair to start dragging
                    nearest_id = self._find_nearest_crosshair(x, y)
                    
                    if nearest_id is not None:
                        # Start dragging this crosshair
                        self.dragging_crosshair_id = nearest_id
                        self.drag_start_pos = (x, y)
                        print(f"Started dragging crosshair #{nearest_id}")
            elif event.button() == QtCore.Qt.MouseButton.RightButton:
                # Right click always stops dragging
                if self.dragging_crosshair_id is not None:
                    print(f"Cancelled dragging crosshair #{self.dragging_crosshair_id}")
                self.dragging_crosshair_id = None
                self.drag_start_pos = None
    
    def _on_mouse_move_drag(self, pos):
        """Handle mouse movement for dragging crosshairs."""
        if self.crosshair_enabled or self.dragging_crosshair_id is None:
            return  # Not dragging or in placement mode
            
        # Convert scene coordinates to data coordinates
        if self.heatmap.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.heatmap.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # Update the crosshair position
            self._update_crosshair_position(self.dragging_crosshair_id, x, y)
    
    def _on_click(self, event):
        """Handle mouse click events on the plot."""
        if not self.crosshair_enabled or event.double():
            return  # Ignore if crosshair disabled or double clicks
            
        # Get the click position in the scene
        scene_pos = event.scenePos()
        # Convert scene coordinates to data coordinates
        if self.heatmap.plot_item.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.heatmap.plot_item.vb.mapSceneToView(scene_pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # Add a permanent crosshair at this position
            self._add_permanent_crosshair(x, y)
            
            print(f"Added crosshair at x: {x:.3f}, y: {y:.3f}")
            
            # Call the optional callback function if provided
            if self.crosshair_func is not None:
                try:
                    self.crosshair_func(x, y)
                except Exception as e:
                    print(f"Error calling crosshair callback function: {e}")
    
    def _add_permanent_crosshair(self, x: float, y: float):
        """Add a permanent crosshair at the specified position."""
        crosshair_id = self.next_crosshair_id
        self.next_crosshair_id += 1
        
        # Create new crosshair lines with a different color for each
        colors = ['r', 'g', 'b', 'c', 'm', 'w']
        color = colors[crosshair_id % len(colors)]
        
        v_line = InfiniteLine(angle=90, movable=False, pen=color)
        h_line = InfiniteLine(angle=0, movable=False, pen=color)
        
        v_line.setPos(x)
        h_line.setPos(y)
        
        # Add to plot
        self.heatmap.plot_item.addItem(v_line)
        self.heatmap.plot_item.addItem(h_line)
        
        # Store crosshair
        self.crosshairs[crosshair_id] = (v_line, h_line)
        
        # Add to manager panel
        self.crosshair_manager.add_crosshair(crosshair_id, x, y)
        self._toggle_crosshair(False)
        self.crosshair_button.setChecked(False)
    
    def _update_crosshair_position(self, crosshair_id: int, x: float, y: float):
        """Update the position of an existing crosshair."""
        if crosshair_id in self.crosshairs:
            v_line, h_line = self.crosshairs[crosshair_id]
            
            # Update line positions
            v_line.setPos(x)
            h_line.setPos(y)
            
            # Update display in manager (in case it was changed programmatically)
            self.crosshair_manager.update_crosshair_display(crosshair_id, x, y)
            
            # Only print when not dragging (to avoid spam)
            if self.dragging_crosshair_id != crosshair_id:
                print(f"Updated crosshair #{crosshair_id} to ({x:.3f}, {y:.3f})")
            
            # Call the optional callback function if provided
            if self.crosshair_func is not None:
                try:
                    self.crosshair_func(x, y)
                except Exception as e:
                    print(f"Error calling crosshair callback function: {e}")
    
    def _delete_crosshair(self, crosshair_id: int):
        """Delete a specific crosshair."""
        if crosshair_id in self.crosshairs:
            v_line, h_line = self.crosshairs[crosshair_id]
            
            # Remove from plot
            self.heatmap.plot_item.removeItem(v_line)
            self.heatmap.plot_item.removeItem(h_line)
            
            # Remove from storage
            del self.crosshairs[crosshair_id]
            
            # Remove from manager panel
            self.crosshair_manager.remove_crosshair(crosshair_id)
            
            print(f"Deleted crosshair #{crosshair_id}")
    
    def _clear_all_crosshairs(self):
        """Clear all permanent crosshairs."""
        for crosshair_id in list(self.crosshairs.keys()):
            self._delete_crosshair(crosshair_id)
        print("Cleared all crosshairs")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == QtCore.Qt.Key.Key_Escape and self.crosshair_enabled:
            # Exit crosshair mode when Escape is pressed
            self.crosshair_button.setChecked(False)
            self._toggle_crosshair(False)
        elif event.key() == QtCore.Qt.Key.Key_Escape and self.dragging_crosshair_id is not None:
            # Cancel dragging when Escape is pressed
            print(f"Cancelled dragging crosshair #{self.dragging_crosshair_id}")
            self.dragging_crosshair_id = None
            self.drag_start_pos = None
        elif event.key() == QtCore.Qt.Key.Key_C:
            # Toggle crosshair mode when C is pressed
            self.crosshair_button.setChecked(not self.crosshair_enabled)
            self._toggle_crosshair(not self.crosshair_enabled)
        else:
            super().keyPressEvent(event)

    



class _HeatMapPlotWidget(HeatMapWidget):
    """See HeatMapPlotWidget."""

    def __init__(self, timeout: float, data_processing_func:Optional[Callable], colormap=pg.colormap.get('viridis')):
        """
        Args:
            timeout: see :py:class:`HeatMapPlotWidget`.
            data_processing_func: see :py:class:`HeatMapPlotWidget`.
        """
        self.timeout = timeout
        # protect access to the sink
        self.heatmap_settings = _HeatMapSettings()
        self.heatmap_settings.start()
        self.data_processing_func = data_processing_func
        super().__init__(colormap=colormap)


    def _stop(self):
        self.heatmap_settings.stop()
        super()._stop()

    def new_source(self, data_set_name: str):
        """Connect to a new data set on the data server.

        Args:
            data_set_name: Name of the new data set.
        """
        # run on the plot_settings thread since we'll need to acquire mutexes
        self.heatmap_settings.run_safe(self._new_source, data_set_name)

    def _new_source(self, data_set_name: str):
        # connect to a new data set
        

        
        with QtCore.QMutexLocker(self.heatmap_settings.sink_mutex):
            try:
                if self.heatmap_settings.sink is not None:
                    self.heatmap_settings.sink.stop()
                    self.heatmap_settings.sink = None
                self.heatmap_settings.sink = DataSink(data_set_name)
                
                    
                self.heatmap_settings.sink.start()

                # ② try to grab the first packet (may timeout)
                self.heatmap_settings.sink.pop(timeout=self.timeout)

                # ③ swap it in under a *short* critical section

                # old_sink, self.heatmap_settings.sink = self.heatmap_settings.sink, sink
                # if old_sink:
                #     old_sink.stop()

                # set title
                try:
                    title = self.heatmap_settings.sink.title
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "title" '
                        'attribute. Not setting the plot title...'
                    )
                    title = None

                # set xlabel
                try:
                    xlabel = self.heatmap_settings.sink.xlabel
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "xlabel" '
                        'attribute. Not setting the plot x-axis label...'
                    )
                    xlabel = None

                # set ylabel
                try:
                    ylabel = self.heatmap_settings.sink.ylabel
                except AttributeError:
                    _logger.info(
                        f'Data source [{data_set_name}] has no "ylabel" '
                        'attribute. Not setting the plot y-axis label...'
                    )
                    ylabel = None

                try:
                    xs = self.heatmap_settings.sink.xs
                except AttributeError:
                    raise RuntimeError(
                        f'Data source [{data_set_name}] has no "xs" '
                        'attribute. Exiting...'
                    )
                else: 
                    if not isinstance(xs, np.ndarray):
                        raise RuntimeError(
                            f'Data source [{data_set_name}] "xs" attribute must be a '
                            f'numpy array, but has type [{type(xs)}]. Exiting...'
                        )
                try:
                    ys = self.heatmap_settings.sink.ys
                except AttributeError:
                    raise RuntimeError(
                        f'Data source [{data_set_name}] has no "ys" '
                        'attribute. Exiting...'
                    )
                else:
                    if not isinstance(ys, np.ndarray):
                        raise RuntimeError(
                            f'Data source [{data_set_name}] "ys" attribute must be a '
                            f'numpy array, but has type [{type(ys)}]. Exiting...'
                        )
                    
                try:
                    data = self.heatmap_settings.sink.datasets
                except KeyError:
                    _logger.error(f'Data series does not exist.')
                    data= np.zeros((len(ys), len(xs)))

                if not isinstance(data, dict):
                    raise ValueError(
                        f'Data series must be a dictionary of numpy arrays, '
                        f'but has type [{type(data)}].'
                    )
            

                # set the new title/labels in the main thread
                self.heatmap_settings.run_main(
                    self._new_source_callback,
                    title,
                    xlabel,
                    ylabel,
                )

                with QtCore.QMutexLocker(self.heatmap_settings.mutex):
                    for plot_name in self.heatmap_settings.series_settings:
                        settings = self.heatmap_settings.series_settings[plot_name]
                        if settings.show:
                            if settings.series in data:
                                try:
                                    self.set_data(xs, ys, np.array(data[settings.series]))
                                    self._process_data()
                                except Exception as e:
                                    _logger.error(
                                        f'Error processing data for heatmap [{plot_name}]: {e}. '
                                        f'Type is {type(data[settings.series])}.'
                                    )
                            else:
                                print("Heatmap series not found in data source:", settings.series)




                # force plot the data since we used the first pop() to extract the
                # plot info
                self.heatmap_settings.force_update = True
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
        with QtCore.QMutexLocker(self.heatmap_settings.sink_mutex):
            if self.heatmap_settings.sink is not None:
                self.heatmap_settings.sink.stop()
                self.heatmap_settings.sink = None

    def update(self):
        """Update the plot if there is new data available."""
        with QtCore.QMutexLocker(self.heatmap_settings.sink_mutex):
            # Check if we need to force update even without a sink
            
            if self.heatmap_settings.sink is None:
                time.sleep(0.1)
                return

            if self.heatmap_settings.force_update:
                self.heatmap_settings.force_update = False
            else:
                try:
                    # wait for new data to be available from the sink
                    self.heatmap_settings.sink.pop(timeout=self.timeout)
                except TimeoutError:
                    return

            if self.data_processing_func is not None:
                self.data_processing_func(self.heatmap_settings.sink)

            self._update_display()

    def _update_display(self):
        """Update the heatmap display based on current settings."""
        with QtCore.QMutexLocker(self.heatmap_settings.mutex):
            for heatmap_name in self.heatmap_settings.series_settings:
                settings=self.heatmap_settings.series_settings[heatmap_name]
                series=settings.series
                show=settings.show
                if show:
                    if self.heatmap_settings.sink is not None:
                        try: 
                            xs = self.heatmap_settings.sink.xs
                        except (KeyError, AttributeError):
                            _logger.error(f'Data source has no "xs" attribute.')
                            xs= np.arange(0, 100)
                        try:
                            ys = self.heatmap_settings.sink.ys
                        except (KeyError, AttributeError):
                            _logger.error(f'Data source has no "ys" attribute.')
                            ys = np.arange(0, 100)
                        # pick out the particular data series
                        try:
                            data = self.heatmap_settings.sink.datasets
                        except (KeyError, AttributeError):
                            _logger.error(f'Data series does not exist.')
                            data= {series: np.zeros((len(ys), len(xs)))}

                        if not isinstance(data, dict):
                            raise ValueError(
                                f'Data series must be a dictionary of numpy arrays, '
                                f'but has type [{type(data)}].'
                            )

                        if series in data:
                            # check for numpy array
                            if isinstance(data[series], np.ndarray) and len(data[series]) > 0:
                                if not isinstance(data[series][0], np.ndarray):
                                    raise ValueError(
                                        f'Data series [{series}] must be a list of numpy '
                                        'arrays, but the first list element has type '
                                        f'[{type(data[series][0])}].'
                                    )
                                # Use the first array in the list
                                plot_data = np.array(data[series])
                            else:
                                plot_data = np.array(data[series])

                            # check numpy array shape
                            if plot_data.shape[0] != len(ys) or plot_data.shape[1] != len(xs):
                                _logger.warning(
                                    f'Data series shape mismatch: {plot_data.shape} vs expected ({len(ys)}, {len(xs)})'
                                )
                                # Try to resize or use what we have
                                if plot_data.size > 0:
                                    try:
                                        self.set_data(xs, ys, plot_data)
                                        self._process_data()
                                    except Exception as e:
                                        _logger.error(
                                            f'Error processing data for heatmap [{heatmap_name}]: {e}. '
                                            f'Type is {type(plot_data)}.'
                                        )
                            else:
                                try:
                                    self.set_data(xs, ys, plot_data)
                                    self._process_data()
                                except Exception as e:
                                    _logger.error(
                                        f'Error processing data for heatmap [{heatmap_name}]: {e}. '
                                        f'Type is {type(plot_data)}.'
                                    )
                    else:
                        # No sink available, but we still want to update display (e.g., show/hide)
                        _logger.debug(f'No data source available for heatmap [{heatmap_name}]')
                        # Optionally clear the display or show a placeholder
                        break  # Exit after first shown heatmap when no sink

    # Crosshair management methods

