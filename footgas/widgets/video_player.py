from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSlider, QStyle,
                             QVBoxLayout, QWidget)

from ..util import ftime


class MediaControlWidget(QWidget):
    seek = pyqtSignal(int)
    volumeChanged = pyqtSignal(float)
    togglePlay = pyqtSignal(bool)
    toggleMute = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()

        self.playing = False
        self.muted = False
        self.cur_time = 0
        self.end = 0

        self.populate()

    def populate(self):
        self.w_play_pause = QPushButton()
        self.w_play_pause.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay
        ))
        self.w_play_pause.clicked.connect(self._toggle_play)

        self.w_time_label = QLabel('- / -')

        self.w_seek = QSlider(Qt.Orientation.Horizontal)
        self.w_seek.setRange(0, 100)
        self.w_seek.setValue(0)
        self.w_seek.valueChanged.connect(
            lambda pos: self.seek.emit(pos)
        )

        # Audio control
        self.w_mute = QPushButton()
        self.w_mute.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaVolume
        ))
        self.w_mute.clicked.connect(self._toggle_mute)
        self.w_audio = QSlider(Qt.Orientation.Horizontal)
        self.w_audio.setMaximumWidth(150)
        self.w_audio.setRange(0, 100)
        self.w_audio.setSliderPosition(10)
        self.w_audio.sliderMoved.connect(self._update_volume)

        media_control_box = QHBoxLayout()
        media_control_box.addWidget(self.w_play_pause)
        media_control_box.addWidget(self.w_time_label)
        media_control_box.addWidget(self.w_seek)
        media_control_box.addWidget(self.w_mute)
        media_control_box.addWidget(self.w_audio)

        self.setLayout(media_control_box)

    def setEnabled(self, enabled: bool):
        self.w_play_pause.setEnabled(enabled)
        self.w_audio.setEnabled(enabled)
        self.w_seek.setEnabled(enabled)
        self.w_audio.setEnabled(enabled)

    def setPlaying(self, playing: bool):
        if self.playing != playing:
            self._toggle_play()

    def setVolume(self, volume: float):
        volume *= 100
        self.w_audio.setSliderPosition(volume)

    def setRange(self, start: int, end: int):
        self.w_seek.setRange(start, end)
        self.end = end

        if self.cur_time < start:
            self.setTime(start)
        elif self.cur_time > end:
            self.setTime(end)
        self._update_label()

    def setPosition(self, position: int):
        self.cur_time = position
        self.w_seek.setSliderPosition(position)
        self._update_label()

    def setTime(self, time: int):
        self.cur_time = time
        self._update_label()

    def _update_label(self):
        self.w_time_label.setText(
            f'{ftime(self.cur_time)} / {ftime(self.end)}'
        )

    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self.w_play_pause.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPause
            ))
        else:
            self.w_play_pause.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPlay
            ))

        self.togglePlay.emit(self.playing)

    def _toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.w_mute.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolumeMuted
            ))
        else:
            self.w_mute.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            ))

        self.toggleMute.emit(self.muted)

    def _update_volume(self, volume: int):
        self.volumeChanged.emit(volume / 100)


class VideoPlayerWidget(QWidget):
    '''
    Video player including all backend resources needed
    '''
    durationChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)

    def __init__(self, initial_volume: float = 0.1) -> None:
        super().__init__()

        self.start_time = 0
        self.end_time = 0
        self.fix_thumbnail = False

        self.populate(initial_volume=initial_volume)

    def populate(self, initial_volume: int = 0) -> None:
        self.w_player = QVideoWidget()
        self.video_player = QMediaPlayer()
        self.video_player.durationChanged.connect(self._update_duration)
        self.video_player.positionChanged.connect(self._update_position)
        self.video_player.mediaStatusChanged.connect(self._media_state_update)
        self.audio_player = QAudioOutput()
        self.audio_player.setVolume(initial_volume)
        self.video_player.setAudioOutput(self.audio_player)
        self.video_player.setVideoOutput(self.w_player)

        self.media_control = MediaControlWidget()
        self.media_control.setVolume(initial_volume)
        self.media_control.togglePlay.connect(self._toggle_play)
        self.media_control.toggleMute.connect(self._toggle_mute)
        self.media_control.volumeChanged.connect(self._set_volume)
        self.media_control.seek.connect(self._seek)

        layout = QVBoxLayout()
        layout.addWidget(self.w_player, stretch=1)
        layout.addWidget(self.media_control)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(layout)

    def setEnabled(self, enabled: bool) -> None:
        self.media_control.setEnabled(enabled)

    def setSource(self, source: QUrl):
        self.fix_thumbnail = True
        self.video_player.setSource(source)
        self.media_control.setPlaying(False)
        self.video_player.pause()
        self.setPosition(0)

    def setPosition(self, position: int):
        self.video_player.setPosition(position)
        self.media_control.setPosition(position)

    def setRange(self, start: int, end: int) -> None:
        '''
        Set the range of the video which should be played
        '''
        self.start_time = max(0, start)
        self.end_time = min(self.video_player.duration(), end)
        self.media_control.setRange(self.start_time, self.end_time)

        # clamp video position inside the range
        pos = self.video_player.position()
        if pos < self.start_time:
            self.video_player.setPosition(self.start_time)
            self.media_control.setPosition(self.start_time)
        elif pos > self.end_time:
            self.video_player.setPosition(self.end_time)
            self.media_control.setPosition(self.end_time)

    def duration(self) -> int:
        return self.video_player.duration()

    def _toggle_play(self, playing: bool):
        if playing:
            self.video_player.play()
        else:
            self.video_player.pause()

    def _toggle_mute(self, muted: bool):
        self.audio_player.setMuted(muted)

    def _set_volume(self, volume: float):
        self.audio_player.setVolume(volume)

    def _seek(self, position: int):
        position = min(self.end_time, max(self.start_time, position))
        self.video_player.setPosition(position)
        self.media_control.setTime(position)

    def _media_state_update(self, state: QMediaPlayer.MediaStatus):
        # video ended, restart from range start
        if state == QMediaPlayer.MediaStatus.EndOfMedia:
            self.video_player.pause()
            self.video_player.play()
            self.video_player.setPosition(self.start_time)

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

    def _update_duration(self, duration: int):
        self.setRange(0, duration)
        self.media_control.setTime(0)
        self.durationChanged.emit(duration)

    def _update_position(self, position: int):
        if position > self.end_time or position < self.start_time:
            self.video_player.setPosition(self.start_time)
            return
        self.media_control.setPosition(position)
        self.positionChanged.emit(position)
