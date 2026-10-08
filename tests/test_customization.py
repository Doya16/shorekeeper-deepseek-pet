import json,pathlib,tempfile,unittest,zipfile
from shorekeeper_pet.paths import EXECUTABLE_NAME,PORTABLE_DIRNAME
from shorekeeper_pet.bindings import BindingMap,PlaybackController
from shorekeeper_pet.audio_player import resolve_audio
from shorekeeper_pet.config_io import export_bundle,import_bundle,save_atomic,migrate_settings

class TimelineTests(unittest.TestCase):
    def setUp(self):
        states={'idle':'gif','thinking':'gif','done':'gif','pet':'gif','working':'gif'}
        self.bindings=BindingMap({'a':states},['gif'],{'pet','done'})
        self.resolve=lambda state:self.bindings.resolve('a',state)
        self.p=PlaybackController(self.resolve,lambda aid:(1200,2200))
    def test_speed_hold_and_no_retrigger(self):
        self.bindings.set('done',speed=2,hold_seconds=1)
        self.p.set_live('done','done-key',0)
        self.p.tick(1.59); self.assertEqual(self.p.state,'done')
        self.p.tick(1.6); self.assertEqual(self.p.state,'idle')
        self.p.set_live('done','done-key',2); self.assertEqual(self.p.state,'idle')
    def test_loop_duration_and_pending_live_state(self):
        self.p.set_live('thinking','one',0)
        self.bindings.set('pet',playback='loop',loop_seconds=3)
        self.p.enter('pet',1)
        self.p.set_live('working','two',2); self.assertEqual(self.p.state,'pet')
        self.p.tick(3.99); self.assertEqual(self.p.state,'pet')
        self.p.tick(4); self.assertEqual(self.p.state,'working')
    def test_indefinite_loop_and_explicit_resume(self):
        self.bindings.set('pet',playback='loop',loop_seconds=0)
        self.p.enter('pet',1); self.p.tick(99999); self.assertEqual(self.p.state,'pet')
        self.p.resume(100000); self.assertEqual(self.p.state,'idle')
    def test_next_state_and_hold(self):
        self.bindings.set('pet',hold_seconds=0,next_state='thinking')
        self.p.enter('pet',0); self.p.tick(1.2); self.assertEqual(self.p.state,'thinking')
        self.bindings.set('done',next_state='hold'); self.p.enter('done',2); self.p.tick(1000); self.assertEqual(self.p.state,'done')
    def test_interruptible_respected_for_live_state(self):
        self.p.set_live('done','one',0); self.p.set_live('working','two',1); self.assertEqual(self.p.state,'done')
        self.p.tick(3.2); self.assertEqual(self.p.state,'working')
        self.bindings.set('pet',interruptible=True); self.p.enter('pet',4); self.p.set_live('thinking','three',5); self.assertEqual(self.p.state,'thinking')
    def test_settings_validation_preserves_old_bindings(self):
        restored=BindingMap(self.bindings.defaults,['gif'],{'pet'},{'pet':{'asset':'gif','speed':float('nan'),'hold_seconds':-10,'audio_file':''}})
        self.assertEqual(restored.resolve('a','pet')['speed'],1)
        self.assertEqual(restored.resolve('a','pet')['hold_seconds'],0)
        self.assertEqual(restored.resolve('a','pet')['audio_file'],'')

