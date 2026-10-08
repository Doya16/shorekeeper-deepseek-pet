import copy
import json
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from shorekeeper_pet import updates, update_ui
from shorekeeper_pet.appearance import appearance
from shorekeeper_pet.config_io import export_bundle, import_bundle, save_atomic
from shorekeeper_pet.paths import UPDATE_REPOSITORY


def release(version='v0.10.0', **values):
    return dict(tag_name=version, draft=False, prerelease=False, body='新版说明', **values)


class Response:
    def __init__(self, data):self.data=data
    def __enter__(self):return self
    def __exit__(self, *args):pass
    def read(self, size):return self.data[:size]


class ReleaseTests(unittest.TestCase):
    def test_numeric_versions_and_never_downgrade(self):
        self.assertEqual(updates.parse_release(release(), '0.9.99').status, 'available')
        self.assertEqual(updates.parse_release(release(), '0.10.0').status, 'current')
        self.assertEqual(updates.parse_release(release(), '0.11.0').status, 'current')
    def test_only_stable_valid_releases_are_accepted(self):
        for tag in ('v0.10.0-beta', 'latest', '../test', '0.10', None):
            with self.assertRaises(ValueError):updates.parse_release(release(tag))
        for key in ('draft', 'prerelease'):
            data=release();data[key]=True
            with self.assertRaises(ValueError):updates.parse_release(data)
    def test_repo_specific_url_ignores_remote_links_and_limits_notes(self):
        data=release(html_url='https://elsewhere.example/');data['body']='x'*20000
        result=updates.parse_release(data, '0.0.0')
        self.assertEqual(result.url, 'https://github.com/'+UPDATE_REPOSITORY+'/releases/tag/v0.10.0')
        self.assertEqual(len(result.notes), 12000)
    def test_request_is_public_bounded_and_targets_own_edition(self):
        requests=[]
        def opener(request, timeout):
            requests.append((request,timeout));return Response(json.dumps(release()).encode())
        self.assertEqual(updates.check_latest('0.0.0', opener=opener).status,'available')
        request,timeout=requests[0]
        self.assertEqual(request.full_url,'https://api.github.com/repos/'+UPDATE_REPOSITORY+'/releases/latest')
        self.assertEqual(timeout,8);self.assertIsNone(request.data)
        self.assertNotIn('Authorization',request.headers)
    def test_network_errors_bad_json_and_large_payload_are_nonfatal(self):
        for data in (b'not json',b'x'*(updates.MAX_RESPONSE+1),b'[]'):
            self.assertEqual(updates.check_latest(opener=lambda *a,**k:Response(data)).status,'unavailable')
        for error in (TimeoutError(),urllib.error.URLError('offline'),urllib.error.HTTPError('https://api.github.com',403,'limit',{},None)):
            with patch('urllib.request.urlopen',side_effect=error):
                self.assertEqual(updates.check_latest().status,'unavailable')
    def test_update_preferences_and_media_survive_two_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);(root/'assets').mkdir();(root/'assets/custom.gif').write_bytes(b'GIF89a')
            config={'appearance':{'check_updates_on_start':False,'ignored_update_version':'0.10.0'},'bindings':{'idle':{'bubble_text':'我的台词'}}}
            for number in range(2):
                archive=pathlib.Path(folder)/f'export-{number}.zip'
                self.assertFalse(export_bundle(archive,config,root))
                root=pathlib.Path(folder)/f'moved-{number}';config=import_bundle(archive,root)
                self.assertFalse(appearance(config)['check_updates_on_start'])
                self.assertEqual(appearance(config)['ignored_update_version'],'0.10.0')
                self.assertEqual(config['bindings']['idle']['bubble_text'],'我的台词')
                self.assertEqual((root/'assets/custom.gif').read_bytes(),b'GIF89a')


