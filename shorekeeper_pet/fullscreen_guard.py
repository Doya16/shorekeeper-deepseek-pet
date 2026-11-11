"""Hide the pet while another program fills the pet's monitor (video, game, presentation). Off by default."""
import ctypes,os,sys

SHELL_CLASSES={'Progman','WorkerW','Shell_TrayWnd','Shell_SecondaryTrayWnd'}


def covering_monitor(own_pid=None):
    """The monitor handle a foreground full-screen window of another program covers, or None."""
    if sys.platform!='win32':return None
    import ctypes.wintypes as w
    user=ctypes.windll.user32;hwnd=user.GetForegroundWindow()
    if not hwnd:return None
    pid=w.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value==(own_pid or os.getpid()):return None
    name=ctypes.create_unicode_buffer(64);user.GetClassNameW(hwnd,name,64)
    if name.value in SHELL_CLASSES:return None
    # A maximised window with a title bar is ordinary work, even when an auto-hidden taskbar lets it fill the screen.
    if user.IsZoomed(hwnd) and user.GetWindowLongW(hwnd,-16)&0x00C00000==0x00C00000:return None
    rect=w.RECT()
    if not user.GetWindowRect(hwnd,ctypes.byref(rect)):return None

    class MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('rcMonitor',w.RECT),('rcWork',w.RECT),('dwFlags',w.DWORD)]
    user.MonitorFromWindow.restype=w.HMONITOR
    monitor=user.MonitorFromWindow(hwnd,2);info=MonitorInfo();info.cbSize=ctypes.sizeof(MonitorInfo)
    if not monitor or not user.GetMonitorInfoW(monitor,ctypes.byref(info)):return None
    m=info.rcMonitor
    # A maximised window leaves the taskbar visible; only a true full-screen window covers the whole monitor.
    if rect.left<=m.left and rect.top<=m.top and rect.right>=m.right and rect.bottom>=m.bottom:return monitor
    return None


def monitor_of(widget):
    if sys.platform!='win32':return None
    import ctypes.wintypes as w
    user=ctypes.windll.user32;user.MonitorFromWindow.restype=w.HMONITOR
    return user.MonitorFromWindow(int(widget.winId()),2)


class FullscreenGuard:
    def __init__(self,pet,detect=covering_monitor,locate=monitor_of):
        self.pet=pet;self.detect=detect;self.locate=locate;self.hidden=False

    def check(self):
        p=self.pet
        if not p.options['fullscreen_hide']:
            if self.hidden:self.restore()
            return
        covered=self.detect()
        mine=covered is not None and covered==self.locate(p)
        if mine and not self.hidden and p.isVisible():
            self.hidden=True;p.voice.stop();p.cost_float.hide();p.hide()
        elif not mine and self.hidden:self.restore()

    def restore(self):
        # Only bring back what this guard hid: a pet the user tucked into the tray stays there.
        self.hidden=False;self.pet.show()
