"""Windows layered-window input routing, independent of Qt enter/leave events."""
import ctypes
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor,QGuiApplication


def set_input_transparent(widget,enabled):
    """Keep Qt's layered painting intact; only change native mouse hit testing.

    HTTRANSPARENT / ignoring a Qt event does not pass input to another process.
    WS_EX_TRANSPARENT on a layered HWND does:
    https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows
    Read the style again so hide/show and changing Always on Top are safe.
    """
    if sys.platform!='win32' or QGuiApplication.platformName()!='windows' or not widget.isVisible(): return
    user32=ctypes.WinDLL('user32',use_last_error=True)
    get=user32.GetWindowLongPtrW; get.argtypes=[ctypes.c_void_p,ctypes.c_int]; get.restype=ctypes.c_ssize_t
    put=user32.SetWindowLongPtrW; put.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ssize_t]; put.restype=ctypes.c_ssize_t
    hwnd=int(widget.winId()); style=get(hwnd,-20)
    desired=style|0x20 if enabled else style&~0x20
    if desired!=style:
        ctypes.set_last_error(0)
        if not put(hwnd,-20,desired) and ctypes.get_last_error(): raise ctypes.WinError(ctypes.get_last_error())


class PointerMode:
    def __init__(self,pet):
        self.pet=pet; self.avatar_opacity=1.0; self.passthrough=False

    def refresh(self):
        p=self.pet
        if not hasattr(p,'pet_rect'): return
        local=p.mapFromGlobal(QCursor.pos())
        p.update_quota_cursor(local)
        over=p.pet_rect.contains(local/p.scale_factor) or p.quota_hit_rect().contains(local)
        self.avatar_opacity=1-p.options['locked_hover_transparency']/100 if p.locked and over else 1.0
        # The lock and quota remain usable. Preserve a control's mouse grab while
        # pressed, so dragging out cancels the click instead of clicking behind it.
        control=(p.lock_button.isVisible() and p.lock_button.geometry().contains(local)) or p.quota_hit_rect().contains(local)
        held=p.lock_button.isDown() or p.quota_press is not None
        # Never capture an underlying application's drag when it crosses a control.
        down=bool(QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if sys.platform=='win32' and QGuiApplication.platformName()=='windows':
            down=bool(ctypes.windll.user32.GetAsyncKeyState(1)&0x8000)
        dragging=down and not held
        self.passthrough=p.locked and not held and (not control or dragging)
        set_input_transparent(p,self.passthrough)
        set_input_transparent(p.bubble_window,p.locked)
