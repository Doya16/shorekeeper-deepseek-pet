"""Compact settings pages and a wheel guard.

Pages are made of titled cards. Short controls (numbers, choices, switches) keep their natural width and sit
two to a row; wide controls (sliders, previews, paths) span the card; buttons line up at their text width.
"""
from PySide6.QtCore import QEvent,QObject,Qt
from PySide6.QtWidgets import (QAbstractScrollArea,QAbstractSlider,QAbstractSpinBox,QApplication,QCheckBox,QComboBox,QFrame,
                               QGridLayout,QHBoxLayout,QLabel,QLayout,QPushButton,QScrollArea,QScrollBar,QVBoxLayout,QWidget)

SPIN_WIDTH=(110,150)
COMBO_WIDTH=(150,300)
GAP=28  # space between the two columns of a card
LABEL_WIDTH=112  # labels line up across cards


def fit(widget):
    """Short controls keep a sensible width instead of stretching across the window."""
    if isinstance(widget,QAbstractSpinBox):
        widget.setMinimumWidth(SPIN_WIDTH[0]);widget.setMaximumWidth(SPIN_WIDTH[1])
    elif isinstance(widget,QComboBox):
        widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        widget.setMinimumWidth(COMBO_WIDTH[0]);widget.setMaximumWidth(COMBO_WIDTH[1])
    return widget


def widen(combo):
    """Room for the longest choice plus the arrow, which the style sheet padding hides from Qt's own size."""
    combo.setMinimumWidth(min(COMBO_WIDTH[1],max(COMBO_WIDTH[0],combo.sizeHint().width()+28)))


def short(widget):
    return isinstance(widget,(QAbstractSpinBox,QComboBox,QCheckBox))


def button_row(layout):
    """A layout holding only buttons: keep them at their text width, aligned left."""
    if not isinstance(layout,QHBoxLayout) or not layout.count():return False
    items=[layout.itemAt(i).widget() for i in range(layout.count())]
    return all(isinstance(w,QPushButton) for w in items)


class Section(QFrame):
    def __init__(self,title=''):
        super().__init__();self.setObjectName('settingsCard')
        outer=QVBoxLayout(self);outer.setContentsMargins(16,12,16,14);outer.setSpacing(8)
        if title:
            head=QLabel(title);head.setObjectName('settingsSection');outer.addWidget(head)
        self.grid=QGridLayout();self.grid.setHorizontalSpacing(12);self.grid.setVerticalSpacing(10)
        self.grid.setColumnMinimumWidth(2,GAP);self.grid.setColumnStretch(5,1)
        for column in (0,3):self.grid.setColumnMinimumWidth(column,LABEL_WIDTH)
        outer.addLayout(self.grid);self.row=0;self.slot=0;self.buttons=None

    def next_row(self):
        if self.slot:self.row+=1;self.slot=0
        self.buttons=None

    def label(self,text):
        label=QLabel(text);label.setObjectName('settingsLabel');return label

    def add_short(self,text,widget):
        self.buttons=None;fit(widget);col=0 if self.slot==0 else 3
        if text:
            self.grid.addWidget(self.label(text),self.row,col,Qt.AlignmentFlag.AlignVCenter)
            self.grid.addWidget(widget,self.row,col+1,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        else:
            self.grid.addWidget(widget,self.row,col,1,2,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        if self.slot:self.row+=1;self.slot=0
        else:self.slot=1

    def add_wide(self,text,item):
        self.next_row()
        if isinstance(item,QLayout) and button_row(item):item.setSpacing(10);item.addStretch(1)
        if text:
            self.grid.addWidget(self.label(text),self.row,0,Qt.AlignmentFlag.AlignVCenter)
            span=(self.row,1,1,5)
        else:span=(self.row,0,1,6)
        (self.grid.addLayout if isinstance(item,QLayout) else self.grid.addWidget)(item,*span)
        self.row+=1

    def add_note(self,label):
        self.next_row();label.setWordWrap(True)
        if not label.objectName():label.setObjectName('settingsNote')
        self.grid.addWidget(label,self.row,0,1,6);self.row+=1

    def add_button(self,button):
        if self.buttons is None:
            self.next_row();self.buttons=QHBoxLayout();self.buttons.setSpacing(10);self.buttons.addStretch(1)
            self.grid.addLayout(self.buttons,self.row,0,1,6);self.row+=1
        self.buttons.insertWidget(self.buttons.count()-1,button)

    def addRow(self,first,second=None):
        if second is None:
            if isinstance(first,QPushButton):self.add_button(first)
            elif isinstance(first,QLabel):self.add_note(first)
            elif short(first):self.add_short('',first)
            else:self.add_wide('',first)
        elif not isinstance(second,QLayout) and short(second):self.add_short(first,second)
        else:self.add_wide(first,second)


class Page:
    """One scrollable settings tab. addRow goes to the current card; section() starts a new one."""

    def __init__(self):
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body=QWidget();body.setObjectName('settingsBody');self.layout=QVBoxLayout(body)
        self.layout.setContentsMargins(4,10,8,10);self.layout.setSpacing(12);self.layout.addStretch(1)
        self.scroll.setWidget(body);self.current=None

    def section(self,title=''):
        self.current=Section(title);self.layout.insertWidget(self.layout.count()-1,self.current);return self.current

    def addRow(self,first,second=None):
        (self.current or self.section()).addRow(first,second)


VALUE_CONTROLS=(QAbstractSpinBox,QComboBox,QAbstractSlider)


class WheelGuard(QObject):
    """In one window, the wheel only changes a number, choice or slider after it has been clicked.
    Otherwise the wheel scrolls the page underneath, as if the control were not there.
    Keyboard focus alone (the first control when the window opens, or Tab) does not count as a click."""

    def __init__(self,window):
        super().__init__(window);self.window=window;self.armed=None
        QApplication.instance().installEventFilter(self)

    def control(self,widget):
        for _ in range(3):
            if widget is None:return None
            if isinstance(widget,QScrollBar):return None
            if isinstance(widget,VALUE_CONTROLS):return widget
            widget=widget.parentWidget()
        return None

    def eventFilter(self,watched,event):
        kind=event.type()
        if kind not in (QEvent.Type.Wheel,QEvent.Type.MouseButtonPress) or not isinstance(watched,QWidget):return False
        if kind==QEvent.Type.MouseButtonPress:
            if watched.window() is self.window:
                control=self.control(watched)
                # An ignored click travels up to the page and the window; those must not undo the choice.
                if control is not None:self.armed=control
                elif self.armed is None or not watched.isAncestorOf(self.armed):self.armed=None
            return False
        control=self.control(watched)
        if control is None or control.window() is not self.window:return False
        if control is self.armed and control.hasFocus():return False
        # Scroll bars and open drop-down lists are never guarded.
        area=control.parentWidget()
        while area is not None and not isinstance(area,QAbstractScrollArea):area=area.parentWidget()
        if area is not None and area.verticalScrollBar().isVisible():
            QApplication.sendEvent(area.verticalScrollBar(),event)
        return True
