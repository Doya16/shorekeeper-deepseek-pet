"""Unified settings, actual mute, pointer locking and portable persistence."""
import copy,json,pathlib,shutil,tempfile,unittest,wave
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent,QWheelEvent,QEnterEvent
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
            self.assertIn('安静陪伴（静音）',labels);self.assertNotIn('锁定桌宠',labels);self.assertIn('关闭守岸人',labels);self.assertNotIn('退出守岸人',labels);self.assertFalse(any('回到当前' in x or x=='打开 DeepSeek Harness' for x in labels))
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
        self.assertTrue(p.lock_button.isChecked());p.lock_button.click()
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
        p.lock_button.click();self.assertFalse(p.locked)
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

    def test_direct_lock_clicks_toggle_without_drag_or_character_reaction(self):
        p=self.pet;button=p.lock_button;point=QPointF(button.rect().center())
        before=(p.pos(),p.controller.serial)
        for expected,tip in ((True,'点击解锁'),(False,'点击锁定')):
            self.mouse(button,QEvent.Type.MouseButtonPress,point)
            self.mouse(button,QEvent.Type.MouseButtonRelease,point)
            self.assertEqual(p.locked,expected);self.assertEqual(button.isChecked(),expected)
            self.assertEqual(button.toolTip(),tip)
            self.assertEqual((p.pos(),p.controller.serial),before)
            self.assertIsNone(p.drag_offset);self.assertFalse(p.click_timer.isActive())
        self.mouse(button,QEvent.Type.MouseButtonPress,point)
        outside=QPointF(button.width()+30,button.height()+30)
        self.mouse(button,QEvent.Type.MouseMove,outside)
        self.mouse(button,QEvent.Type.MouseButtonRelease,outside)
        self.assertFalse(p.locked);self.assertEqual(p.pos(),before[0])

    def test_lock_button_stays_centered_and_syncs_settings_and_hover(self):
        p=self.pet;button=p.lock_button
        for scale in (.5,1,1.5):
            p.set_scale(scale)
            self.assertAlmostEqual(button.x()+button.width()/2,p.pet_rect.center().x()*p.scale_factor,delta=1)
            self.assertEqual(button.y(),round(p.pet_rect.top()*p.scale_factor))
            self.assertTrue(p.rect().contains(button.geometry()))
        p.hover_timer.start(500);p.click_timer.start(500);serial=p.controller.serial
        point=QPointF(button.rect().center())
        QApplication.sendEvent(button,QEnterEvent(point,point,QPointF(button.mapToGlobal(point.toPoint()))))
        self.assertFalse(p.hover_timer.isActive());self.assertFalse(p.click_timer.isActive())
        self.assertEqual(p.controller.serial,serial)
        p.open_preferences('桌面与声音')
        p.preferences.controls['interaction_locked'].setChecked(True)
        self.assertTrue(button.isChecked());self.assertEqual(button.toolTip(),'点击解锁')
        button.click();self.assertFalse(p.preferences.controls['interaction_locked'].isChecked())

    def test_lock_transparency_changes_pixels_and_survives_export(self):
        p=self.pet;p.open_preferences('桌面与声音');spin=p.preferences.controls['lock_button_transparency']
        spin.setValue(0);solid=p.lock_button.grab().toImage()
        spin.setValue(80);faint=p.lock_button.grab().toImage()
        solid_alpha=sum(solid.pixelColor(x,y).alpha() for y in range(solid.height()) for x in range(solid.width()))
        faint_alpha=sum(faint.pixelColor(x,y).alpha() for y in range(faint.height()) for x in range(faint.width()))
        self.assertGreater(solid_alpha,faint_alpha*3)
        p.preferences.controls['lock_button_size'].setValue(135)
        cfg=module.load_settings();self.assertEqual(cfg['appearance']['lock_button_transparency'],80)
        archive=self.root.parent/'lock.zip';self.assertEqual(export_bundle(archive,cfg,self.root),[])
        restored=import_bundle(archive,self.root.parent/'换电脑')
        self.assertEqual(restored['appearance']['lock_button_transparency'],80)
        self.assertEqual(restored['appearance']['lock_button_size'],135)

    def test_hover_reveals_lock_even_when_locked_and_size_scales_proportionally(self):
        p=self.pet;b=p.lock_button
        with patch('shorekeeper_pet.lock_button.QCursor.pos',return_value=QPoint(-3000,-3000)) as cursor:
            for locked in (False,True):
                p.set_option('interaction_locked',locked)
                cursor.return_value=p.mapToGlobal(QPoint(-30,-30));b.refresh_visibility();self.assertFalse(b.isVisible())
                cursor.return_value=p.mapToGlobal((p.pet_rect.center()*p.scale_factor).toPoint());b.refresh_visibility();self.assertTrue(b.isVisible())
                cursor.return_value=p.mapToGlobal(b.geometry().center());b.refresh_visibility();self.assertTrue(b.isVisible())
                cursor.return_value=p.mapToGlobal(p.quota_hit_rect().center().toPoint());b.refresh_visibility();self.assertFalse(b.isVisible())
            p.set_scale(1);p.set_option('lock_button_size',75);small=b.width()
            p.set_option('lock_button_size',150);self.assertAlmostEqual(b.width(),small*2,delta=1)
            one=b.width();p.set_scale(1.5);self.assertAlmostEqual(b.width(),one*1.5,delta=1)
            self.assertAlmostEqual(b.x()+b.width()/2,p.pet_rect.center().x()*p.scale_factor,delta=1)

    def test_quota_click_refreshes_when_unlocked_or_locked_without_character_reaction(self):
        p=self.pet
        with patch.object(p,'refresh_quota') as refresh:
            for locked in (False,True):
                p.set_option('interaction_locked',locked)
                point=p.quota_hit_rect().center();serial=p.controller.serial
                self.mouse(p,QEvent.Type.MouseButtonPress,point)
                self.mouse(p,QEvent.Type.MouseButtonRelease,point)
                self.assertEqual(p.controller.serial,serial)
                self.assertFalse(p.click_timer.isActive())
            self.assertEqual(refresh.call_count,2)

    def test_quota_resize_drag_out_and_drag_back_never_refresh(self):
        p=self.pet
        with patch.object(p,'refresh_quota') as refresh:
            rect=p.quota_hit_rect();edge=QPointF(rect.right(),rect.center().y())
            self.mouse(p,QEvent.Type.MouseButtonPress,edge)
            self.mouse(p,QEvent.Type.MouseMove,edge+QPointF(35,0))
            self.mouse(p,QEvent.Type.MouseButtonRelease,edge+QPointF(35,0))
            self.assertNotEqual(p.options['quota_scale'],1)
            for locked in (False,True):
                p.set_option('interaction_locked',locked)
                point=p.quota_hit_rect().center()
                self.mouse(p,QEvent.Type.MouseButtonPress,point)
                self.mouse(p,QEvent.Type.MouseMove,point+QPointF(80,80))
                self.mouse(p,QEvent.Type.MouseMove,point)
                self.mouse(p,QEvent.Type.MouseButtonRelease,point)
                self.mouse(p,QEvent.Type.MouseButtonPress,point)
                self.mouse(p,QEvent.Type.MouseButtonRelease,point+QPointF(0,-80))
            refresh.assert_not_called()

    def test_locked_hover_fades_only_avatar_and_retains_control_targets(self):
        p=self.pet;p.transition_old=None;p.set_option('interaction_locked',True)
        with patch('shorekeeper_pet.pointer_mode.QCursor.pos') as cursor:
            cursor.return_value=p.mapToGlobal(QPoint(-40,-40))
            p.lock_button.refresh_visibility();p.pointer_mode.refresh();solid=p.grab().toImage()
            self.assertEqual(p.pointer_mode.avatar_opacity,1);self.assertTrue(p.pointer_mode.passthrough)
            cursor.return_value=p.mapToGlobal((p.pet_rect.center()*p.scale_factor).toPoint())
            p.lock_button.refresh_visibility();p.pointer_mode.refresh();faint=p.grab().toImage()
            self.assertAlmostEqual(p.pointer_mode.avatar_opacity,.3);self.assertTrue(p.pointer_mode.passthrough)
            # Alpha is reduced in the character, without fading the balance box.
            def alpha(image,rect):
                ratio=image.devicePixelRatio();r=rect.toAlignedRect()
                return sum(image.pixelColor(round(x*ratio),round(y*ratio)).alpha() for y in range(r.top(),r.bottom()) for x in range(r.left(),r.right()))
            body=p.quota_hit_rect().translated(0,-p.pet_rect.height()*p.scale_factor/2)
            self.assertGreater(alpha(solid,body),alpha(faint,body)*2)
            self.assertEqual(alpha(solid,p.quota_hit_rect()),alpha(faint,p.quota_hit_rect()))
            for point in (p.lock_button.geometry().center(),p.quota_hit_rect().center().toPoint()):
                cursor.return_value=p.mapToGlobal(point);p.pointer_mode.refresh();self.assertFalse(p.pointer_mode.passthrough)
            p.set_option('interaction_locked',False);p.pointer_mode.refresh()
            self.assertEqual(p.pointer_mode.avatar_opacity,1);self.assertFalse(p.pointer_mode.passthrough)

    def test_hover_transparency_setting_saved_and_exported_without_media_changes(self):
        p=self.pet;p.open_preferences('桌面与声音');p.preferences.controls['locked_hover_transparency'].setValue(85)
        cfg=module.load_settings();self.assertEqual(cfg['appearance']['locked_hover_transparency'],85)
        archive=self.root.parent/'faded.zip';self.assertEqual(export_bundle(archive,cfg,self.root),[])
        restored=import_bundle(archive,self.root.parent/'另一台电脑')
        self.assertEqual(restored['appearance']['locked_hover_transparency'],85)
        self.assertEqual(restored['bindings'],cfg['bindings'])
        from shorekeeper_pet.appearance import appearance
        self.assertEqual(appearance({})['locked_hover_transparency'],70)
        self.assertEqual(appearance({'appearance':{'locked_hover_transparency':float('nan')}})['locked_hover_transparency'],70)
        self.assertEqual(appearance({'appearance':{'locked_hover_transparency':120}})['locked_hover_transparency'],95)

    def test_tooltip_is_refreshed_when_displayed(self):
        p=self.pet
        from PySide6.QtGui import QHelpEvent
        point=p.quota_hit_rect().center().toPoint()
        with patch.object(p,'quota_details',return_value='下次刷新：2026/11/02 22:35（1小时2分钟后）'):
            QApplication.sendEvent(p,QHelpEvent(QEvent.Type.ToolTip,point,p.mapToGlobal(point)))
        self.assertIn('1小时2分钟后',p.toolTip())

    def test_icon_choice_applies_immediately_and_survives_export_import(self):
        from shorekeeper_pet.paths import ROOT as actual_root
        shutil.copytree(actual_root/'resources',self.root/'resources')
        shutil.copy2(actual_root/'assets/shorekeeper.ico',self.root/'assets/shorekeeper.ico')
        p=self.pet;p.open_preferences('桌面与声音');control=p.preferences.controls['tray_icon_style']
        control.setCurrentIndex(control.findData('clean'));clean=p.tray.icon().pixmap(32,32).toImage()
        control.setCurrentIndex(control.findData('badged'));badged=p.tray.icon().pixmap(32,32).toImage()
        self.assertNotEqual(clean,badged)
        for icon in (p.icon,p.windowIcon(),p.preferences.windowIcon(),self.app.windowIcon()):self.assertEqual(icon.pixmap(32,32).toImage(),badged)
        control.setCurrentIndex(control.findData('clean'))
        cfg=module.load_settings();archive=self.root.parent/'icons.zip';self.assertEqual(export_bundle(archive,cfg,self.root),[])
        restored=import_bundle(archive,self.root.parent/'图标迁移')
        self.assertEqual(restored['appearance']['tray_icon_style'],'clean')
        p.set_option('tray_icon_style','badged');p.apply_settings(restored)
        self.assertEqual(p.tray.icon().pixmap(32,32).toImage(),clean)
        self.assertIn('创建桌面快捷方式',[b.text() for b in p.preferences.buttons])

    def test_legacy_quiet_migrates_and_explicit_new_preference_wins(self):
        self.assertTrue(migrate_settings({'quiet':True})['appearance']['audio_muted'])
        self.assertFalse(migrate_settings({'quiet':True,'appearance':{'audio_muted':False}})['appearance']['audio_muted'])
        self.assertFalse(migrate_settings({})['appearance']['interaction_locked'])


if __name__=='__main__':unittest.main()
