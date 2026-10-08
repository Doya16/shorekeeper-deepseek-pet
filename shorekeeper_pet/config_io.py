"""Atomic config snapshots and portable exports. Never includes DeepSeek account data."""
import copy,hashlib,json,os,pathlib,re,shutil,tempfile,time,zipfile
from .audio_player import resolve_audio,AUDIO_EXTS
from .voice_pool import clips_for,clip_bubble_text
from .paths import EXECUTABLE_NAME,PORTABLE_DIRNAME

def migrate_settings(settings):
    result=copy.deepcopy(settings); version=result.get('schema_version',0)
    options=result.setdefault('appearance',{})
    # Codex appearance/media imports work without carrying its connection settings.
    for key in ('codex_home','codex_executable','launch_with_codex'):
        options.pop(key,None)
    legacy=not isinstance(version,int) or version<7; result['schema_version']=7
    bindings=result.get('bindings',{})
    if isinstance(bindings,dict):
        bindings.pop('quota',None)
        for binding in bindings.values():
            if not isinstance(binding,dict): continue
            if binding.get('next_state')=='quota': binding['next_state']='auto'
            if legacy and binding.get('bubble_mode')!='off' and binding.get('audio_subtitles',True) and any(clip_bubble_text(c) for c in clips_for(binding)):
                binding['bubble_mode']='audio'
    return result

