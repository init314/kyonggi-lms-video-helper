from pathlib import Path
import argparse
import logging
import os
import subprocess
import sys

import keyring
from PySide6.QtCore import QSettings, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSpinBox, QStyle,
    QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget,
)

from application.converter import convert_audio_to_prompts
from application.pipeline import BatchResult, download_and_transcribe
from config import (APP_ROOT, DEFAULT_CHUNK_SIZE, DEFAULT_DOWNLOAD_DIR, DEFAULT_LANGUAGE,
                    DEFAULT_MODEL_REF, DEFAULT_OUTPUT_DIR, DEFAULT_OVERLAP, SUPPORTED_MEDIA_EXTENSIONS)
from domain.models import ConversionOptions
from services.cancellation import JobCancelled
from services.displays import get_virtual_display, list_displays
from services.lms_downloader import SERVICE, USERNAME_KEY


class ConvertWorker(QThread):
    log = Signal(str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, source, options, week=None, download_dir=None):
        super().__init__()
        self.source, self.options = source, options
        self.week, self.download_dir = week, download_dir

    def run(self):
        try:
            if self.week is None:
                result = convert_audio_to_prompts(self.source, self.options, self.log.emit, self.isInterruptionRequested)
            else:
                result = download_and_transcribe(self.source, self.week, self.download_dir,
                                                self.options, self.log.emit, self.isInterruptionRequested)
            self.done.emit(result)
        except JobCancelled as exc:
            self.log.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))


