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

def deepseek_process_tree():
    from .process_scan import process_tree
    return process_tree(('deepseek harness.exe',),is_deepseek_desktop)

def deepseek_processes():
    return desktop_roots(deepseek_process_tree())

def desktop_roots(parents):
    return {pid for pid,parent in parents.items() if parent not in parents}

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
