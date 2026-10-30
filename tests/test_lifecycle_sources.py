import json,pathlib,tempfile,threading,time,unittest,urllib.error
from unittest.mock import patch
from PySide6.QtGui import QDesktopServices
from shorekeeper_pet.client_lifetime import ClientLifetime
from shorekeeper_pet import updates,update_ui
from shorekeeper_pet.appearance import appearance
from shorekeeper_pet.config_io import export_bundle,import_bundle
from shorekeeper_pet.paths import UPDATE_REPOSITORY

class ClientLifetimeTests(unittest.TestCase):
    def test_manual_launch_without_client_stays_open(self):
        guard=ClientLifetime()
        for now in (0,8,1000):self.assertFalse(guard.observe({},now))
    def test_last_client_exit_is_debounced_and_fires_once(self):
        g=ClientLifetime();self.assertFalse(g.observe({10:1},0))
        self.assertFalse(g.observe({},2));self.assertFalse(g.observe({},9))
        self.assertTrue(g.observe({},10));self.assertFalse(g.observe({},12))
    def test_tray_background_and_other_instance_keep_pet_alive(self):
        g=ClientLifetime();g.observe({10:1,20:1},0)
        for now in (2,20,100):self.assertFalse(g.observe({20:1},now))
        self.assertFalse(g.observe({},102));self.assertTrue(g.observe({},110))
    def test_restart_during_grace_cancels_pending_exit(self):
        g=ClientLifetime();g.observe({10:1},0);g.observe({},2)
        self.assertFalse(g.observe({20:1},8));self.assertIsNone(g.missing_since)
        self.assertFalse(g.observe({},10));self.assertFalse(g.observe({},16));self.assertTrue(g.observe({},18))
    def test_surviving_renderer_does_not_block_exit_or_restart(self):
        g=ClientLifetime();g.observe({10:1,11:10,12:11},0)
        self.assertFalse(g.observe({11:10,12:11},2))
        self.assertTrue(g.observe({11:10,12:11},10))
        self.assertFalse(g.observe({11:10,12:11,20:1,21:20},12));self.assertIsNone(g.missing_since)
    def test_access_errors_reset_grace_without_proving_exit(self):
        g=ClientLifetime();g.observe({10:1},0);g.observe({},2)
        self.assertFalse(g.observe(None,10));self.assertFalse(g.observe({},12));self.assertFalse(g.observe({},18));self.assertTrue(g.observe({},20))
    def test_disable_cancels_pending_and_reenable_waits_for_client(self):
        g=ClientLifetime();g.observe({10:1},0);g.observe({},2);g.observe({},10,False)
        self.assertFalse(g.observe({},100));self.assertFalse(g.seen)

class Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.data[:n]

def release():
    prefix='Shorekeeper-DeepSeek-' if 'deepseek' in UPDATE_REPOSITORY else 'Shorekeeper-'
    return dict(tag_name='v9.9.9',draft=False,prerelease=False,body='说明',assets=[{'name':prefix+'Windows-v9.9.9.zip','browser_download_url':'https://untrusted.example/malware.exe','digest':'sha256:'+'a'*64}])

class UpdateSourceTests(unittest.TestCase):
    def test_auto_uses_github_without_mirror_when_reachable(self):
        calls=[]
        def read(req,timeout):calls.append(req);return Response(json.dumps(release()).encode())
        result=updates.check_latest('0.0.0',opener=read)
        self.assertEqual(result.source,'github');self.assertEqual(len(calls),1)
    def test_auto_falls_back_after_timeout_or_rate_limit_or_html(self):
        for error in (TimeoutError(),urllib.error.HTTPError('https://api.github.com',403,'rate',{},None),'html'):
            calls=[]
            def read(req,timeout):
                calls.append(req)
                if len(calls)==1:
                    if error=='html':return Response(b'<html>error</html>')
                    raise error
                return Response(json.dumps(release()).encode())
            result=updates.check_latest('0.0.0',opener=read)
            self.assertEqual(result.source,'mirror');self.assertEqual(result.status,'available')
            self.assertEqual(len(calls),2);self.assertTrue(calls[1].full_url.startswith(updates.MIRROR))
            self.assertTrue(all('Authorization' not in r.headers and r.data is None for r in calls))
    def test_manual_route_never_silently_changes(self):
        for route in ('github','mirror'):
            calls=[]
            def read(req,timeout):calls.append(req);raise TimeoutError()
            result=updates.check_latest(source=route,opener=read)
            self.assertEqual(result.source,route);self.assertEqual(result.status,'unavailable');self.assertEqual(len(calls),1)
    def test_download_urls_are_built_from_fixed_project_assets(self):
        data=release();data['assets'] += [{'name':'../../evil.exe'},None,{'name':[]},{'name':data['assets'][0]['name']}]
        result=updates.parse_release(data,'0.0.0');self.assertEqual(len(result.assets),1)
        a=result.assets[0];self.assertEqual(a.sha256,'a'*64)
        self.assertTrue(a.url.startswith('https://github.com/'+UPDATE_REPOSITORY+'/releases/download/v9.9.9/'))
        self.assertEqual(updates.source_url(a.url,'mirror'),updates.MIRROR+a.url)
        for unsafe in ('https://elsewhere.example','https://github.com/'+UPDATE_REPOSITORY+'/releases-evil','file:///local'):
            with self.assertRaises(ValueError):updates.source_url(unsafe,'mirror')
    def test_source_and_exit_preferences_migrate_with_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'assets').mkdir();(root/'assets/a.gif').write_bytes(b'GIF89a')
            key='exit_with_deepseek' if 'deepseek' in UPDATE_REPOSITORY else 'exit_with_codex'
            config={'appearance':{'update_source':'mirror',key:False},'bindings':{'idle':{'bubble_text':'保留台词'}}}
            archive=root/'profile.zip';self.assertFalse(export_bundle(archive,config,root))
            restored=import_bundle(archive,root/'new computer');options=appearance(restored)
            self.assertEqual(options['update_source'],'mirror');self.assertFalse(options[key]);self.assertEqual(restored['bindings'],config['bindings'])
            self.assertEqual(appearance({'appearance':{'update_source':'invalid'}})['update_source'],'auto')
