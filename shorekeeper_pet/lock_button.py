"""A small hover-revealed lock toggle above the character."""
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QPainterPath,QPen,QColor,QCursor
from PySide6.QtWidgets import QAbstractButton


class LockButton(QAbstractButton):
    def __init__(self,pet):
        super().__init__(pet);self.pet=pet;self.hovered=False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCheckable(True)
        self.clicked.connect(lambda checked:pet.set_option('interaction_locked',checked))
        self.sync();self.hide()

    def sync(self):
        self.setChecked(self.pet.locked)
        text='点击解锁' if self.pet.locked else '点击锁定'
        self.setToolTip(text);self.setAccessibleName(text);self.update()

    def position_on_pet(self):
        p=self.pet;s=p.scale_factor;r=p.pet_rect
        size=max(1,round(28*p.options['lock_button_size']/100*p.options['pet_size']/230*s))
        self.setGeometry(round(r.center().x()*s-size/2),max(0,round(r.top()*s)),size,size)
        self.sync();self.raise_();self.refresh_visibility()

    def refresh_visibility(self):
        p=self.pet
        over=p.pet_rect.contains(p.mapFromGlobal(QCursor.pos())/p.scale_factor)
        self.setVisible(p.isVisible() and (over or self.isDown()))

    def enterEvent(self,event):
        self.hovered=True;self.pet.hover_timer.stop();self.pet.click_timer.stop();self.update()
        super().enterEvent(event)

    def leaveEvent(self,event):
        self.hovered=False;self.update();super().leaveEvent(event)

    def mousePressEvent(self,event):
        self.pet.hover_timer.stop();self.pet.click_timer.stop()
        if event.button()==Qt.MouseButton.LeftButton:self.setDown(True)
        self.refresh_visibility();event.accept()

    def mouseMoveEvent(self,event):
        self.pet.hover_timer.stop()
        if event.buttons()&Qt.MouseButton.LeftButton:self.setDown(self.rect().contains(event.position().toPoint()))
        event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            activate=self.isDown() and self.rect().contains(event.position().toPoint())
            self.setDown(False)
            if activate:self.click()
        event.accept()

    def mouseDoubleClickEvent(self,event): self.setDown(False);event.accept()
    def wheelEvent(self,event): event.accept()
    def contextMenuEvent(self,event): self.pet.contextMenuEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width()/36,self.height()/36)
        opacity=1-self.pet.options['lock_button_transparency']/100
        painter.setOpacity(opacity)
        if self.isDown():painter.translate(0,1)
        # Both outlines remain legible over light hair and dark backgrounds.
        shackle=QPainterPath()
        if self.isChecked():
            shackle.moveTo(11,17);shackle.lineTo(11,11);shackle.cubicTo(11,2,25,2,25,11);shackle.lineTo(25,17)
        else:
            shackle.moveTo(13,17);shackle.lineTo(13,10);shackle.cubicTo(13,1,28,1,28,10)
        painter.setPen(QPen(QColor('#203f67'),5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));painter.drawPath(shackle)
        painter.setPen(QPen(QColor('#edf6ff'),2.8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));painter.drawPath(shackle)
        painter.setPen(QPen(QColor('#dbefff'),1.5))
        painter.setBrush(QColor('#2c6598' if self.isChecked() else '#55728e'))
        painter.drawRoundedRect(QRectF(7,16,22,16),4,4)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#f3faff'))
        painter.drawEllipse(QRectF(16.2,21,3.6,3.6));painter.drawRoundedRect(QRectF(17,23,2,4),.8,.8)
        painter.end()