def save_atomic(path,data,backup=True):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if backup and path.is_file(): shutil.copy2(path,path.with_suffix('.json.bak'))
    temp=path.with_suffix('.json.tmp')
    with temp.open('w',encoding='utf8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
    temp.replace(path)

def bundle_payload(settings,root,portable=False):
    root=pathlib.Path(root); result=migrate_settings(settings)
    files={}; warnings=[]
    for folder in ('assets','fonts','licenses','defaults'):
        for file in (root/folder).rglob('*'):
            if file.is_file(): files[file.relative_to(root).as_posix()]=file
    options=result.setdefault('appearance',{})
    audio_directory=options.get('audio_directory','audio')
    library=pathlib.Path(audio_directory or 'audio')
    if not library.is_absolute(): library=root/library
    library=library.resolve(); library_names={}
    # Keep the entire configured audio library, including not-yet-bound clips.
    # Sidecar text travels with its audio; unrelated documents are not collected.
    if library.is_dir():
        for source in library.rglob('*'):
            if not source.is_file() or source.suffix.lower() not in AUDIO_EXTS: continue
            relative=source.relative_to(library).as_posix(); files['audio/'+relative]=source
            library_names[str(source.resolve())]=relative
            sidecar=source.with_suffix('.txt')
            if sidecar.is_file(): files['audio/'+sidecar.relative_to(library).as_posix()]=sidecar
    def collect_audio(value,state):
        if not value: return ''
        source=resolve_audio(value,audio_directory,root)
        if source:
            relative=library_names.get(str(source.resolve()))
            if relative: return relative
            digest=hashlib.sha256(source.read_bytes()).hexdigest()[:12]
            # Stable names survive repeated export/import without growing suffixes.
            safe='voice-'+digest+source.suffix.lower()
            files['audio/'+safe]=source
            sidecar=source.with_suffix('.txt')
            if sidecar.is_file(): files['audio/'+pathlib.Path(safe).with_suffix('.txt').as_posix()]=sidecar
            return safe
        warnings.append(f'{state}: 音频 {pathlib.Path(value).name} 不存在，迁移后需要重新选择。')
        return pathlib.Path(value).name
    for state,binding in result.get('bindings',{}).items():
        if 'audio_clips' in binding:
            binding['audio_clips']=clips_for(binding)
            for clip in binding['audio_clips']: clip['file']=collect_audio(clip['file'],state)
            # An obsolete fallback must not revive a removed clip on another PC.
            binding.pop('audio_file',None)
        elif binding.get('audio_file'):
            binding['audio_file']=collect_audio(binding['audio_file'],state)
    options['audio_directory']='audio'
    if portable:
        result['thread']='auto'; result.pop('position',None)
        options['deepseek_home']=''; options['deepseek_executable']=''
    return result,files,warnings

def export_bundle(destination,settings,root,portable=False):
    destination=pathlib.Path(destination); root=pathlib.Path(root)
    cfg,files,warnings=bundle_payload(settings,root,portable)
    if portable:
        runtime=root if (root/EXECUTABLE_NAME).is_file() else root/'dist'/PORTABLE_DIRNAME
        if not (runtime/EXECUTABLE_NAME).is_file(): raise FileNotFoundError('便携运行程序尚未构建，请使用已提供的 Windows 便携版。')
        files[EXECUTABLE_NAME]=runtime/EXECUTABLE_NAME
        for file in (runtime/'_internal').rglob('*'):
            if file.is_file(): files[file.relative_to(runtime).as_posix()]=file
        for name in ('README.md','MIGRATION.txt','THIRD_PARTY.txt','requirements.txt','tools/创建桌面快捷方式.cmd','tools/run_pet.py','tools/create_shortcut.ps1','tools/install_deepseek_plugin.ps1'):
            if (root/name).is_file(): files[name]=root/name
        for name in ('package.json','index.js','state.js','cordis.patch.yml','dsh-shorekeeper-pet-0.1.2.tgz'):
            path=root/'integrations/deepseek'/name
            if path.is_file(): files[path.relative_to(root).as_posix()]=path
        for file in (root/'shorekeeper_pet').glob('*.py'): files[file.relative_to(root).as_posix()]=file
        for file in (root/'docs').rglob('*'):
            if file.is_file() and file.suffix.lower() in ('.md','.png','.jpg','.gif'): files[file.relative_to(root).as_posix()]=file
    manifest=dict(format='shorekeeper-portable' if portable else 'shorekeeper-profile',schema_version=7,created_at=time.time(),warnings=warnings,files={name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in files.items()})
    destination.parent.mkdir(parents=True,exist_ok=True); temp=destination.with_suffix(destination.suffix+'.tmp')
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            z.writestr('settings.json',json.dumps(cfg,ensure_ascii=False,indent=2)); z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            z.writestr('audio/','')
            for name,p in files.items(): z.write(p,name)
        temp.replace(destination)
    except Exception:
        if temp.exists(): temp.unlink()
        raise
    return warnings

def import_bundle(source,root):
    root=pathlib.Path(root)
    with zipfile.ZipFile(source) as z:
        if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>1_500_000_000: raise ValueError('配置包过大')
        names=z.namelist()
        if len(names)!=len(set(names)): raise ValueError('配置包有重复条目')
        for name in names:
            p=pathlib.PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name: raise ValueError('配置包包含不安全路径')
        if z.getinfo('settings.json').file_size>2_000_000 or z.getinfo('manifest.json').file_size>5_000_000: raise ValueError('配置文件过大')
        manifest=json.loads(z.read('manifest.json')); settings=json.loads(z.read('settings.json'))
        if manifest.get('format') not in ('shorekeeper-profile','shorekeeper-portable') or not isinstance(settings,dict): raise ValueError('不是守岸人配置包')
        allowed={'fonts':{'.ttf','.otf','.ttc','.txt','.json'},'audio':AUDIO_EXTS|{'.txt'},'assets':{'.gif','.webp','.jpg','.jpeg','.json','.ico','.png'},'licenses':{'.txt'},'defaults':AUDIO_EXTS|{'.txt','.json'}}
        prepared=[]
        for name in names:
            p=pathlib.PurePosixPath(name)
            if not p.parts or p.parts[0] not in allowed or p.suffix.lower() not in allowed[p.parts[0]]: continue
            dest=(root/name).resolve()
            if not dest.is_relative_to(root.resolve()): raise ValueError('文件目标超出桌宠目录')
            data=z.read(name); expected=manifest.get('files',{}).get(name,{}).get('sha256')
            if not expected or hashlib.sha256(data).hexdigest()!=expected: raise ValueError('配置包校验失败：'+name)
            prepared.append((dest,data))
    # All entries are verified before any file is written. Imported code is never executed.
    for dest,data in prepared:
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_name(dest.name+'.importing'); tmp.write_bytes(data); tmp.replace(dest)
    return migrate_settings(settings)
