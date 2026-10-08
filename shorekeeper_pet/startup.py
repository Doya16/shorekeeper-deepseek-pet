"""Optional per-user Windows startup watcher; does not modify DeepSeek."""
import ctypes,json,os,pathlib,subprocess,sys,time
from ctypes import wintypes
from .paths import ROOT

RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME='ShorekeeperDeepSeekPet'

def launch_args(root=ROOT,watch=False):
    root=pathlib.Path(root)
    if getattr(sys,'frozen',False): args=[str(pathlib.Path(sys.executable).resolve())]
    else:
        python=pathlib.Path(sys.executable)
        hidden=python.with_name('pythonw.exe')
        args=[str(hidden if hidden.exists() else python),str(root/'tools/run_pet.py')]
    return args+(['--watch-deepseek'] if watch else [])

def registered_command():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
            return winreg.QueryValueEx(key,RUN_NAME)[0]
    except FileNotFoundError:return ''

def configure(enabled,root=ROOT):
    if sys.platform!='win32': raise OSError('随 DeepSeek 启动目前仅支持 Windows。')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if enabled:winreg.SetValueEx(key,RUN_NAME,0,winreg.REG_SZ,subprocess.list2cmdline(launch_args(root,True)))
        else:
            try:winreg.DeleteValue(key,RUN_NAME)
            except FileNotFoundError:pass
    if enabled:
        return subprocess.Popen(launch_args(root,True),cwd=root,creationflags=subprocess.CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def is_deepseek_desktop(path):
    return pathlib.PureWindowsPath(str(path)).name.lower()=='deepseek harness.exe'

def deepseek_processes():
    if sys.platform!='win32':return set()
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    found=set()
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry);ok=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            if entry.exe.lower() == 'deepseek harness.exe':
                process=kernel.OpenProcess(0x1000,False,entry.pid)
                if process:
                    try:
                        path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
                        if kernel.QueryFullProcessImageNameW(process,0,path,ctypes.byref(size)) and is_deepseek_desktop(path.value):found.add(entry.pid)
                    finally:kernel.CloseHandle(process)
            ok=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    return found

class LaunchEdges:
    """One launch per desktop run, including a restart between two polls."""
    def __init__(self):self.previous=set()
    def update(self,current):
        current=set(current);launch=bool(current) and not bool(current & self.previous)
        self.previous=current;return launch

def watch(root=ROOT):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR];kernel.CreateMutexW.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.ReleaseMutex.argtypes=[wintypes.HANDLE];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    mutex=kernel.CreateMutexW(None,False,r'Local\ShorekeeperDeepSeekPetWatcher')
    if not mutex:raise ctypes.WinError(ctypes.get_last_error())
    owned=False
    try:
        owned=kernel.WaitForSingleObject(mutex,6000) in (0,0x80)
        if not owned:return 0
        expected=subprocess.list2cmdline(launch_args(root,True));edges=LaunchEdges()
        while registered_command()==expected:
            try:
                if edges.update(deepseek_processes()):
                    subprocess.Popen(launch_args(root),cwd=root,creationflags=subprocess.CREATE_NO_WINDOW,
                                     stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except OSError:pass
            time.sleep(2)
        return 0
    finally:
        if owned:kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)
