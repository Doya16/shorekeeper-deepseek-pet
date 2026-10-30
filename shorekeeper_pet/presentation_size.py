"""Independent bubble width and quota scale, relative to the pet's zoom."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSlider,QSpinBox,QCheckBox,QPushButton

LIMITS={'bubble_width_ratio':(75,400),'quota_scale':(50,250)}

def edge_at(point,rect):
    if not rect.adjusted(-7,-2,7,2).contains(point): return 0
    left=abs(point.x()-rect.left()); right=abs(point.x()-rect.right())
    return (-1 if left<right else 1) if min(left,right)<=10 else 0

def paint_grips(painter,rect,scale=1):
    painter.save(); painter.setPen(QPen(QColor('#83a4c9'),2/max(scale,.1)))
    half=min(7/max(scale,.1),rect.height()/5)
    for x in (rect.left()+4/max(scale,.1),rect.right()-4/max(scale,.1)):
        painter.drawLine(round(x),round(rect.center().y()-half),round(x),round(rect.center().y()+half))
    painter.restore()

class EdgeResize:
    def __init__(self,widget,pet,key):
        self.widget=widget; self.pet=pet; self.key=key; self.active=False; self.text=''; self.state='idle'

    def begin(self,event,rect,unit):
        if self.pet.locked: return False
        side=edge_at(event.position(),rect)
        if event.button()!=Qt.MouseButton.LeftButton or not side: return False
        self.text=self.pet.bubble_text(); self.state=self.pet.bubble_state()
        self.start_x=event.globalPosition().x(); self.start_value=self.pet.options[self.key]
        self.side=side; self.unit=unit; self.active=True
        self.pet.hover_timer.stop(); self.pet.click_timer.stop()
        self.widget.setCursor(Qt.CursorShape.SizeHorCursor); event.accept(); return True

    def move(self,event,rect):
        if self.pet.locked:
            self.finish(); self.widget.unsetCursor(); return False
        if self.active:
            value=self.start_value+2*self.side*(event.globalPosition().x()-self.start_x)/self.unit
            self.pet.set_presentation_size(self.key,value,save=False)
            event.accept(); return True
        self.widget.setCursor(Qt.CursorShape.SizeHorCursor if edge_at(event.position(),rect) else Qt.CursorShape.ArrowCursor)
        return False

    def finish(self,event=None):
        if not self.active: return False
        if event is not None and event.button()!=Qt.MouseButton.LeftButton: return False
        self.active=False; self.widget.unsetCursor()
        self.pet.save_settings(); self.pet.update_layout()
        if event is not None: event.accept()
        return True

class PresentationControl(QWidget):
    def __init__(self,pet,quota=True):
        super().__init__(); self.pet=pet; self.controls={}; self.source=id(self)
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0)
        items=[('气泡宽度','bubble_width_ratio')]+([('配额条大小','quota_scale')] if quota else [])
        for label,key in items:
            box.addWidget(QLabel(label)); row=QHBoxLayout(); slider=QSlider(Qt.Orientation.Horizontal); spin=QSpinBox()
            for control in (slider,spin): control.setRange(*LIMITS[key]); control.setSingleStep(5); control.setAccessibleName(label)
            spin.setSuffix(' %'); spin.setKeyboardTracking(False)
            slider.valueChanged.connect(lambda v,key=key:self.change(key,v)); spin.valueChanged.connect(lambda v,key=key:self.change(key,v))
            row.addWidget(slider,1); row.addWidget(spin); box.addLayout(row); self.controls[key]=(slider,spin)
        self.info=QLabel(); self.info.setWordWrap(True); box.addWidget(self.info)
        row=QHBoxLayout(); self.preview=QCheckBox('显示气泡预览（无声音）'); self.preview.toggled.connect(lambda on:pet.set_bubble_preview(self.source,on)); row.addWidget(self.preview)
        reset=QPushButton('恢复比例'); reset.clicked.connect(self.reset); row.addWidget(reset); box.addLayout(row)
        tip=QLabel('也可拖动气泡或配额条左右两侧的小竖线。气泡只改变宽度；配额条连同文字一起缩放。调整后随桌宠整体缩放，自动保存。'); tip.setWordWrap(True); box.addWidget(tip)
        pet.size_changed.connect(self.refresh); self.refresh()

    def change(self,key,percent):
        if not self.pet.set_presentation_size(key,percent/100): self.info.setText('保存失败，请检查桌宠目录是否可写。')

    def reset(self):
        for key in self.controls: self.pet.set_presentation_size(key,1)

    def refresh(self):
        for key,controls in self.controls.items():
            for control in controls:
                control.blockSignals(True); control.setValue(round(self.pet.options[key]*100)); control.blockSignals(False)
        p=self.pet
        self.info.setText(f'当前气泡宽度 {p.bubble_window.width()} px · 配额条 {round(p.quota_rect.width()*p.scale_factor)} × {round(p.quota_rect.height()*p.scale_factor)} px\n百分比独立保存；屏幕放不下时临时适配，换到大屏后恢复。')

    def hideEvent(self,event):
        self.preview.setChecked(False); self.pet.set_bubble_preview(self.source,False); super().hideEvent(event)
