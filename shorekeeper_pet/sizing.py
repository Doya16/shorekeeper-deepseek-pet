"""Live, persistent sizing controls shared by the quick dialog and preferences."""
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QSlider,QSpinBox,QPushButton,QScrollArea
from .appearance import stylesheet
from .presentation_size import PresentationControl

def normalize_scale(value):
    try: value=float(value)
    except (ValueError,TypeError): return 1.0
    return max(.5,min(2.,value)) if math.isfinite(value) else 1.0

def fitted_scale(requested,width,height,area_width,area_height):
    return min(normalize_scale(requested),max(1,area_width)/width,max(1,area_height)/height)

class SizeControl(QWidget):
    def __init__(self,pet):
        super().__init__(); self.pet=pet
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        row=QHBoxLayout(); self.slider=QSlider(Qt.Orientation.Horizontal); self.slider.setRange(50,200); self.slider.setSingleStep(5); self.slider.setPageStep(10)
        self.slider.setAccessibleName('桌宠整体大小'); self.slider.setToolTip('拖动滑块，桌宠立即改变大小；松开后继续保留。')
        self.percent=QSpinBox(); self.percent.setRange(50,200); self.percent.setSuffix(' %'); self.percent.setSingleStep(5); self.percent.setKeyboardTracking(False)
        row.addWidget(self.slider,1); row.addWidget(self.percent); layout.addLayout(row)
        self.info=QLabel(); self.info.setWordWrap(True); layout.addWidget(self.info)
        row=QHBoxLayout()
        for title,callback in [('恢复 100%',lambda:pet.set_scale(1)),('适合当前屏幕',self.fit_screen)]:
            button=QPushButton(title); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        tip=QLabel('也可将鼠标放在桌宠上，按住 Ctrl 滚轮缩放。角色、气泡和额度条同步调整，所有修改自动保存。'); tip.setWordWrap(True); layout.addWidget(tip)
        self.slider.valueChanged.connect(self.change); self.percent.valueChanged.connect(self.change)
        pet.size_changed.connect(self.refresh); self.refresh()
    def change(self,percent):
        ok=self.pet.set_scale(percent/100)
        if not ok: self.info.setText('保存失败，请检查桌宠目录的写入权限。')
    def fit_screen(self):
        area=self.pet.screen_area()
        self.pet.set_scale(round(normalize_scale(area.height()*.27/self.pet.scene_height)*20)/20)
    def refresh(self):
        percent=round(self.pet.requested_scale*100)
        for control in (self.slider,self.percent):
            control.blockSignals(True); control.setValue(percent); control.blockSignals(False)
        detail='含余额框' if self.pet.options['show_quota'] else '余额框已隐藏'
        text=f'当前显示：{self.pet.width()} × {self.pet.height()}（{detail}）'
        if self.pet.scale_factor+0.005<self.pet.requested_scale: text+=f' · 当前屏幕自动适配为 {self.pet.scale_factor:.0%}'
        self.info.setText(text)

class SizeDialog(QDialog):
    def __init__(self,pet):
        super().__init__(None); self.pet=pet; self.setWindowTitle('守岸人 · 调整大小'); self.setWindowIcon(pet.icon); self.resize(600,620)
        layout=QVBoxLayout(self); layout.setContentsMargins(20,20,20,20)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); body.setObjectName('settingsBody'); content=QVBoxLayout(body); scroll.setWidget(body); layout.addWidget(scroll)
        title=QLabel('拖动滑块，直接看桌宠的变化'); content.addWidget(title)
        self.control=SizeControl(pet); content.addWidget(self.control)
        self.presentation_control=PresentationControl(pet); content.addWidget(self.presentation_control)
        done=QPushButton('完成'); done.clicked.connect(self.hide); layout.addWidget(done); self.apply_style()
    def apply_style(self): self.setStyleSheet(stylesheet(self.pet.options))
