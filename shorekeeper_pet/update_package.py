"""Public program-only update packages. No personal files may enter a patch."""
import hashlib,json,os,pathlib,re,shutil,stat,urllib.request,zipfile
from .paths import ROOT,VERSION,UPDATE_REPOSITORY,EXECUTABLE_NAME
from .updates import source_url,version_tuple

HELPER='shorekeeper-updater.exe'
MAX_ZIP=350_000_000
MAX_UNPACKED=1_200_000_000
MAX_MANIFEST=2_000_000
PROTECTED={'settings.json','settings.json.bak','voice-history.json','assets','audio','fonts','defaults','exports','backups'}

def prefix(repository=UPDATE_REPOSITORY):
    return 'Shorekeeper-DeepSeek-' if 'deepseek' in repository else 'Shorekeeper-'

def names(version,repository=UPDATE_REPOSITORY):
    version_tuple(version)
    base=prefix(repository)
    return base+'Program-Update-v'+version+'.zip',base+'AutoUpdate-v'+version+'.json'

def safe_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:return False
    parts=name.split('/')
    reserved={'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}
    return all(p not in ('','.','..') and not p.endswith((' ','.')) and p.split('.')[0].lower() not in reserved for p in parts)

def program_file(name,executable=EXECUTABLE_NAME):
    if not safe_name(name):return False
    first=name.split('/')[0].lower()
    if first in PROTECTED:return False
    return (name==executable or name in ('BUILD_INFO.json','requirements.txt','LICENSE','THIRD_PARTY.txt','MIGRATION.txt')
            or name.startswith(('shorekeeper_pet/','resources/','integrations/'))
            or bool(re.fullmatch(r'\.programs/\d{1,5}\.\d{1,5}\.\d{1,5}/.+',name))
            or name in ('tools/'+HELPER,'tools/run_pet.py','tools/create_shortcut.ps1','tools/install_deepseek_plugin.ps1'))

def validate_manifest(data,target,current=VERSION,repository=UPDATE_REPOSITORY,executable=EXECUTABLE_NAME):
    if not isinstance(data,dict) or data.get('schema')!=1 or data.get('repository')!=repository or data.get('version')!=target:
        raise ValueError('更新包与当前桌宠版本不匹配')
    if version_tuple(target)<=version_tuple(current):raise ValueError('不能安装相同或更旧的版本')
    if version_tuple(data.get('minimum_version'))>version_tuple(current):raise ValueError('当前版本暂不支持这个更新包')
    if data.get('bridge_protocol',1)!=1:raise ValueError('此更新需要新版连接插件，请先在 Harness 更新守岸人插件')
    archive,_=names(target,repository);patch=data.get('patch',{})
    if (patch.get('name')!=archive or not isinstance(patch.get('bytes'),int) or not 1<=patch['bytes']<=MAX_ZIP
            or not re.fullmatch('[a-f0-9]{64}',str(patch.get('sha256','')))):
        raise ValueError('更新下载清单无效')
    files=data.get('files')
    if not isinstance(files,dict) or not 2<=len(files)<=8000:raise ValueError('更新文件清单无效')
    total=0;seen=set()
    for name,entry in files.items():
        if (not program_file(name,executable) or (name.startswith('.programs/') and not name.startswith('.programs/'+target+'/')) or name.casefold() in seen):raise ValueError('更新包包含非程序文件或重复路径')
        seen.add(name.casefold())
        if (not isinstance(entry,dict) or type(entry.get('bytes')) is not int or entry['bytes']<0
                or not re.fullmatch('[a-f0-9]{64}',str(entry.get('sha256','')))):
            raise ValueError('程序文件校验信息无效')
        total+=entry['bytes']
    if (total>MAX_UNPACKED or executable not in files or 'tools/'+HELPER not in files
            or '.programs/'+target+'/'+executable not in files or not any(n.startswith('.programs/'+target+'/_internal/') for n in files)):
        raise ValueError('更新程序不完整或过大')
    return data

def digest(path):
    with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_archive(path,manifest):
    patch=manifest['patch'];path=pathlib.Path(path)
    if path.stat().st_size!=patch['bytes'] or digest(path)!=patch['sha256']:raise ValueError('更新包大小或 SHA-256 校验失败')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if len(entries)!=len(manifest['files']) or len({x.filename.casefold() for x in entries})!=len(entries):
            raise ValueError('更新包包含额外或重复文件')
        for entry in entries:
            expected=manifest['files'].get(entry.filename)
            if (expected is None or entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16)
                    or entry.file_size!=expected['bytes']):raise ValueError('更新包文件列表不符')
            with archive.open(entry) as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=expected['sha256']:raise ValueError('更新程序文件校验失败')

def fetch(url,destination,size,sha256,source,progress=lambda *_:None,cancel=None,opener=urllib.request.urlopen):
    routes=('github','mirror') if source=='auto' else (source,)
    if any(r not in ('github','mirror') for r in routes):raise ValueError('无效更新来源')
    error=None
    for route in routes:
        try:
            request=urllib.request.Request(source_url(url,route),headers={'User-Agent':'Shorekeeper-Updater/'+VERSION})
            with opener(request,timeout=30) as response,open(destination,'wb') as out:
                length=0;hash_=hashlib.sha256()
                while True:
                    if cancel and cancel.is_set():raise InterruptedError('下载已取消')
                    block=response.read(128*1024)
                    if not block:break
                    length+=len(block)
                    if length>size:raise ValueError('更新下载超出声明大小')
                    hash_.update(block);out.write(block);progress(length,size)
            if length!=size or hash_.hexdigest()!=sha256:raise ValueError('下载校验失败，请稍后重试')
            return route
        except (OSError,ValueError) as exc:
            pathlib.Path(destination).unlink(missing_ok=True);error=exc
            if cancel and cancel.is_set():raise
    raise error

def prepare(result,source,root=ROOT,progress=lambda *_:None,cancel=None):
    root=pathlib.Path(root).resolve();zip_name,manifest_name=names(result.version)
    asset=next((a for a in result.assets if a.name==manifest_name),None)
    if not asset or not asset.sha256 or not 0<asset.bytes<=MAX_MANIFEST:
        raise ValueError('此版本尚未提供可校验的一键更新包，请稍后重试')
    helper=root/'tools'/HELPER
    if not helper.is_file():raise ValueError('缺少更新助手，请先安装含一键更新功能的版本')
    from .update_recovery import new_cache,clean_caches
    clean_caches(root);work=new_cache(root)
    try:
        manifest_path=work/'manifest.json'
        fetch(asset.url,manifest_path,asset.bytes,asset.sha256,source,cancel=cancel)
        manifest=validate_manifest(json.loads(manifest_path.read_text('utf8')),result.version)
        url=f'https://github.com/{UPDATE_REPOSITORY}/releases/download/v{result.version}/{zip_name}'
        archive=work/'program.zip';patch=manifest['patch']
        fetch(url,archive,patch['bytes'],patch['sha256'],source,progress,cancel)
        verify_archive(archive,manifest)
        shutil.copy2(helper,work/HELPER)
        return work,manifest
    except Exception:
        # Only the freshly created private staging directory is removed.
        assert work.parent==root/'.update-cache'
        shutil.rmtree(work,ignore_errors=True);raise
