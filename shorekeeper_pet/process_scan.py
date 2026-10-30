"""Read PID, parent PID and executable path using limited-query access only."""
import ctypes,os,sys
from ctypes import wintypes

def process_tree(names,accept):
    if sys.platform!='win32':return {}
    names={n.lower() for n in names}
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.ProcessIdToSessionId.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    session=wintypes.DWORD()
    if not kernel.ProcessIdToSessionId(os.getpid(),ctypes.byref(session)):raise ctypes.WinError(ctypes.get_last_error())
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    found={}
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry);ok=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        if not ok:raise ctypes.WinError(ctypes.get_last_error())
        while ok:
            if entry.exe.lower() in names:
                other=wintypes.DWORD()
                if not kernel.ProcessIdToSessionId(entry.pid,ctypes.byref(other)):
                    if ctypes.get_last_error()!=87:raise ctypes.WinError(ctypes.get_last_error())
                elif other.value==session.value:
                    handle=kernel.OpenProcess(0x1000,False,entry.pid)
                    if not handle:
                        # ERROR_INVALID_PARAMETER means the process exited between reads.
                        if ctypes.get_last_error()!=87:raise ctypes.WinError(ctypes.get_last_error())
                    else:
                        try:
                            path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
                            if not kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)):
                                raise ctypes.WinError(ctypes.get_last_error())
                            if accept(path.value):found[entry.pid]=entry.parent
                        finally:kernel.CloseHandle(handle)
            ok=kernel.Process32NextW(snapshot,ctypes.byref(entry))
        if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
    finally:kernel.CloseHandle(snapshot)
    return found
