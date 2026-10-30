"""Public GitHub/mirror release checks; never installs or replaces files."""
from dataclasses import dataclass,replace
import json,re,urllib.error,urllib.parse,urllib.request
from .paths import VERSION,UPDATE_REPOSITORY

MAX_RESPONSE=1_000_000
MIRROR='https://gh-proxy.org/'
SOURCE_LABELS={'github':'GitHub 官方源','mirror':'镜像加速（GH-Proxy）','auto':'自动选择'}

@dataclass(frozen=True)
class ReleaseAsset:
    name:str
    label:str
    url:str
    sha256:str=''

@dataclass(frozen=True)
class UpdateResult:
    status:str
    version:str=''
    url:str=''
    notes:str=''
    message:str=''
    source:str='github'
    assets:tuple=()

def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?\d{1,5}\.\d{1,5}\.\d{1,5}',value):raise ValueError('Not a stable release version')
    return tuple(map(int,value.removeprefix('v').split('.')))

def releases_url(repository=UPDATE_REPOSITORY):return 'https://github.com/'+repository+'/releases/latest'

def source_url(url,source,repository=UPDATE_REPOSITORY):
    # A mirror receives public, fixed-project URLs only, never arbitrary links.
    prefixes=('https://github.com/'+repository+'/releases','https://api.github.com/repos/'+repository+'/releases/')
    if not any(url==p or url.startswith(p+'/') if p.endswith('releases') else url.startswith(p) for p in prefixes):raise ValueError('Invalid update URL')
    return MIRROR+url if source=='mirror' else url

def parse_release(data,current=VERSION,repository=UPDATE_REPOSITORY):
    if not isinstance(data,dict) or data.get('draft') is not False or data.get('prerelease') is not False:raise ValueError('Not a published stable release')
    tag=data.get('tag_name');version=version_tuple(tag)
    url='https://github.com/'+repository+'/releases/tag/'+urllib.parse.quote(tag,safe='')
    notes=data.get('body') or ''
    if not isinstance(notes,str):raise ValueError('Invalid release notes')
    prefix='Shorekeeper-DeepSeek-' if 'deepseek' in repository else 'Shorekeeper-'
    number=tag.removeprefix('v')
    allowed={f'{prefix}Windows-v{number}.zip':'下载完整包',f'{prefix}Settings-Patch-v{number}.zip':'下载程序补丁',f'{prefix}SHA256SUMS-v{number}.txt':'下载校验文件'}
    assets=[];seen=set()
    for asset in data.get('assets',[]) if isinstance(data.get('assets',[]),list) else []:
        if not isinstance(asset,dict):continue
        name=asset.get('name')
        if not isinstance(name,str) or name not in allowed or name in seen:continue
        seen.add(name);digest=asset.get('digest') or ''
        sha=digest[7:] if isinstance(digest,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',digest) else ''
        link='https://github.com/'+repository+'/releases/download/'+urllib.parse.quote(tag,safe='')+'/'+name
        assets.append(ReleaseAsset(name,allowed[name],link,sha))
    return UpdateResult('available' if version>version_tuple(current) else 'current',number,url,notes[:12000],assets=tuple(assets))

def check_latest(current=VERSION,repository=UPDATE_REPOSITORY,opener=None,source='auto'):
    opener=opener or urllib.request.urlopen
    selected=('github','mirror') if source not in ('github','mirror') else (source,)
    message='本次未能检查更新。请检查网络，或切换更新来源。'
    for route in selected:
        request=urllib.request.Request(source_url('https://api.github.com/repos/'+repository+'/releases/latest',route,repository),headers={'Accept':'application/vnd.github+json','User-Agent':'Shorekeeper-Update-Check/'+current,'X-GitHub-Api-Version':'2022-11-28'})
        try:
            with opener(request,timeout=8) as response:raw=response.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE:raise ValueError('Release response too large')
            return replace(parse_release(json.loads(raw.decode('utf8')),current,repository),source=route)
        except urllib.error.HTTPError as error:
            message=('该来源暂时限制了请求，请稍后重试或切换来源。' if error.code in (403,429) else '暂时没有可用的正式版本。' if error.code==404 else '暂时无法连接更新来源，请稍后重试。')
        except (OSError,ValueError,TypeError):pass
    return UpdateResult('unavailable',url=releases_url(repository),message=message,source=selected[-1])
