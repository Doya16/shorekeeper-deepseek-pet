import copy,hashlib,json,os,pathlib,tempfile,unittest,uuid,zipfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch,Mock
from shorekeeper_pet import update_package as package,update_apply as engine,update_ui
from shorekeeper_pet.paths import EXECUTABLE_NAME,UPDATE_REPOSITORY
from shorekeeper_pet.appearance import appearance
import test_updates

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name);self.root=self.base/'中文 安装目录';self.root.mkdir()
        (self.root/EXECUTABLE_NAME).write_bytes(b'OLD PROGRAM')
        self.personal={'settings.json':b'{"appearance":{"show_quota":false},"caption":"mine"}',
                       'assets/mine.gif':b'GIF89a','audio/mine.ogg':b'VOICE','fonts/mine.ttf':b'FONT','my-folder/notes.txt':b'USER'}
        for name,data in self.personal.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.work=self.base/'job';self.work.mkdir()
        self.files={EXECUTABLE_NAME:b'NEW PROGRAM','tools/'+package.HELPER:b'HELPER','.programs/9.0.0/'+EXECUTABLE_NAME:b'NEW CORE','.programs/9.0.0/_internal/runtime.dll':b'NEW DLL'}
        self.build()
    def tearDown(self):self.temp.cleanup()
    def build(self):
        with zipfile.ZipFile(self.work/'program.zip','w') as z:
            for name,data in self.files.items():z.writestr(name,data)
        archive=self.work/'program.zip'
        self.manifest={'schema':1,'repository':UPDATE_REPOSITORY,'version':'9.0.0','minimum_version':'0.0.0','bridge_protocol':1,
            'patch':{'name':package.names('9.0.0')[0],'bytes':archive.stat().st_size,'sha256':package.digest(archive)},
            'files':{n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in self.files.items()}}
        (self.work/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf8')
        self.job={'id':str(uuid.uuid4()),'pid':os.getpid(),'root':str(self.root),'target_version':'9.0.0','current_version':'1.0.0'}
        self.job_path=self.work/'job.json';self.job_path.write_text(json.dumps(self.job),encoding='utf8')
    def test_manifest_rejects_personal_paths_traversal_links_and_version_mismatch(self):
        for name in ('settings.json','assets/a.gif','audio/a.wav','fonts/a.ttf','defaults/settings.json','../x','_internal/../x','_internal/CON','_internal/a:ads','_internal/a.','C:/x'):
            m=copy.deepcopy(self.manifest);m['files'][name]={'bytes':0,'sha256':'0'*64}
            with self.assertRaises(ValueError,msg=name):package.validate_manifest(m,'9.0.0','1.0.0')
        for key,value in [('repository','other/repo'),('minimum_version','10.0.0'),('bridge_protocol',2)]:
            m=copy.deepcopy(self.manifest);m[key]=value
            with self.assertRaises(ValueError):package.validate_manifest(m,'9.0.0','1.0.0')
        with self.assertRaises(ValueError):package.validate_manifest(self.manifest,'9.0.0','10.0.0')
    def test_download_verification_fails_before_install_mutation(self):
        with (self.work/'program.zip').open('ab') as f:f.write(b'changed')
        with self.assertRaises(ValueError):engine.apply(self.job_path,waiter=lambda _:None)
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'OLD PROGRAM')
    def test_success_preserves_every_user_file_and_retains_complete_backup(self):
        child=Mock(pid=100);child.poll.return_value=None
        self.assertTrue(engine.apply(self.job_path,waiter=lambda _:None,launcher=lambda *_:child,health=lambda *_:True))
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'NEW PROGRAM')
        backup=self.root/'.update-backups'/self.job['id']
        for name,data in self.personal.items():
            self.assertEqual((self.root/name).read_bytes(),data)
        self.assertEqual((backup/'settings.json').read_bytes(),self.personal['settings.json'])
        self.assertEqual((backup/EXECUTABLE_NAME).read_bytes(),b'OLD PROGRAM')
        self.assertEqual(json.loads((self.root/'update-result.json').read_text('utf8'))['status'],'success')
    def test_failed_restart_restores_original_program_and_configuration(self):
        child=Mock(pid=100);child.poll.return_value=None;launch=Mock(return_value=child)
        self.assertFalse(engine.apply(self.job_path,waiter=lambda _:None,launcher=launch,health=lambda *_:False))
        child.terminate.assert_called_once();self.assertEqual(launch.call_count,2)
        self.assertTrue(launch.call_args.args[1]['rollback'])
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'OLD PROGRAM')
        for name,data in self.personal.items():self.assertEqual((self.root/name).read_bytes(),data)
    def test_locked_install_or_insufficient_space_leaves_original_untouched(self):
        with patch.object(engine.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            self.assertFalse(engine.apply(self.job_path,waiter=lambda _:None,launcher=Mock()))
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'OLD PROGRAM')
        lock=self.root/'.update-lock.json'
        lock.write_text(json.dumps({'root':str(self.root),'pid':os.getpid()}),encoding='utf8')
        with self.assertRaises(RuntimeError):engine.apply(self.job_path)

    def make_versioned(self):
        from shorekeeper_pet.update_recovery import atomic_json,version_dir,POINTER
        old=version_dir(self.root,'1.0.0');old.mkdir(parents=True)
        (old/EXECUTABLE_NAME).write_bytes(b'OLD CORE');(self.root/EXECUTABLE_NAME).write_bytes(b'STABLE LAUNCHER')
        atomic_json(self.root/POINTER,{'version':'1.0.0'})

    def test_versioned_upgrade_keeps_bootstrap_and_old_core(self):
        self.make_versioned();child=Mock(pid=100);child.poll.return_value=None
        self.assertTrue(engine.apply(self.job_path,waiter=lambda _:None,launcher=lambda *_:child,health=lambda *_:True))
        from shorekeeper_pet.update_recovery import active_program
        self.assertEqual(active_program(self.root).read_bytes(),b'NEW CORE')
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'STABLE LAUNCHER')
        self.assertEqual((self.root/'.programs/1.0.0'/EXECUTABLE_NAME).read_bytes(),b'OLD CORE')

    def test_interrupted_activation_recovers_old_version_and_exact_settings(self):
        from shorekeeper_pet import update_recovery as recovery
        self.make_versioned()
        def crash(*_):
            (self.root/'settings.json').write_bytes(b'NEW NORMALIZED CONFIG')
            raise KeyboardInterrupt('simulated updater process termination')
        with self.assertRaises(KeyboardInterrupt):engine.apply(self.job_path,waiter=lambda _:None,launcher=crash)
        journal=recovery.read_json(self.root/recovery.JOURNAL);journal['pid']=0
        recovery.atomic_json(self.root/recovery.JOURNAL,journal)
        self.assertTrue(recovery.recover(self.root))
        self.assertEqual(recovery.active_program(self.root).read_bytes(),b'OLD CORE')
        for name,data in self.personal.items():self.assertEqual((self.root/name).read_bytes(),data)
        self.assertFalse((self.root/recovery.JOURNAL).exists())

    def test_interrupted_download_cleanup_preserves_live_and_unowned_folders(self):
        from shorekeeper_pet import update_recovery as recovery
        stale=recovery.new_cache(self.root);(stale/'program.zip').write_bytes(b'PARTIAL DOWNLOAD')
        owner=recovery.read_json(stale/'owner.json');owner['pid']=0;recovery.atomic_json(stale/'owner.json',owner)
        active=recovery.new_cache(self.root)
        unknown=self.root/'.update-cache/keep-mine';unknown.mkdir();(unknown/'notes').write_bytes(b'USER')
        recovery.clean_caches(self.root)
        self.assertFalse(stale.exists());self.assertTrue(active.exists());self.assertTrue(unknown.exists())
        self.assertEqual((self.root/EXECUTABLE_NAME).read_bytes(),b'OLD PROGRAM')

    def test_committed_update_is_not_rolled_back_after_late_interruption(self):
        from shorekeeper_pet import update_recovery as recovery
        self.make_versioned();child=Mock(pid=100);child.poll.return_value=None
        self.assertTrue(engine.apply(self.job_path,waiter=lambda _:None,launcher=lambda *_:child,health=lambda *_:True))
        recovery.atomic_json(self.root/recovery.JOURNAL,dict(root=str(self.root),phase='committed'))
        self.assertFalse(recovery.recover(self.root));self.assertEqual(recovery.active_program(self.root).read_bytes(),b'NEW CORE')

