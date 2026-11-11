"""Turn cost estimated from token counts and DeepSeek's published prices."""
import unittest
from datetime import datetime
from decimal import Decimal
from shorekeeper_pet.pricing import BEIJING,family,peak,turn_report
from shorekeeper_pet.turn_cost import bubble_text,money


def hour(*when):
    return int(datetime(*when,tzinfo=BEIJING).timestamp())//3600


WEDNESDAY_10=hour(2026,11,11,10)
WEDNESDAY_13=hour(2026,11,11,13)
SATURDAY_10=hour(2026,11,14,10)


def event(*rows,search=0,fetch=0):
    tokens=[dict(provider='deepseek-account',model=m,hour=h,hit=a,miss=b,out=c) for m,h,a,b,c in rows]
    return dict(thread_id='a',turn_id='1',ended=1,usage=dict(tokens=tokens,search=search,fetch=fetch))


class PricingTests(unittest.TestCase):
    def test_peak_hours_follow_beijing_weekdays(self):
        self.assertTrue(peak(WEDNESDAY_10));self.assertTrue(peak(hour(2026,11,11,17)))
        self.assertFalse(peak(WEDNESDAY_13));self.assertFalse(peak(hour(2026,11,11,18)));self.assertFalse(peak(hour(2026,11,11,8)))
        self.assertFalse(peak(SATURDAY_10))

    def test_flash_at_peak(self):
        report=turn_report(event(('deepseek-flash',WEDNESDAY_10,1_000_000,1_000_000,1_000_000)))
        self.assertEqual(report['amount'],Decimal('10.04'));self.assertEqual(report['currency'],'CNY')

    def test_off_peak_is_half_price(self):
        report=turn_report(event(('deepseek-v4-pro',SATURDAY_10,1_000_000,1_000_000,1_000_000)))
        self.assertEqual(report['amount'],Decimal('18.15'))

    def test_a_turn_across_peak_and_off_peak(self):
        report=turn_report(event(('deepseek-flash',WEDNESDAY_10,0,0,1_000_000),('deepseek-flash',WEDNESDAY_13,0,0,1_000_000)))
        self.assertEqual(report['amount'],Decimal(12))

    def test_typical_small_turn(self):
        report=turn_report(event(('deepseek-flash',SATURDAY_10,9472,1381,201)))
        self.assertEqual(money(report),'¥0.0024')

    def test_web_requests_are_added(self):
        self.assertEqual(turn_report(event(('deepseek-flash',SATURDAY_10,0,0,1_000_000),search=2,fetch=1))['amount'],Decimal('4.015'))

    def test_requests_without_any_tokens_are_not_a_cost(self):
        self.assertIsNone(turn_report(event(search=2,fetch=1)))

    def test_old_aliases_use_flash_prices(self):
        self.assertEqual(family('deepseek-account','deepseek-v4-flash'),'flash')
        self.assertEqual(family('deepseek-account','deepseek-v4-flash-vision-exp'),'flash')

    def test_other_providers_and_unknown_models_are_not_guessed(self):
        self.assertIsNone(turn_report(dict(usage=dict(tokens=[dict(provider='opencode',model='deepseek-v4-pro',hour=1,hit=1,miss=1,out=1)]))))
        self.assertIsNone(turn_report(event(('deepseek-coder',SATURDAY_10,1,1,1))))
        self.assertIsNone(turn_report(event(('',SATURDAY_10,1,1,1))))

    def test_old_plugin_or_empty_turn_gives_nothing(self):
        self.assertIsNone(turn_report(dict(thread_id='a')))
        self.assertIsNone(turn_report(event()))
        self.assertIsNone(turn_report(event(('',0,0,0,0))))

    def test_bad_values_are_ignored(self):
        bad=dict(usage=dict(tokens=[dict(provider='deepseek-account',model='deepseek-flash',hour=SATURDAY_10,hit=-5,miss=True,out='9')]))
        self.assertIsNone(turn_report(bad))
        self.assertIsNone(turn_report(dict(usage=dict(tokens=['x']))))

    def test_bubble_says_it_is_an_estimate(self):
        report=turn_report(event(('deepseek-flash',SATURDAY_10,0,0,1_000_000)))
        self.assertEqual(bubble_text(report),'这一轮大约用了 ¥4.0000')


if __name__=='__main__':
    unittest.main()
