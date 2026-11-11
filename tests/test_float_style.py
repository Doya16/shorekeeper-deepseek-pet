"""Bold, italic and colour for each floating-text line."""
import pathlib,tempfile,unittest
from unittest.mock import patch
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.cost_float import line_styles,render,text_size
from shorekeeper_pet.appearance import font,load_fonts
from shorekeeper_pet.paths import ROOT

LINES=[('-¥0.0731','cost'),('用时 4分12秒','time')]


def has_colour(image,colour,tolerance=24):
    target=QColor(colour)
    for x in range(0,image.width(),2):
        for y in range(0,image.height(),2):
            c=image.pixelColor(x,y)
            if c.alpha()>230 and abs(c.red()-target.red())<tolerance and abs(c.green()-target.green())<tolerance and abs(c.blue()-target.blue())<tolerance:return True
    return False


class StyleOptionTests(unittest.TestCase):
    def test_defaults_keep_the_current_look(self):
        o=module.appearance({})
        self.assertEqual((o['turn_cost_cost_color'],o['turn_cost_time_color']),('#e4572e','#2f6db5'))
        self.assertFalse(any(o[k] for k in ('turn_cost_cost_bold','turn_cost_cost_italic','turn_cost_time_bold','turn_cost_time_italic')))

    def test_bad_values_fall_back(self):
        o=module.appearance(dict(appearance=dict(turn_cost_cost_color='red',turn_cost_time_color='#12345g',turn_cost_cost_bold='yes')))
        self.assertEqual((o['turn_cost_cost_color'],o['turn_cost_time_color'],o['turn_cost_cost_bold']),('#e4572e','#2f6db5',False))
        self.assertEqual(module.appearance(dict(appearance=dict(turn_cost_time_color='#1D9E75')))['turn_cost_time_color'],'#1D9E75')


class StyleRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);load_fonts(ROOT)

    def styles(self,**changes):
        o=dict(module.appearance({}));o.update(changes);return line_styles(o)

    def test_colour_is_used_for_each_line(self):
        used=font('ZCOOL KuaiLe',40)
        image=render(used,LINES,0,1.,self.styles(turn_cost_cost_color='#8c2bd6',turn_cost_time_color='#1d9e75')).toImage()
        self.assertTrue(has_colour(image,'#8c2bd6'));self.assertTrue(has_colour(image,'#1d9e75'));self.assertFalse(has_colour(image,'#e4572e'))

    def test_bold_and_italic_change_the_glyphs(self):
        used=font('ZCOOL KuaiLe',40);plain=render(used,LINES,0,1.,self.styles()).toImage()
        for key in ('turn_cost_cost_bold','turn_cost_cost_italic','turn_cost_time_bold','turn_cost_time_italic'):
            styled=render(used,LINES,0,1.,self.styles(**{key:True})).toImage()
            self.assertTrue(styled.size()!=plain.size() or styled!=plain,key)

    def test_italic_leaves_room_for_the_slant(self):
        used=font('ZCOOL KuaiLe',40)
        self.assertGreater(text_size(used,LINES,0,self.styles(turn_cost_time_italic=True))[0],text_size(used,LINES,0,self.styles())[0]-1)


class StyleSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();path=pathlib.Path(self.temp.name)/'settings.json'
        save_atomic(path,dict(appearance=dict(audio_muted=True)))
        self.patch=patch.object(module,'SETTINGS',path);self.patch.start()
        self.pet=module.Pet(offline=True);self.pet.timer.stop();self.pet.slow_timer.stop()
        self.pet.open_preferences('桌面与声音');self.d=self.pet.preferences

    def tearDown(self):
        self.d.hide();self.d.deleteLater();self.pet.hide();self.patch.stop();self.temp.cleanup()

    def kinds(self):
        return ('cost','time') if module.appearance({})['turn_cost_order']!='time' else ('time',)

    def test_switches_save(self):
        for kind in self.kinds():
            for style in ('bold','italic'):
                self.d.controls[f'turn_cost_{kind}_{style}'].setChecked(True)
                self.assertTrue(module.appearance(module.load_settings())[f'turn_cost_{kind}_{style}'])

    def test_palette_choice_saves_and_shows_on_the_button(self):
        for kind in self.kinds():
            with patch('PySide6.QtWidgets.QColorDialog.getColor',return_value=QColor('#123456')):self.d.choose_line_color(kind)
            self.assertEqual(module.appearance(module.load_settings())[f'turn_cost_{kind}_color'],'#123456')
            self.assertIn('#123456',self.d.color_buttons[kind].text())
            self.d.set_line_color(kind,None)
            self.assertNotEqual(module.appearance(module.load_settings())[f'turn_cost_{kind}_color'],'#123456')

    def test_cancelled_palette_changes_nothing(self):
        kind=self.kinds()[-1];before=self.pet.options[f'turn_cost_{kind}_color']
        with patch('PySide6.QtWidgets.QColorDialog.getColor',return_value=QColor()):self.d.choose_line_color(kind)
        self.assertEqual(self.pet.options[f'turn_cost_{kind}_color'],before)

    def test_only_existing_lines_have_style_rows(self):
        self.assertEqual('turn_cost_cost_bold' in self.d.controls,'cost' in self.kinds())
        self.assertIn('turn_cost_time_bold',self.d.controls)

    def test_float_uses_the_chosen_style(self):
        self.pet.set_option('turn_cost_time_color','#1d9e75');self.pet.set_option('turn_cost_outline','none')
        self.pet.show();self.pet.cost_float.play([('用时 4分12秒','time')])
        self.assertTrue(has_colour(self.pet.cost_float.image.toImage(),'#1d9e75'))
        self.pet.cost_float.animation.stop();self.pet.cost_float.hide()


if __name__=='__main__':
    unittest.main()