class StudySsalmeokApp(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('StudySsalmeok', 'StudySsalmeok')
        self.worker = None
        self.quit_when_done = False
        self.last_output_dir = Path(DEFAULT_OUTPUT_DIR)
        self.setWindowTitle('공부 쌀먹 · 강의 다운로드와 전사')
        self.resize(820, 720)
        self.create_widgets()
        self.create_tray()
        self.refresh_display()

    def create_widgets(self):
        root = QVBoxLayout(self)
        title = QLabel('공부 쌀먹')
        title.setStyleSheet('font-size: 24px; font-weight: bold')
        root.addWidget(title)
        root.addWidget(QLabel('전사하는 동안 다음 영상을 다운로드합니다. 전사·요약 프롬프트는 영상 순서대로 만듭니다.'))
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(['LMS 다운로드 → 전사', '내 컴퓨터의 영상·오디오 전사'])
        form.addRow('작업', self.mode)
        self.course_input = QLineEdit(self.settings.value('course', ''))
        self.course_input.setPlaceholderText('LMS에 표시된 과목명')
        self.week_input = QSpinBox()
        self.week_input.setRange(1, 100)
        self.week_input.setValue(int(self.settings.value('week', 1)))
        form.addRow('과목명', self.course_input)
        form.addRow('주차', self.week_input)
        self.audio_input = QLineEdit()
        self.select_audio_button = QPushButton('찾기')
        self.select_audio_button.clicked.connect(self.select_audio_file)
        form.addRow('영상·오디오', self.path_row(self.audio_input, self.select_audio_button))
        self.model_input = QLineEdit(self.settings.value('model', DEFAULT_MODEL_REF))
        self.download_input = QLineEdit(self.settings.value('downloads', str(DEFAULT_DOWNLOAD_DIR)))
        self.output_input = QLineEdit(self.settings.value('output', str(DEFAULT_OUTPUT_DIR)))
        for label, field in [('STT 모델', self.model_input), ('영상 저장 폴더', self.download_input), ('전사 출력 폴더', self.output_input)]:
            button = QPushButton('폴더 선택')
            button.clicked.connect(lambda checked=False, field=field: self.select_folder(field))
            form.addRow(label, self.path_row(field, button))
        self.language_input = QLineEdit(DEFAULT_LANGUAGE)
        form.addRow('언어', self.language_input)
        self.chunk_size_input = QSpinBox()
        self.chunk_size_input.setRange(1000, 100000)
        self.chunk_size_input.setValue(DEFAULT_CHUNK_SIZE)
        self.overlap_input = QSpinBox()
        self.overlap_input.setRange(0, 50000)
        self.overlap_input.setValue(DEFAULT_OVERLAP)
        form.addRow('청크 크기', self.chunk_size_input)
        form.addRow('중복 길이', self.overlap_input)
        self.display_label = QLabel()
        form.addRow('다운로드 화면', self.display_label)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.start_button = QPushButton('시작')
        self.start_button.clicked.connect(self.start_convert)
        self.stop_button = QPushButton('중지')
        self.stop_button.clicked.connect(self.stop_convert)
        self.stop_button.setEnabled(False)
        account_button = QPushButton('LMS 계정 설정')
        account_button.clicked.connect(self.configure_account)
        hide_button = QPushButton('트레이로 숨기기')
        hide_button.clicked.connect(self.hide)
        output_button = QPushButton('결과 폴더')
        output_button.clicked.connect(lambda: open_folder(self.last_output_dir))
        for button in (self.start_button, self.stop_button, account_button, hide_button, output_button):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view)
        root.addWidget(QLabel('창을 닫아도 트레이에서 계속 실행됩니다. 완전히 종료하려면 트레이 메뉴의 종료를 누르세요.'))
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.update_mode()

    def path_row(self, field, button):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field)
        layout.addWidget(button)
        return row

    def create_tray(self):
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('공부 쌀먹 · 대기 중')
        menu = QMenu(self)
        for title, callback in [('열기', self.show_window), ('작업 중지', self.stop_convert), ('종료', self.request_quit)]:
            action = QAction(title, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window()
                                   if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def show_window(self):
        self.refresh_display()
        # Settings belong on a physical monitor, even when the pointer or a
        # previous window position was on the virtual download display.
        app = QApplication.instance()
        screens = app.screens()
        if sys.platform == 'win32':
            # Qt reports monitor model names, while Win32 reports DISPLAY device
            # names. Match their desktop origins, which stay fixed across DPI.
            physical_origins = {(display.x, display.y) for display in list_displays() if not display.is_virtual}
            screens = [screen for screen in screens
                       if (screen.geometry().x(), screen.geometry().y()) in physical_origins]
        preferred = app.screenAt(QCursor.pos())
        screen = next((screen for screen in screens if screen == preferred), None)
        if screen is None:
            screen = next((screen for screen in screens if screen == app.primaryScreen()), None)
        if screen is None and screens:
            screen = screens[0]
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.x() + max(0, (area.width() - self.width()) // 2),
                      area.y() + max(0, (area.height() - self.height()) // 2))
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def refresh_display(self):
        try:
            display = get_virtual_display()
            self.display_label.setText(f'가상 화면 · {display.name} · {display.width}×{display.height}')
        except RuntimeError as exc:
            self.display_label.setText(str(exc))

    def update_mode(self):
        lms = self.mode.currentIndex() == 0
        self.course_input.setEnabled(lms)
        self.week_input.setEnabled(lms)
        self.download_input.setEnabled(lms)
        self.audio_input.setEnabled(not lms)
        self.select_audio_button.setEnabled(not lms)

    def select_audio_file(self):
        patterns = ' '.join(f'*{extension}' for extension in SUPPORTED_MEDIA_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(self, '영상·오디오 선택', '', f'Media Files ({patterns});;All Files (*)')
        if path:
            self.audio_input.setText(path)

    def select_folder(self, field):
        path = QFileDialog.getExistingDirectory(self, '폴더 선택', field.text())
        if path:
            field.setText(path)

    def configure_account(self):
        username, ok = QInputDialog.getText(self, 'LMS 계정', '경기대학교 LMS 아이디')
        if not ok or not username.strip():
            return
        password, ok = QInputDialog.getText(self, 'LMS 계정', '비밀번호 (Windows 자격 증명 관리자에 저장)', QLineEdit.EchoMode.Password)
        if not ok or not password:
            return
        try:
            keyring.set_password(SERVICE, username.strip(), password)
            keyring.set_password(SERVICE, USERNAME_KEY, username.strip())
            self.append_log('LMS 계정을 Windows 자격 증명 관리자에 저장했습니다.')
        except Exception:
            self.on_error('LMS 계정을 저장하지 못했습니다. Windows 자격 증명 관리자를 확인하세요.')

    def start_convert(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            model = self.model_input.text().strip()
            if not model:
                raise ValueError('STT 모델을 입력하세요.')
            if self.overlap_input.value() >= self.chunk_size_input.value():
                raise ValueError('중복 길이는 청크 크기보다 작아야 합니다.')
            options = ConversionOptions(Path(self.output_input.text().strip() or DEFAULT_OUTPUT_DIR), model,
                                        self.language_input.text().strip() or DEFAULT_LANGUAGE,
                                        self.chunk_size_input.value(), self.overlap_input.value())
            if self.mode.currentIndex() == 0:
                get_virtual_display()
                course = self.course_input.text().strip()
                if not course:
                    raise ValueError('과목명을 입력하세요.')
                self.worker = ConvertWorker(course, options, self.week_input.value(),
                                            Path(self.download_input.text().strip() or DEFAULT_DOWNLOAD_DIR))
            else:
                path = self.audio_input.text().strip()
                if not Path(path).is_file():
                    raise ValueError('전사할 영상·오디오 파일을 선택하세요.')
                self.worker = ConvertWorker(path, options)
        except (ValueError, RuntimeError) as exc:
            self.on_error(str(exc))
            return
        for key, value in {'course': self.course_input.text(), 'week': self.week_input.value(),
                           'model': model, 'downloads': self.download_input.text(),
                           'output': self.output_input.text()}.items():
            self.settings.setValue(key, value)
        self.start_button.setEnabled(False)
        self.mode.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.tray.setToolTip('공부 쌀먹 · 작업 중')
        self.append_log('작업 시작')
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_convert(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.stop_button.setEnabled(False)
            self.append_log('중지 요청: 현재 다운로드 블록 또는 전사 구간을 마치면 중지합니다. 모델 준비 중에는 기다릴 수 있습니다.')

    def on_done(self, result):
        self.last_output_dir = result.output_dir
        if isinstance(result, BatchResult):
            self.append_log(f'작업 종료: 전사 {len(result.completed)}개 완료, 실패 {len(result.failures)}개')
        else:
            self.append_log(f'완료: 프롬프트 {result.prompt_count}개 생성')
        self.append_log(f'출력 폴더: {result.output_dir}')

    def on_finished(self):
        self.start_button.setEnabled(True)
        self.mode.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.tray.setToolTip('공부 쌀먹 · 작업 종료 (열기에서 로그 확인)')
        if self.quit_when_done:
            QApplication.instance().quit()

    def on_error(self, message):
        self.append_log(f'오류: {message}')
        self.tray.setToolTip('공부 쌀먹 · 오류 (열기에서 로그 확인)')
        if self.isVisible():
            QMessageBox.warning(self, '오류', message)

    def append_log(self, message):
        self.log_view.append(message)
        logging.getLogger('study_ssalmeok').info(message)

    def closeEvent(self, event):
        event.ignore()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
        else:
            self.request_quit()

    def request_quit(self):
        if self.worker and self.worker.isRunning():
            self.quit_when_done = True
            self.stop_convert()
            self.hide()
        else:
            QApplication.instance().quit()


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', action='store_true', help='설정 창 표시')
    parser.add_argument('--background', action='store_true', help='설정 창 없이 트레이에서 시작')
    parser.add_argument('--course', help='창을 표시하지 않고 처리할 과목명')
    parser.add_argument('--week', type=int, help='처리할 주차')
    args = parser.parse_args()
    if bool(args.course) != (args.week is not None):
        parser.error('--course와 --week를 함께 입력하세요')
    (APP_ROOT / 'logs').mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('study_ssalmeok')
    logger.setLevel(logging.INFO)
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(APP_ROOT / 'logs' / 'app.log', maxBytes=2_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    window = StudySsalmeokApp()
    if args.show or (not args.background and not args.course) or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show_window()
    if args.course:
        window.course_input.setText(args.course)
        window.week_input.setValue(args.week)
        QTimer.singleShot(0, window.start_convert)
    return app.exec()
