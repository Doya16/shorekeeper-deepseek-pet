"""A short list whose rows can be ticked and reordered, by dragging or with the up and down buttons."""
from PySide6.QtCore import QEvent,Qt,QTimer,Signal
from PySide6.QtWidgets import QAbstractItemView,QHBoxLayout,QListWidget,QListWidgetItem,QPushButton,QVBoxLayout,QWidget


class OrderList(QWidget):
    changed=Signal(list,dict)

    def __init__(self,rows):
        super().__init__();self.loading=False
        layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        self.list=QListWidget();self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction);self.list.setAccessibleName('播报内容和顺序')
        self.list.setToolTip('勾选要显示的内容，拖动或用右侧按钮调整上下顺序')
        for key,label in rows:
            item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,key)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsDragEnabled);item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setFixedWidth(200);self.fit();layout.addWidget(self.list)
        buttons=QVBoxLayout();buttons.setSpacing(6)
        for text,step in (('上移',-1),('下移',1)):
            button=QPushButton(text);button.clicked.connect(lambda checked=False,step=step:self.move(step));buttons.addWidget(button)
        buttons.addStretch(1);layout.addLayout(buttons);layout.addStretch(1)
        self.list.itemChanged.connect(self.emit);self.list.model().rowsMoved.connect(self.emit)

    def fit(self):
        """Every row visible at the current font, which the style sheet may change after construction."""
        rows=self.list.count();height=max(self.list.sizeHintForRow(0),self.list.fontMetrics().height()+12) if rows else 28
        self.list.setFixedHeight(height*rows+2*self.list.frameWidth()+4)

    def event(self,event):
        if event.type() in (QEvent.Type.FontChange,QEvent.Type.StyleChange,QEvent.Type.Polish):QTimer.singleShot(0,self.fit)
        return super().event(event)

    def order(self):return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]

    def enabled(self):
        return {self.list.item(i).data(Qt.ItemDataRole.UserRole):self.list.item(i).checkState()==Qt.CheckState.Checked for i in range(self.list.count())}

    def move(self,step):
        row=self.list.currentRow()
        if row<0:row=0 if step>0 else self.list.count()-1
        target=row+step
        if not 0<=target<self.list.count():return
        self.loading=True;item=self.list.takeItem(row);self.list.insertItem(target,item);self.list.setCurrentRow(target);self.loading=False
        self.emit()

    def emit(self,*args):
        if not self.loading:self.changed.emit(self.order(),self.enabled())

    def set_state(self,order,enabled):
        self.loading=True
        items={self.list.item(i).data(Qt.ItemDataRole.UserRole):self.list.takeItem(i) for i in reversed(range(self.list.count()))}
        for key in [k for k in order if k in items]+[k for k in items if k not in order]:
            item=items[key];item.setCheckState(Qt.CheckState.Checked if enabled.get(key,True) else Qt.CheckState.Unchecked);self.list.addItem(item)
        self.loading=False
