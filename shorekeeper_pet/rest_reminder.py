"""Drink-water and stand-up reminder.

Counts continuous time at the computer: being away for IDLE_RESET seconds starts the count again.
When it is due the pet hands over a cup of milk tea (the "feed" animation) and shows a card for SHOW_SECONDS:
remind me in 30 minutes, got it (next one after the usual interval), or switch reminders off.
"""
import sys,time
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QApplication,QFrame,QLabel,QPushButton,QVBoxLayout,QWidget
from .appearance import stylesheet

SHOW_SECONDS=10
SNOOZE_MINUTES=30
IDLE_RESET=300


def idle_seconds():
    """Seconds since the last keyboard or mouse input anywhere in the session (0 when unknown)."""
    if sys.platform!='win32':return 0
    import ctypes,ctypes.wintypes as w

    class LastInput(ctypes.Structure):
        _fields_=[('cbSize',w.UINT),('dwTime',w.DWORD)]
    info=LastInput();info.cbSize=ctypes.sizeof(LastInput)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):return 0
    return max(0,(ctypes.windll.kernel32.GetTickCount()-info.dwTime)&0xFFFFFFFF)/1000


def message(minutes):
    if minutes>=90:return f'已经连续坐了 {minutes} 分钟啦。\n先喝口水，起来走一走再回来吧。'
    return f'已经陪你坐了 {minutes} 分钟。\n喝口水，伸个懒腰吧。'


class ReminderCard(QFrame):
    def __init__(self,reminder):
        pet=reminder.pet
        flags=Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowStaysOnTopHint
        super().__init__(pet if isinstance(pet,QWidget) else None,flags)
        self.reminder=reminder;self.pet=pet;self.style_key=None
        self.setObjectName('restReminder');self.setWindowTitle('守岸人 · 休息提醒')
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating);self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        box=QVBoxLayout(self);box.setContentsMargins(16,14,16,14);box.setSpacing(8)
        self.text=QLabel();self.text.setTextFormat(Qt.TextFormat.PlainText);self.text.setWordWrap(True);box.addWidget(self.text)
        self.buttons={}
        for key,label,action in (('later','30 分钟后再提醒',reminder.later),('ok','知道了',reminder.acknowledge),('off','关闭提醒（可在设置里重新打开）',reminder.switch_off)):
            button=QPushButton(label);button.clicked.connect(action);box.addWidget(button);self.buttons[key]=button

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#6592c9'),2));p.setBrush(QColor('#f4f9ff'));p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),16,16)

    def present(self,text):
        p=self.pet;options=p.options;key=(options['font_family'],options['ui_font_size'])
        if key!=self.style_key:
            self.setStyleSheet(stylesheet(options));self.style_key=key
        self.text.setText(text);self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,p.on_top)
        area=p.screen_area();self.setFixedWidth(min(area.width(),max(280,min(420,round(330*p.scale_factor)))));self.adjustSize()
        # Above the pet, like the speech bubble; below it when there is no room.
        rect=p.pet_rect;s=p.scale_factor;top=p.y()+round(rect.top()*s);centre=p.x()+round(rect.center().x()*s)
        x=max(area.left(),min(centre-self.width()//2,area.right()-self.width()+1));y=top-self.height()-6
        if y<area.top():y=min(area.bottom()-self.height()+1,p.y()+round(rect.bottom()*s)+6)
        self.move(x,max(area.top(),y));self.show();self.raise_()


class RestReminder:
    def __init__(self,pet,clock=time.monotonic,idle=idle_seconds):
        self.pet=pet;self.clock=clock;self.idle=idle;self.card=None;self.until=0
        self.since=clock();self.due=self.since+self.interval()

    def interval(self):return self.pet.options['rest_interval_minutes']*60

    @property
    def active(self):return self.card is not None and self.card.isVisible()

    def restart(self,delay=None):
        now=self.clock();self.due=now+(self.interval() if delay is None else delay)

    def check(self):
        p=self.pet;now=self.clock()
        if not p.options['rest_reminder']:
            if self.active:self.card.hide()
            return
        if self.active:
            if now>=self.until or not p.isVisible():self.acknowledge()
            return
        if self.idle()>=IDLE_RESET:
            # Away from the computer counts as a break.
            self.since=now;self.restart();return
        if now<self.due:return
        if not p.isVisible() or p.fullscreen_guard.hidden or p.notification is not None or p.voice.busy or p.drag_offset is not None:return
        self.show(now)

    def show(self,now=None):
        p=self.pet;now=self.clock() if now is None else now
        if self.card is None:self.card=ReminderCard(self)
        p.edge_dock.reveal()
        p.preview_id=None;p.override_text='';p.controller.enter('feed',time.monotonic(),'interaction');p.tick()
        self.until=now+SHOW_SECONDS;self.card.present(message(max(1,round((now-self.since)/60))))

    def close(self):
        if self.card:self.card.hide()
        self.pet.edge_dock.tuck_later()

    def later(self):self.close();self.restart(SNOOZE_MINUTES*60)

    def acknowledge(self):self.close();self.since=self.clock();self.restart()

    def switch_off(self):
        self.close();self.pet.set_option('rest_reminder',False)

    def options_changed(self):
        """A new interval, or switching back on, counts from now."""
        self.since=self.clock();self.restart()
        if not self.pet.options['rest_reminder'] and self.active:self.card.hide()
