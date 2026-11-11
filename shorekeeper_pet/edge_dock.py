"""Tuck the pet half behind a screen edge after it is dragged there.

It slides out while the pointer is over it or while it is announcing something, then slides back.
Only outer edges count: dragging onto a neighbouring monitor never docks.
"""
from PySide6.QtCore import QEasingCurve,QPoint,QPropertyAnimation,QRect,QTimer
from PySide6.QtWidgets import QApplication

SNAP=18          # releasing the pet this close to an outer edge docks it
VISIBLE=.6       # share of the art still on screen while tucked, when it has no wall to peek from
WALL_SHOWN=.06   # how much of a wall stays visible, as a share of the art's width
MARGIN=6         # gap to the edge when it slides out
HIDE_DELAY=1200  # ms after the pointer leaves, before it slides back
SLIDE_MS=220


def wall_fraction(image,tolerance=18):
    """The tucked art (by default a pose peeking from behind a wall on its right) is cut just past where the wall
    starts, so a strip of wall shows at the screen edge. Art without such a wall keeps VISIBLE of its width."""
    width,height=image.width(),image.height()
    if width<20 or height<20:return VISIBLE
    edge=image.pixelColor(width-3,height//2)
    if edge.alpha()<200:return VISIBLE
    rows=range(0,height,max(1,height//60))
    def wall(x):
        hits=0
        for y in rows:
            c=image.pixelColor(x,y)
            hits+=c.alpha()>200 and abs(c.red()-edge.red())<tolerance and abs(c.green()-edge.green())<tolerance and abs(c.blue()-edge.blue())<tolerance
        return hits>.85*len(rows)
    for x in range(width//4,width):
        if wall(x):
            start=x/width
            return min(.95,start+WALL_SHOWN) if .3<=start<=.9 else VISIBLE
    return VISIBLE


class EdgeDock:
    def __init__(self,pet):
        self.pet=pet;self.side=None;self.area=None;self.tucked=False;self.fraction_for=None;self.fraction=VISIBLE
        self.animation=QPropertyAnimation(pet,b'pos',pet);self.animation.setDuration(SLIDE_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.timer=QTimer(pet);self.timer.setSingleShot(True);self.timer.timeout.connect(self.tuck_if_idle)

    @property
    def docked(self):return self.side is not None

    def pet_global(self):
        r=self.pet.pet_rect;s=self.pet.scale_factor
        return QRect(round(self.pet.x()+r.left()*s),round(self.pet.y()+r.top()*s),round(r.width()*s),round(r.height()*s))

    @staticmethod
    def outer(area,side):
        """True when no other screen continues past this edge."""
        y=area.center().y()
        probe=QPoint(area.left()-4,y) if side=='left' else QPoint(area.right()+4,y)
        return QApplication.screenAt(probe) is None

    def try_dock(self,area):
        """Called when a drag ends, before the window is pulled back onto the screen."""
        if not self.pet.options['edge_dock']:return False
        g=self.pet_global()
        for side,near in (('left',g.left()<=area.left()+SNAP),('right',g.right()>=area.right()-SNAP)):
            if near and self.outer(area,side):
                self.side=side;self.area=QRect(area);self.place(True);return True
        return False

    def restore(self,side,area):
        if self.pet.options['edge_dock'] and side in ('left','right') and self.outer(area,side):
            self.side=side;self.area=QRect(area);self.place(True,animate=False)

    def art(self):
        return self.pet.binding('hover')['asset']

    def visible_fraction(self):
        """How much of the tucked art stays on screen: up to just past the wall it peeks from, if it has one."""
        asset=self.art()
        if self.fraction_for!=asset:self.fraction_for=asset;self.fraction=wall_fraction(self.pet.get_animation(asset).frames[0])
        return self.fraction

    def cut(self):
        """Where the screen edge falls on the art, in the pet's unscaled coordinates."""
        p=self.pet;image=p.image_rect(p.get_animation(self.art()).frames[0]);shown=image.width()*self.visible_fraction()
        return image.left()+shown if self.side=='right' else image.right()-shown

    def target(self,tucked):
        p=self.pet;r=p.pet_rect;s=p.scale_factor;a=self.area
        if tucked:x=(a.right()+1 if self.side=='right' else a.left())-self.cut()*s
        elif self.side=='right':x=a.right()+1-MARGIN-(r.left()+r.width())*s
        else:x=a.left()+MARGIN-r.left()*s
        y=max(a.top(),min(p.y(),a.bottom()-p.height()+1))
        return QPoint(round(x),round(y))

    def place(self,tucked,animate=True):
        self.tucked=tucked;self.timer.stop();self.animation.stop();target=self.target(tucked)
        if animate and self.pet.isVisible() and self.pet.pos()!=target:
            self.animation.setStartValue(self.pet.pos());self.animation.setEndValue(target);self.animation.start()
        else:self.pet.move(target)

    def reveal(self):
        self.timer.stop()
        if self.docked and self.tucked:self.place(False)

    def tuck_later(self,delay=HIDE_DELAY):
        if self.docked and not self.tucked:self.timer.start(delay)

    def busy(self):
        p=self.pet
        return p.underMouse() or p.drag_offset is not None or p.notification is not None or p.voice.busy or bool(p.cost_text)

    def tuck_if_idle(self):
        if not self.docked or self.tucked:return
        if self.busy():self.timer.start(HIDE_DELAY)
        else:self.place(True)

    def undock(self):
        self.side=None;self.area=None;self.tucked=False;self.animation.stop();self.timer.stop()

    def mirrored(self,asset):
        """On the left edge the peeking art is flipped, so its wall meets the screen edge."""
        return self.side=='left' and asset==self.art()

    def state(self):
        return dict(side=self.side) if self.docked else None
