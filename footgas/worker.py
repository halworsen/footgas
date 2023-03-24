import os
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal

from .util import strtoms


class SaveWorker(QObject):
    progress = pyqtSignal(int)
    done = pyqtSignal()

    NO_WINDOW_FLAG = 0x08000000

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
        ], creationflags=self.NO_WINDOW_FLAG)

        self.progress.emit(40)

        # get the max bitrate we can encode at
        duration = (strtoms(self.end) - strtoms(self.start)) / 1e3
        max_encode_rate = ((self.max_size_mb * 8192) / duration)
        max_encode_rate -= self.audio_bitrate_kb
        max_encode_rate = int(max_encode_rate)

        self.progress.emit(50)

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
        ], creationflags=self.NO_WINDOW_FLAG)

        self.progress.emit(75)

        # check file size.
        # keep re-encoding at progressively lower quality
        quality_factor = 1
        encode_rate = max_encode_rate
        prog = 75
        size = os.path.getsize(self.out_file) / 1e6
        first_size_diff = size - self.max_size_mb
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
            ], creationflags=self.NO_WINDOW_FLAG)

            size = os.path.getsize(self.out_file) / 1e6

            # very difficult to judge progress here but it's something?
            # basically check how close the filesize is to the goal size
            size_diff = size - self.max_size_mb
            prog = 75 + int((1 - (size_diff / first_size_diff)) * 25)
            self.progress.emit(min(prog, 99))

        # remove the trimmed file
        os.remove(trimmed_file)
        self.progress.emit(100)
        self.done.emit()
