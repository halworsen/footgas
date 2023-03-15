from PyQt6.QtCore import Qt, QThread, QUrl
from PyQt6.QtWidgets import QHBoxLayout, QProgressBar, QVBoxLayout, QWidget
from superqt import QRangeSlider

from .util import ftime
from .widgets.footgas_options import FootgasOptionsWidget
from .widgets.video_player import VideoPlayerWidget
from .worker import SaveWorker


class Footgas(QWidget):
    APP_TITLE = 'footgas{ext}'
    DEFAULT_SIZE = (1280, 720)

    def __init__(self):
        super().__init__()

        self.source_file = ''
        self.clip_start = 0
        self.clip_end = 0

        self.setWindowTitle(self.APP_TITLE.format(ext=''))
        self.populate()

        size = self.screen().size()
        # on my system at least. ymmv /shrug
        controls_height = 183
        self.resize(size.width() // 2, size.height() // 2 + controls_height)

    def populate(self):
        # Video player
        self.w_video_player = VideoPlayerWidget()
        self.w_video_player.durationChanged.connect(
            self._video_duration_changed
        )
        self.w_video_player.videoDropped.connect(self._set_source)
        self.w_video_player.setEnabled(False)

        # Options
        self.w_options = FootgasOptionsWidget()
        self.w_options.sourceSelected.connect(self._set_source)
        self.w_options.save.connect(self._save)
        self.w_options.overrideStartChanged.connect(self._set_clip_start)
        self.w_options.overrideEndChanged.connect(self._set_clip_end)
        self.w_options.startNowClicked.connect(self._set_clip_start)
        self.w_options.endNowClicked.connect(self._set_clip_end)
        self.w_options.setEnabled(False)

        # Clip range control
        self.w_clip_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.w_clip_range.setRange(0, 100)
        self.w_clip_range.setValue((0, 100))
        self.w_clip_range.valueChanged.connect(self._change_clip_range)
        self.w_clip_range.setEnabled(False)

        # wrap in another widget to get margins
        layout = QHBoxLayout()
        layout.addWidget(self.w_clip_range)
        clip_range_widget = QWidget()
        clip_range_widget.setLayout(layout)

        # Save progress bar
        self.w_progress = QProgressBar()
        self.w_progress.setRange(0, 100)
        self.w_progress.setValue(0)

        layout = QHBoxLayout()
        layout.addWidget(self.w_progress)
        progress_widget = QWidget()
        progress_widget.setLayout(layout)

        vbox = QVBoxLayout()
        vbox.addWidget(self.w_video_player, stretch=1)
        vbox.addWidget(clip_range_widget)
        vbox.addWidget(self.w_options)
        vbox.addWidget(progress_widget)

        self.setLayout(vbox)

    def _set_clip_start(self, start: int = -1):
        '''
        Set the start time of the clip
        '''
        if start == -1:
            start = self.w_video_player.position()
        self.clip_start = start
        self.w_video_player.setRange(self.clip_start, self.clip_end)
        self.w_options.setStart(start)
        self.w_clip_range.setValue((start, self.clip_end))

        # When changing the clip start position, always restart the clip
        self.w_video_player.setPosition(self.clip_start)

    def _set_clip_end(self, end: int = -1):
        '''
        Set the end time of the clip
        '''
        if end == -1:
            end = self.w_video_player.position()
        self.clip_end = end
        self.w_video_player.setRange(self.clip_start, self.clip_end)
        self.w_options.setEnd(end)
        self.w_clip_range.setValue((self.clip_start, end))

    def _set_source(self, filename: str):
        self.source_file = filename
        self.setWindowTitle(self.APP_TITLE.format(ext=f' - {filename}'))

        url = QUrl.fromLocalFile(filename)
        self.w_video_player.setSource(url)

        self._set_clip_start(0)
        self._set_clip_end(self.w_video_player.duration())

        self.w_video_player.setEnabled(True)
        self.w_options.setEnabled(True)
        self.w_clip_range.setEnabled(True)

    def _change_clip_range(self, times):
        start, end = times

        # update clip start/end
        if start != self.clip_start:
            self._set_clip_start(start)
        if end != self.clip_end:
            self._set_clip_end(end)

    def _video_duration_changed(self, duration):
        if not duration:
            return
        self.w_clip_range.setRange(0, duration)
        self.w_clip_range.setValue((0, duration))

    def _save(self, filename: str):
        start, end = map(ftime, self.w_clip_range.value())
        self.w_clip_range.setEnabled(False)
        self.w_options.setEnabled(False)

        self.save_t = QThread()
        self.save_worker = SaveWorker(
            file=self.source_file,
            out_fn=filename,
            start=start,
            end=end,
            max_size_mb=self.w_options.maxFileSize(),
            resolution=self.w_options.resolution(),
            fps=self.w_options.fps(),
            audio_bitrate_kb=self.w_options.audioBitrate(),
        )
        self.save_worker.moveToThread(self.save_t)

        self.save_t.started.connect(self.save_worker.save_clip)
        self.save_worker.done.connect(self.save_worker.deleteLater)
        self.save_worker.done.connect(self.save_t.quit)
        self.save_worker.done.connect(self.save_t.deleteLater)

        self.save_worker.progress.connect(
            lambda p: self.w_progress.setValue(p)
        )
        self.save_worker.done.connect(
            lambda: (
                self.w_clip_range.setEnabled(True),
                self.w_options.setEnabled(True)
            )
        )

        self.save_t.start()
