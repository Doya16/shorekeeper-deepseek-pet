"""Visual, per-interaction GIF editor for the existing desktop companion."""
import time
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QPixmap,QIcon
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QLineEdit,QComboBox,QPushButton,QAbstractItemView
from .bindings import PLAYBACKS

TRIGGERS={
 'pet':('单击 / 摸头','单击角色，或从右键菜单选择“摸摸头”。'),
 'feed':('递奶茶','从右键菜单选择“递一杯奶茶”。'),
 'hover':('鼠标停留','鼠标在角色上停留 1 秒时触发；移开后恢复任务状态。'),
 'drag':('拖动中','按住角色并移动时播放，持续到松开。'),
 'drop':('松开 / 放下','拖动结束、放下角色时播放。'),
 'doubleclick':('双击角色','双击角色时触发绑定的 GIF、语音和气泡，不打开面板。'),
 'idle':('待机陪伴','没有正在运行的任务，或任务完成一段时间后。'),
 'thinking':('整理 / 思考中','任务开始或工具返回后，等待下一次公开操作。'),
 'reading':('查阅资料','检测到搜索、读取、查看等工具操作时。'),
 'writing':('编辑内容','检测到修改文件等编辑操作时。'),
 'working':('执行工具','检测到其他正在执行的工具操作时。'),
 'waiting':('等待你回应','DeepSeek 发起需要用户回答的问题时。'),
 'done':('任务完成','检测到最终回复或任务完成事件时。'),
 'error':('任务出错','检测到任务错误事件时。'),
 'paused':('任务暂停','检测到任务被中断时。'),
 'unknown':('状态未更新','活动任务较长时间没有新的可识别状态时。'),
}

