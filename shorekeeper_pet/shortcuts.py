"""Unicode desktop links with an install-local, non-exported first-run marker."""
import hashlib,json,os,pathlib,subprocess,sys,threading
from .paths import APPLICATION_ID,EXECUTABLE_NAME

_LOCK=threading.Lock()

def marker_path(root,state_root=None):
    base=pathlib.Path(state_root) if state_root else pathlib.Path(os.environ.get('LOCALAPPDATA',pathlib.Path.home()/'AppData/Local'))/'Shorekeeper/shortcuts'
    identity=APPLICATION_ID+'|'+os.path.normcase(str(pathlib.Path(root).resolve()))
    return base/(hashlib.sha256(identity.encode('utf8')).hexdigest()+'.json')

def create_desktop_shortcut(root,destination=None,*,state_root=None):
    root=pathlib.Path(root).resolve();target=root/EXECUTABLE_NAME
    if not target.is_file():raise OSError('请在解压后的 Windows 便携版中创建快捷方式。')
    script=root/'tools/create_shortcut.ps1'
    if not script.is_file():raise OSError('快捷方式工具缺失，请重新解压完整程序包。')
    shell=pathlib.Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    args=[str(shell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-Target',str(target)]
    if destination is not None:args+=['-Destination',str(pathlib.Path(destination).resolve())]
    with _LOCK:
        completed=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if completed.returncode:raise OSError('无法创建桌面快捷方式，请检查桌面写入权限及同名快捷方式。')
        try:
            report=json.loads(completed.stdout.decode('utf-8-sig').strip())
            link=pathlib.Path(report['shortcut'])
            if not link.is_file():raise ValueError('missing shortcut')
        except (ValueError,KeyError,TypeError) as error:raise OSError('快捷方式创建结果无法验证。') from error
        marker=marker_path(root,state_root);marker.parent.mkdir(parents=True,exist_ok=True)
        temp=marker.with_suffix('.tmp');temp.write_text(json.dumps({'shortcut':str(link)},ensure_ascii=False),'utf8');temp.replace(marker)
        return link

def ensure_first_launch_shortcut(root,*,normal=True,frozen=None,state_root=None,destination=None):
    if frozen is None:frozen=bool(getattr(sys,'frozen',False))
    if not normal or not frozen or marker_path(root,state_root).is_file():return None
    try:return create_desktop_shortcut(root,destination,state_root=state_root)
    except (OSError,subprocess.SubprocessError):return None
