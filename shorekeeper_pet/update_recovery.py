"""Permanent launcher and recovery for journaled, immutable program versions."""
import ctypes,json,os,pathlib,re,shutil,subprocess,sys,time,uuid
from .paths import EXECUTABLE_NAME

POINTER='current-program.json'
JOURNAL='.update-transaction.json'
CONFIGS=('settings.json','settings.json.bak','voice-history.json')

def atomic_json(path,value):
    path=pathlib.Path(path);temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf8',newline='\n') as out:
        json.dump(value,out,ensure_ascii=False,indent=2);out.flush();os.fsync(out.fileno())
    # A reader or scanner holding the target makes Windows refuse the replace for a moment.
    until=time.monotonic()+10
    while True:
        try:temp.replace(path);break
        except PermissionError:
            if time.monotonic()>until:raise
            time.sleep(.1)

def read_json(path,default=None):
    try:return json.loads(pathlib.Path(path).read_text('utf8'))
    except FileNotFoundError:return default

def live(pid):
    if type(pid) is not int or pid<=0:return False
    if sys.platform!='win32':
        try:os.kill(pid,0);return True
        except ProcessLookupError:return False
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint]
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x100000,False,pid)
    if not h:
        if ctypes.get_last_error()==87:return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:return k.WaitForSingleObject(h,0)==258
    finally:k.CloseHandle(h)

def wait_exit(pid,timeout=60):
    until=time.monotonic()+timeout
    while live(pid):
        if time.monotonic()>until:raise TimeoutError('桌宠尚未退出，更新未执行')
        time.sleep(.2)

def local_path(root,name):
    root=pathlib.Path(root).resolve();parts=pathlib.PurePosixPath(name).parts
    if not parts or any(p in ('.','..') for p in name.split('/')) or '\\' in name or ':' in name or name.startswith('/'):
        raise ValueError('无效的更新路径')
    p=root
    for part in parts:
        p=p/part
        if p.is_symlink() or p.is_junction():raise ValueError('更新路径不能包含链接')
    if not p.resolve().is_relative_to(root):raise ValueError('更新路径越界')
    return p

def version_dir(root,version):
    if not isinstance(version,str) or not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}',version):raise ValueError('无效程序版本')
    return local_path(root,'.programs/'+version)

def active_program(root):
    data=read_json(pathlib.Path(root)/POINTER)
    if data is None:return pathlib.Path(root)/EXECUTABLE_NAME
    core=version_dir(root,data['version'])/EXECUTABLE_NAME
    if not core.is_file():raise ValueError('当前程序不完整，请重新解压便携包')
    return core

def new_cache(root):
    identity=str(uuid.uuid4());path=local_path(root,'.update-cache/'+identity)
    path.mkdir(parents=True)
    atomic_json(path/'owner.json',{'root':str(pathlib.Path(root).resolve()),'pid':os.getpid(),'id':identity})
    return path

def clean_caches(root):
    root=pathlib.Path(root).resolve();base=local_path(root,'.update-cache')
    if not base.exists():return
    for path in base.iterdir():
        if not path.is_dir() or path.is_symlink() or path.is_junction():continue
        try:
            if str(uuid.UUID(path.name))!=path.name:continue
            owner=read_json(path/'owner.json',{})
            if owner.get('root')!=str(root) or owner.get('id')!=path.name or live(owner.get('pid')):continue
            for walk,dirs,files in os.walk(path,followlinks=False):
                for name in dirs+files:local_path(path,(pathlib.Path(walk)/name).relative_to(path).as_posix())
            shutil.rmtree(local_path(root,'.update-cache/'+path.name))
        except (OSError,ValueError):continue

def replace_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.update-tmp');shutil.copy2(source,temp)
    with temp.open('rb+') as stream:os.fsync(stream.fileno())
    until=time.monotonic()+10
    while True:
        try:temp.replace(target);break
        except PermissionError:
            if time.monotonic()>until:raise
            time.sleep(.2)

