"""Independent installer with immutable program versions and a recoverable journal."""
import argparse,json,os,pathlib,shutil,subprocess,sys,time,uuid,zipfile
from .paths import UPDATE_REPOSITORY,EXECUTABLE_NAME
from .update_package import validate_manifest,verify_archive
from .update_recovery import (atomic_json,read_json,live,wait_exit,local_path,version_dir,
    active_program,snapshot,restore,recover,replace_file,POINTER,JOURNAL)

def check_root(value):
    root=pathlib.Path(value)
    if not root.is_absolute() or root.is_symlink() or root.is_junction():raise ValueError('安装目录不能是链接')
    root=root.resolve()
    if root.parent==root or len(root.parts)<3 or not (root/EXECUTABLE_NAME).is_file():raise ValueError('不是有效的桌宠安装目录')
    return root

def start(root,job):
    env=os.environ.copy()
    if job.get('rollback'):env.pop('SHOREKEEPER_UPDATE_TOKEN',None)
    else:env['SHOREKEEPER_UPDATE_TOKEN']=job['id']
    args=['--preview'] if job.get('offline_test') is True else []
    kwargs=dict(cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if sys.platform=='win32':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
    return subprocess.Popen([str(active_program(root)),*args],**kwargs)

def healthy(root,child,target,token,timeout=45):
    until=time.monotonic()+timeout;first=None
    while time.monotonic()<until:
        if child.poll() is not None:return False
        try:
            data=read_json(root/'runtime.json',{})
            good=(data.get('version')==target and data.get('pid')==child.pid
                  and data.get('update_token')==token and 0<=time.time()-data.get('updated_at',0)<5)
            if good:
                if first is None:first=time.monotonic()
                elif time.monotonic()-first>=2:return True
            else:first=None
        except (OSError,ValueError):pass
        time.sleep(.25)
    return False

def _apply(job_path,*,waiter=wait_exit,launcher=start,health=healthy):
    job_path=pathlib.Path(job_path).resolve();work=job_path.parent;job=read_json(job_path)
    if not isinstance(job,dict) or type(job.get('pid')) is not int or (job['pid']<0 or (job['pid']==0 and job.get('parent_stopped') is not True)):raise ValueError('无效更新任务')
    identity=str(uuid.UUID(job.get('id','')))
    if identity!=job['id']:raise ValueError('无效更新标识')
    root=check_root(job['root']);manifest=read_json(work/'manifest.json')
    validate_manifest(manifest,job['target_version'],job['current_version'])
    archive=work/'program.zip';verify_archive(archive,manifest)
    if (root/JOURNAL).exists():recover(root,wait=False)
    target=version_dir(root,job['target_version']);stage=local_path(work,'extracted')
    child=None;journal=None;exited=False
    def report(status,message):
        data=dict(status=status,message=message,version=job['target_version'],updated_at=time.time())
        atomic_json(work/'result.json',data);atomic_json(root/'update-result.json',data)
    atomic_json(work/'ready.json',{'id':identity,'pid':os.getpid()})
    if (work/'owner.json').exists():
        atomic_json(work/'owner.json',{'root':str(root),'pid':os.getpid(),'id':work.name})
    try:
        waiter(job['pid']);exited=True
        if (work/'cancel').exists():raise InterruptedError('已取消更新')
        if job.get('watcher_paused'):time.sleep(2.5)
        if shutil.disk_usage(root).free<sum(v['bytes'] for v in manifest['files'].values())*2+30_000_000:
            raise OSError('磁盘空间不足，原程序和配置未改动')
        report('installing','正在准备程序更新，配置与素材保留')
        stage.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as z:
            for name in manifest['files']:
                dst=local_path(stage,name);dst.parent.mkdir(parents=True,exist_ok=True)
                with z.open(name) as src,dst.open('wb') as out:shutil.copyfileobj(src,out)
        legacy=not (root/POINTER).exists()
        global_files=[n for n in manifest['files'] if not n.startswith('.programs/') and (legacy or n!=EXECUTABLE_NAME)]
        snapshot(root,identity,global_files+['market-runtime.json','program-files.json'])
        journal=dict(id=identity,root=str(root),pid=os.getpid(),old_version=job['current_version'],
                     target_version=job['target_version'],legacy=legacy,phase='prepared')
        atomic_json(root/JOURNAL,journal)
        source=version_dir(stage,job['target_version']);target.parent.mkdir(exist_ok=True)
        if target.exists():
            from .update_package import digest
            for name,entry in manifest['files'].items():
                if name.startswith('.programs/'):
                    path=local_path(root,name)
                    if not path.is_file() or path.stat().st_size!=entry['bytes'] or digest(path)!=entry['sha256']:
                        raise ValueError('同版本程序目录已有不同内容，请保留备份后重新安装')
        else:source.rename(target)
        journal['phase']='activating';atomic_json(root/JOURNAL,journal)
        for name in sorted(global_files,key=lambda n:n==EXECUTABLE_NAME):replace_file(local_path(stage,name),local_path(root,name))
        if UPDATE_REPOSITORY=='Doya16/dsh-shorekeeper':
            atomic_json(root/'market-runtime.json',{'version':job['target_version'],'program_sha256':manifest['patch']['sha256']})
        atomic_json(root/'program-files.json',{'version':job['target_version'],'files':list(manifest['files'])})
        atomic_json(root/POINTER,{'version':job['target_version']})
        journal['phase']='checking';atomic_json(root/JOURNAL,journal)
        report('restarting','程序已更新，正在重新启动守岸人')
        child=launcher(root,job)
        if not health(root,child,job['target_version'],identity):raise RuntimeError('新版启动验证未通过，已恢复旧版')
        journal['phase']='committed';atomic_json(root/JOURNAL,journal)
        report('success','已更新并重启守岸人，原配置与素材已保留')
        (root/JOURNAL).unlink(missing_ok=True)
        return True
    except Exception as exc:
        if child is not None and child.poll() is None:
            child.terminate();child.wait(timeout=15)
        if journal:restore(root,journal)
        report('rolled_back' if journal else 'failed',str(exc))
        if exited:
            try:launcher(root,dict(job,rollback=True))
            except Exception:pass
        return False

def apply(job_path,**dependencies):
    job=read_json(job_path);root=check_root(job['root']);lock=local_path(root,'.update-lock.json')
    if lock.exists():
        existing=read_json(lock)
        if existing.get('root')!=str(root) or live(existing.get('pid')):raise RuntimeError('这个桌宠已有更新正在进行')
        lock.unlink()
    with lock.open('x',encoding='utf8') as f:json.dump({'root':str(root),'pid':os.getpid()},f)
    try:return _apply(job_path,**dependencies)
    finally:lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job');parser.add_argument('--recover-root');parser.add_argument('--recover-only',action='store_true');parser.add_argument('--wait-pid',type=int,default=0)
    args,forward=parser.parse_known_args()
    if args.recover_root:
        wait_exit(args.wait_pid);root=check_root(args.recover_root);recover(root,wait=False)
        if not args.recover_only:subprocess.Popen([str(active_program(root)),*(forward[1:] if forward[:1]==['--'] else forward)],cwd=root)
        return 0
    try:return 0 if apply(args.job) else 1
    except Exception as exc:
        if args.job:atomic_json(pathlib.Path(args.job).resolve().parent/'result.json',{'status':'failed','message':str(exc)})
        return 1

if __name__=='__main__':raise SystemExit(main())