class TransferTests(unittest.TestCase):
    def test_codex_media_import_does_not_enable_codex_startup_or_copy_its_paths(self):
        cfg=migrate_settings({'appearance':{'codex_home':'private','codex_executable':'private.exe','launch_with_codex':True,'volume':32},'bindings':{'pet':{'bubble_mode':'custom','bubble_text':'你好'}}})
        self.assertNotIn('codex_home',cfg['appearance'])
        self.assertNotIn('launch_with_codex',cfg['appearance'])
        self.assertEqual(cfg['appearance']['volume'],32)
        self.assertEqual(cfg['bindings']['pet']['bubble_text'],'你好')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name)/'origin'; self.root.mkdir()
        for directory in ('assets/originals','fonts','audio'): (self.root/directory).mkdir(parents=True)
        (self.root/'assets/originals/a.gif').write_bytes(b'GIF89a')
        (self.root/'fonts/font.ttf').write_bytes(b'font')
        (self.root/'audio/notice.wav').write_bytes(b'RIFF test data')
        self.settings={'thread':'private-local-id','appearance':{'audio_directory':str(self.root/'audio'),'deepseek_home':'local-account-path'},'bindings':{'pet':{'audio_file':'notice.wav','speed':.5}}}
    def tearDown(self): self.tmp.cleanup()
    def test_roundtrip_embeds_audio_and_fonts(self):
        dest=self.root.parent/'profile.zip'; export_bundle(dest,self.settings,self.root)
        target=self.root.parent/'restored'; restored=import_bundle(dest,target)
        self.assertEqual(restored['bindings']['pet']['speed'],.5)
        audio=resolve_audio(restored['bindings']['pet']['audio_file'],restored['appearance']['audio_directory'],target)
        self.assertIsNotNone(audio); self.assertEqual(audio.read_bytes(),b'RIFF test data')
        self.assertTrue((target/'fonts/font.ttf').exists())
    def test_portable_resets_machine_connection_and_excludes_private_files(self):
        runtime=self.root/'dist'/PORTABLE_DIRNAME; (runtime/'_internal').mkdir(parents=True); (runtime/EXECUTABLE_NAME).write_bytes(b'MZtest'); (runtime/'_internal/core.dll').write_bytes(b'core')
        (self.root/'auth.json').write_text('secret'); (self.root/'runtime.json').write_text('private')
        dest=self.root.parent/'portable.zip'; export_bundle(dest,self.settings,self.root,True)
        with zipfile.ZipFile(dest) as z:
            names=z.namelist(); cfg=json.loads(z.read('settings.json'))
            self.assertNotIn('auth.json',names); self.assertNotIn('runtime.json',names); self.assertIn(EXECUTABLE_NAME,names)
            self.assertEqual(cfg['thread'],'auto'); self.assertEqual(cfg['appearance']['deepseek_home'],'')
    def test_path_traversal_is_rejected_before_writes(self):
        dest=self.root.parent/'bad.zip'
        with zipfile.ZipFile(dest,'w') as z: z.writestr('../escape','bad')
        with self.assertRaises(ValueError): import_bundle(dest,self.root.parent/'target')
        self.assertFalse((self.root.parent/'escape').exists())
    def test_empty_missing_audio_is_optional(self):
        self.assertIsNone(resolve_audio('','audio',self.root)); self.assertIsNone(resolve_audio('missing.mp3','audio',self.root))
        self.settings['bindings']['pet']['audio_file']='missing.wav'
        warnings=export_bundle(self.root.parent/'missing.zip',self.settings,self.root)
        self.assertEqual(len(warnings),1)
    def test_atomic_save_keeps_previous_snapshot(self):
        path=self.root/'settings.json'; save_atomic(path,{'x':1}); save_atomic(path,{'x':2})
        self.assertEqual(json.loads(path.read_text())['x'],2); self.assertEqual(json.loads(path.with_suffix('.json.bak').read_text())['x'],1)

    def test_unused_library_audio_and_text_survive_reexport(self):
        (self.root/'audio/unused.ogg').write_bytes(b'OggS unused')
        (self.root/'audio/unused.txt').write_text('尚未绑定的台词',encoding='utf8')
        (self.root/'audio/unrelated.json').write_text('{"private":"omit"}')
        archive=self.root.parent/'all-audio.zip'; export_bundle(archive,self.settings,self.root)
        target=self.root.parent/'next'; restored=import_bundle(archive,target)
        self.assertEqual((target/'audio/unused.ogg').read_bytes(),b'OggS unused')
        self.assertEqual((target/'audio/unused.txt').read_text('utf8'),'尚未绑定的台词')
        self.assertFalse((target/'audio/unrelated.json').exists())
        second=self.root.parent/'again.zip'; export_bundle(second,restored,target)
        with zipfile.ZipFile(archive) as a,zipfile.ZipFile(second) as b:
            self.assertEqual(sorted(n for n in a.namelist() if n.startswith('audio/')),sorted(n for n in b.namelist() if n.startswith('audio/')))

    def test_remove_quota_binding_without_touching_other_customization(self):
        original={'bindings':{'quota':{'asset':'old'},'pet':{'next_state':'quota','bubble_text':'保留','speed':.7}}}
        updated=migrate_settings(original)
        self.assertEqual(updated['bindings'],{'pet':{'next_state':'auto','bubble_text':'保留','speed':.7}})
        self.assertIn('quota',original['bindings'])

if __name__=='__main__': unittest.main()
