import copy,datetime,json,pathlib,shutil,threading
from PySide6.QtCore import Qt,QObject,Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QTabWidget,QScrollArea,QComboBox,QSpinBox,QCheckBox,QPushButton,QLineEdit,QFileDialog,QMessageBox
from .appearance import stylesheet,load_fonts
from .config_io import export_bundle,import_bundle,save_atomic
from .paths import ROOT,DSH_HOME
from .sizing import SizeControl
from .paths import VERSION,AUDIO_SESSION_NAME
from .presentation_size import PresentationControl

class Jobs(QObject):
    finished=Signal(str); failed=Signal(str)

class Preferences(QDialog):
    def __init__(self,pet):
        super().__init__(None); self.pet=pet; self.loading=True; self.controls={}; self.buttons=[]
        self.setWindowTitle('守岸人 · 外观、声音与迁移'); self.setWindowIcon(pet.icon); self.resize(790,740); self.setMinimumSize(660,530)
        layout=QVBoxLayout(self); layout.setContentsMargins(20,18,20,18)
        title=QLabel('把陪伴调整成你喜欢的样子'); title.setObjectName('settingsTitle'); layout.addWidget(title)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1)
        visual=self.tab('字体与大小')
        self.size_control=SizeControl(pet); visual.addRow('整体缩放 · 实时预览',self.size_control)
        names=list(dict.fromkeys(pet.font_families+['Microsoft YaHei','Segoe UI']+QFontDatabase.families()))
        visual.addRow('面板与额度字体',self.combo('font_family',names))
        visual.addRow('默认气泡字体',self.combo('bubble_font_family',names))
        visual.addRow('气泡文字',self.spin('bubble_font_size',12,40,' px'))
        visual.addRow('额度条文字',self.spin('quota_font_size',12,32,' px'))
        visual.addRow('设置面板文字',self.spin('ui_font_size',13,28,' px'))
        self.presentation_control=PresentationControl(pet); visual.addRow('气泡与配额 · 实时预览',self.presentation_control)
        visual.addRow('角色基础大小（100%）',self.spin('pet_size',140,420,' px'))
        add=QPushButton('添加本地字体文件…'); add.clicked.connect(self.add_font); visual.addRow(add)
        note=QLabel('已内置站酷快乐体与霞鹜文楷，随迁移包携带，无需安装到系统。单个状态也可以单独设置字体与字号。'); note.setWordWrap(True); visual.addRow(note)
        voice=self.tab('声音')
        enabled=QCheckBox('开启本地语音提醒'); enabled.toggled.connect(lambda v:self.change('audio_enabled',v)); self.controls['audio_enabled']=enabled; voice.addRow(enabled)
        voice.addRow('音量',self.spin('volume',0,100,' %'))
        voice.addRow('同一状态最短播报间隔',self.spin('audio_cooldown',0,300,' 秒'))
        row,self.audio_dir=self.path_control('audio_directory','选择音频目录',directory=True); voice.addRow('音频目录',row)
        note=QLabel('自动播报会先说完整句，GIF 切换不会截断声音。多会话完成提醒依次播放；忙时其他交互保留一条待播提醒，优先任务通知；待机／悬停不插队。思考默认每轮只播一次，轮次在实际播放时记账。主动试听或停止声音可以中断。'); note.setWordWrap(True); voice.addRow(note)
        stop=QPushButton('停止当前声音'); stop.clicked.connect(pet.voice.stop); voice.addRow(stop)
        transfer=self.tab('保存与迁移')
        note=QLabel('修改会自动保存。你也可以立即保存快照，或把 GIF、字体、已绑定音频和配置一起打包。便携包还包含 Windows 运行程序。'); note.setWordWrap(True); transfer.addRow(note)
        self.add_button(transfer,'立即保存全部配置',self.save_now)
        self.add_button(transfer,'保存一份配置快照（JSON）',self.snapshot)
        self.add_button(transfer,'导出配置与素材包（ZIP）',lambda:self.export(False))
        self.add_button(transfer,'导出 Windows 便携完整包（ZIP）',lambda:self.export(True))
        self.add_button(transfer,'导入配置与素材包…',self.import_file)
        tip=QLabel('迁移包会重置当前会话和本机连接路径，新电脑自动寻找已登录的 DeepSeek Harness（需安装连接插件）。不会包含账户凭据、聊天记录或额度缓存。'); tip.setWordWrap(True); transfer.addRow(tip)
        connect=self.tab('连接 DeepSeek')
        self.add_button(connect,'安装 / 更新 Harness 连接插件',self.install_bridge)
        note=QLabel('首次使用：登录官方 DeepSeek Harness，然后从托盘完全退出，点击上方安装按钮，再重新打开客户端。换电脑或更新连接插件时同样操作。'); note.setWordWrap(True); connect.addRow(note)
        launch=QCheckBox('随 DeepSeek 启动桌宠'); launch.toggled.connect(lambda value:self.change('launch_with_deepseek',value)); self.controls['launch_with_deepseek']=launch; connect.addRow(launch)
        note=QLabel('勾选后，登录 Windows 时会在后台等待 DeepSeek 打开，再启动桌宠。取消勾选会移除本机的启动联动。该选项随配置迁移，在新电脑首次手动启动桌宠后恢复。'); note.setWordWrap(True); connect.addRow(note)
        self.sessions=QComboBox(); self.sessions.currentIndexChanged.connect(self.select_thread); connect.addRow('跟随的会话',self.sessions)
        note=QLabel('推荐自动跟随最近活动。固定到已结束的旧会话后，其他会话的思考、查阅和编辑动画不会触发。'); note.setWordWrap(True); connect.addRow(note)
        row,self.deepseek_home=self.path_control('deepseek_home','选择 DeepSeek 数据目录',True); connect.addRow('数据目录',row)
        row,self.deepseek_exe=self.path_control('deepseek_executable','选择 DeepSeek Harness.exe',False); connect.addRow('DeepSeek 程序',row)
        note=QLabel('留空即可自动检测：数据目录使用 DSH_HOME 或当前用户的 .dsh；程序从官方默认安装位置查找。新电脑请先安装并登录 DeepSeek。'); note.setWordWrap(True); connect.addRow(note)
        reconnect=QPushButton('应用连接并刷新余额'); reconnect.clicked.connect(pet.refresh_quota); connect.addRow(reconnect)
        self.connection_status=QLabel(); self.connection_status.setWordWrap(True); connect.addRow(self.connection_status)
        updates=self.tab('版本与更新')
        updates.addRow(QLabel(AUDIO_SESSION_NAME+'  ·  当前版本 v'+VERSION))
        automatic=QCheckBox('每次启动时检查 GitHub 更新'); automatic.toggled.connect(lambda value:self.change('check_updates_on_start',value)); self.controls['check_updates_on_start']=automatic; updates.addRow(automatic)
        check=QPushButton('立即检查更新'); check.clicked.connect(lambda:pet.updates.check(True)); check.setEnabled(not pet.updates.busy); pet.updates.busy_changed.connect(lambda busy:check.setEnabled(not busy)); updates.addRow(check)
        self.update_status=QLabel(pet.updates.status); self.update_status.setWordWrap(True); pet.updates.status_changed.connect(self.update_status.setText); updates.addRow(self.update_status)
        restore=QPushButton('恢复已忽略版本的提醒'); restore.clicked.connect(lambda:self.change('ignored_update_version','')); updates.addRow(restore)
        tip=QLabel('有新版时显示提示，检查失败不会打断使用。更新页面中请选择适用于当前版本的程序补丁；使用完整包时，请解压到新目录，再导入自己的配置与素材。'); tip.setWordWrap(True); updates.addRow(tip)
        self.status=QLabel('设置自动保存'); self.status.setWordWrap(True); layout.addWidget(self.status)
        close=QPushButton('完成'); close.clicked.connect(self.hide); layout.addWidget(close)
        self.jobs=Jobs(); self.jobs.finished.connect(self.job_finished); self.jobs.failed.connect(self.job_failed)
        self.refresh_controls(); self.loading=False; self.apply_style()
    def tab(self,title):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); body.setObjectName('settingsBody'); form=QFormLayout(body); form.setContentsMargins(16,18,16,18); form.setSpacing(16); form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow); scroll.setWidget(body); self.tabs.addTab(scroll,title); return form
    def install_bridge(self):
        from .integration_setup import install
        self.status.setText('正在安装连接插件…')
        for button in self.buttons: button.setEnabled(False)
        options=dict(self.pet.options)
        def run():
            try:self.jobs.finished.emit(install(options))
            except Exception as error:self.jobs.failed.emit(str(error))
        threading.Thread(target=run,daemon=True).start()
    def combo(self,key,names):
        control=QComboBox()
        for name in names: control.addItem(name,name)
        control.currentIndexChanged.connect(lambda:self.change(key,control.currentData())); self.controls[key]=control; return control
    def spin(self,key,low,high,suffix):
        control=QSpinBox(); control.setRange(low,high); control.setSuffix(suffix); control.setKeyboardTracking(False); control.valueChanged.connect(lambda value:self.change(key,value)); self.controls[key]=control; return control
    def path_control(self,key,title,directory):
        row=QHBoxLayout(); control=QLineEdit(); control.setPlaceholderText('留空自动检测' if key.startswith('deepseek') else 'audio'); self.controls[key]=control; control.editingFinished.connect(lambda:self.change(key,control.text().strip())); row.addWidget(control,1)
        button=QPushButton('浏览…')
        def choose():
            value=QFileDialog.getExistingDirectory(self,title,control.text()) if directory else QFileDialog.getOpenFileName(self,title,control.text(),'程序 (*.exe)')[0]
            if value: control.setText(value); self.change(key,value)
        button.clicked.connect(choose); row.addWidget(button); return row,control
    def add_button(self,form,label,callback):
        button=QPushButton(label); button.clicked.connect(callback); form.addRow(button); self.buttons.append(button)
    def refresh_controls(self):
        self.loading=True
        for key,control in self.controls.items():
            value=self.pet.options[key]
            if isinstance(control,QComboBox):
                idx=control.findData(value)
                if idx<0: control.addItem(value,value); idx=control.count()-1
                control.setCurrentIndex(idx)
            elif isinstance(control,QSpinBox): control.setValue(round(value))
            elif isinstance(control,QCheckBox): control.setChecked(bool(value))
            else: control.setText(value)
        self.refresh_threads(); self.size_control.refresh()
        self.connection_status.setText('当前数据目录：'+str(self.pet.monitor.home)); self.loading=False
    def refresh_threads(self):
        selected=self.pet.monitor.selected; self.sessions.blockSignals(True); self.sessions.clear(); self.sessions.addItem('自动跟随最近活动（推荐）','auto')
        for row in self.pet.thread_list: self.sessions.addItem(row['title'][:40],row['id'])
        if self.sessions.findData(selected)<0: self.sessions.addItem('固定会话（目前未在列表中）',selected)
        self.sessions.setCurrentIndex(self.sessions.findData(selected)); self.sessions.blockSignals(False)
    def select_thread(self):
        if self.loading: return
        ok=self.pet.select_thread(self.sessions.currentData() or 'auto'); self.status.setText('跟随设置已保存' if ok else '跟随设置保存失败')
    def change(self,key,value):
        if self.loading: return
        try:
            ok=self.pet.set_option(key,value); self.status.setText('已自动保存' if ok else '保存失败，请检查目录权限。')
        except OSError as error:
            self.refresh_controls(); self.status.setText('设置未更改：'+str(error))
    def apply_style(self): self.setStyleSheet(stylesheet(self.pet.options)+'QLabel#settingsTitle{font-size:25px;font-weight:600;color:#2e5280;}')
    def save_now(self): self.status.setText('全部配置已保存' if self.pet.save_settings() else '保存失败')
    def snapshot(self):
        path,_=QFileDialog.getSaveFileName(self,'保存配置快照',str(ROOT/'exports'/('settings-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')),'JSON (*.json)')
        if not path: return
        try: save_atomic(path,self.pet.settings,backup=False); self.status.setText('快照已保存：'+path)
        except OSError as error: self.status.setText('保存失败：'+str(error))
    def export(self,portable):
        name=('Shorekeeper-Windows-' if portable else 'Shorekeeper-Profile-')+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip'
        path,_=QFileDialog.getSaveFileName(self,'导出完整便携包' if portable else '导出配置与素材',str(ROOT/'exports'/name),'ZIP (*.zip)')
        if not path: return
        self.pet.save_settings(); data=copy.deepcopy(self.pet.settings); self.set_busy(True); self.status.setText('正在打包，请稍候…')
        def work():
            try:
                warnings=export_bundle(path,data,ROOT,portable); self.jobs.finished.emit('已导出：'+path+('\n'+'\n'.join(warnings) if warnings else ''))
            except Exception as error: self.jobs.failed.emit('导出失败：'+str(error))
        threading.Thread(target=work,daemon=True).start()
    def set_busy(self,value):
        for button in self.buttons: button.setEnabled(not value)
    def job_finished(self,text): self.set_busy(False); self.status.setText(text)
    def job_failed(self,text): self.set_busy(False); self.status.setText(text)
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'导入配置',str(ROOT/'exports'),'守岸人配置 (*.zip *.json)')
        if not path: return
        try:
            self.pet.voice.stop()
            stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); save_atomic(ROOT/'backups'/('before-import-'+stamp+'.json'),self.pet.settings,backup=False)
            data=json.loads(pathlib.Path(path).read_text('utf8')) if path.lower().endswith('.json') else import_bundle(path,ROOT)
            if not isinstance(data,dict): raise ValueError('配置格式不正确')
            self.pet.apply_settings(data); self.refresh_controls(); self.status.setText('配置已导入并应用。原配置已保存在 backups。')
        except Exception as error: self.status.setText('导入失败：'+str(error))
    def add_font(self):
        path,_=QFileDialog.getOpenFileName(self,'添加本地字体','','字体 (*.ttf *.otf *.ttc)')
        if not path: return
        target=ROOT/'fonts'/pathlib.Path(path).name
        if pathlib.Path(path).resolve()!=target.resolve(): shutil.copy2(path,target)
        self.pet.font_families=load_fonts(ROOT)
        for key in ('font_family','bubble_font_family'):
            control=self.controls[key]
            for family in self.pet.font_families:
                if control.findData(family)<0: control.addItem(family,family)
        self.status.setText('字体已加入桌宠目录，可从字体列表选择。')
