"""A short burst of confetti above the pet when a task completes."""
import math,random
from PySide6.QtCore import QElapsedTimer,QPointF,QRectF,Qt,QTimer
from PySide6.QtGui import QColor,QPainter
from PySide6.QtWidgets import QWidget

COLORS=('#e4572e','#f2a541','#3fa37a','#3a78c2','#d4537e','#8c6bd6')
PIECES=36;LIFE_MS=1500;SIZE=(360,300);GRAVITY=900.


class Confetti(QWidget):
    def __init__(self,pet,seed=None):
        super().__init__(pet,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowTransparentForInput)
        self.pet=pet;self.random=random.Random(seed);self.pieces=[];self.clock=QElapsedTimer()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('守岸人 · 撒花')
        self.timer=QTimer(self);self.timer.setInterval(16);self.timer.timeout.connect(self.step)

    def burst(self):
        s=self.pet.scale_factor;w,h=round(SIZE[0]*s),round(SIZE[1]*s);self.resize(w,h)
        x,y=self.pet.cost_float_anchor(0)
        area=self.pet.screen_area()
        self.move(max(area.left(),min(x-w//2,area.right()-w+1)),max(area.top(),min(y-h+round(40*s),area.bottom()-h+1)))
        origin=QPointF(x-self.x(),y-self.y()-round(20*s));r=self.random;self.pieces=[]
        for i in range(PIECES):
            angle=math.radians(r.uniform(-150,-30));speed=r.uniform(260,520)*s
            self.pieces.append(dict(p=QPointF(origin),v=QPointF(math.cos(angle)*speed,math.sin(angle)*speed),
                spin=r.uniform(-540,540),turn=r.uniform(0,360),color=QColor(COLORS[i%len(COLORS)]),size=(r.uniform(5,9)*s,r.uniform(8,13)*s)))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,self.pet.on_top)
        self.clock.start();self.last=0;self.show();self.timer.start()

    def step(self):
        now=self.clock.elapsed();dt=(now-self.last)/1000;self.last=now
        for piece in self.pieces:
            piece['v']+=QPointF(0,GRAVITY*self.pet.scale_factor*dt);piece['v']*=.985
            piece['p']+=piece['v']*dt;piece['turn']+=piece['spin']*dt
        if now>=LIFE_MS:self.timer.stop();self.hide()
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(Qt.PenStyle.NoPen)
        fade=1 if not self.clock.isValid() else max(0.,min(1.,(LIFE_MS-self.clock.elapsed())/400))
        p.setOpacity(fade)
        for piece in self.pieces:
            p.save();p.translate(piece['p']);p.rotate(piece['turn']);w,h=piece['size']
            p.setBrush(piece['color']);p.drawRoundedRect(QRectF(-w/2,-h/2,w,h),1.5,1.5);p.restore()
        p.end()
