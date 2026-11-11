"""Dock the pet at a screen edge after it is dragged there.

Docked, it has two poses. Out: in full view against the edge, with its ordinary animations, including the quiet idle.
Tucked: half behind the edge, peeking out with the hover art (flipped on the left edge).
It comes out while a task runs, while it has something to say, while the pointer is on it, and when the user has been
away from the computer for a while. It tucks itself away again once everything has been quiet for the delay chosen
in the settings. A pointer that only peeks at a tucked pet sends it back in shortly after leaving.
Only outer edges dock: with another monitor beyond the edge, the hidden half would show up on that monitor.
"""
import time
from PySide6.QtCore import QEasingCurve,QPoint,QPropertyAnimation,QRect,QTimer
from PySide6.QtWidgets import QApplication

SNAP=18          # releasing the pet this close to an outer edge docks it
VISIBLE=.6       # share of the art still on screen while tucked, when it has no wall to peek from
WALL_SHOWN=.06   # how much of a wall stays visible, as a share of the art's width
MARGIN=6         # gap to the edge when it is out
PEEK_MS=1200     # after the pointer leaves a pet it only peeked at, before it slides back
AWAY_SECONDS=300 # no keyboard or mouse input for this long: come out and wait in full view
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
    def __init__(self,pet,clock=time.monotonic,idle=None):
        self.pet=pet;self.side=None;self.area=None;self.tucked=False;self.peeking=False;self.quiet_since=None
        self.clock=clock;self.idle=idle;self.fraction_for=None;self.fraction=VISIBLE
        self.animation=QPropertyAnimation(pet,b'pos',pet);self.animation.setDuration(SLIDE_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.timer=QTimer(pet);self.timer.setSingleShot(True);self.timer.timeout.connect(self.peek_over)

    @property
    def docked(self):return self.side is not None

    def pet_global(self):
        r=self.pet.pet_rect;s=self.pet.scale_factor
        return QRect(round(self.pet.x()+r.left()*s),round(self.pet.y()+r.top()*s),round(r.width()*s),round(r.height()*s))

    @staticmethod
    def outer(area,side,screens=None):
        """True when no other monitor lies beyond this edge. With different display scaling on two monitors, the
        screen coordinates leave a gap between them, so a neighbour is found by direction rather than by touching."""
        for screen in (QApplication.screens() if screens is None else screens):
            g=screen.geometry()
            if g.contains(area.center()):continue
            if g.top()>area.bottom() or g.bottom()<area.top():continue
            if side=='right' and g.left()>=area.right()-8:return False
            if side=='left' and g.right()<=area.left()+8:return False
        return True

    def try_dock(self,area):
        """Called when a drag ends, before the window is pulled back onto the screen. It docks out in full view."""
        if not self.pet.options['edge_dock']:return False
        g=self.pet_global()
        for side,near in (('left',g.left()<=area.left()+SNAP),('right',g.right()>=area.right()-SNAP)):
            if near and self.outer(area,side):
                self.side=side;self.area=QRect(area);self.peeking=False;self.quiet_since=self.clock();self.place(False);return True
        return False

    def restore(self,side,area):
        if self.pet.options['edge_dock'] and side in ('left','right') and self.outer(area,side):
            self.side=side;self.area=QRect(area);self.quiet_since=None;self.place(True,animate=False)

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
        self.tucked=tucked;self.animation.stop();target=self.target(tucked)
        if animate and self.pet.isVisible() and self.pet.pos()!=target:
            self.animation.setStartValue(self.pet.pos());self.animation.setEndValue(target);self.animation.start()
        else:self.pet.move(target)

    # What keeps it out.
    def working(self):
        status=self.pet.live_status
        return bool(status.get('active')) and not status.get('stale')

    def busy(self):
        p=self.pet;reminder=getattr(p,'rest_reminder',None)
        return (p.underMouse() or p.drag_offset is not None or p.notification is not None or p.voice.busy
                or bool(p.cost_text) or bool(reminder and reminder.active))

    def away(self):
        if self.idle is None:
            from .rest_reminder import idle_seconds
            self.idle=idle_seconds
        return self.idle()>=AWAY_SECONDS

    def wants_out(self):return self.working() or self.busy() or self.away()

    def showing_peek_art(self):
        """The tucked pose, also kept while the pointer peeks at a tucked pet."""
        return self.docked and (self.tucked or self.peeking)

    def update(self):
        """Once a second: come out when needed, tuck away after the quiet delay."""
        if not self.docked or self.peeking or self.animation.state()==QPropertyAnimation.State.Running:return
        if self.wants_out():
            self.quiet_since=None
            if self.tucked:self.place(False)
            return
        if self.tucked:return
        now=self.clock()
        if self.quiet_since is None:self.quiet_since=now
        elif now-self.quiet_since>=self.pet.options['dock_tuck_seconds']:self.place(True)

    def reveal(self):
        """Something to show (a task, a completion, a bubble): out now, and the quiet delay starts over afterwards."""
        self.quiet_since=None;self.timer.stop();self.peeking=False
        if self.docked and self.tucked:self.place(False)

    def tuck_later(self):
        """Whatever kept it out has ended: the quiet delay counts from now."""
        self.quiet_since=None

    def hover_in(self):
        self.timer.stop()
        if self.docked and self.tucked:self.peeking=True;self.place(False)

    def hover_out(self):
        if self.docked and self.peeking:self.timer.start(PEEK_MS)

    def peek_over(self):
        if not self.peeking:return
        if self.pet.underMouse() or self.pet.drag_offset is not None:self.timer.start(PEEK_MS);return
        self.peeking=False
        if not self.wants_out():self.place(True)

    def undock(self):
        self.side=None;self.area=None;self.tucked=False;self.peeking=False;self.quiet_since=None;self.animation.stop();self.timer.stop()

    def mirrored(self,asset):
        """On the left edge the peeking art is flipped, so its wall meets the screen edge."""
        return self.side=='left' and self.showing_peek_art() and asset==self.art()

    def state(self):
        return dict(side=self.side) if self.docked else None