def snapshot(root,identity,names):
    backup=local_path(root,'.update-backups/'+str(uuid.UUID(identity)))
    backup.mkdir(parents=True,exist_ok=False);saved={}
    for name in sorted(set(names)|set(CONFIGS)|{POINTER}):
        path=local_path(root,name);saved[name]=path.is_file()
        if path.exists() and not path.is_file():raise ValueError('程序目标不是文件：'+name)
        if saved[name]:
            dst=local_path(backup,name);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
    atomic_json(backup/'snapshot.json',saved)
    return saved

def restore(root,journal):
    backup=local_path(root,'.update-backups/'+str(uuid.UUID(journal['id'])))
    saved=read_json(backup/'snapshot.json')
    if not isinstance(saved,dict):raise ValueError('更新前备份不存在')
    from .update_package import program_file
    for name,existed in saved.items():
        if name not in (*CONFIGS,POINTER,'market-runtime.json','program-files.json') and not program_file(name):raise ValueError('备份包含无效路径')
        target=local_path(root,name)
        if existed:replace_file(local_path(backup,name),target)
        else:target.unlink(missing_ok=True)
    atomic_json(pathlib.Path(root)/'update-result.json',{'status':'rolled_back','version':journal['old_version'],
        'message':'上次更新中断，已恢复更新前版本与配置；可重新点击一键更新。','updated_at':time.time()})
    (pathlib.Path(root)/JOURNAL).unlink(missing_ok=True)

def stop_interrupted_core(root,journal):
    health=read_json(pathlib.Path(root)/'runtime.json',{});pid=health.get('pid')
    if health.get('update_token')!=journal['id'] or not live(pid):return
    if sys.platform!='win32':raise RuntimeError('请关闭上次更新启动的桌宠后重试')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint]
    k.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint)]
    k.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x1001,False,pid)
    if not h:raise ctypes.WinError(ctypes.get_last_error())
    try:
        buf=ctypes.create_unicode_buffer(32768);size=ctypes.c_uint(len(buf))
        if not k.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
        if pathlib.Path(buf.value).resolve()!=version_dir(root,journal['target_version'])/EXECUTABLE_NAME:
            raise RuntimeError('上次更新进程身份不匹配，请关闭桌宠后重试')
        if not k.TerminateProcess(h,1):raise ctypes.WinError(ctypes.get_last_error())
    finally:k.CloseHandle(h)
    wait_exit(pid,15)

def recover(root,*,wait=True):
    root=pathlib.Path(root).resolve();journal=read_json(root/JOURNAL)
    if not journal:return False
    if journal.get('root')!=str(root):raise ValueError('更新日志目录不匹配')
    if journal.get('phase')=='committed':(root/JOURNAL).unlink();return False
    if live(journal.get('pid')) and journal['pid']!=os.getpid():
        if not wait:raise RuntimeError('更新正在进行')
        wait_exit(journal['pid'],90);return recover(root,wait=False)
    stop_interrupted_core(root,journal);restore(root,journal)
    return True

def bootstrap_main():
    root=pathlib.Path(sys.executable).resolve().parent
    try:
        journal=read_json(root/JOURNAL)
        if journal and journal.get('legacy') and journal.get('phase')!='committed' and not live(journal.get('pid')):
            work=new_cache(root);helper=work/'shorekeeper-updater.exe';shutil.copy2(root/'tools/shorekeeper-updater.exe',helper)
            child=subprocess.Popen([str(helper),'--recover-root',str(root),'--wait-pid',str(os.getpid()),'--',*sys.argv[1:]],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
            atomic_json(work/'owner.json',{'root':str(root),'pid':child.pid,'id':work.name});return 0
        recover(root);clean_caches(root)
        if sys.argv[1:]==['--recover-only']:return 0
        program=active_program(root)
        if program==root/EXECUTABLE_NAME:raise ValueError('缺少程序版本信息，请重新解压便携包')
        return subprocess.call([str(program),*sys.argv[1:]],cwd=root)
    except Exception as exc:
        (root/'update-launch-error.log').write_text(str(exc),encoding='utf8')
        if sys.platform=='win32':ctypes.windll.user32.MessageBoxW(None,str(exc),'守岸人 · 启动恢复',0x10)
        return 1
