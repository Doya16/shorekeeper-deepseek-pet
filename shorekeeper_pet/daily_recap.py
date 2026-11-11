"""Per-day counts for a short recap bubble: finished turns, errors, estimated spend and the longest turn."""
import datetime,json,pathlib,time
from decimal import Decimal,InvalidOperation
from .config_io import save_atomic

KEEP_DAYS=30


def day_of(timestamp):
    return datetime.date.fromtimestamp(timestamp).isoformat()


def duration_text(seconds,compact=False):
    seconds=max(0,round(seconds));gap='' if compact else ' '
    if seconds<60:return f'{seconds}{gap}秒'
    if seconds<3600:
        m,s=divmod(seconds,60);return f'{m}{gap}分' + (f'{gap}{s}{gap}秒' if s else '')
    h,rest=divmod(seconds,3600);return f'{h}{gap}小时' + (f'{gap}{rest//60}{gap}分' if rest//60 else '')


class DailyStats:
    def __init__(self,path,clock=time.time):
        self.path=pathlib.Path(path);self.clock=clock;self.seen=set()
        try:data=json.loads(self.path.read_text('utf8'))
        except (OSError,ValueError):data={}
        self.days=data.get('days',{}) if isinstance(data.get('days'),dict) else {}
        self.shown=data.get('shown','') if isinstance(data.get('shown'),str) else ''

    def entry(self,day):
        row=self.days.setdefault(day,{})
        for key in ('turns','errors','longest'):row[key]=row.get(key,0) if isinstance(row.get(key,0),(int,float)) else 0
        try:Decimal(str(row.get('cost','0')))
        except InvalidOperation:row['cost']='0'
        row.setdefault('cost','0');return row

    def record(self,event):
        """Count a finished turn once, on the day it ended."""
        key=(event.get('thread_id'),event.get('turn_id'),event.get('ended'))
        if key in self.seen or event.get('state') not in ('done','error'):return False
        self.seen.add(key);ended=event.get('ended') or self.clock();row=self.entry(day_of(ended))
        row['turns' if event['state']=='done' else 'errors']+=1
        started=event.get('started')
        if isinstance(started,(int,float)) and isinstance(ended,(int,float)) and ended>=started:row['longest']=max(row['longest'],round(ended-started))
        self.save();return True

    def add_cost(self,ended,amount):
        row=self.entry(day_of(ended or self.clock()));row['cost']=str(Decimal(row['cost'])+amount);self.save()

    def save(self):
        cutoff=(datetime.date.fromtimestamp(self.clock())-datetime.timedelta(days=KEEP_DAYS)).isoformat()
        self.days={k:v for k,v in self.days.items() if k>=cutoff}
        try:save_atomic(self.path,dict(days=self.days,shown=self.shown),backup=False)
        except OSError:pass

    def text(self,day,title):
        row=self.days.get(day)
        if not row or not (row.get('turns') or row.get('errors')):return None
        lines=[title,f"完成 {row['turns']} 轮" + (f"，出错 {row['errors']} 次" if row.get('errors') else '')]
        cost=Decimal(str(row.get('cost','0')));parts=[]
        if cost>0:parts.append(f'花费约 ¥{cost.quantize(Decimal(".01"))}' if cost>=Decimal('.01') else '花费不到 ¥0.01')
        if row.get('longest'):parts.append('最长一轮 '+duration_text(row['longest']))
        if parts:lines.append('，'.join(parts))
        return '\n'.join(lines)

    def today(self):
        return self.text(day_of(self.clock()),'今天到现在') or '今天还没有完成的任务。'

    def due(self):
        """The recap of the last active day before today, once per day."""
        today=day_of(self.clock())
        if self.shown==today:return None
        self.shown=today;self.save()
        earlier=sorted(d for d in self.days if d<today)
        if not earlier:return None
        last=earlier[-1];yesterday=(datetime.date.fromisoformat(today)-datetime.timedelta(days=1)).isoformat()
        date=datetime.date.fromisoformat(last)
        return self.text(last,'昨天的小结' if last==yesterday else f'{date.month}月{date.day}日的小结')
