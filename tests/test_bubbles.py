"""Behavioral checks for narrow bubbles, exclusive captions and saved profiles."""
import copy,json,pathlib,shutil,tempfile,time,unittest,wave
from unittest.mock import patch
from PySide6.QtCore import QRect,Qt,QPointF,QEvent
from PySide6.QtGui import QFontMetrics,QFontDatabase,QMouseEvent
from PySide6.QtWidgets import QApplication
from shorekeeper_pet import pet as module
from shorekeeper_pet.renderer import wrap_text
from shorekeeper_pet.config_io import migrate_settings,save_atomic,export_bundle,import_bundle
from shorekeeper_pet.voice_pool import clean_clips


class BubbleMigrationTests(unittest.TestCase):
    def test_legacy_pairs_migrate_but_explicit_modes_survive_later_restarts(self):
        pair={'audio_clips':[{'file':'voice.wav','subtitle':'配对字幕'}],'bubble_text':'旧台词','bubble_mode':'custom'}
        source={'schema_version':6,'bindings':{'pet':pair,'idle':dict(pair,bubble_mode='off'),'feed':dict(pair,audio_subtitles=False)}}
        cfg=migrate_settings(source)
        self.assertEqual(cfg['bindings']['pet']['bubble_mode'],'audio')
        self.assertEqual(cfg['bindings']['pet']['bubble_text'],'旧台词')
        self.assertEqual(cfg['bindings']['idle']['bubble_mode'],'off')
        self.assertEqual(cfg['bindings']['feed']['bubble_mode'],'custom')
        cfg['bindings']['pet']['bubble_mode']='custom'
        self.assertEqual(migrate_settings(cfg),cfg)
        self.assertEqual(source['bindings']['pet']['bubble_mode'],'custom')


class BubbleWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name)/'original'; self.root.mkdir()
        self.original_root=module.ROOT; self.original_settings=module.SETTINGS
        asset=module.CATALOG[0]; self.aid=asset['id']
        target=self.root/asset['path']; target.parent.mkdir(parents=True); shutil.copy2(module.ROOT/asset['path'],target)
        (self.root/'audio').mkdir()
        with wave.open(str(self.root/'audio/voice.wav'),'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(8000); out.writeframes(b'\0\0'*8000)
        cfg={'schema_version':7,'appearance':{'audio_enabled':False},'bindings':{s:{'asset':self.aid,'audio_clips':[],'bubble_mode':'custom','bubble_text':'测试台词','bubble_seconds':0} for s in module.STATES}}
        module.ROOT=self.root; module.SETTINGS=self.root/'settings.json'; save_atomic(module.SETTINGS,cfg)
        self.pet=module.Pet(offline=True); self.pet.timer.stop(); self.pet.hover_timer.stop(); self.pet.click_timer.stop()
        self.pet.screen_area=lambda:QRect(-1280,0,1280,900)
        self.pet.show(); self.pet.update_layout()

    def tearDown(self):
        self.pet.voice.stop(); self.pet.hide(); self.pet.bubble_window.hide()
        for dialog in (self.pet.binding_editor,self.pet.preferences,self.pet.size_dialog):
            if dialog:
                if hasattr(dialog,'timer'): dialog.timer.stop()
                dialog.hide(); dialog.deleteLater()
        self.pet.deleteLater(); self.app.processEvents()
        module.ROOT=self.original_root; module.SETTINGS=self.original_settings
        QFontDatabase.removeAllApplicationFonts(); self.temp.cleanup()

    def test_horizontal_edges_follow_character_at_all_sizes_and_screen_edges(self):
        p=self.pet
        for size in (140,230,420):
            p.options['pet_size']=size
            for scale in (.5,.85,1,1.333,2):
                p.set_scale(scale)
                for x in (-1280,-900,-p.width()):
                    p.move(x,500); p.clamp_position(); p.update_bubble()
                    left=p.x()+p.pet_rect.left()*p.scale_factor
                    right=p.x()+p.pet_rect.right()*p.scale_factor
                    self.assertGreaterEqual(p.bubble_window.x(),left)
                    self.assertLessEqual(p.bubble_window.x()+p.bubble_window.width(),right)
                    self.assertLess(right-left-p.bubble_window.width(),2.01)

    def test_long_text_wraps_without_line_or_character_truncation_or_font_shrink(self):
        p=self.pet; text='这是完整的长台词。'*650+'结束标记'
        p.set_binding('idle',bubble_text=text)
        self.assertEqual(''.join(p.bubble_lines),text)
        self.assertGreater(len(p.bubble_lines),8)
        self.assertEqual(p.bubble_scale,p.scale_factor)
        self.assertGreater(p.bubble_window.height(),p.screen_area().height())
        metrics=QFontMetrics(p.bubble_font)
        self.assertTrue(all(metrics.horizontalAdvance(line)<=p.bubble_width-52 for line in p.bubble_lines))
        self.assertEqual(wrap_text('甲\n\n乙\n',metrics,500),['甲','','乙',''])
        self.assertEqual(clean_clips([{'file':'voice.wav','subtitle':text,'bubble_text':text}])[0]['bubble_text'],text)
        self.assertTrue(p.save_settings())
        self.assertEqual(module.load_settings()['bindings']['idle']['bubble_text'],text)

    def pointer(self,widget,kind,global_point,button,buttons):
        local=QPointF(widget.mapFromGlobal(global_point.toPoint()))
        event=QMouseEvent(kind,local,global_point,button,buttons,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(widget,event)

    def drag_edge(self,widget,rect,side,dx):
        point=QPointF(rect.left()+3 if side<0 else rect.right()-3,rect.center().y())
        start=QPointF(widget.mapToGlobal(point.toPoint())); end=start+QPointF(dx,0)
        self.pointer(widget,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
        self.pointer(widget,QEvent.Type.MouseMove,end,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton)
        self.pointer(widget,QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)

    def test_both_edges_resize_bubble_and_quota_without_pet_interactions(self):
        p=self.pet; p.move(-800,400); p.set_scale(1)
        serial=p.controller.serial; state=p.state
        for side in (-1,1):
            p.set_presentation_size('bubble_width_ratio',1.5)
            self.drag_edge(p.bubble_window,p.bubble_window.hit_rect(),side,side*35)
            self.assertGreater(p.options['bubble_width_ratio'],1.5)
            self.assertEqual(module.load_settings()['appearance']['bubble_width_ratio'],p.options['bubble_width_ratio'])
            self.drag_edge(p.bubble_window,p.bubble_window.hit_rect(),side,-side*20)
            self.assertLess(p.options['bubble_width_ratio'],1.5+70/230)
            p.set_presentation_size('quota_scale',1)
            before=p.quota_rect.height(); self.drag_edge(p,p.quota_hit_rect(),side,side*25)
            self.assertGreater(p.options['quota_scale'],1); self.assertGreater(p.quota_rect.height(),before)
            self.assertEqual(module.load_settings()['appearance']['quota_scale'],p.options['quota_scale'])
            self.assertEqual(p.controller.serial,serial); self.assertEqual(p.state,state)
            self.assertIsNone(p.drag_offset); self.assertFalse(p.click_timer.isActive())

    def test_ratios_survive_zoom_screen_fitting_restart_and_transfer(self):
        p=self.pet; p.screen_area=lambda:QRect(0,0,3000,2000)
        p.set_presentation_size('bubble_width_ratio',2.15); p.set_presentation_size('quota_scale',1.6)
        for zoom in (.5,.85,1,1.5,2):
            p.set_scale(zoom)
            self.assertAlmostEqual(p.bubble_window.width(),p.options['pet_size']*2.15*p.scale_factor,delta=2)
            self.assertAlmostEqual(p.quota_rect.width()*p.scale_factor,p.quota_base_width*1.6*p.scale_factor)
            self.assertAlmostEqual(p.quota_rect.height()*p.scale_factor,p.quota_base_height*1.6*p.scale_factor)
        p.set_scale(1); base_width=p.quota_rect.width(); base_height=p.quota_rect.height()
        p.options['pet_size']=345; p.update_layout()
        self.assertAlmostEqual(p.quota_rect.width(),base_width*1.5)
        self.assertAlmostEqual(p.quota_rect.height(),base_height*1.5)
        p.options['pet_size']=230; p.update_layout()
        p.screen_area=lambda:QRect(-500,0,500,400); p.update_layout(); p.clamp_position(); p.update_bubble()
        self.assertLessEqual(p.bubble_window.width(),500); self.assertTrue(p.screen_area().contains(p.frameGeometry()))
        self.assertEqual(p.options['bubble_width_ratio'],2.15); self.assertEqual(p.options['quota_scale'],1.6)
        p.save_settings(); cfg=module.load_settings()
        from shorekeeper_pet.appearance import appearance
        self.assertEqual(appearance(cfg)['bubble_width_ratio'],2.15)
        self.assertEqual(appearance(cfg)['quota_scale'],1.6)
        archive=self.root.parent/'sizing.zip'; self.assertEqual(export_bundle(archive,cfg,self.root),[])
        restored=import_bundle(archive,self.root.parent/'another-pc')
        self.assertEqual(restored['appearance'],cfg['appearance'])
        self.assertEqual(restored['bindings'],cfg['bindings'])

    def test_preview_and_sliders_are_synced_without_playing_audio_or_changing_bindings(self):
        p=self.pet; before=copy.deepcopy(p.bindings.to_dict()); serial=p.controller.serial
        p.set_binding('idle',bubble_mode='off'); before=copy.deepcopy(p.bindings.to_dict())
        p.open_size(); control=p.preferences.presentation_control
        control.preview.setChecked(True)
        self.assertTrue(p.bubble_visible()); self.assertIn('预览',p.bubble_text()); self.assertFalse(p.voice.busy)
        control.controls['bubble_width_ratio'][0].setValue(175)
        control.controls['quota_scale'][1].setValue(135)
        self.assertEqual(control.controls['bubble_width_ratio'][1].value(),175)
        p.open_preferences(); other=p.preferences.presentation_control
        self.assertEqual(other.controls['quota_scale'][0].value(),135)
        p.set_presentation_size('bubble_width_ratio',1.9)
        self.assertEqual(control.controls['bubble_width_ratio'][1].value(),190)
        self.assertEqual(other.controls['bubble_width_ratio'][1].value(),190)
        p.preferences.hide(); self.assertFalse(p.presentation_previews); self.assertFalse(p.bubble_visible())
        self.assertEqual(p.bindings.to_dict(),before); self.assertEqual(p.controller.serial,serial)

    def test_bubble_does_not_disappear_mid_resize_when_audio_finishes(self):
        p=self.pet; p.set_binding('idle',bubble_mode='audio')
        p.voice.busy=True; p.voice.selected_state='idle'; p.voice.selected_clip={'subtitle':'播完前开始调整'}
        p.update_layout(); rect=p.bubble_window.hit_rect()
        start=QPointF(p.bubble_window.mapToGlobal(QPointF(rect.right()-3,rect.center().y()).toPoint()))
        self.pointer(p.bubble_window,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
        self.assertTrue(p.bubble_window.edge_resize.active)
        p.voice._finish()
        self.assertTrue(p.bubble_visible()); self.assertEqual(p.bubble_text(),'播完前开始调整')
        self.pointer(p.bubble_window,QEvent.Type.MouseButtonRelease,start,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
        self.assertFalse(p.bubble_visible())

    def test_paired_bubble_survives_gif_change_then_hides_without_generic_fallback(self):
        p=self.pet
        clips=[{'file':'voice.wav','subtitle':'只显示抽中的这句','enabled':True}]
        p.set_binding('thinking',bubble_mode='audio',bubble_text='不能出现的通用台词',audio_clips=clips,bubble_seconds=.01)
        p.set_binding('reading',bubble_mode='audio')
        self.assertTrue(p.voice.trigger('thinking',p.binding('thinking'),p.options,preview=True))
        p.voice.pending.stop()  # Exercise state lifetime without playing sound in tests.
        p.controller.enter('reading',time.monotonic()-60,'live'); p.tick()
        self.assertEqual(p.state,'reading'); self.assertEqual(p.bubble_state(),'thinking')
        self.assertTrue(p.bubble_visible()); self.assertEqual(p.bubble_text(),'只显示抽中的这句')
        p.voice._finish()
        self.assertFalse(p.bubble_visible()); self.assertEqual(p.bubble_text(),'')
        self.assertFalse(p.voice.busy)

    def test_empty_missing_disabled_audio_and_custom_mode_do_not_show_paired_text(self):
        p=self.pet
        p.set_binding('idle',bubble_mode='audio',bubble_text='不得回退',audio_clips=[{'file':'missing.wav','subtitle':'缺失文件'}])
        self.assertFalse(p.voice.trigger('idle',p.binding('idle'),p.options,preview=True))
        self.assertFalse(p.bubble_visible()); self.assertEqual(p.bubble_text(),'')
        p.set_binding('idle',audio_clips=[{'file':'voice.wav','subtitle':'原文','bubble_text':''}])
        p.voice.trigger('idle',p.binding('idle'),p.options,preview=True); p.voice.pending.stop()
        self.assertFalse(p.bubble_visible()); self.assertEqual(p.bubble_text(),'')
        p.voice.selected_clip['bubble_text']='配对文案'
        p.set_binding('idle',bubble_mode='custom',bubble_text='只使用我的台词')
        self.assertEqual(p.bubble_text(),'只使用我的台词'); self.assertFalse(p.voice_bubble())
        p.save_settings(); self.assertEqual(module.load_settings()['bindings']['idle']['bubble_mode'],'custom')
        p.set_binding('idle',bubble_mode='off'); self.assertFalse(p.bubble_visible())

    def test_mode_controls_and_long_pairs_survive_two_exports(self):
        p=self.pet
        # Restrict the test gallery to its fixture instead of loading all 83 GIFs.
        from shorekeeper_pet.studio import BindingEditor
        p.binding_editor=BindingEditor(p,[module.ASSETS[self.aid]],module.ASSETS,self.root)
        editor=p.binding_editor; combo=editor.controls['bubble_mode']
        self.assertGreaterEqual(combo.findText('自定义音频+字幕'),0)
        combo.setCurrentIndex(combo.findData('audio'))
        self.assertFalse(editor.controls['bubble_text'].isEnabled())
        self.assertFalse(editor.controls['bubble_seconds'].isEnabled())
        self.assertTrue(editor.controls['font_size'].isEnabled())
        text='长字幕'*1700
        p.set_binding('pet',audio_clips=[{'file':'voice.wav','subtitle':text,'bubble_text':text}],bubble_text='保留但不显示的台词')
        cfg=copy.deepcopy(p.settings); root=self.root
        for i in range(2):
            archive=self.root.parent/f'profile-{i}.zip'; self.assertEqual(export_bundle(archive,cfg,root),[])
            root=self.root.parent/f'新电脑-{i}'; cfg=import_bundle(archive,root)
            self.assertEqual(cfg['bindings']['pet']['bubble_mode'],'audio')
            self.assertEqual(cfg['bindings']['pet']['audio_clips'][0]['bubble_text'],text)
            self.assertEqual(cfg['bindings']['pet']['bubble_text'],'保留但不显示的台词')
            self.assertEqual((root/'audio/voice.wav').read_bytes(),(self.root/'audio/voice.wav').read_bytes())
            self.assertEqual((root/module.ASSETS[self.aid]['path']).read_bytes(),(self.root/module.ASSETS[self.aid]['path']).read_bytes())


if __name__=='__main__': unittest.main()
