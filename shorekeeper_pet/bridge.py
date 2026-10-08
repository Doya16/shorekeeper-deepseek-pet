"""Read Harness pet plugin metadata, never credentials or chat logs."""
from __future__ import annotations
import json, os, pathlib, time
from decimal import Decimal, InvalidOperation
from .paths import ROOT, DSH_HOME

def discover_deepseek(explicit=''):
    if explicit:
        p=pathlib.Path(explicit); return str(p) if p.is_file() else None
    for base in (os.environ.get('LOCALAPPDATA',''),os.environ.get('ProgramFiles','')):
        for suffix in ('Programs/DeepSeek Harness/DeepSeek Harness.exe','DeepSeek Harness/DeepSeek Harness.exe'):
            p=pathlib.Path(base)/suffix
            if p.is_file(): return str(p)
    return None

def read_snapshot(home):
    path=pathlib.Path(home)/'shorekeeper-pet/desktop.json'
    if path.stat().st_size>2_000_000: raise ValueError('状态文件过大')
    value=json.loads(path.read_text('utf8'))
    if value.get('schema')!=1 or value.get('backend')!='deepseek-harness': raise ValueError('状态格式不受支持')
    return value

def is_connected(value):
    age=time.time()-value.get('updated_at',0)
    return bool(value.get('connected')) and -5<=age<10

def balance_data(value):
    b=value.get('balance',{}); connected=is_connected(value); rows=[]
    for key in ('wallets','bonus'):
        for row in b.get(key,[]) if isinstance(b.get(key,[]),list) else []:
            try:
                amount=Decimal(row['balance'])
                if row.get('currency') not in ('CNY','USD') or not amount.is_finite() or abs(amount)>Decimal('1e12'): continue
                rows.append(dict(currency=row['currency'],balance=str(amount),bonus=key=='bonus'))
            except (KeyError,TypeError,InvalidOperation): continue
    error='' if connected and b.get('status')=='ready' else (
        '请登录 DeepSeek Harness' if b.get('status')=='signed-out' else
        '请打开 DeepSeek Harness 并安装桌宠连接插件' if not connected else '余额暂不可用')
    return dict(windows=[],wallets=rows,updated_at=b.get('updated_at',0),
        source='live' if connected else 'cache',error=error,status=b.get('status','unavailable'))

def balance_label(data,compact=False):
    rows=data.get('wallets',[])
    if not rows: return '算力余额：--' if compact else data.get('error') or '余额读取中…'
    totals={currency:sum((Decimal(r['balance']) for r in rows if r['currency']==currency),Decimal(0)) for currency in ('CNY','USD')}
    currency=next((c for c in ('CNY','USD') if totals[c]>0),rows[0]['currency'])
    total=totals[currency]
    amount=format(total.quantize(Decimal('.01')),'f')
    stale=data.get('error') or data.get('source')!='live' or time.time()-data.get('updated_at',0)>300
    return f"算力余额：{'¥' if currency=='CNY' else '$'}{amount}"+(' *' if stale else '')

class RateClient:
    def __init__(self,executable='',deepseek_home=''):
        self.executable=executable; self.deepseek_home=deepseek_home
    def read(self):
        home=pathlib.Path(self.deepseek_home or DSH_HOME)
        try:
            request=home/'shorekeeper-pet/refresh'; request.parent.mkdir(parents=True,exist_ok=True); request.touch()
            return balance_data(read_snapshot(home))
        except (OSError,ValueError,TypeError):
            return dict(windows=[],wallets=[],error='请打开 DeepSeek Harness 并安装桌宠连接插件',source='unavailable')
    def close(self): pass

class Monitor:
    def __init__(self,home=DSH_HOME):
        self.home=pathlib.Path(home); self.selected='auto'; self.threads=[]
        self.observe_since=time.time(); self.instance=None; self.sequence=0; self.error=''; self.last={}
    def cached_rate(self): return balance_data(self.last) if self.last else None
    def poll(self):
        base=dict(state='idle',message='',title='',thread_id='',turn_id='',stale=False,active=False,events=[])
        try:
            value=read_snapshot(self.home); self.last=value
            if not is_connected(value): raise ValueError('桌宠连接插件尚未连接')
            self.error=''
        except (OSError,ValueError,TypeError):
            self.error='请打开 DeepSeek Harness 并安装桌宠连接插件'; self.threads=[]
            return dict(base,state='unknown',stale=True)
        if self.instance!=value.get('instance'):
            self.instance=value.get('instance'); self.sequence=0
        events=[]
        for event in value.get('events',[]):
            seq=event.get('seq',0)
            if seq>self.sequence and event.get('ended',0)>=self.observe_since: events.append(event.copy())
            self.sequence=max(self.sequence,seq)
        rows=value.get('sessions',[])
        self.threads=[dict(id=r['thread_id'],title=r['title']) for r in rows]
        choices=[r for r in rows if self.selected=='auto' or r['thread_id']==self.selected]
        if not choices: return dict(base,events=events)
        row=max(choices,key=lambda r:(bool(r.get('active')),r.get('last_event',0)))
        result=dict(base,**{k:v for k,v in row.items() if k in ('state','message','title','thread_id','turn_id','active','started','ended','last_event','revision')})
        if not result['active'] and result['state'] in ('done','error','paused'): result['state']='idle'
        result['events']=events; return result
