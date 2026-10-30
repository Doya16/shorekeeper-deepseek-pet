"""Rebuild the approved multi-resolution Windows app icon from native assets."""
from pathlib import Path
import struct
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QPen
from PySide6.QtCore import Qt,QRectF,QByteArray,QBuffer,QIODevice
from PySide6.QtSvg import QSvgRenderer

root=Path(__file__).resolve().parents[1]
app=QApplication.instance() or QApplication([])
folder=root/'resources/icons';base=QIcon(str(root/'assets/shorekeeper.ico'))
deep=(folder/'badge.svg').exists()
mark=QSvgRenderer(str(folder/'badge.svg')) if deep else QPixmap(str(folder/'badge.png'))
frames=[];sizes=(16,24,32,48,64,128,256)
for size in sizes:
    result=QPixmap(size,size);result.fill(Qt.transparent)
    p=QPainter(result);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawPixmap(0,0,base.pixmap(size,size))
    side=round(size*.38);x=y=size-side
    p.setPen(QPen(QColor('#c6d1ed'),max(.6,size/256)))
    p.setBrush(QColor('#f8faff' if deep else '#16171b'));p.drawRoundedRect(QRectF(x+.5,y+.5,side-1,side-1),side*.24,side*.24)
    inset=max(.5,size*(.009 if deep else .035));r=QRectF(x+inset,y+inset,side-2*inset,side-2*inset)
    if deep:mark.render(p,r)
    else:p.drawPixmap(r,mark,QRectF(mark.rect()))
    p.end()
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);result.save(buffer,'PNG');frames.append(bytes(data))
offset=6+16*len(sizes);directory=[]
for size,data in zip(sizes,frames):
    directory.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset));offset+=len(data)
(folder/'app.ico').write_bytes(struct.pack('<HHH',0,1,len(sizes))+b''.join(directory)+b''.join(frames))
print(folder/'app.ico')