class OneClickWidgetTests(unittest.TestCase):
    setUpClass=classmethod(test_updates.UpdateWidgetTests.setUpClass.__func__)
    setUp=test_updates.UpdateWidgetTests.setUp
    tearDown=test_updates.UpdateWidgetTests.tearDown
    result=test_updates.UpdateWidgetTests.result
    wait_for=test_updates.UpdateWidgetTests.wait_for
    def test_periodic_check_is_independent_of_startup_and_can_be_disabled(self):
        self.pet.options.update(check_updates_on_start=False,check_updates_periodic=True,update_interval_hours=3)
        self.controller.schedule();self.assertEqual(self.controller.periodic.interval(),3*3600000)
        with patch.object(self.controller,'check') as check:self.controller.check_periodic();check.assert_called_once_with(False)
        self.pet.options['check_updates_periodic']=False;self.controller.reconfigure();self.assertFalse(self.controller.periodic.isActive())
    def test_persistent_silent_notice_yields_to_voice_and_returns(self):
        self.pet.voice=SimpleNamespace(busy=False);self.pet.bubble_visible=lambda:True
        before=copy.deepcopy(self.pet.settings);self.controller._finished(self.result())
        self.assertIsNone(self.controller.dialog);self.assertTrue(self.controller.notice.isVisible())
        self.pet.voice.busy=True;self.assertFalse(self.controller.notice.refresh());self.assertFalse(self.controller.notice.isVisible())
        self.pet.voice.busy=False;self.assertTrue(self.controller.notice.refresh());self.assertEqual(self.pet.settings,before)
        self.assertEqual(self.controller.notice.install_button.text(),'更新并重启守岸人')
        self.assertEqual(self.controller.notice.snooze_button.text(),'今日不再提醒')
    def test_today_snooze_survives_restart_and_expires_next_day(self):
        self.controller._finished(self.result());self.controller.notice.snooze_button.click()
        self.assertFalse(self.controller.notice.isVisible());saved=json.loads((self.root/'settings.json').read_text('utf8'))
        self.assertEqual(saved['appearance']['update_snoozed_date'],date.today().isoformat())
        self.pet.options=appearance(saved);self.controller._finished(self.result());self.assertFalse(self.controller.notice.isVisible())
        with patch.object(update_ui,'date') as day:
            day.today.return_value=date.fromordinal(date.today().toordinal()+1)
            self.assertTrue(self.controller.notice.refresh())
    def test_notice_button_downloads_then_hands_off_once_and_saves_first(self):
        self.pet.save_settings=Mock(return_value=True);self.pet.shutdown=Mock()
        self.controller._finished(self.result());work=self.root/'download';work.mkdir()
        def spawn(args,**kwargs):
            job=json.loads((work/'job.json').read_text('utf8'))
            (work/'ready.json').write_text(json.dumps({'id':job['id']}),encoding='utf8')
            child=Mock();child.poll.return_value=None;return child
        with patch.object(update_ui.sys,'frozen',True,create=True),patch.object(update_ui,'ROOT',self.root),patch.object(package,'prepare',return_value=(work,{})) as prepare,patch.object(update_ui.subprocess,'Popen',side_effect=spawn) as launch:
            self.controller.notice.install_button.click()
            self.wait_for(lambda:self.pet.shutdown.called)
            self.pet.save_settings.assert_called_once();prepare.assert_called_once();launch.assert_called_once()
            self.assertEqual(json.loads((work/'job.json').read_text('utf8'))['root'],str(self.root))
            self.controller.notice.install_button.click();self.assertEqual(prepare.call_count,1)

    def test_update_preferences_survive_portable_migration(self):
        from shorekeeper_pet.config_io import export_bundle,import_bundle
        self.pet.options.update(check_updates_periodic=False,update_interval_hours=12,update_snoozed_date=date.today().isoformat())
        self.pet.set_option('show_quota',False);archive=self.root/'profile.zip'
        self.assertEqual(export_bundle(archive,self.pet.settings,self.root),[])
        restored=appearance(import_bundle(archive,self.root/'another computer'))
        for key in ('check_updates_periodic','update_interval_hours','update_snoozed_date','show_quota'):self.assertEqual(restored[key],self.pet.options[key])

if __name__=='__main__':unittest.main()
