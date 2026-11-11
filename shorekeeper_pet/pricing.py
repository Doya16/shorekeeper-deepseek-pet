"""Estimate what a finished turn cost from its token counts and DeepSeek's published prices.

Prices are CNY per million tokens at peak time, from the official pricing page
(https://api-docs.deepseek.com/zh-cn/quick_start/pricing, checked 2026-11-11).
Off-peak time is half price. Update this table when DeepSeek changes its prices.
"""
from datetime import datetime,timedelta,timezone
from decimal import Decimal

# family: (input served from cache, input not cached, output)
PRICES={'flash':(Decimal('0.04'),Decimal('2'),Decimal('8')),'pro':(Decimal('0.30'),Decimal('9'),Decimal('27'))}
OFF_PEAK=Decimal('0.5')
REQUEST=Decimal('0.005')  # web search or fetch, per successful request
BILLED_BY_DEEPSEEK=('deepseek-account','deepseek-official','deepseek')
BEIJING=timezone(timedelta(hours=8))
MILLION=Decimal(1_000_000)


def family(provider,model):
    """Only calls DeepSeek bills to this account are priced; anything else is unknown."""
    if provider not in BILLED_BY_DEEPSEEK:return None
    name=str(model).lower()
    if not name.startswith('deepseek'):return None
    if 'pro' in name:return 'pro'
    if 'flash' in name:return 'flash'
    return None


def peak(hour):
    """Weekdays 9:00-12:00 and 14:00-18:00 Beijing time. Public holidays are not known and count as weekdays."""
    t=datetime.fromtimestamp(hour*3600,BEIJING)
    return t.weekday()<5 and (9<=t.hour<12 or 14<=t.hour<18)


def count(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else 0


def turn_report(event):
    """A cost report for a finished turn, or None when the plugin sent no usage or a call cannot be priced."""
    usage=event.get('usage')
    if not isinstance(usage,dict) or not isinstance(usage.get('tokens'),list):return None
    total=Decimal(0); used=False
    for row in usage['tokens']:
        if not isinstance(row,dict):return None
        tokens=count(row.get('hit')),count(row.get('miss')),count(row.get('out'))
        if not any(tokens):continue
        name=family(row.get('provider'),row.get('model'))
        if name is None or not isinstance(row.get('hour'),int):return None
        price=PRICES[name];scale=1 if peak(row['hour']) else OFF_PEAK
        total+=sum(p*n for p,n in zip(price,tokens))*scale/MILLION; used=True
    # Every turn calls the model at least once; no tokens means the counts did not arrive.
    if not used:return None
    total+=REQUEST*(count(usage.get('search'))+count(usage.get('fetch')))
    return dict(amount=total,currency='CNY',shared=False,ended=event.get('ended'),estimate=True)
