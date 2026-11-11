import unittest
from decimal import Decimal

from shorekeeper_pet.turn_cost import TurnCost, bubble_text, money


def quota(value, updated):
    return dict(status='ready', error='', updated_at=updated, wallets=[dict(currency='CNY', balance=value, bonus=False)])


ACTIVE = dict(active=True, thread_id='t', turn_id='1', started=100)
END = dict(active=False, events=[dict(thread_id='t', turn_id='1', ended=110)])


class TurnCostTest(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.refreshes = 0
        self.tracker = TurnCost(self.refresh, clock=lambda: self.now)

    def refresh(self):
        self.refreshes += 1

    def finish(self):
        self.now = 110.0
        return self.tracker.observe(END, quota('45.00', 90))

    def test_reports_the_drop_after_the_turn(self):
        self.assertIsNone(self.tracker.observe(ACTIVE, quota('45.00', 90)))
        self.assertIsNone(self.finish())
        self.now = 112.0
        report = self.tracker.observe(dict(active=False, events=[]), quota('44.9877', 111))
        self.assertEqual(report['amount'], Decimal('0.0123'))
        self.assertEqual(money(report), '¥0.0123')
        self.assertIsNone(self.tracker.observe(dict(active=False, events=[]), quota('44.9877', 111)))

    def test_a_reading_from_before_the_end_is_not_the_cost(self):
        self.tracker.observe(ACTIVE, quota('45.00', 90))
        self.finish()
        self.now = 111.0
        self.assertIsNone(self.tracker.observe(dict(active=False, events=[]), quota('44.50', 105)))

    def test_start_refresh_replaces_an_old_baseline(self):
        self.tracker.observe(ACTIVE, quota('46.00', 90))
        self.now = 101.0
        self.tracker.observe(ACTIVE, quota('45.00', 100.5))
        self.finish()
        self.now = 112.0
        report = self.tracker.observe(dict(active=False, events=[]), quota('44.90', 111))
        self.assertEqual(report['amount'], Decimal('0.10'))

    def test_overlapping_tasks_are_labelled_as_a_total(self):
        self.tracker.observe(ACTIVE, quota('45.00', 90), others=1)
        self.finish()
        self.now = 112.0
        report = self.tracker.observe(dict(active=False, events=[]), quota('44.00', 111))
        self.assertIn('合计', bubble_text(report))

    def test_gives_up_when_the_balance_never_moves(self):
        self.tracker.observe(ACTIVE, quota('45.00', 90))
        self.finish()
        self.now = 141.0
        self.assertIsNone(self.tracker.observe(dict(active=False, events=[]), quota('45.00', 140)))
        self.assertIsNone(self.tracker.pending)

    def test_unavailable_balance_reports_nothing(self):
        self.tracker.observe(ACTIVE, dict(status='signed-out', wallets=[]))
        self.assertIsNone(self.finish())
        self.assertIsNone(self.tracker.pending)

    def test_tiny_amount_is_not_shown_as_zero(self):
        self.assertEqual(money(dict(amount=Decimal('0.00001'), currency='CNY')), '<¥0.0001')


class TurnCostOptionTest(unittest.TestCase):
    def test_floating_text_is_the_default(self):
        from shorekeeper_pet.appearance import appearance
        self.assertEqual(appearance({})['turn_cost_style'],'float')
        self.assertEqual(appearance({'appearance':{'turn_cost_style':'bad'}})['turn_cost_style'],'float')
        self.assertEqual(appearance({'appearance':{'turn_cost_style':'off'}})['turn_cost_style'],'off')


if __name__ == '__main__':
    unittest.main()
