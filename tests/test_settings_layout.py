"""Settings dialog layout and the wheel guard."""
import pathlib,tempfile,unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent,QPoint,QPointF,Qt
from PySide6.QtGui import QMouseEvent,QWheelEvent
from PySide6.QtWidgets import QAbstractSpinBox,QApplication,QComboBox,QPushButton,QScrollArea,QSlider
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.settings_layout import COMBO_WIDTH,SPIN_WIDTH


def wheel(widget,steps=-1):
    centre=QPointF(widget.width()/2,widget.height()/2)
    event=QWheelEvent(centre,QPointF(widget.mapToGlobal(centre.toPoint())),QPoint(0,0),QPoint(0,120*steps),
                      Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(widget,event)


class SettingsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();path=pathlib.Path(self.temp.name)/'settings.json'
        save_atomic(path,dict(appearance=dict(audio_muted=True)))
        self.patch=patch.object(module,'SETTINGS',path);self.patch.start()
        self.pet=module.Pet(offline=True);self.pet.timer.stop()
        self.pet.open_preferences('桌面与声音');self.d=self.pet.preferences;self.d.resize(980,500);self.app.processEvents()

    def tearDown(self):
        self.d.hide();self.d.deleteLater();self.pet.hide();self.patch.stop();self.temp.cleanup()

    def page(self):
        return self.d.tabs.currentWidget()

    def test_wheel_over_an_unselected_number_scrolls_the_page_instead(self):
        spin=self.d.controls['lock_button_size'];before=spin.value();bar=self.page().verticalScrollBar()
        self.assertTrue(bar.maximum()>0);bar.setValue(0);self.d.tabs.setFocus()
        wheel(spin,-1)
        self.assertEqual(spin.value(),before);self.assertGreater(bar.value(),0)

    def click(self,widget):
        local=QPointF(widget.width()/2,widget.height()/2);where=QPointF(widget.mapToGlobal(local.toPoint()))
        QApplication.sendEvent(widget,QMouseEvent(QEvent.Type.MouseButtonPress,local,where,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
        QApplication.sendEvent(widget,QMouseEvent(QEvent.Type.MouseButtonRelease,local,where,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier))

    def test_wheel_changes_a_number_after_it_is_clicked(self):
        spin=self.d.controls['lock_button_size'];spin.setValue(100);self.d.activateWindow();self.click(spin);spin.setFocus();self.app.processEvents()
        if not spin.hasFocus():self.skipTest('no keyboard focus on this platform')
        wheel(spin,1);self.assertNotEqual(spin.value(),100)

    def test_keyboard_focus_alone_does_not_let_the_wheel_change_a_value(self):
        combo=self.d.controls['turn_cost_style'];before=combo.currentIndex();self.d.activateWindow();combo.setFocus();self.app.processEvents()
        wheel(combo,-1);self.assertEqual(combo.currentIndex(),before)

    def test_window_opens_on_the_tab_bar(self):
        self.d.hide();self.pet.open_preferences();self.app.processEvents()
        focus=QApplication.focusWidget()
        if focus is not None:self.assertNotIsInstance(focus,(QAbstractSpinBox,QComboBox))

    def test_studio_gallery_stays_large_and_the_page_scrolls(self):
        self.d.select_page('交互工作室');self.app.processEvents()
        self.assertGreaterEqual(self.d.editor.gallery.height(),440);self.assertGreater(self.d.tabs.currentWidget().verticalScrollBar().maximum(),0)

    def test_wheel_over_an_unselected_choice_keeps_it(self):
        combo=self.d.controls['turn_cost_style'];before=combo.currentIndex();self.d.tabs.setFocus()
        wheel(combo,-1);self.assertEqual(combo.currentIndex(),before)

    def test_sliders_in_the_size_page_and_studio_are_guarded(self):
        self.d.select_page('字体与大小');self.app.processEvents();self.d.tabs.setFocus()
        slider=self.d.size_control.slider;before=slider.value();wheel(slider,-1);self.assertEqual(slider.value(),before)
        for slider in self.d.editor.findChildren(QSlider):
            before=slider.value();wheel(slider,-1);self.assertEqual(slider.value(),before)

    def test_short_controls_keep_a_compact_width(self):
        for key,control in self.d.controls.items():
            if isinstance(control,QAbstractSpinBox):self.assertLessEqual(control.maximumWidth(),SPIN_WIDTH[1],key)
            if isinstance(control,QComboBox):self.assertLessEqual(control.maximumWidth(),COMBO_WIDTH[1],key)

    def test_buttons_are_not_stretched_across_the_page(self):
        self.d.resize(1400,800)
        for index in range(self.d.tabs.count()):
            page=self.d.tabs.widget(index)
            if not isinstance(page,QScrollArea) or page.widget() is self.d.editor:continue
            self.d.tabs.setCurrentIndex(index);self.app.processEvents()
            for button in page.widget().findChildren(QPushButton):
                self.assertLess(button.width(),400,(self.d.tabs.tabText(index),button.text(),button.width()))

    def test_every_setting_is_on_a_page(self):
        for key,control in self.d.controls.items():
            self.assertIsNotNone(control.parentWidget(),key)
            self.assertIs(control.window(),self.d,key)


if __name__=='__main__':
    unittest.main()
