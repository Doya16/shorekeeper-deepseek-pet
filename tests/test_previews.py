"""Looping previews beside the cards on the size page and the desktop page."""
import pathlib,tempfile,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QScrollArea
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.previews import LOOPS,CardPreview
from shorekeeper_pet.settings_layout import Section

PAGES={'字体与大小':{'size','fonts','bubble'},'桌面与声音':{'finish','desk','rest','lock','sound'}}


def changed(a,b):
    return any(a.pixel(x,y)!=b.pixel(x,y) for x in range(0,a.width(),3) for y in range(0,a.height(),3))


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();path=pathlib.Path(self.temp.name)/'settings.json'
        save_atomic(path,dict(appearance=dict(audio_muted=True)))
        self.patch=patch.object(module,'SETTINGS',path);self.patch.start()
        self.pet=module.Pet(offline=True);self.pet.timer.stop();self.pet.slow_timer.stop()

    def tearDown(self):
        if self.pet.preferences:self.pet.preferences.hide();self.pet.preferences.deleteLater()
        self.pet.hide();self.patch.stop();self.temp.cleanup()

    def open(self,page):
        self.pet.open_preferences(page);self.app.processEvents();return self.pet.preferences

    def test_every_card_on_both_pages_has_a_preview(self):
        d=self.open('字体与大小')
        for title,modes in PAGES.items():
            d.select_page(title);self.app.processEvents();page=d.tabs.currentWidget()
            cards=page.widget().findChildren(Section)
            self.assertEqual({c.preview.mode for c in cards if c.preview is not None},modes,title)
            self.assertTrue(all(c.preview is not None for c in cards),title)

    def test_every_scene_draws_through_its_whole_loop(self):
        for mode,loop in LOOPS.items():
            view=CardPreview(self.pet,mode)
            for ms in range(0,loop,250):
                image=view.render_at(ms);self.assertFalse(image.isNull(),(mode,ms))

    def test_lock_preview_shows_the_windows_through_the_pet(self):
        view=CardPreview(self.pet,'lock');self.pet.set_option('locked_hover_transparency',0)
        solid=view.render_at(3000)
        self.pet.set_option('locked_hover_transparency',80);see_through=view.render_at(3000)
        self.assertTrue(changed(solid,see_through))
        self.assertFalse(changed(view.render_at(1000),view.render_at(1000)))

    def test_lock_button_follows_its_settings(self):
        view=CardPreview(self.pet,'lock');before=view.render_at(1000)
        self.pet.set_option('lock_button_size',200);self.assertTrue(changed(before,view.render_at(1000)))

    def test_completion_preview_follows_the_settings(self):
        view=CardPreview(self.pet,'finish');floating=view.render_at(2400)
        self.pet.set_option('turn_cost_style','off');self.assertTrue(changed(floating,view.render_at(2400)))
        self.pet.set_option('turn_cost_style','float');self.pet.set_option('turn_cost_font_size',60)
        self.assertTrue(changed(floating,view.render_at(2400)))

    def test_desk_preview_shows_full_screen_hiding_only_when_on(self):
        view=CardPreview(self.pet,'desk');self.pet.set_option('fullscreen_hide',False);off=view.render_at(12500)
        self.pet.set_option('fullscreen_hide',True);self.assertTrue(changed(off,view.render_at(12500)))

    def test_only_visible_previews_animate(self):
        d=self.open('字体与大小');d.show();self.app.processEvents()
        running={mode for mode,view in d.previews.items() if view.timer.isActive()}
        self.assertEqual(running,PAGES['字体与大小'])
        d.select_page('桌面与声音');self.app.processEvents()
        self.assertEqual({mode for mode,view in d.previews.items() if view.timer.isActive()},PAGES['桌面与声音'])
        d.hide();self.app.processEvents();self.assertFalse(any(view.timer.isActive() for view in d.previews.values()))

    def test_no_sideways_scrolling_at_the_default_size(self):
        d=self.open('字体与大小');d.show();self.app.processEvents()
        for index in range(d.tabs.count()):
            d.tabs.setCurrentIndex(index);self.app.processEvents();page=d.tabs.widget(index)
            if isinstance(page,QScrollArea):self.assertEqual(page.horizontalScrollBar().maximum(),0,d.tabs.tabText(index))


if __name__=='__main__':
    unittest.main()
