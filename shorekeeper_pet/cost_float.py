"""Damage-number style text that drifts up from the balance box, rests, then fades."""
import math
from PySide6.QtCore import Qt,QEasingCurve,QPointF,QRectF,QVariantAnimation
from PySide6.QtGui import QColor,QFont,QFontMetricsF,QPainter,QPen,QPixmap
from PySide6.QtWidgets import QWidget
from .appearance import font

RISE=78;OFFSET_LIMIT=400;SAMPLE='-¥0.1234'
APPEAR_MS=150;RISE_MS=900;HOLD_MS=4000;FADE_MS=600
TOTAL_MS=RISE_MS+HOLD_MS+FADE_MS
OUTLINES={'none':0,'thin':1.5,'thick':3}
ANCHORS=('bottom','inside','above')
INSIDE_MARGIN=.08  # "inside" starts this far below the top of the pet image
PAD_X=14;PAD_Y=8
EASE=QEasingCurve(QEasingCurve.Type.OutCubic)


def clamp_offset(dx,dy,limit=OFFSET_LIMIT):
    return max(-limit,min(limit,round(dx))),max(-limit,min(limit,round(dy)))


def place(anchor,size,offset,area,rise,progress):
    """Top-left corner on screen. The start is kept low enough for the whole rise to stay visible."""
    left,top,right,bottom=area
    x=max(left,min(anchor[0]+offset[0]-size[0]//2,right-size[0]+1))
    y=max(top+rise,min(anchor[1]+offset[1]-size[1],bottom-size[1]+1))
    return x,y-round(rise*progress)


def timeline(ms):
    """How far the text has risen and how visible it is, ms after it started."""
    ms=max(0.,float(ms))
    risen=EASE.valueForProgress(min(1.,ms/RISE_MS))
    if ms<APPEAR_MS:opacity=ms/APPEAR_MS
    elif ms<RISE_MS+HOLD_MS:opacity=1.
    else:opacity=max(0.,1-(ms-RISE_MS-HOLD_MS)/FADE_MS)
    return risen,opacity


def text_font(pet):
    # Regular weight: most bundled display fonts have no bold face, and a faked bold smears the edges.
    used=font(pet.options['turn_cost_font_family'],round(pet.options['turn_cost_font_size']*pet.scale_factor))
    used.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    used.setStyleStrategy(QFont.StyleStrategy.PreferQuality)
    return used


def outline_width(pet):
    return OUTLINES.get(pet.options['turn_cost_outline'],0)*pet.scale_factor


LINE_COLORS={'cost':'#e4572e','time':'#2f6db5'}
SMALL=.72  # the time line is smaller than the amount
SAMPLES={'cost':SAMPLE,'time':'用时 4分12秒'}


def lines_of(text):
    """A single string is one amount line; otherwise a list of (text, kind)."""
    return [(text,'cost')] if isinstance(text,str) else [(t,k) for t,k in text if t]


def line_font(used,kind):
    if kind!='time':return used
    small=QFont(used);small.setPixelSize(max(10,round(used.pixelSize()*SMALL)));return small


def sample_lines(options):
    order=[k for k in options['turn_cost_order'].split(',') if options.get('turn_cost_show_'+k)]
    return [(SAMPLES[k],k) for k in order] or [(SAMPLE,'cost')]


def text_size(used,text,outline):
    edge=math.ceil(outline);lines=lines_of(text)
    width=max(QFontMetricsF(line_font(used,k)).horizontalAdvance(t) for t,k in lines)
    height=sum(QFontMetricsF(line_font(used,k)).height() for t,k in lines)
    return math.ceil(width)+2*(PAD_X+edge),math.ceil(height)+2*(PAD_Y+edge)


def render(used,text,outline,ratio):
    """The text drawn once at the screen's real pixel density, so it stays sharp while it moves."""
    width,height=text_size(used,text,outline);edge=math.ceil(outline)
    image=QPixmap(round(width*ratio),round(height*ratio));image.setDevicePixelRatio(ratio);image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    top=PAD_Y+edge
    for line,kind in lines_of(text):
        f=line_font(used,kind);metrics=QFontMetricsF(f);p.setFont(f)
        base=QPointF((width-metrics.horizontalAdvance(line))/2,top+metrics.ascent())
        if outline:
            # A halo of the same glyphs, so the outline lines up exactly with the hinted text.
            p.setPen(QColor(255,255,255,240));steps=max(12,round(outline*12))
            for ring in (outline,outline/2):
                for i in range(steps):
                    a=2*math.pi*i/steps;p.drawText(base+QPointF(ring*math.cos(a),ring*math.sin(a)),line)
        p.setPen(QColor(LINE_COLORS.get(kind,LINE_COLORS['cost'])));p.drawText(base,line);top+=metrics.height()
    p.end()
    return image


class CostFloat(QWidget):
    def __init__(self,pet):
        super().__init__(pet,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowTransparentForInput)
        self.pet=pet;self.text='';self.elapsed=0.;self.opacity=0.;self.used=None;self.image=None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('守岸人 · 本轮花费')
        self.animation=QVariantAnimation(self);self.animation.setStartValue(0.);self.animation.setEndValue(float(TOTAL_MS))
        self.animation.setDuration(TOTAL_MS)
        self.animation.valueChanged.connect(self.advance);self.animation.finished.connect(self.hide)

    def rise(self):return round(RISE*self.pet.scale_factor)

    def play(self,text):
        self.text=chr(10).join(line for line,kind in lines_of(text));self.used=text_font(self.pet);outline=outline_width(self.pet)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,self.pet.on_top)
        self.resize(*text_size(self.used,text,outline))
        self.image=render(self.used,text,outline,self.pet.devicePixelRatioF())
        self.animation.stop();self.advance(0.);self.show();self.animation.start()

    def advance(self,value):
        # Recomputed every frame so the text follows the pet if it is dragged.
        self.elapsed=float(value);risen,self.opacity=timeline(self.elapsed)
        self.move(*self.pet.cost_float_position((self.width(),self.height()),self.rise(),risen))
        self.update()

    def paintEvent(self,event):
        if self.image is None:return
        p=QPainter(self);p.setOpacity(self.opacity);p.drawPixmap(0,0,self.image);p.end()


class CostFloatPlacer(QWidget):
    """A draggable sample of the text where it comes to rest. Double-click, or the settings button, finishes."""

    def __init__(self,pet):
        super().__init__(pet,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowStaysOnTopHint)
        self.pet=pet;self.image=None;self.key=None;self.grab_at=None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('守岸人 · 飘字位置')
        self.setToolTip('拖到想要的位置，双击完成')
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.sync()

    def sync(self):
        o=self.pet.options;lines=sample_lines(o);key=(o['turn_cost_font_family'],o['turn_cost_font_size'],o['turn_cost_outline'],tuple(lines),self.pet.scale_factor,self.pet.devicePixelRatioF())
        if key!=self.key:
            self.key=key;used=text_font(self.pet);outline=outline_width(self.pet)
            self.resize(*text_size(used,lines,outline));self.image=render(used,lines,outline,self.pet.devicePixelRatioF());self.update()
        if self.grab_at is None:self.place_now()

    def rise(self):return round(RISE*self.pet.scale_factor)

    def place_now(self):
        self.move(*self.pet.cost_float_position((self.width(),self.height()),self.rise(),1.))

    def offset_at(self,x,y):
        # The sample sits where the text rests; the stored offset is where it starts, one rise lower.
        return self.pet.cost_float_offset_for(x,y+self.rise(),self.width(),self.height())

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.grab_at=event.position()
        event.accept()

    def mouseMoveEvent(self,event):
        if self.grab_at is None:return
        corner=event.globalPosition()-self.grab_at
        self.pet.set_cost_float_offset(*self.offset_at(corner.x(),corner.y()),save=False)
        self.place_now()
        # Store where the screen edge actually allowed it to go.
        self.pet.set_cost_float_offset(*self.offset_at(self.x(),self.y()),save=False)
        event.accept()

    def mouseReleaseEvent(self,event):
        if self.grab_at is not None:
            self.grab_at=None;self.pet.set_cost_float_offset(self.pet.options['turn_cost_offset_x'],self.pet.options['turn_cost_offset_y'])
        event.accept()

    def mouseDoubleClickEvent(self,event):
        self.grab_at=None;self.hide();event.accept()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#588ccd'),2,Qt.PenStyle.DashLine));p.setBrush(QColor(249,252,255,150))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),10,10)
        if self.image is not None:p.drawPixmap(0,0,self.image)
        p.end()
