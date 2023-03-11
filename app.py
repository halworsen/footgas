import sys
from shutil import which

from PyQt6.QtWidgets import QApplication, QMessageBox, QStyleFactory

from footgas import Footgas

if __name__ == '__main__':
    app = QApplication(sys.argv)
    styles = QStyleFactory.keys()
    if 'Fusion' in styles:
        app.setStyle('Fusion')

    # check if ffmpeg is installed
    if which('ffmpeg') is None or which('ffprobe') is None:
        error_popup = QMessageBox()
        error_popup.setWindowTitle('Error')
        error_popup.setIcon(QMessageBox.Icon.Critical)
        error_msg = 'Couldn\'t find ffmpeg/ffprobe.'
        error_msg += '\n\n'
        error_msg += 'Check that ffmpeg is installed and on the path, then try again.'
        error_popup.setText(error_msg)
        error_popup.show()
    else:
        w = Footgas()
        w.layout().setContentsMargins(0, 0, 0, 0)
        w.show()
    app.exec()
