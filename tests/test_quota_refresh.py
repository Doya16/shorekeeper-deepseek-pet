import threading,unittest
from shorekeeper_pet.quota_refresh import QuotaRefresh

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.now=10.;self.event=threading.Event();self.feedback=QuotaRefresh(self.event,lambda:self.now)

    def test_click_during_periodic_read_is_not_lost_or_completed_by_older_response(self):
        f=self.feedback;old=f.begin_read();f.request()
        self.assertTrue(self.event.is_set());self.assertEqual(f.label(),'刷新中…')
        f.finish(old,dict(source='live'));self.assertEqual(f.label(),'刷新中…')
        ticket=f.begin_read();self.assertFalse(self.event.is_set())
        f.request();self.assertEqual(f.sequence,ticket);self.assertFalse(self.event.is_set())
        self.now+=1;f.finish(ticket,dict(source='live'));self.assertEqual(f.label(),'')

    def test_changed_connection_queues_a_new_read_even_while_old_one_is_pending(self):
        f=self.feedback;f.request(('client-a','home-a'));old=f.begin_read()
        f.request(('client-b','home-b'));self.assertTrue(self.event.is_set())
        f.finish(old,dict(source='live'));self.assertEqual(f.label(),'刷新中…')
        current=f.begin_read();self.assertNotEqual(old,current)
        self.now+=1;f.finish(current,dict(source='live'));self.assertEqual(f.label(),'')

    def test_fast_success_is_visible_without_a_success_popup(self):
        f=self.feedback;f.request();f.finish(f.begin_read(),dict(source='live'))
        self.assertEqual(f.label(),'刷新中…')
        self.now+=.61;self.assertEqual(f.label(),'')

    def test_error_or_cache_shows_failure_then_restores_and_allows_retry(self):
        f=self.feedback
        for result in (dict(error='offline'),dict(source='cache')):
            f.request();ticket=f.begin_read();self.now+=1;f.finish(ticket,result)
            self.assertEqual(f.label(),'刷新失败')
            self.now+=2.6;self.assertEqual(f.label(),'')
        f.request();self.assertEqual(f.label(),'刷新中…');self.assertTrue(self.event.is_set())
