"""Unified settings, actual mute, pointer locking and portable persistence."""
import copy,json,pathlib,shutil,tempfile,unittest,wave
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent,QWheelEvent
from PySide6.QtWidgets import QApplication,QPushButton
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic,migrate_settings,export_bundle,import_bundle


class SettingsControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name)/'原电脑'; self.root.mkdir()
        asset=module.CATALOG[0]; self.aid=asset['id']; target=self.root/asset['path']; target.parent.mkdir(parents=True)
        shutil.copy2(module.ROOT/asset['path'],target)
        (self.root/'audio').mkdir()
        with wave.open(str(self.root/'audio/voice.wav'),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*16000)
        self.patches=[patch.object(module,'ROOT',self.root),patch.object(module,'SETTINGS',self.root/'settings.json')]
        for p in self.patches:p.start()
        cfg={'schema_version':7,'appearance':{'audio_enabled':False,'volume':63},'bindings':{s:{'asset':self.aid,'audio_clips':[{'file':'voice.wav','bubble_text':'配对台词'}],'bubble_mode':'custom','bubble_text':'自己的气泡','bubble_seconds':0,'audio_delay':20,'audio_policy':'entry'} for s in module.STATES}}
        save_atomic(module.SETTINGS,cfg)
        self.pet=module.Pet(offline=True);self.pet.timer.stop();self.pet.hover_timer.stop();self.pet.click_timer.stop()
        self.pet.show(); self.pet.update_layout()
        refresh=patch.object(self.pet,'refresh_assets',return_value=[]);refresh.start();self.patches.append(refresh)

    def tearDown(self):
        self.pet.timer.stop();self.pet.hover_timer.stop();self.pet.click_timer.stop();self.pet.voice.stop()
        if self.pet.preferences:self.pet.preferences.hide();self.pet.preferences.deleteLater()
        self.pet.hide();self.pet.deleteLater();self.app.processEvents()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def mouse(self,widget,kind,local,global_pos=None,button=Qt.MouseButton.LeftButton):
        global_pos=global_pos or widget.mapToGlobal(local.toPoint())
        event=QMouseEvent(kind,local,QPointF(global_pos),button,button,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget,event)

    def test_one_settings_window_contains_every_entry_and_update_check(self):
        p=self.pet
        for menu in (p.context_menu(),p.tray.contextMenu()):
            labels=[a.text() for a in menu.actions()]
            self.assertEqual(labels.count('设置…'),1)
            self.assertFalse(any(s in labels for s in ('调整大小…','交互工作室','外观、声音与迁移','检查更新…','陪伴面板')))
            self.assertIn('安静陪伴（静音）',labels);self.assertIn('锁定桌宠',labels)
        p.open_bindings();window=p.preferences
        self.assertIs(p.binding_editor.window(),window);self.assertFalse(p.binding_editor.isWindow())
        self.assertEqual(window.tabs.currentWidget(),p.binding_editor)
        p.open_size();self.assertIs(p.preferences,window);self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()),'字体与大小')
        p.open_panel();self.assertIs(p.preferences,window);self.assertIsNone(p.panel);self.assertIsNone(p.size_dialog)
        with patch.object(p.updates,'check') as check:
            next(b for b in window.findChildren(QPushButton) if b.text()=='立即检查更新').click()
            check.assert_called_once_with(True)
        window.controls['interaction_locked'].setChecked(True)
        p.tray.contextMenu().aboutToShow.emit()
        action=next(a for a in p.tray.contextMenu().actions() if a.text()=='锁定桌宠')
        self.assertTrue(action.isChecked());action.trigger()
        self.assertFalse(p.locked);self.assertFalse(window.controls['interaction_locked'].isChecked())

    def test_mute_cancels_current_delay_queue_and_late_decode_without_losing_volume(self):
        p=self.pet;p.set_option('audio_enabled',True);voice=p.voice
        self.assertTrue(voice.trigger('pet',p.binding('pet'),p.options))
        generation=voice.generation
        voice.trigger('feed',p.binding('feed'),p.options);self.assertIsNotNone(voice.queued)
        p.set_option('audio_muted',True)
        self.assertFalse(voice.busy);self.assertFalse(voice.pending.isActive());self.assertIsNone(voice.queued)
        with patch.object(voice.player,'play') as play:
            voice._prepared(generation,str(self.root/'audio/voice.wav'),'');play.assert_not_called()
        self.assertFalse(voice.trigger('done',p.binding('done'),p.options))
        self.assertFalse(voice.trigger('pet',p.binding('pet'),p.options,preview=True))
        self.assertEqual(p.options['volume'],63);self.assertTrue(p.options['audio_enabled'])
        self.assertTrue(p.bubble_visible())
        p.set_option('audio_muted',False)
        self.assertFalse(voice.busy)
        self.assertTrue(voice.trigger('pet',p.binding('pet'),p.options,preview=True));self.assertEqual(p.options['volume'],63)

    def test_lock_blocks_pointer_interactions_and_keeps_task_events_and_unlock(self):
        p=self.pet;p.click_timer.start(50);p.hover_timer.start(50);p.set_option('interaction_locked',True)
        self.assertFalse(p.click_timer.isActive());self.assertFalse(p.hover_timer.isActive())
        before=(p.pos(),p.requested_scale,p.options['quota_scale'],p.options['bubble_width_ratio'],p.controller.serial)
        point=p.pet_rect.center()*p.scale_factor
        for kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseMove,QEvent.Type.MouseButtonRelease,QEvent.Type.MouseButtonDblClick):
            self.mouse(p,kind,point,p.mapToGlobal(point.toPoint())+QPoint(100,40))
        for widget,rect in ((p,p.quota_hit_rect()),(p.bubble_window,p.bubble_window.hit_rect())):
            edge=QPointF(rect.right(),rect.center().y())
            self.mouse(widget,QEvent.Type.MouseButtonPress,edge)
            self.mouse(widget,QEvent.Type.MouseMove,edge+QPointF(100,0))
            self.mouse(widget,QEvent.Type.MouseButtonRelease,edge+QPointF(100,0))
        wheel=QWheelEvent(point,QPointF(p.mapToGlobal(point.toPoint())),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.ControlModifier,Qt.ScrollPhase.NoScrollPhase,False)
        QApplication.sendEvent(p,wheel);p.hover_react();p.react('feed')
        self.assertEqual(before,(p.pos(),p.requested_scale,p.options['quota_scale'],p.options['bubble_width_ratio'],p.controller.serial))
        self.assertIsNone(p.drag_offset);self.assertFalse(p.click_timer.isActive())
        p.on_status({'state':'writing','thread_id':'test','turn_id':'turn','message':'示例编辑','active':True,'events':[]});self.assertEqual(p.state,'writing')
        p.on_status({'state':'writing','thread_id':'test','turn_id':'turn','active':True,'events':[{'state':'done','thread_id':'other','turn_id':'other','message':'示例完成'}]});self.assertEqual(p.state,'done')
        action=next(a for a in p.context_menu().actions() if a.text()=='锁定桌宠');action.trigger();self.assertFalse(p.locked)
        p.react('pet');self.assertEqual(p.state,'pet')

    def test_import_restart_and_repeat_export_preserve_options_and_all_media(self):
        p=self.pet;p.set_option('audio_muted',True);p.set_option('interaction_locked',True);p.save_settings()
        cfg=module.load_settings();self.assertTrue(cfg['appearance']['audio_muted']);self.assertTrue(cfg['appearance']['interaction_locked'])
        # Include a font and unused image/audio as well as the bound pair.
        (self.root/'fonts').mkdir();(self.root/'fonts/test.otf').write_bytes(b'font-test')
        original=copy.deepcopy(cfg);source=self.root
        for n in range(2):
            archive=self.root.parent/f'profile-{n}.zip';self.assertEqual(export_bundle(archive,cfg,source),[])
            source=self.root.parent/f'另一台电脑 {n}';cfg=import_bundle(archive,source)
            self.assertEqual(cfg['appearance'],original['appearance']);self.assertEqual(cfg['bindings'],original['bindings'])
            for name in ['audio/voice.wav','fonts/test.otf',module.ASSETS[self.aid]['path']]:self.assertEqual((source/name).read_bytes(),(self.root/name).read_bytes())
        with patch.object(p,'refresh_assets',return_value=[]): p.apply_settings(cfg)
        self.assertTrue(p.locked);self.assertTrue(p.options['audio_muted'])

    def test_legacy_quiet_migrates_and_explicit_new_preference_wins(self):
        self.assertTrue(migrate_settings({'quiet':True})['appearance']['audio_muted'])
        self.assertFalse(migrate_settings({'quiet':True,'appearance':{'audio_muted':False}})['appearance']['audio_muted'])
        self.assertFalse(migrate_settings({})['appearance']['interaction_locked'])


if __name__=='__main__':unittest.main()
