from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QWidget)

from ..util import ftime, strtoms


class FootgasOptionsWidget(QWidget):
    sourceSelected = pyqtSignal(str)
    save = pyqtSignal(str)
    overrideStartChanged = pyqtSignal(int)
    overrideEndChanged = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()

        self.last_safe_max_size = '8'
        self.manual_set = False

        self.populate()

    def populate(self):
        # Select source/save buttons
        self.w_video_select = QPushButton('Select source')
        self.w_video_select.clicked.connect(self._set_source)

        self.w_save = QPushButton('Save clip')
        self.w_save.setEnabled(False)
        self.w_save.clicked.connect(self._save)

        start_label = QLabel()
        start_label.setText('Start:')
        self.w_override_start = QLineEdit()
        self.w_override_start.setToolTip('Start time')
        self.w_override_start.setEnabled(False)
        self.w_override_start.textChanged.connect(self._update_override_start)

        end_label = QLabel()
        end_label.setText('End:')
        self.w_override_end = QLineEdit()
        self.w_override_end.setToolTip('End time')
        self.w_override_end.setEnabled(False)
        self.w_override_end.textChanged.connect(self._update_override_end)

        max_size_label = QLabel()
        max_size_label.setText('Max filesize (MB):')
        self.w_max_size = QLineEdit()
        self.w_max_size.setToolTip('Max filesize (MB)')
        self.w_max_size.setText(self.last_safe_max_size)
        self.w_max_size.textChanged.connect(self._validate_max_file_size)

        self.w_resolution = QComboBox()
        self.w_resolution.addItem('1920x1080')
        self.w_resolution.addItem('1280x720')
        self.w_resolution.addItem('640x480')
        self.w_resolution.setCurrentIndex(1)

        self.w_fps = QComboBox()
        self.w_fps.addItem('144FPS')
        self.w_fps.addItem('60FPS')
        self.w_fps.addItem('30FPS')
        self.w_fps.addItem('24FPS')
        self.w_fps.setCurrentIndex(2)

        audio_bitrate_label = QLabel()
        audio_bitrate_label.setText('Audio bitrate:')
        self.w_audio_bitrate = QComboBox()
        self.w_audio_bitrate.addItem('64kbps')
        self.w_audio_bitrate.addItem('128kbps')
        self.w_audio_bitrate.addItem('256kbps')
        self.w_audio_bitrate.setCurrentIndex(1)

        options_box = QHBoxLayout()
        options_box.addWidget(self.w_video_select)
        options_box.addWidget(self.w_save)
        options_box.addWidget(start_label)
        options_box.addWidget(self.w_override_start)
        options_box.addWidget(end_label)
        options_box.addWidget(self.w_override_end)
        options_box.addWidget(self.w_resolution)
        options_box.addWidget(self.w_fps)
        options_box.addWidget(audio_bitrate_label)
        options_box.addWidget(self.w_audio_bitrate)
        options_box.addWidget(max_size_label)
        options_box.addWidget(self.w_max_size)

        self.setLayout(options_box)

    def setEnabled(self, enabled: bool) -> None:
        self.w_save.setEnabled(enabled)
        self.w_override_start.setEnabled(enabled)
        self.w_override_end.setEnabled(enabled)

    def setStart(self, start: int) -> None:
        time = ftime(start)
        self.manual_set = True
        self.w_override_start.setText(time)

    def setEnd(self, end: int) -> None:
        time = ftime(end)
        self.manual_set = True
        self.w_override_end.setText(time)

    def maxFileSize(self) -> int:
        return int(self.w_max_size.text())

    def resolution(self) -> str:
        return self.w_resolution.currentText()

    def fps(self) -> int:
        return int(self.w_fps.currentText()[:-3])

    def audioBitrate(self) -> int:
        return int(self.w_audio_bitrate.currentText()[:-4])

    def _set_source(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Select clip source')
        if not fn:
            return

        self.sourceSelected.emit(fn)

    def _save(self):
        out_fn, _ = QFileDialog.getSaveFileName(
            self,
            'Select save destination',
            filter='*.mp4',
        )
        if not out_fn:
            return

        self.save.emit(out_fn)

    def _update_override_start(self):
        if self.manual_set:
            self.manual_set = False
            return

        start_ms = strtoms(self.w_override_start.text())
        if start_ms is None:
            return

        self.overrideStartChanged.emit(start_ms)

    def _update_override_end(self):
        if self.manual_set:
            self.manual_set = False
            return

        end_ms = strtoms(self.w_override_end.text())
        if end_ms is None:
            return

        self.overrideEndChanged.emit(end_ms)

    def _validate_max_file_size(self):
        # only allow integers
        try:
            self.last_safe_max_size = int(self.w_max_size.text())
        except ValueError:
            self.w_max_size.setText(self.last_safe_max_size[:-1])