class BindingEditor(QDialog):
    def __init__(self,pet,catalog,asset_table,root):
        super().__init__(None)
        self.pet=pet; self.catalog=catalog; self.assets=asset_table; self.root=root
        self.state='pet'; self.loading=False; self.preview_animation=None; self.preview_start=0
        self.setWindowTitle('守岸人 · 自定义 GIF 绑定')
        self.setWindowIcon(pet.icon)
        self.resize(930,735); self.setMinimumSize(820,620)
        self.setStyleSheet('''QDialog{background:#f4f7fc;color:#2c4260;} QLabel{color:#3b5373;font:13px "Microsoft YaHei";} QListWidget{background:white;border:1px solid #d7e2f0;border-radius:10px;color:#344c6b;font:12px "Microsoft YaHei";outline:0;} QListWidget::item{border-radius:6px;padding:4px;} QListWidget::item:selected{background:#dceaff;color:#244a82;} QListWidget::item:hover{background:#edf4ff;} QLineEdit,QComboBox,QPushButton{color:#344c6b;background:white;border:1px solid #cad9ee;border-radius:7px;padding:7px 10px;font:12px "Microsoft YaHei";} QPushButton:hover{background:#e5effe;} QComboBox QAbstractItemView{background:white;color:#344c6b;selection-background-color:#dceaff;selection-color:#244a82;}''')
        outer=QVBoxLayout(self); outer.setContentsMargins(22,18,22,18); outer.setSpacing(10)
        heading=QLabel('让每一种回应，都由你来选'); heading.setStyleSheet('font-size:21px;font-weight:600;color:#2f4d79;'); outer.addWidget(heading)
        hint=QLabel('先选左侧交互，再点击右侧 GIF。自动保存，立即生效。'); outer.addWidget(hint)
        body=QHBoxLayout(); body.setSpacing(18); outer.addLayout(body,1)
        self.triggers=QListWidget(); self.triggers.setFixedWidth(210)
        for state,(label,desc) in TRIGGERS.items():
            item=QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole,state); item.setToolTip(desc); self.triggers.addItem(item)
        self.triggers.currentItemChanged.connect(self.select_trigger); body.addWidget(self.triggers)
        right=QVBoxLayout(); right.setSpacing(9); body.addLayout(right,1)
        self.heading=QLabel(); self.heading.setStyleSheet('font-size:17px;font-weight:600;'); right.addWidget(self.heading)
        self.description=QLabel(); self.description.setWordWrap(True); right.addWidget(self.description)
        top=QHBoxLayout(); top.setSpacing(18); right.addLayout(top)
        self.preview=QLabel(); self.preview.setFixedSize(176,176); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setStyleSheet('background:#e9eff8;border:1px solid #dae4f2;border-radius:12px;'); top.addWidget(self.preview)
        controls=QVBoxLayout(); top.addLayout(controls,1)
        self.current=QLabel(); self.current.setWordWrap(True); controls.addWidget(self.current)
        controls.addWidget(QLabel('播放方式'))
        self.playback=QComboBox()
        for key,label in PLAYBACKS.items(): self.playback.addItem(label,key)
        self.playback.currentIndexChanged.connect(self.change_playback); controls.addWidget(self.playback)
        self.try_button=QPushButton('在桌宠上试一下'); self.try_button.clicked.connect(self.try_binding); controls.addWidget(self.try_button)
        self.reset_button=QPushButton('此项恢复默认'); self.reset_button.clicked.connect(self.reset_binding); controls.addWidget(self.reset_button); controls.addStretch()
        self.search=QLineEdit(); self.search.setPlaceholderText('搜索 GIF 名称，例如：摸头、思考、加班'); self.search.textChanged.connect(self.filter_gallery); right.addWidget(self.search)
        self.gallery=QListWidget(); self.gallery.setViewMode(QListWidget.ViewMode.IconMode); self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust); self.gallery.setMovement(QListWidget.Movement.Static); self.gallery.setIconSize(QSize(78,78)); self.gallery.setGridSize(QSize(113,113)); self.gallery.setWordWrap(True); self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for asset in catalog:
            # Read a single original frame for the picker thumbnail, never regenerate art.
            pixmap=QPixmap(str(root/asset['path']))
            icon=QIcon(pixmap.scaled(78,78,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            name=asset['name'].removesuffix('.gif')
            pack='163' if asset['id'].startswith('p3') else ('DLC' if asset['id'].startswith('p2') else 'GB0227')
            item=QListWidgetItem(icon,name+'\n'+pack); item.setData(Qt.ItemDataRole.UserRole,asset['id']); item.setToolTip(f"{asset['id']} · {name}\n{asset['frames']} 帧 / {asset['duration_ms']/1000:.2f} 秒"); self.gallery.addItem(item)
        self.gallery.currentItemChanged.connect(self.choose_asset); right.addWidget(self.gallery,1)
        self.saved=QLabel(''); self.saved.setStyleSheet('color:#587da0;font-size:12px;'); right.addWidget(self.saved)
        bottom=QHBoxLayout(); foot=QLabel('自定义绑定跨画风保留；“恢复默认”后才跟随画风。'); foot.setStyleSheet('color:#788ba4;font-size:11px;'); bottom.addWidget(foot,1)
        close=QPushButton('完成'); close.clicked.connect(self.hide); bottom.addWidget(close); outer.addLayout(bottom)
        self.timer=QTimer(self); self.timer.setInterval(30); self.timer.timeout.connect(self.animate_preview)
        self.triggers.setCurrentRow(0)

    def select_trigger(self,item,old=None):
        if item is None: return
        self.state=item.data(Qt.ItemDataRole.UserRole); self.load_selection()

    def load_selection(self):
        self.loading=True
        binding=self.pet.binding(self.state); asset=self.assets[binding['asset']]
        self.heading.setText(TRIGGERS[self.state][0]); self.description.setText(TRIGGERS[self.state][1])
        self.current.setText(('已自定义' if binding['custom'] else '跟随画风默认')+'\n'+asset['name'].removesuffix('.gif'))
        self.playback.setCurrentIndex(self.playback.findData(binding['playback']))
        for i in range(self.gallery.count()):
            item=self.gallery.item(i)
            if item.data(Qt.ItemDataRole.UserRole)==binding['asset']:
                self.gallery.setCurrentItem(item); self.gallery.scrollToItem(item); break
        self.preview_animation=self.pet.get_animation(binding['asset']); self.preview_start=time.monotonic()
        self.saved.setText('当前设置已保存' if binding['custom'] else '使用默认绑定，点击任意 GIF 可修改')
        self.refresh_labels(); self.loading=False; self.animate_preview()

    def refresh_labels(self):
        for i in range(self.triggers.count()):
            item=self.triggers.item(i); state=item.data(Qt.ItemDataRole.UserRole)
            item.setText(TRIGGERS[state][0]+('  · 自定义' if self.pet.binding(state)['custom'] else ''))

    def choose_asset(self,item,old=None):
        if self.loading or item is None: return
        self.pet.set_binding(self.state,asset=item.data(Qt.ItemDataRole.UserRole)); self.load_selection()

    def change_playback(self):
        if self.loading: return
        self.pet.set_binding(self.state,playback=self.playback.currentData()); self.load_selection()

    def reset_binding(self): self.pet.reset_binding(self.state); self.load_selection()
    def try_binding(self): self.pet.preview_binding(self.state); self.preview_start=time.monotonic()

    def filter_gallery(self,text):
        needle=text.strip().casefold()
        for i in range(self.gallery.count()):
            item=self.gallery.item(i); item.setHidden(needle not in (item.text()+' '+item.toolTip()).casefold())

    def animate_preview(self):
        if self.preview_animation is None: return
        mode=self.pet.binding(self.state)['playback']
        frame=self.preview_animation.frame((time.monotonic()-self.preview_start)*1000,playback=mode)
        self.preview.setPixmap(QPixmap.fromImage(frame).scaled(172,172,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def showEvent(self,event): self.load_selection(); self.timer.start(); super().showEvent(event)
    def hideEvent(self,event): self.timer.stop(); self.pet.clear_override(); super().hideEvent(event)
