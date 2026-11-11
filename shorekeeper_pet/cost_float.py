"""Damage-number style text that drifts up from the balance box."""
from PySide6.QtCore import Qt,QEasingCurve,QPoint,QPointF,QVariantAnimation
from PySide6.QtGui import QColor,QFontMetrics,QPainter,QPainterPath,QPen
from PySide6.QtWidgets import QWidget
from .appearance import font

RISE=78;DURATION=3200


class CostFloat(QWidget):
    def __init__(self,pet):
        super().__init__(pet,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowTransparentForInput)
        self.pet=pet; self.text=''; self.progress=0.; self.anchor=QPoint()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('守岸人 · 本轮花费')
        self.animation=QVariantAnimation(self); self.animation.setStartValue(0.); self.animation.setEndValue(1.)
        self.animation.setDuration(DURATION); self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.advance); self.animation.finished.connect(self.hide)

    def play(self,text,anchor):
        self.text=text; self.anchor=anchor
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,self.pet.on_top)
        self.font_used=font(self.pet.options['bubble_font_family'],round(28*self.pet.scale_factor),True)
        metrics=QFontMetrics(self.font_used)
        self.resize(metrics.horizontalAdvance(text)+36,metrics.height()+20)
        self.animation.stop(); self.advance(0.); self.show(); self.animation.start()

    def advance(self,value):
        self.progress=float(value)
        self.move(self.anchor.x()-self.width()//2,self.anchor.y()-self.height()-round(RISE*self.pet.scale_factor*self.progress))
        self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1 if self.progress<.55 else max(0,(1-self.progress)/.45))
        metrics=QFontMetrics(self.font_used); path=QPainterPath()
        path.addText(QPointF(18,10+metrics.ascent()),self.font_used,self.text)
        p.setPen(QPen(QColor(255,255,255,235),5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#e4572e')); p.drawPath(path); p.end()
