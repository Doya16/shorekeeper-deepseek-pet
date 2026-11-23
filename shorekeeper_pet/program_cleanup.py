"""Remove program versions and update snapshots that nothing can use any more.

An update installs the new version beside the old one in .programs/<version>/ and keeps a snapshot of the replaced files
in .update-backups/<id>/, so an interrupted update can roll back. Once the new version runs and no update is in progress,
the older versions (about 265 MB each) and the snapshots are dead weight. The helper that applies an update and the
launcher at the top of the folder both come from older releases, so the cleanup runs in the new program itself, a while
after it has started (the update helper has committed by then). A folder that cannot be removed now, for instance because
a leftover process still runs from it, is tried again at the next start. Results go to program-cleanup.json.
"""
import json,os,pathlib,re,shutil,stat,sys,threading,time,uuid
from .update_recovery import JOURNAL,POINTER,read_json,local_path,atomic_json

VERSION_NAME=re.compile(r'\d{1,5}\.\d{1,5}\.\d{1,5}')
REMOVING=re.compile(r'\.removing-\d{1,5}\.\d{1,5}\.\d{1,5}')   # renamed for removal; left over if removal stopped halfway
LOCK='.update-lock.json'
REPORT='program-cleanup.json'
FIRST_DELAY_MS=120_000     # after start: the update helper has long finished its health check and committed
RETRY_DELAY_MS=900_000     # an update was still in progress: look once more later


def busy(root):
    root=pathlib.Path(root)
    return (root/JOURNAL).exists() or (root/LOCK).exists()


def _linked(path):
    return path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction())


def _size(path):
    total=0
    for walk,dirs,files in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if not _linked(pathlib.Path(walk)/d)]
        for name in files:
            try: total+=os.lstat(os.path.join(walk,name)).st_size
            except OSError: pass
    return total


def _remove(path):
    def retry(func,name,exc):
        # read-only files (copied from a zip) cannot be deleted until they are writable
        try: os.chmod(name,stat.S_IWRITE); func(name)
        except OSError: raise exc
    shutil.rmtree(path,onexc=retry)


def prune(root,running_version):
    """Remove every .programs/<version> except the running one, and every update snapshot. Never follows links."""
    root=pathlib.Path(root).resolve()
    if busy(root): return dict(skipped='update in progress')
    pointer=read_json(root/POINTER) or {}
    if pointer.get('version')!=running_version: return dict(skipped='not the active program')
    removed,failed,freed=[],[],0
    # Another process may still run from an older version, e.g. the "start with DeepSeek" watcher started before the update.
    in_use={running_version}|running_versions(root)
    programs=lambda n:bool(VERSION_NAME.fullmatch(n)) or bool(REMOVING.fullmatch(n))
    for base,keep,valid in (('.programs',in_use,programs),('.update-backups',set(),lambda n:_uuid(n))):
        folder=root/base
        if not folder.is_dir() or _linked(folder): continue
        for entry in sorted(folder.iterdir()):
            if entry.name in keep or not valid(entry.name) or not entry.is_dir() or _linked(entry): continue
            name=base+'/'+entry.name
            try:
                path=local_path(root,name); size=_size(path)
                # A version is removed whole or not at all: if any file is still open (a running program, a loaded
                # library), nothing in it is touched now. Renaming first marks a removal that stops halfway.
                if _in_use(path): raise OSError('in use')
                if base=='.programs' and not REMOVING.fullmatch(entry.name):
                    moved=folder/f'.removing-{entry.name}'; path.rename(moved); path=moved
                _remove(path); removed.append(name); freed+=size
            except (OSError,ValueError): failed.append(name)
    result=dict(time=time.time(),version=running_version,removed=removed,failed=failed,freed_bytes=freed)
    if removed or failed:
        try: atomic_json(root/REPORT,result)
        except OSError: pass
    return result


def _uuid(name):
    try: return str(uuid.UUID(name))==name
    except ValueError: return False


def _in_use(path):
    """True if any file under path cannot be opened for deletion by this process alone (Windows; False elsewhere)."""
    if sys.platform!='win32': return False
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.SetFileInformationByHandle.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    invalid=wintypes.HANDLE(-1).value
    for walk,dirs,files in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if not _linked(pathlib.Path(walk)/d)]
        for name in files:
            target=os.path.join(walk,name)
            try: os.chmod(target,stat.S_IWRITE)
            except OSError: pass
            # DELETE access with no sharing fails while anyone else has the file open.
            handle=kernel.CreateFileW(target,0x00010000,0,None,3,0x80,None)
            if handle in (None,invalid):
                if ctypes.get_last_error()==2: continue   # vanished meanwhile
                return True
            try:
                # A running program or a loaded library keeps no open handle but refuses to be marked for deletion.
                # Mark it and take the mark back at once; nothing is deleted here.
                mark=ctypes.c_ubyte(1)
                if not kernel.SetFileInformationByHandle(handle,4,ctypes.byref(mark),1): return True   # FileDispositionInfo
                mark.value=0; kernel.SetFileInformationByHandle(handle,4,ctypes.byref(mark),1)
            finally: kernel.CloseHandle(handle)
    return False


def running_versions(root):
    """Versions under .programs/ that a running process was started from (Windows; empty elsewhere)."""
    if sys.platform!='win32': return set()
    import ctypes
    from ctypes import wintypes
    psapi=ctypes.WinDLL('psapi'); kernel=ctypes.WinDLL('kernel32')
    kernel.OpenProcess.restype=wintypes.HANDLE; kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    ids=(wintypes.DWORD*8192)(); got=wintypes.DWORD()
    if not psapi.EnumProcesses(ids,ctypes.sizeof(ids),ctypes.byref(got)): return set()
    base=os.path.normcase(str(pathlib.Path(root).resolve()/'.programs'))+os.sep; found=set()
    for pid in ids[:got.value//ctypes.sizeof(wintypes.DWORD)]:
        handle=kernel.OpenProcess(0x1000,False,pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle: continue
        try:
            buffer=ctypes.create_unicode_buffer(32768); size=wintypes.DWORD(len(buffer))
            if kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):
                image=os.path.normcase(buffer.value)
                if image.startswith(base): found.add(image[len(base):].split(os.sep)[0])
        finally: kernel.CloseHandle(handle)
    return {os.path.basename(v) for v in found}


def prune_later(root,running_version,first=FIRST_DELAY_MS,retry=RETRY_DELAY_MS):
    """Schedule the cleanup on the Qt event loop; the removal itself runs on a background thread."""
    from PySide6.QtCore import QTimer
    def attempt(again):
        if busy(root):
            if again: QTimer.singleShot(retry,lambda:attempt(False))
            return
        threading.Thread(target=prune,args=(root,running_version),daemon=True).start()
    QTimer.singleShot(first,lambda:attempt(True))
