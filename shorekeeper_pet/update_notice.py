"""Persistent, silent update card; speech captions temporarily take its place."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QFrame,QVBoxLayout,QLabel,QPushButton,QWidget,QApplication
from .appearance import stylesheet

class UpdateNotice(QFrame):
    def __init__(self,controller):
        pet=controller.pet
        flags=Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowStaysOnTopHint
        super().__init__(pet if isinstance(pet,QWidget) else None,flags)
        self.controller=controller;self.pet=pet;self.style_key=None
        self.setObjectName('updateNotice');self.setWindowTitle('守岸人 · 版本更新')
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        box=QVBoxLayout(self);box.setContentsMargins(16,14,16,14);box.setSpacing(8)
        self.title=QLabel('守岸人 · 有新版本');self.title.setWordWrap(True);box.addWidget(self.title)
        self.text=QLabel();self.text.setTextFormat(Qt.TextFormat.PlainText);self.text.setWordWrap(True);box.addWidget(self.text)
        self.install_button=QPushButton('更新并重启守岸人');self.install_button.clicked.connect(controller.install);box.addWidget(self.install_button)
        self.snooze_button=QPushButton('今日不再提醒');self.snooze_button.clicked.connect(controller.snooze_today);box.addWidget(self.snooze_button)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#6592c9'),2));painter.setBrush(QColor('#e7f1ff'))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),16,16)

    def refresh(self):
        c=self.controller;p=self.pet
        visible=getattr(p,'isVisible',lambda:True)()
        voice=getattr(p,'voice',None)
        speaking=bool(voice and voice.busy and p.bubble_visible())
        preview=bool(getattr(p,'presentation_previews',False))
        if not c.should_remind() or not visible or speaking or preview:
            self.hide();return False
        options=p.options;key=(options['font_family'],options['ui_font_size'])
        if key!=self.style_key:
            self.setStyleSheet(stylesheet(options)+'QFrame#updateNotice{background:#e7f1ff;border:2px solid #6592c9;border-radius:16px;}')
            self.style_key=key
        self.text.setText(('新版 v'+c.latest.version+'\n设置 → 版本与更新 → 一键更新') if not c.installing else c.status)
        self.install_button.setEnabled(not c.installing);self.snooze_button.setEnabled(not c.installing)
        area=p.screen_area() if hasattr(p,'screen_area') else QApplication.primaryScreen().availableGeometry()
        scale=getattr(p,'scale_factor',1)
        self.setFixedWidth(min(area.width(),max(300,min(440,round(360*scale)))))
        self.adjustSize()
        if isinstance(p,QWidget):
            center=p.frameGeometry().center().x();x=max(area.left(),min(center-self.width()//2,area.right()-self.width()+1))
            y=p.y()-self.height()-6
            if y<area.top():y=min(area.bottom()-self.height()+1,p.y()+p.height()+6)
            self.move(x,max(area.top(),y))
        self.show();return True
