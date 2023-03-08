import sys

from PyQt6.QtCore import QUrl, Qt, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QStyle, QSlider, QVBoxLayout, QFileDialog, QLabel, QProgressBar, QComboBox, QLineEdit
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from superqt import QRangeSlider

import os
import subprocess


class SaveWorker(QObject):
    progress = pyqtSignal(int)
    done = pyqtSignal()

    def __init__(
            self,
            file: str,
            out_fn: str,
            start: str = '0',
            end: str = '05:00',
            max_size_mb: int = 8,
            resolution: str = '1280x720',
            fps: int = 30,
            audio_bitrate_kb: int = 128,
            parent=None,
    ) -> None:
        super().__init__(parent)
        self.file = file
        self.out_file = out_fn
        self.start = start
        self.end = end
        self.max_size_mb = max_size_mb
        self.resolution = resolution
        self.fps = fps
        self.audio_bitrate_kb = audio_bitrate_kb

    def save_clip(self):
        self.progress.emit(10)

        # trim the clip first
        trimmed_file = f'{self.file}-TRIMMED.tmp'
        subprocess.run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', f'{self.file}',
            '-c', 'copy', '-ss', f'{self.start}', '-to', f'{self.end}',
            '-f', 'mp4',
            f'{trimmed_file}',
        ])

        self.progress.emit(20)

        # get the max bitrate we can encode at
        pout = subprocess.run([
            'ffprobe', '-i', f'{trimmed_file}',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
        ], capture_output=True)
        pout = pout.stdout.decode('utf8')
        duration = float(pout)

        max_encode_rate = ((self.max_size_mb * 8192) / duration) - self.audio_bitrate_kb
        max_encode_rate = int(max_encode_rate)

        self.progress.emit(40)

        # encode once
        subprocess.run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', f'{trimmed_file}',
            '-c:v', 'libx264',
            '-fpsmax',  f'{self.fps}', '-s', f'{self.resolution}',
            '-b:v', f'{max_encode_rate} K',
            '-maxrate:v', f'{max_encode_rate} K',
            '-b:a', f'{self.audio_bitrate_kb} K',
            '-maxrate:a', f'{self.audio_bitrate_kb} K',
            f'{self.out_file}'
        ])

        self.progress.emit(75)

        # check file size.
        # keep re-encoding at progressively lower quality
        quality_factor = 1
        encode_rate = max_encode_rate
        prog = 75
        size = os.path.getsize(self.out_file) / 1e6
        while size > self.max_size_mb:
            # this should converge on the largest possible bitrate
            # while staying under the filesize limit
            quality_factor = quality_factor * (self.max_size_mb / size)
            encode_rate = max_encode_rate * quality_factor

            subprocess.run([
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-i', f'{trimmed_file}',
                '-c:v', 'libx264',
                '-fpsmax',  f'{self.fps}', '-s', f'{self.resolution}',
                '-b:v', f'{encode_rate} K',
                '-maxrate:v', f'{encode_rate} K',
                '-b:a', f'{self.audio_bitrate_kb} K',
                '-maxrate:a', f'{self.audio_bitrate_kb} K',
                f'{self.out_file}'
            ])

            size = os.path.getsize(self.out_file) / 1e6

            # practically impossible to judge progress here but it's something
            prog += 2
            self.progress.emit(min(prog, 99))

        # remove the trimmed file
        os.remove(trimmed_file)
        self.progress.emit(100)
        self.done.emit()


