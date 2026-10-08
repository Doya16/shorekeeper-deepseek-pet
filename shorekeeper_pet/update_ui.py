"""Non-blocking, once-per-launch release notification shared by both editions."""
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit

from .appearance import stylesheet
from .paths import VERSION, AUDIO_SESSION_NAME
from .updates import check_latest, releases_url, UpdateResult


class UpdateDialog(QDialog):
    def __init__(self, controller, result):
        super().__init__(None)
        self.controller = controller
        self.result = result
        self.setWindowTitle(AUDIO_SESSION_NAME + ' · 版本更新')
        self.setWindowIcon(controller.pet.icon)
        self.setMinimumWidth(540)
        self.resize(660, 480 if result.status == 'available' else 260)
        self.setStyleSheet(stylesheet(controller.pet.options))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)
        title = QLabel({'available': '发现新版本', 'current': '已是最新版本',
                        'unavailable': '暂时无法检查更新'}[result.status])
        title.setStyleSheet('font-size:26px;font-weight:600;color:#2e5280;')
        layout.addWidget(title)
        versions = QLabel(AUDIO_SESSION_NAME + '  ·  当前 v' + VERSION +
                          ('  →  新版 v' + result.version if result.status == 'available' else ''))
        versions.setWordWrap(True)
        layout.addWidget(versions)
        if result.status == 'available':
            tip = QLabel('更新前可先备份配置与素材。下载时请确认补丁适用于当前版本；'
                         '退出桌宠后，将程序补丁解压到原目录并覆盖同名文件。\n'
                         '如果使用完整包，请解压到新目录，再导入自己的配置与素材包。')
            tip.setWordWrap(True)
            layout.addWidget(tip)
            self.notes = QPlainTextEdit()
            self.notes.setReadOnly(True)
            self.notes.setPlainText(result.notes or '此版本未填写更新说明，可打开更新页面查看。')
            layout.addWidget(self.notes, 1)
        elif result.status == 'unavailable':
            message = QLabel(result.message)
            message.setWordWrap(True)
            layout.addWidget(message)
        self.browser_status = QLabel()
        self.browser_status.setWordWrap(True)
        layout.addWidget(self.browser_status)
        actions = QHBoxLayout()
        self.open_button = QPushButton('打开更新页面')
        self.open_button.clicked.connect(self.open_release)
        actions.addWidget(self.open_button)
        if result.status == 'available':
            backup = QPushButton('备份配置与素材…')
            backup.clicked.connect(controller.backup)
            actions.addWidget(backup)
        actions.addStretch()
        layout.addLayout(actions)
        dismiss = QHBoxLayout()
        dismiss.addStretch()
        if result.status == 'available':
            self.ignore_button = QPushButton('忽略此版本')
            self.ignore_button.clicked.connect(self.ignore)
            dismiss.addWidget(self.ignore_button)
        close = QPushButton('稍后提醒' if result.status == 'available' else '关闭')
        close.clicked.connect(self.reject)
        dismiss.addWidget(close)
        layout.addLayout(dismiss)

    def open_release(self):
        if not QDesktopServices.openUrl(QUrl(self.result.url or releases_url())):
            self.browser_status.setText('无法打开浏览器，请稍后重试。')

    def ignore(self):
        if self.controller.pet.set_option('ignored_update_version', self.result.version):
            self.reject()
        else:
            self.browser_status.setText('未能保存忽略设置，请检查桌宠目录的写入权限。')


class UpdateController(QObject):
    finished = Signal(object)
    status_changed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.busy = False
        self.closed = False
        self.startup_checked = False
        self.manual_requested = False
        self.dialog = None
        self.status = '尚未检查更新'
        self.finished.connect(self._finished)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_startup)

    def schedule(self):
        self.timer.start(3000)

    def check_startup(self):
        if not self.startup_checked and self.pet.options['check_updates_on_start']:
            self.check(False)

    def _status(self, value):
        self.status = value
        self.status_changed.emit(value)

    def check(self, manual=True):
        if self.closed:
            return
        self.startup_checked = True
        self.manual_requested = self.manual_requested or manual
        if self.busy:
            return
        self.busy = True
        self.busy_changed.emit(True)
        self._status('正在检查 GitHub 更新…')

        def work():
            try:
                result = check_latest()
            except Exception:
                result = UpdateResult('unavailable', url=releases_url(),
                                      message='本次未能检查更新，请稍后重试。')
            try:
                self.finished.emit(result)
            except RuntimeError:
                pass  # The app has already closed; the worker owns no files.
        threading.Thread(target=work, daemon=True, name='release-check').start()

    @Slot(object)
    def _finished(self, result):
        if self.closed:
            return
        self.busy = False
        self.busy_changed.emit(False)
        manual = self.manual_requested
        self.manual_requested = False
        message = ('发现新版 v' + result.version if result.status == 'available'
                   else '已是最新版本' if result.status == 'current' else result.message)
        self._status(datetime.now().strftime('%H:%M') + ' · ' + message)
        if not manual and (result.status != 'available' or
                           not self.pet.options['check_updates_on_start'] or
                           self.pet.options['ignored_update_version'] == result.version):
            return
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = UpdateDialog(self, result)
        self.dialog.show()  # Modeless: task animations, voice, and dragging keep working.

    def backup(self):
        self.pet.open_preferences()
        preferences = self.pet.preferences
        for index in range(preferences.tabs.count()):
            if preferences.tabs.tabText(index) == '保存与迁移':
                preferences.tabs.setCurrentIndex(index)
                break
        preferences.export(False)

    def close(self):
        self.closed = True
        self.timer.stop()
        if self.dialog:
            self.dialog.close()
