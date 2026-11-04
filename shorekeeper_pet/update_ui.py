"""Periodic silent notifications and one-click program updates."""
import threading,json,os,pathlib,subprocess,sys,time,uuid
from datetime import datetime,date

from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit

from .appearance import stylesheet
from .paths import VERSION, AUDIO_SESSION_NAME,ROOT,UPDATE_REPOSITORY
from .updates import check_latest, releases_url, UpdateResult, source_url, SOURCE_LABELS, readable_notes


class UpdateDialog(QDialog):
    def __init__(self, controller, result):
        super().__init__(None)
        self.controller = controller
        self.result = result
        self.setWindowTitle(AUDIO_SESSION_NAME + ' · 版本更新')
        self.setWindowIcon(controller.pet.icon)
        self.setMinimumWidth(540)
        self.resize(680, 640 if result.status == 'available' else 260)
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
        source=QLabel('本次使用：'+SOURCE_LABELS[result.source]);layout.addWidget(source)
        if result.status == 'available':
            tip = QLabel('点击“一键更新”即可下载程序更新、保留当前配置并重启守岸人。GIF、音频、字幕和字体不会重复下载或覆盖。')
            install=QPushButton('一键更新');install.clicked.connect(controller.install);layout.addWidget(install)
            controller.install_changed.connect(install.setDisabled)
            tip.setWordWrap(True)
            layout.addWidget(tip)
            self.notes = QPlainTextEdit()
            self.notes.setReadOnly(True)
            self.notes.setPlainText(readable_notes(result.notes) or ('镜像来源不显示更新说明，可打开更新页面查看。' if result.source=='mirror' else '此版本未填写更新说明，可打开更新页面查看。'))
            self.notes.setMinimumHeight(220)
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

    def effective_source(self):
        choice=self.controller.pet.options['update_source']
        return self.result.source if choice=='auto' else choice

    def open_release(self):
        source=self.effective_source()
        url=releases_url().removesuffix('/latest') if source=='mirror' else self.result.url or releases_url()
        if not QDesktopServices.openUrl(QUrl(source_url(url,source))):
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
    install_changed = Signal(bool)
    install_progress = Signal(str)
    install_ready = Signal(object)
    install_failed = Signal(str)

    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.busy = False
        self.closed = False
        self.startup_checked = False
        self.manual_requested = False
        self.dialog = None
        self.status = '尚未检查更新'
        self.latest=None;self.installing=False;self.cancel=threading.Event();self.helper=None
        from .update_notice import UpdateNotice
        self.notice=UpdateNotice(self)
        self.install_progress.connect(self._status);self.install_ready.connect(self._handoff);self.install_failed.connect(self._install_failed)
        self.finished.connect(self._received)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_startup)
        self.periodic=QTimer(self);self.periodic.timeout.connect(self.check_periodic)
        self.resume_timer=QTimer(self);self.resume_timer.timeout.connect(self.resume_watcher)
        if os.environ.get('SHOREKEEPER_UPDATE_TOKEN') and UPDATE_REPOSITORY!='Doya16/dsh-shorekeeper':self.resume_timer.start(1000)
        try:
            result=json.loads((ROOT/'update-result.json').read_text('utf8'))
            self.status=result.get('message',self.status)
        except (OSError,ValueError):pass

    def resume_watcher(self):
        try:result=json.loads((ROOT/'update-result.json').read_text('utf8'))
        except (OSError,ValueError):return
        if result.get('status')!='success' or result.get('version')!=VERSION:return
        self.resume_timer.stop()
        enabled=any(self.pet.options.get(k) for k in ('launch_with_codex','launch_with_deepseek'))
        if enabled and not getattr(self.pet,'offline',False):
            def resume():
                try:
                    from .startup import configure
                    configure(True,ROOT)
                except Exception:pass
            threading.Thread(target=resume,daemon=True,name='resume-launch-watcher').start()

    def schedule(self):
        self.timer.start(3000)
        self.reconfigure()

    def reconfigure(self):
        self.periodic.stop()
        if not self.closed and not getattr(self.pet,'offline',False) and self.pet.options['check_updates_periodic']:
            self.periodic.start(round(self.pet.options['update_interval_hours']*3600000))
        self.notice.refresh()

    def check_periodic(self):
        if self.pet.options['check_updates_periodic']:self.check(False)

    def should_remind(self):
        return bool(not self.closed and self.latest and self.latest.status=='available'
                    and self.pet.options['ignored_update_version']!=self.latest.version
                    and self.pet.options['update_snoozed_date']!=date.today().isoformat())

    def snooze_today(self):
        if self.pet.set_option('update_snoozed_date',date.today().isoformat()):self.notice.hide()
        else:self._status('保存失败，请检查目录是否可写。')

    def check_startup(self):
        if not self.startup_checked and self.pet.options['check_updates_on_start']:
            self.check(False)

    def _status(self, value):
        self.status = value
        self.status_changed.emit(value)
        self.notice.refresh()

    def check(self, manual=True):
        if self.closed or self.installing:
            return
        self.startup_checked = True
        self.manual_requested = self.manual_requested or manual
        if self.busy:
            return
        self.busy = True
        self.busy_changed.emit(True)
        choice=self.pet.options['update_source']
        self._status('正在检查更新 · '+SOURCE_LABELS[choice]+'…')

        def work():
            try:
                result = check_latest(source=choice)
            except Exception:
                result = UpdateResult('unavailable', url=releases_url(),
                                      message='本次未能检查更新，请稍后重试。')
            try:
                self.finished.emit((choice,result))
            except RuntimeError:
                pass  # The app has already closed; the worker owns no files.
        threading.Thread(target=work, daemon=True, name='release-check').start()

    @Slot(object)
    def _received(self,payload):
        choice,result=payload
        if self.closed:return
        if choice!=self.pet.options['update_source']:
            self.busy=False;self.busy_changed.emit(False);self.manual_requested=False
            self._status('来源已更换，请点击立即检查更新。');return
        self._finished(result)

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
        self._status(datetime.now().strftime('%H:%M') + ' · ' + SOURCE_LABELS[result.source] + ' · ' + message)
        if result.status in ('available','current'):
            self.latest=result if result.status=='available' else None
        self.notice.refresh()
        if not manual:return
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = UpdateDialog(self, result)
        self.dialog.show()  # Modeless: task animations, voice, and dragging keep working.

    def install(self):
        if self.closed or self.installing:return
        if not self.latest or self.latest.status!='available':
            self.check(True);return
        if not getattr(sys,'frozen',False):
            self._status('一键更新适用于已打包的 Windows 程序。');return
        if not self.pet.save_settings():
            self._status('配置保存失败，尚未开始更新。');return
        self.installing=True;self.cancel.clear();self.install_changed.emit(True)
        self._status('正在下载程序更新…')
        result=self.latest;source=self.pet.options['update_source']
        watcher=any(self.pet.options.get(k) for k in ('launch_with_codex','launch_with_deepseek')) and UPDATE_REPOSITORY!='Doya16/dsh-shorekeeper'
        def work():
            paused=False;folder=None
            try:
                from .update_package import prepare,HELPER
                from .update_apply import atomic_json
                folder,manifest=prepare(result,source,progress=lambda n,total:self.install_progress.emit(f'正在下载程序更新… {n*100//total}%'),cancel=self.cancel)
                if self.cancel.is_set():return
                job=dict(id=str(uuid.uuid4()),root=str(ROOT),pid=os.getpid(),current_version=VERSION,target_version=result.version,watcher_paused=watcher)
                if watcher:
                    from .startup import configure
                    configure(False,ROOT);paused=True
                atomic_json(folder/'job.json',job)
                self.helper=subprocess.Popen([str(folder/HELPER),'--job',str(folder/'job.json')],cwd=folder,creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                until=time.monotonic()+15
                while time.monotonic()<until:
                    ready=folder/'ready.json'
                    if ready.exists() and json.loads(ready.read_text('utf8')).get('id')==job['id']:
                        self.install_ready.emit(str(folder));return
                    if self.helper.poll() is not None:
                        failure=json.loads((folder/'result.json').read_text('utf8'));raise RuntimeError(failure.get('message','更新助手无法启动'))
                    time.sleep(.1)
                raise TimeoutError('更新助手未就绪，原程序未改动')
            except Exception as exc:
                if folder is not None:(folder/'cancel').touch()
                if paused:
                    try:
                        from .startup import configure
                        configure(True,ROOT)
                    except Exception:pass
                try:self.install_failed.emit(str(exc))
                except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='program-update').start()

    @Slot(object)
    def _handoff(self,folder):
        if self.closed:return
        self._status('下载校验通过，正在更新并重启守岸人…')
        self.pet.shutdown()

    @Slot(str)
    def _install_failed(self,message):
        if self.closed:return
        self.installing=False;self.install_changed.emit(False)
        self._status('更新未完成：'+message)

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
        self.periodic.stop();self.resume_timer.stop();self.cancel.set();self.notice.hide()
        if self.dialog:
            self.dialog.close()
