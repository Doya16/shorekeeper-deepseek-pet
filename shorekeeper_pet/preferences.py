import copy,datetime,json,pathlib,shutil,threading
from PySide6.QtCore import Qt,QObject,Signal,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication,QStyle,QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QTabWidget,QScrollArea,QComboBox,QSpinBox,QCheckBox,QPushButton,QLineEdit,QFileDialog,QMessageBox
from .appearance import stylesheet,load_fonts
from .config_io import export_bundle,import_bundle,save_atomic
from .paths import ROOT,DSH_HOME
from .sizing import SizeControl
from .paths import VERSION,AUDIO_SESSION_NAME
from .presentation_size import PresentationControl
from .settings_layout import Page,WheelGuard,widen,long_list
from .order_list import OrderList
from .previews import CardPreview

class Jobs(QObject):
    finished=Signal(str); failed=Signal(str)

class Preferences(QDialog):
    def __init__(self,pet,catalog,assets,root):
        super().__init__(None); self.pet=pet; self.loading=True; self.controls={}; self.buttons=[]; self.previews={}; self.color_buttons={}
        self.setWindowTitle(AUDIO_SESSION_NAME+' · 设置'); self.setWindowIcon(pet.icon); self.resize(1040,780); self.setMinimumSize(760,560)
        layout=QVBoxLayout(self); layout.setContentsMargins(20,18,20,18)
        title=QLabel('把陪伴调整成你喜欢的样子'); title.setObjectName('settingsTitle'); layout.addWidget(title)
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1)
        visual=self.tab('字体与大小')
        visual.section('整体大小',self.preview('size'))
        self.size_control=SizeControl(pet); self.size_control.setMaximumWidth(620); visual.addRow(self.size_control)
        visual.addRow('角色基础大小（100%）',self.spin('pet_size',140,420,' px'))
        visual.section('字体与字号',self.preview('fonts'))
        names=list(dict.fromkeys(pet.font_families+['Microsoft YaHei','Segoe UI']+QFontDatabase.families()))
        visual.addRow('面板与额度字体',self.combo('font_family',names))
        visual.addRow('默认气泡字体',self.combo('bubble_font_family',names))
        visual.addRow('气泡文字',self.spin('bubble_font_size',12,40,' px'))
        visual.addRow('额度条文字',self.spin('quota_font_size',12,32,' px'))
        visual.addRow('设置面板文字',self.spin('ui_font_size',13,28,' px'))
        add=QPushButton('添加本地字体文件…'); add.clicked.connect(self.add_font); visual.addRow(add)
        note=QLabel('已内置站酷快乐体与霞鹜文楷，随迁移包携带，无需安装到系统。单个状态也可以单独设置字体与字号。'); note.setWordWrap(True); visual.addRow(note)
        visual.section('气泡与余额框 · 实时预览',self.preview('bubble'))
        self.presentation_control=PresentationControl(pet); self.presentation_control.setMaximumWidth(620); visual.addRow(self.presentation_control)
        from .studio import BindingEditor
        self.editor=BindingEditor(pet,catalog,assets,root,parent=self.tabs)
        # The studio scrolls as a page, so its GIF list can stay large in a small window.
        studio=QScrollArea(); studio.setWidgetResizable(True); studio.setFrameShape(QScrollArea.Shape.NoFrame); studio.setWidget(self.editor)
        self.editor.gallery.setMinimumHeight(440); self.tabs.addTab(studio,'交互工作室')
        voice=self.tab('桌面与声音')
        voice.section('完成播报',self.preview('finish'))
        turn_cost=QComboBox()
        for label,value in (('飘字','float'),('气泡','bubble'),('飘字和气泡','both'),('关闭','off')):turn_cost.addItem(label,value)
        turn_cost.currentIndexChanged.connect(lambda:self.change('turn_cost_style',turn_cost.currentData()));self.controls['turn_cost_style']=turn_cost;voice.addRow('播报方式',turn_cost)
        celebrate=QCheckBox('完成时撒花'); celebrate.toggled.connect(lambda value:self.change('celebrate_done',value)); self.controls['celebrate_done']=celebrate; voice.addRow(celebrate)
        self.order=OrderList([('cost','计费'),('time','计时')]); self.order.changed.connect(self.change_order); voice.addRow('播报内容',self.order)
        voice.addRow('飘字字体',self.combo('turn_cost_font_family',names))
        for kind,label in (('cost','计费样式'),('time','计时样式')):voice.addRow(label,self.line_style(kind))
        voice.addRow('飘字字号',self.spin('turn_cost_font_size',14,72,' px'))
        outline=QComboBox()
        for label,value in (('细描边','thin'),('粗描边','thick'),('无描边','none')):outline.addItem(label,value)
        outline.currentIndexChanged.connect(lambda:self.change('turn_cost_outline',outline.currentData()));self.controls['turn_cost_outline']=outline;voice.addRow('飘字描边',outline)
        anchor=QComboBox()
        for label,value in (('底部居中','bottom'),('顶部居中 · 桌宠内','inside'),('顶部居中 · 桌宠上方','above')):anchor.addItem(label,value)
        anchor.activated.connect(lambda:pet.set_cost_float_anchor(anchor.currentData()));self.controls['turn_cost_anchor']=anchor;voice.addRow('飘字起点',anchor)
        cost_place=QHBoxLayout();cost_move=QPushButton('拖动微调位置');cost_move.clicked.connect(pet.toggle_cost_float_placer);cost_reset=QPushButton('回到预设位置');cost_reset.clicked.connect(lambda:pet.set_cost_float_offset(0,0));cost_place.addWidget(cost_move);cost_place.addWidget(cost_reset);voice.addRow('飘字位置',cost_place)
        cost_note=QLabel('金额按本轮 token 用量和 DeepSeek 官方价格估算，含子代理和联网搜索，按北京时间区分高峰和空闲价格，法定节假日按工作日价格算，可能略高。连接插件较旧时改用前后余额差，飘字最多等 5 秒，超时不显示；在“连接 DeepSeek”页重新安装连接插件即可改用估算。选择起点会清除拖动微调；微调最多偏离起点 400 像素，靠近屏幕边缘时会自动收回。');cost_note.setWordWrap(True);voice.addRow(cost_note)
        voice.section('桌面',self.preview('desk'))
        icon_style=QComboBox();icon_style.addItem('APP 小标','badged');icon_style.addItem('纯净图标','clean')
        icon_style.currentIndexChanged.connect(lambda:self.change('tray_icon_style',icon_style.currentData()));self.controls['tray_icon_style']=icon_style;voice.addRow('底部栏与托盘图标',icon_style)
        self.pack=QComboBox(); self.pack.addItem('163 · 小小守岸人','163'); self.pack.addItem('GB0227 · 近景表情','GB0227'); self.pack.currentIndexChanged.connect(lambda:pet.set_pack(self.pack.currentData()) if not self.loading else None); voice.addRow('默认表情风格',self.pack)
        self.top=QCheckBox('保持置顶'); self.top.toggled.connect(lambda value:pet.set_top(value) if not self.loading else None); voice.addRow(self.top)
        for key,label in (('edge_dock','拖到屏幕边缘时贴边藏起'),('daily_recap','每天显示一次小结'),('fullscreen_hide','全屏程序运行时隐藏')):
            box=QCheckBox(label); box.toggled.connect(lambda value,key=key:self.change(key,value)); self.controls[key]=box; voice.addRow(box)
        voice.addRow('贴边后多久藏起',self.spin('dock_tuck_seconds',10,600,' 秒'))
        dock_note=QLabel('把桌宠拖到屏幕左右边缘松手，它会先靠边待机，安静到设定时间后藏起一半；有任务进行、有提醒、鼠标移上去或你离开电脑 5 分钟以上时会出来。小结也可以从右键菜单“今日小结”随时查看。'); voice.addRow(dock_note)
        self.notes=QCheckBox('气泡显示已公开的任务进度'); self.notes.toggled.connect(lambda value:pet.set_notes(value) if not self.loading else None); voice.addRow(self.notes)
        voice.section('休息提醒',self.preview('rest'))
        rest=QCheckBox('开启喝水和久坐提醒'); rest.toggled.connect(lambda value:self.change('rest_reminder',value)); self.controls['rest_reminder']=rest; voice.addRow(rest)
        voice.addRow('提醒间隔',self.spin('rest_interval_minutes',15,240,' 分钟'))
        rest_note=QLabel('连续使用电脑到设定时间后，守岸人递上一杯奶茶，提醒卡片停留 10 秒。可以选择 30 分钟后再提醒、知道了，或关闭提醒。离开电脑 5 分钟以上会重新计时。'); voice.addRow(rest_note)
        voice.section('锁定',self.preview('lock'))
        locked=QCheckBox('锁定桌宠'); locked.toggled.connect(lambda value:self.change('interaction_locked',value)); self.controls['interaction_locked']=locked; voice.addRow(locked)
        voice.addRow('锁定悬停透明度',self.spin('locked_hover_transparency',0,95,' %'))
        voice.addRow('锁按钮大小',self.spin('lock_button_size',50,200,' %'))
        voice.addRow('锁按钮透明度',self.spin('lock_button_transparency',0,90,' %'))
        tip=QLabel('静音立即停止声音并暂停后续播报与试听，取消后恢复原音量。锁定后，角色区域的点击会穿透到下方窗口，鼠标移入时淡化；任务状态与完成提醒继续。小锁仍可解锁，余额框仍可点击刷新。也可从托盘打开设置解锁。'); tip.setWordWrap(True); voice.addRow(tip)
        voice.section('声音',self.preview('sound'))
        muted=QCheckBox('安静陪伴（静音）'); muted.toggled.connect(lambda value:self.change('audio_muted',value)); self.controls['audio_muted']=muted; voice.addRow(muted)
        enabled=QCheckBox('开启本地语音提醒'); enabled.toggled.connect(lambda v:self.change('audio_enabled',v)); self.controls['audio_enabled']=enabled; voice.addRow(enabled)
        voice.addRow('音量',self.spin('volume',0,100,' %'))
        voice.addRow('同一状态最短播报间隔',self.spin('audio_cooldown',0,300,' 秒'))
        row,self.audio_dir=self.path_control('audio_directory','选择音频目录',directory=True); voice.addRow('音频目录',row)
        stop=QPushButton('停止当前声音'); stop.clicked.connect(pet.voice.stop); voice.addRow(stop)
        note=QLabel('自动播报会先说完整句，GIF 切换不会截断声音。多会话完成提醒依次播放；忙时其他交互保留一条待播提醒，优先任务通知；待机／悬停不插队。思考默认每轮只播一次，轮次在实际播放时记账。主动试听或停止声音可以中断。'); note.setWordWrap(True); voice.addRow(note)
        transfer=self.tab('保存与迁移')
        transfer.section('保存')
        note=QLabel('修改会自动保存。你也可以立即保存快照，或把 GIF、字体、已绑定音频和配置一起打包。便携包还包含 Windows 运行程序。'); note.setWordWrap(True); transfer.addRow(note)
        self.add_button(transfer,'立即保存全部配置',self.save_now)
        self.add_button(transfer,'保存一份配置快照（JSON）',self.snapshot)
        transfer.section('导出与导入')
        self.add_button(transfer,'导出配置与素材包（ZIP）',lambda:self.export(False))
        self.add_button(transfer,'导出 Windows 便携完整包（ZIP）',lambda:self.export(True))
        self.add_button(transfer,'导入配置与素材包…',self.import_file)
        self.add_button(transfer,'创建桌面快捷方式',self.create_shortcut)
        tip=QLabel('迁移包会重置当前会话和本机连接路径，新电脑自动寻找已登录的 DeepSeek Harness（需安装连接插件）。不会包含账户凭据、聊天记录或额度缓存。'); tip.setWordWrap(True); transfer.addRow(tip)
        connect=self.tab('连接 DeepSeek')
        connect.section('连接')
        self.add_button(connect,'安装 / 更新 Harness 连接插件',self.install_bridge)
        note=QLabel('首次使用：登录官方 DeepSeek Harness，然后从托盘完全退出，点击上方安装按钮，再重新打开客户端。换电脑或更新连接插件时同样操作。'); note.setWordWrap(True); connect.addRow(note)
        reconnect=QPushButton('应用连接并刷新余额'); reconnect.clicked.connect(pet.refresh_quota); connect.addRow(reconnect)
        self.connection_status=QLabel(); self.connection_status.setObjectName('settingsLabel'); self.connection_status.setWordWrap(True); connect.addRow(self.connection_status)
        connect.section('启动与退出')
        launch=QCheckBox('随 DeepSeek 启动桌宠'); launch.toggled.connect(lambda value:self.change('launch_with_deepseek',value)); self.controls['launch_with_deepseek']=launch; connect.addRow(launch)
        exit_client=QCheckBox('随 DeepSeek 完全退出而关闭');exit_client.toggled.connect(lambda value:self.change('exit_with_deepseek',value));self.controls['exit_with_deepseek']=exit_client;connect.addRow(exit_client)
        note=QLabel('勾选后，登录 Windows 时会在后台等待 DeepSeek 打开，再启动桌宠。取消勾选会移除本机的启动联动。该选项随配置迁移，在新电脑首次手动启动桌宠后恢复。'); note.setWordWrap(True); connect.addRow(note)
        close_tip=QLabel('客户端完全退出约 8–10 秒后关闭桌宠；关闭窗口但仍在托盘运行时继续陪伴。手动先打开桌宠时，会等待客户端至少运行一次。');close_tip.setWordWrap(True);connect.addRow(close_tip)
        connect.section('跟随与数据目录')
        self.sessions=QComboBox(); self.sessions.currentIndexChanged.connect(self.select_thread); connect.addRow('跟随的会话',self.sessions)
        note=QLabel('推荐自动跟随最近活动。固定到已结束的旧会话后，其他会话的思考、查阅和编辑动画不会触发。'); note.setWordWrap(True); connect.addRow(note)
        row,self.deepseek_home=self.path_control('deepseek_home','选择 DeepSeek 数据目录',True); connect.addRow('数据目录',row)
        row,self.deepseek_exe=self.path_control('deepseek_executable','选择 DeepSeek Harness.exe',False); connect.addRow('DeepSeek 程序',row)
        note=QLabel('留空即可自动检测：数据目录使用 DSH_HOME 或当前用户的 .dsh；程序从官方默认安装位置查找。新电脑请先安装并登录 DeepSeek。'); note.setWordWrap(True); connect.addRow(note)
        updates=self.tab('版本与更新')
        updates.section('检查更新')
        current=QLabel(AUDIO_SESSION_NAME+'  ·  当前版本 v'+VERSION); current.setObjectName('settingsLabel'); updates.addRow(current)
        source=QComboBox()
        for text,value in [('自动选择（推荐）','auto'),('GitHub 官方源','github'),('镜像加速（中国大陆网络）','mirror')]:source.addItem(text,value)
        source.currentIndexChanged.connect(lambda:self.change('update_source',source.currentData()));self.controls['update_source']=source;updates.addRow('更新来源',source)
        updates.addRow('检查间隔',self.spin('update_interval_hours',1,168,' 小时'))
        automatic=QCheckBox('每次启动时检查更新'); automatic.toggled.connect(lambda value:self.change('check_updates_on_start',value)); self.controls['check_updates_on_start']=automatic; updates.addRow(automatic)
        periodic=QCheckBox('定时检查更新');periodic.toggled.connect(lambda value:self.change('check_updates_periodic',value));self.controls['check_updates_periodic']=periodic;updates.addRow(periodic)
        source_tip=QLabel('自动模式先尝试 GitHub，无法取得结果时切换镜像。镜像由第三方 GH-Proxy 提供，只负责传输；一键更新始终校验发布者签名，校验失败不会安装。也可手动固定来源。');source_tip.setWordWrap(True);updates.addRow(source_tip)
        updates.section('安装更新')
        install=QPushButton('一键更新');install.clicked.connect(pet.updates.install);install.setEnabled(not pet.updates.installing);pet.updates.install_changed.connect(install.setDisabled);updates.addRow(install)
        check=QPushButton('立即检查更新'); check.clicked.connect(lambda:pet.updates.check(True)); check.setEnabled(not pet.updates.busy); pet.updates.busy_changed.connect(lambda busy:check.setEnabled(not busy)); updates.addRow(check)
        restore=QPushButton('恢复已忽略版本的提醒'); restore.clicked.connect(lambda:self.change('ignored_update_version','')); updates.addRow(restore)
        self.update_status=QLabel(pet.updates.status); self.update_status.setObjectName('settingsLabel'); self.update_status.setWordWrap(True); pet.updates.status_changed.connect(self.update_status.setText); updates.addRow(self.update_status)
        tip=QLabel('发现新版时显示无声常驻气泡，语音台词结束后恢复。点击“一键更新”或气泡中的“更新并重启守岸人”，自动下载程序更新、保留配置素材并重启。“今日不再提醒”在当天及当天重启后保持生效。'); tip.setWordWrap(True); updates.addRow(tip)
        footer=QHBoxLayout(); self.status=QLabel('设置自动保存'); self.status.setWordWrap(True); footer.addWidget(self.status,1)
        close=QPushButton('完成'); close.setMinimumWidth(120); close.clicked.connect(self.hide); footer.addWidget(close); layout.addLayout(footer)
        self.wheel_guard=WheelGuard(self)
        self.jobs=Jobs(); self.jobs.finished.connect(self.job_finished); self.jobs.failed.connect(self.job_failed)
        self.refresh_controls(); self.loading=False; self.apply_style()
    def showEvent(self,event):
        # Start on the tab bar, never inside a choice the keyboard or wheel could change by accident.
        super().showEvent(event); self.tabs.tabBar().setFocus(); QTimer.singleShot(0,self.fit_pages)
    def fit_pages(self):
        """Grow the window, within its screen, until the widest page and every preview card are in view.
        Never shrinks a window the user made larger."""
        current=self.tabs.currentWidget()
        if not self.isVisible() or not isinstance(current,QScrollArea): return
        pages=[self.tabs.widget(i) for i in range(self.tabs.count())]
        need=max((page.widget().minimumSizeHint().width() for page in pages if isinstance(page,QScrollArea) and page.widget()),default=0)
        # Window edges, tabs and margins around the page, plus room for a page's own vertical scroll bar.
        bar=0 if current.verticalScrollBar().isVisible() else self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        chrome=self.width()-current.viewport().width()+bar
        screen=(self.screen() or QApplication.primaryScreen()).availableGeometry()
        frame=self.frameGeometry().width()-self.width(); title=self.frameGeometry().height()-self.height()
        width=max(self.width(),min(need+chrome,screen.width()-frame)); height=min(self.height(),screen.height()-title)
        if (width,height)==(self.width(),self.height()): return
        self.resize(width,height); g=self.frameGeometry()
        self.move(max(screen.left(),min(g.left(),screen.right()+1-g.width())),max(screen.top(),min(g.top(),screen.bottom()+1-g.height())))
    def line_style(self,kind):
        """Bold and italic switches and a colour button for one floating-text line."""
        row=QHBoxLayout(); row.setSpacing(10)
        for key,label in ((f'turn_cost_{kind}_bold','加粗'),(f'turn_cost_{kind}_italic','斜体')):
            box=QCheckBox(label); box.toggled.connect(lambda value,key=key:self.change(key,value)); self.controls[key]=box; row.addWidget(box)
        button=QPushButton('颜色'); button.setObjectName('colorButton'); button.setToolTip('点击打开调色盘')
        button.clicked.connect(lambda checked=False,kind=kind:self.choose_line_color(kind)); self.color_buttons[kind]=button; row.addWidget(button)
        reset=QPushButton('默认颜色'); reset.clicked.connect(lambda checked=False,kind=kind:self.set_line_color(kind,None)); row.addWidget(reset); row.addStretch(1)
        return row
    def choose_line_color(self,kind):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog
        colour=QColorDialog.getColor(QColor(self.pet.options[f'turn_cost_{kind}_color']),self,'计费颜色' if kind=='cost' else '计时颜色')
        if colour.isValid(): self.set_line_color(kind,colour.name())
    def set_line_color(self,kind,colour):
        from .appearance import DEFAULTS
        self.change(f'turn_cost_{kind}_color',colour or DEFAULTS[f'turn_cost_{kind}_color']); self.paint_color_buttons()
    def paint_color_buttons(self):
        for kind,button in self.color_buttons.items():
            colour=self.pet.options[f'turn_cost_{kind}_color']
            button.setText('颜色 '+colour.upper()); button.setStyleSheet(f'QPushButton{{border-left:16px solid {colour};padding-left:8px;}}')
    def preview(self,mode):
        view=CardPreview(self.pet,mode); self.previews[mode]=view; return view
    def select_page(self,title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index)==title: self.tabs.setCurrentIndex(index); break

    def tab(self,title):
        page=Page(); self.tabs.addTab(page.scroll,title); return page
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
        control.currentIndexChanged.connect(lambda:self.change(key,control.currentData())); self.controls[key]=control; return long_list(control)
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
        self.top.setChecked(self.pet.on_top); self.notes.setChecked(self.pet.show_notes); self.pack.setCurrentIndex(self.pack.findData(self.pet.pack))
        self.refresh_threads(); self.size_control.refresh(); self.editor.update_timing(); self.paint_color_buttons()
        self.order.set_state(self.pet.options['turn_cost_order'].split(','),{k:self.pet.options['turn_cost_show_'+k] for k in ('cost','time')})
        self.connection_status.setText('当前数据目录：'+str(self.pet.monitor.home)); self.loading=False
        for combo in self.findChildren(QComboBox):widen(combo)
    def refresh_threads(self):
        selected=self.pet.monitor.selected; self.sessions.blockSignals(True); self.sessions.clear(); self.sessions.addItem('自动跟随最近活动（推荐）','auto')
        for row in self.pet.thread_list: self.sessions.addItem(row['title'][:40],row['id'])
        if self.sessions.findData(selected)<0: self.sessions.addItem('固定会话（目前未在列表中）',selected)
        self.sessions.setCurrentIndex(self.sessions.findData(selected)); self.sessions.blockSignals(False); widen(self.sessions)
    def select_thread(self):
        if self.loading: return
        ok=self.pet.select_thread(self.sessions.currentData() or 'auto'); self.status.setText('跟随设置已保存' if ok else '跟随设置保存失败')
    def change_order(self,order,enabled):
        if self.loading: return
        self.change('turn_cost_order',','.join(order))
        for key,on in enabled.items(): self.change('turn_cost_show_'+key,on)
    def change(self,key,value):
        if self.loading: return
        try:
            ok=self.pet.set_option(key,value); self.status.setText('已自动保存' if ok else '保存失败，请检查目录权限。')
        except OSError as error:
            self.refresh_controls(); self.status.setText('设置未更改：'+str(error))
    def apply_style(self):
        size=int(self.pet.options['ui_font_size'])
        self.setStyleSheet(stylesheet(self.pet.options)+'QLabel#settingsTitle{font-size:25px;font-weight:600;color:#2e5280;}'
            +'QFrame#settingsCard{background:#ffffff;border:1px solid #dbe5f1;border-radius:12px;}'
            +f'QLabel#settingsSection{{font-size:{size+1}px;font-weight:600;color:#2e5280;}}'
            +f'QLabel#settingsNote{{font-size:{max(12,size-3)}px;color:#6f819b;}}'
            +'QLabel#settingsLabel{color:#3d5573;}QFrame#settingsCard QPushButton{padding:6px 16px;}')
        # A larger panel font widens the pages; keep every preview in view.
        if self.isVisible(): QTimer.singleShot(0,self.fit_pages)
    def create_shortcut(self):
        from .shortcuts import create_desktop_shortcut
        self.set_busy(True);self.status.setText('正在创建桌面快捷方式…')
        def work():
            try:self.jobs.finished.emit('桌面快捷方式已创建：'+str(create_desktop_shortcut(ROOT)))
            except Exception as error:self.jobs.failed.emit('创建失败：'+str(error))
        threading.Thread(target=work,daemon=True).start()
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
        for key in ('font_family','bubble_font_family','turn_cost_font_family'):
            control=self.controls[key]
            for family in self.pet.font_families:
                if control.findData(family)<0: control.addItem(family,family)
        self.status.setText('字体已加入桌宠目录，可从字体列表选择。')