class Window(QWidget):
    APP_TITLE = 'footgas{ext}'
    DEFAULT_SIZE = (1280, 850)

    def __init__(self):
        super().__init__()
        self.dont_seek = False
        self.fix_thumbnail = False
        self.setWindowTitle(self.APP_TITLE.format(ext=''))
        self.resize(*self.DEFAULT_SIZE)
        self.populate()

    def ftime(self, time: int, add_ms: bool = True) -> str:
        s = time * 1e-3
        ms = int((s - int(s)) * 1e3)
        min = int(s // 60)

        formatted = f'{str(min).rjust(2, "0")}:{str(int(s) % 60).rjust(2, "0")}'
        if add_ms:
            formatted += f'.{str(ms).rjust(3, "0")}'
        return formatted

    def strtoms(self, time) -> int:
        m, s, ms = 0, 0, 0
        if not time or time.isalpha():
            return None

        # validate time formatting
        time = time.split(':')
        if not time[0]:
            return None
        if len(time) < 2 or time[0].isalpha() or time[1].isalpha():
            return None
        m = int(time[0])

        s_ms = time[1].split('.')
        if not s_ms[0] or s_ms[0].isalpha():
            return None
        s = int(s_ms[0])
        if len(s_ms) > 1 and not s_ms[1].isalpha():
            ms = int(s_ms[1])

        return int(((m * 60) + s) * 1e3 + ms)

    def populate(self):
        self.w_player = QVideoWidget()

        self.video_player = QMediaPlayer()
        self.video_player.playbackStateChanged.connect(self.playstate_update)
        self.video_player.durationChanged.connect(self.update_duration)
        self.video_player.positionChanged.connect(self.update_time)
        self.video_player.mediaStatusChanged.connect(self.update_mediastate)

        self.audio_player = QAudioOutput()
        self.audio_player.setVolume(0.1)
        self.video_player.setAudioOutput(self.audio_player)
        self.video_player.setVideoOutput(self.w_player)

        self.w_video_select = QPushButton('Select source')
        self.w_video_select.clicked.connect(self.set_source)

        self.w_save = QPushButton('Save clip')
        self.w_save.setEnabled(False)
        self.w_save.clicked.connect(self.start_save_clip)

        io_box = QVBoxLayout()
        io_box.addWidget(self.w_video_select)
        io_box.addWidget(self.w_save)

        self.w_play_pause = QPushButton()
        self.w_play_pause.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay
        ))
        self.w_play_pause.setEnabled(False)
        self.w_play_pause.clicked.connect(self.play_pause)

        self.w_time_label = QLabel('* / *')
        self.w_clip_label = QLabel('* -> *')
        time_box = QVBoxLayout()
        time_box.addWidget(self.w_time_label)
        time_box.addWidget(self.w_clip_label)

        self.w_seek = QRangeSlider(Qt.Orientation.Horizontal)
        self.w_seek.setRange(0, 100)
        self.w_seek.setValue((0, 100))
        self.w_seek.valueChanged.connect(self.seek)

        self.w_mute = QPushButton()
        self.w_mute.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaVolume
        ))
        self.w_mute.clicked.connect(self.toggle_mute)
        self.w_audio = QSlider(Qt.Orientation.Horizontal)
        self.w_audio.setMaximumWidth(150)
        self.w_audio.setRange(0, 100)
        self.w_audio.setSliderPosition(10)
        self.w_audio.sliderMoved.connect(self.set_volume)

        start_label = QLabel()
        start_label.setText('Start:')
        self.w_override_start = QLineEdit()
        self.w_override_start.setToolTip('Start time')
        self.w_override_start.setEnabled(False)
        self.w_override_start.textChanged.connect(self.update_override_start)

        end_label = QLabel()
        end_label.setText('End:')
        self.w_override_end = QLineEdit()
        self.w_override_end.setToolTip('End time')
        self.w_override_end.setEnabled(False)
        self.w_override_end.textChanged.connect(self.update_override_end)

        max_size_label = QLabel()
        max_size_label.setText('Max filesize (MB):')
        self.w_max_size = QLineEdit()
        self.w_max_size.setToolTip('Max filesize (MB)')
        self.w_max_size.setText('8')

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

        ctl_box = QHBoxLayout()
        ctl_box.addLayout(io_box)
        ctl_box.addWidget(self.w_play_pause)
        ctl_box.addLayout(time_box)
        ctl_box.addWidget(self.w_seek)
        ctl_box.addWidget(self.w_mute)
        ctl_box.addWidget(self.w_audio)

        self.w_progress = QProgressBar()
        self.w_progress.setRange(0, 100)
        self.w_progress.setValue(0)

        vbox = QVBoxLayout()
        vbox.addWidget(self.w_player)
        vbox.addLayout(ctl_box)
        vbox.addLayout(options_box)
        vbox.addWidget(self.w_progress)

        self.setLayout(vbox)

    def set_source(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Select clip source')
        if not fn:
            return

        self.fix_thumbnail = True
        url = QUrl.fromLocalFile(fn)
        self.video_player.setSource(url)
        self.setWindowTitle(self.APP_TITLE.format(ext=f' - {url.fileName()}'))
        self.w_save.setEnabled(True)
        self.w_play_pause.setEnabled(True)
        self.w_override_start.setEnabled(True)
        self.w_override_end.setEnabled(True)

        self.update_time(0)

    def update_mediastate(self, state):
        # video ended, restart from range start
        if state == QMediaPlayer.MediaStatus.EndOfMedia:
            start, _ = self.w_seek.value()
            self.video_player.pause()
            self.video_player.play()
            self.video_player.setPosition(start)

        if not self.fix_thumbnail:
            return

        # autoplay
        if state == QMediaPlayer.MediaStatus.LoadedMedia:
            self.video_player.play()
            self.video_player.setPosition(0)
        # but immediately pause when the thumbnail is updated
        if state == QMediaPlayer.MediaStatus.BufferedMedia:
            self.video_player.pause()
            self.fix_thumbnail = False

    def playstate_update(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.w_play_pause.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPause
            ))
        else:
            self.w_play_pause.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPlay
            ))

    def seek(self, times):
        if self.dont_seek:
            self.dont_seek = False
            return
        start, end = times
        self.video_player.setPosition(start)

        start, end = map(self.ftime, times)
        self.w_clip_label.setText(f'{start} -> {end}')
        self.w_override_start.setText(start)
        self.w_override_end.setText(end)

    def update_duration(self, duration):
        if not duration:
            return
        self.w_seek.setRange(0, duration)
        self.w_seek.setValue((0, duration))

    def update_time(self, time):
        dur = self.video_player.duration()
        self.w_time_label.setText(f'{self.ftime(time)} / {self.ftime(dur)}')

        # loop back to start of clip when past the end
        start, end = self.w_seek.value()
        if time > end:
            self.video_player.setPosition(start)

    def update_override_start(self):
        start_ms = self.strtoms(self.w_override_start.text())
        if start_ms is None:
            return

        self.dont_seek = True
        _, end = self.w_seek.value()
        self.w_seek.setValue((start_ms, end))
        self.w_clip_label.setText(f'{self.ftime(start_ms)} -> {self.ftime(end)}')

        # update video position if the new start is beyond current position
        if start_ms > self.video_player.position():
            self.video_player.setPosition(start_ms)

    def update_override_end(self):
        end_ms = self.strtoms(self.w_override_end.text())
        if end_ms is None:
            return

        self.dont_seek = True
        start, _ = self.w_seek.value()
        self.w_seek.setValue((start, end_ms))
        self.w_clip_label.setText(f'{self.ftime(start)} -> {self.ftime(end_ms)}')

        # update video position if the new end is before current position
        if end_ms < self.video_player.position():
            self.video_player.setPosition(end_ms)

    def play_pause(self):
        state = self.video_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.video_player.pause()
        else:
            # go back to start if out of range
            start, end = self.w_seek.value()
            position = self.video_player.position()
            if position < start or position > end:
                self.video_player.setPosition(start)
            self.video_player.play()

    def set_volume(self, volume):
        volume /= 100
        self.audio_player.setVolume(volume)

    def toggle_mute(self):
        muted = not self.audio_player.isMuted()
        self.audio_player.setMuted(muted)

        if muted:
            self.w_mute.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolumeMuted
            ))
        else:
            self.w_mute.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            ))

    def start_save_clip(self):
        self.w_save.setEnabled(False)
        file = self.video_player.source().toLocalFile()
        out_fn, _ = QFileDialog.getSaveFileName(self, 'Select save destination')
        if not out_fn:
            return
        start, end = map(self.ftime, self.w_seek.value())

        max_size = 0
        try:
            max_size = int(self.w_max_size.text())
        except ValueError:
            return

        self.save_t = QThread()
        self.save_worker = SaveWorker(
            file=file,
            out_fn=out_fn,
            start=start,
            end=end,
            max_size_mb=max_size,
            resolution=self.w_resolution.currentText(),
            fps=int(self.w_fps.currentText()[:-3]),
            audio_bitrate_kb=int(self.w_audio_bitrate.currentText()[:-4]),
        )
        self.save_worker.moveToThread(self.save_t)

        self.save_t.started.connect(self.save_worker.save_clip)
        self.save_worker.done.connect(self.save_worker.deleteLater)
        self.save_worker.done.connect(self.save_t.quit)
        self.save_worker.done.connect(self.save_t.deleteLater)

        self.save_worker.progress.connect(lambda p: self.w_progress.setValue(p))
        self.save_worker.done.connect(lambda: self.w_save.setEnabled(True))

        self.save_t.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec()
