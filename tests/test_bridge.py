import json,pathlib,tempfile,time,unittest
from unittest.mock import patch
from shorekeeper_pet.bridge import Monitor,RateClient,balance_data,balance_label

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=pathlib.Path(self.tmp.name)
        self.path=self.home/'shorekeeper-pet/desktop.json';self.path.parent.mkdir()
        self.monitor=Monitor(self.home);self.monitor.observe_since=100
        self.data=dict(schema=1,backend='deepseek-harness',instance='one',connected=True,
          updated_at=110,sessions=[],events=[],balance=dict(status='ready',wallets=[dict(currency='CNY',balance='3.14')],bonus=[],updated_at=110))
    def tearDown(self):self.tmp.cleanup()
    def row(self,name,active=True,turn='1'):
        return dict(thread_id=name,title=name,state='writing' if active else 'done',turn_id=turn,
                    active=active,started=101,ended=0 if active else 105,last_event=105,revision=1)
    def event(self,name,seq=1,when=105,turn='1'):
        return dict(thread_id=name,title=name,turn_id=turn,state='done',started=101,ended=when,seq=seq)
    def poll(self):
        self.path.write_text(json.dumps(self.data),'utf8')
        with patch('shorekeeper_pet.bridge.time.time',return_value=110):return self.monitor.poll()
    def test_concurrent_completion_is_not_lost_to_active_session(self):
        self.data['sessions']=[self.row('a'),self.row('b')];self.poll()
        self.data['sessions'][0]=self.row('a',False);self.data['events']=[self.event('a')]
        got=self.poll();self.assertEqual(got['thread_id'],'b');self.assertTrue(got['active'])
        self.assertEqual(got['events'][0]['thread_id'],'a');self.assertEqual(self.poll()['events'],[])
    def test_old_events_not_replayed_but_fast_new_completion_survives(self):
        self.data['events']=[self.event('old',1,90),self.event('new',2)]
        self.assertEqual([e['thread_id'] for e in self.poll()['events']],['new'])
    def test_turn_finished_then_next_started_between_polls(self):
        self.data['sessions']=[self.row('a',turn='2')];self.data['events']=[self.event('a')]
        got=self.poll();self.assertEqual(got['turn_id'],'2');self.assertEqual(got['events'][0]['turn_id'],'1')
    def test_fixed_session_still_receives_other_completions(self):
        self.monitor.selected='a';self.data['sessions']=[self.row('a'),self.row('b')]
        self.data['events']=[self.event('b')];got=self.poll()
        self.assertEqual(got['thread_id'],'a');self.assertEqual(got['events'][0]['thread_id'],'b')
    def test_restart_resets_sequence_and_disconnect_clears_active_state(self):
        self.data['events']=[self.event('a',40)];self.poll()
        self.data['instance']='two';self.data['events']=[self.event('b')]
        self.assertEqual(self.poll()['events'][0]['thread_id'],'b')
        self.data['connected']=False;self.assertEqual(self.poll()['state'],'unknown')
        self.assertFalse(self.poll()['active'])
    def test_malformed_and_stale_bridge_are_unavailable(self):
        self.path.write_text('{','utf8');self.assertEqual(self.monitor.poll()['state'],'unknown')
        self.data['updated_at']=80;self.assertEqual(self.poll()['state'],'unknown')
    def test_money_and_bonus_are_not_percentages(self):
        self.data['balance']['bonus']=[dict(currency='CNY',balance='1.02')]
        with patch('shorekeeper_pet.bridge.time.time',return_value=110):
            data=balance_data(self.data);self.assertEqual(balance_label(data,True),'算力余额：¥4.16')
            self.assertEqual(data['windows'],[])
    def test_missing_balance_does_not_become_zero(self):
        self.data['balance']={'status':'unavailable'}
        with patch('shorekeeper_pet.bridge.time.time',return_value=110):
            self.assertEqual(balance_label(balance_data(self.data),True),'算力余额：--')
    def test_bonus_only_account_and_mixed_currencies(self):
        self.data['balance'].update(wallets=[dict(currency='CNY',balance='0E-16')],bonus=[dict(currency='USD',balance='5')])
        with patch('shorekeeper_pet.bridge.time.time',return_value=110):
            self.assertEqual(balance_label(balance_data(self.data),True),'算力余额：$5.00')
    def test_balance_refresh_only_touches_plugin_request_file(self):
        self.poll()
        RateClient(deepseek_home=str(self.home)).read()
        self.assertTrue((self.home/'shorekeeper-pet/refresh').is_file())
        self.assertFalse((self.home/'.credentials.yaml').exists())

if __name__=='__main__':unittest.main()