class FakePet(QObject):
    def __init__(self, root):
        super().__init__();self.root=root;self.icon=QIcon()
        self.settings={'appearance':{},'bindings':{'idle':{'bubble_text':'保留原台词'}}}
        self.options=appearance(self.settings)
    def set_option(self,key,value):
        self.options[key]=value;self.settings['appearance']=dict(self.options)
        save_atomic(self.root/'settings.json',self.settings);return True


class UpdateWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        self.pet=FakePet(self.root);self.controller=update_ui.UpdateController(self.pet)
    def tearDown(self):
        self.controller.close()
        if self.controller.dialog:self.controller.dialog.deleteLater()
        self.pet.deleteLater();self.app.processEvents();self.temp.cleanup()
    def wait_for(self, predicate):
        deadline=time.monotonic()+2
        while not predicate() and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.01)
        self.assertTrue(predicate())
    def result(self):return updates.UpdateResult('available','9.9.9',updates.releases_url(),'说明')
    def test_startup_checks_once_in_worker_and_does_not_touch_settings(self):
        main=threading.get_ident();calls=[];before=copy.deepcopy(self.pet.settings)
        def check():calls.append(threading.get_ident());return updates.UpdateResult('current')
        with patch.object(update_ui,'check_latest',side_effect=check):
            self.controller.check_startup();self.wait_for(lambda:not self.controller.busy)
            self.controller.check_startup()
        self.assertEqual(len(calls),1);self.assertNotEqual(calls[0],main)
        self.assertIsNone(self.controller.dialog);self.assertEqual(self.pet.settings,before)
        self.assertFalse((self.root/'settings.json').exists())
    def test_disabled_startup_makes_no_request(self):
        self.pet.options['check_updates_on_start']=False
        with patch.object(update_ui,'check_latest') as request:
            self.controller.check_startup();request.assert_not_called()
    def test_automatic_error_is_silent_and_manual_error_is_visible(self):
        result=updates.UpdateResult('unavailable',message='断网了')
        self.controller._finished(result);self.assertIsNone(self.controller.dialog)
        self.controller.manual_requested=True;self.controller._finished(result)
        self.assertTrue(self.controller.dialog.isVisible())
    def test_ignored_version_is_hidden_until_manual_check_or_later_version(self):
        self.pet.options['ignored_update_version']='9.9.9'
        self.controller._finished(self.result());self.assertIsNone(self.controller.dialog)
        self.controller.manual_requested=True;self.controller._finished(self.result())
        self.assertTrue(self.controller.dialog.isVisible())
        self.controller.dialog.close();self.controller._finished(updates.UpdateResult('available','10.0.0'))
        self.assertEqual(self.controller.dialog.result.version,'10.0.0')
    def test_ignore_is_saved_but_dismiss_does_not_change_settings(self):
        self.controller._finished(self.result());before=copy.deepcopy(self.pet.settings)
        self.controller.dialog.reject();self.assertEqual(self.pet.settings,before)
        self.controller._finished(self.result());self.controller.dialog.ignore_button.click()
        data=json.loads((self.root/'settings.json').read_text('utf8'))
        self.assertEqual(data['appearance']['ignored_update_version'],'9.9.9')
        self.assertEqual(data['bindings'],before['bindings'])
    def test_shutdown_ignores_late_results(self):
        self.controller.close();self.controller._finished(self.result());self.assertIsNone(self.controller.dialog)
    def test_manual_check_joins_inflight_request_and_plain_text_notes(self):
        ready=threading.Event();done=threading.Event()
        def check():ready.set();done.wait(1);return updates.UpdateResult('available','9.9.9',notes='<script>alert(1)</script>')
        with patch.object(update_ui,'check_latest',side_effect=check) as request:
            self.controller.check(False);self.assertTrue(ready.wait(1));self.controller.check(True)
            done.set();self.wait_for(lambda:not self.controller.busy)
            self.assertEqual(request.call_count,1)
        self.assertEqual(self.controller.dialog.notes.toPlainText(),'<script>alert(1)</script>')
        self.assertFalse(self.controller.dialog.isModal())


if __name__=='__main__':unittest.main()
