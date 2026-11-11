"""Work out what a finished Harness turn took from the balance."""
import time
from decimal import Decimal

SETTLE_SECONDS=30
REFRESH_AFTER=(2,8,16,24)
SYMBOLS={'CNY':'¥','USD':'$'}


def balance_total(quota):
    """The balance the pet displays, or None while it cannot be trusted."""
    if not quota or quota.get('status')!='ready' or quota.get('error') or not quota.get('wallets'):return None
    totals={}
    for row in quota['wallets']:totals[row['currency']]=totals.get(row['currency'],Decimal(0))+Decimal(row['balance'])
    currency=next((c for c in SYMBOLS if totals.get(c,0)>0),quota['wallets'][0]['currency'])
    return currency,totals[currency]


def money(report):
    symbol=SYMBOLS.get(report['currency'],'')
    if report['amount']<Decimal('.0001'):return f'<{symbol}0.0001'
    return f"{symbol}{report['amount'].quantize(Decimal('.0001'))}"


def bubble_text(report):
    extra='\n期间还有其他任务在跑，这是合计。' if report['shared'] else ''
    return f'这一轮用了 {money(report)}{extra}'


class TurnCost:
    """Compares the balance before a turn with the first lower reading after it."""

    def __init__(self,refresh,clock=time.time):
        self.refresh=refresh; self.clock=clock; self.current=None; self.pending=None

    def observe(self,status,quota,others=0):
        now=self.clock(); total=balance_total(quota); updated=(quota or {}).get('updated_at',0)
        if status.get('active') and status.get('turn_id'):self.track(status,total,updated,now,others)
        for event in status.get('events',[]):self.finish(event,now)
        return self.settle(total,updated,now)

    def track(self,status,total,updated,now,others):
        key=(status.get('thread_id'),status.get('turn_id'))
        if not self.current or self.current['key']!=key:
            if self.pending:self.pending['shared']=True
            self.current=dict(key=key,before=total,started=status.get('started',now),read=updated,shared=False)
            self.refresh()
        current=self.current
        # The refresh requested at the start replaces a reading older than the turn.
        if total and updated>current['read'] and current['read']<current['started'] and now<current['started']+5:
            current.update(before=total,read=updated)
        if current['before'] is None:current['before']=total
        if others:current['shared']=True

    def finish(self,event,now):
        current=self.current
        if not current or current['key']!=(event.get('thread_id'),event.get('turn_id')):return
        self.current=None
        if current['before'] is not None:
            self.pending=dict(current,ended=event.get('ended',now),refreshes=list(REFRESH_AFTER))

    def settle(self,total,updated,now):
        pending=self.pending
        if not pending:return None
        age=now-pending['ended']
        if pending['refreshes'] and age>=pending['refreshes'][0]:
            del pending['refreshes'][0]; self.refresh()
        currency,before=pending['before']
        if total and total[0]==currency and updated>=pending['ended'] and total[1]<before:
            self.pending=None
            return dict(amount=before-total[1],currency=currency,shared=pending['shared'])
        if age>SETTLE_SECONDS:self.pending=None
        return None
