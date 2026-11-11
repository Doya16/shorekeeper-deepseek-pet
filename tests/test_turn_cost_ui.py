"""The floating text on a real pet: timing against the completion animation, screen edges and dragging."""
import pathlib,tempfile,time,unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent,QPoint,QPointF,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.cost_float import FADE_MS,HOLD_MS,OFFSET_LIMIT,RISE,RISE_MS,TOTAL_MS,clamp_offset,place,timeline


def quota(value,updated):
    return dict(windows=[],status='ready',error='',source='live',updated_at=updated,wallets=[dict(currency='CNY',balance=value,bonus=False)])


class PlaceTests(unittest.TestCase):
    AREA=(0,0,1919,1039);SIZE=(120,50)

    def test_default_position_sits_above_the_anchor(self):
        self.assertEqual(place((500,600),self.SIZE,(0,0),self.AREA,78,0),(440,550))

    def test_rise_moves_up_by_the_full_distance(self):
        self.assertEqual(place((500,600),self.SIZE,(0,0),self.AREA,78,1),(440,472))

    def test_every_edge_keeps_the_whole_text_on_screen(self):
        for anchor,offset in (((0,0),(-400,-400)),((1919,0),(400,-400)),((0,1039),(-400,400)),((1919,1039),(400,400))):
            for progress in (0,.5,1):
                x,y=place(anchor,self.SIZE,offset,self.AREA,78,progress)
                self.assertTrue(0<=x and x+120<=1920 and 0<=y and y+50<=1040,(anchor,offset,progress,x,y))

    def test_monitor_with_negative_coordinates(self):
        x,y=place((-1900,-900),self.SIZE,(-400,-400),(-1920,-1080,-1,-41),78,1)
        self.assertEqual((x,y),(-1920,-1080))

    def test_offset_is_limited(self):
        self.assertEqual(clamp_offset(9999,-9999),(OFFSET_LIMIT,-OFFSET_LIMIT))

    def test_rises_then_rests_about_four_seconds_then_fades(self):
        self.assertEqual(timeline(0),(0,0));self.assertLess(timeline(RISE_MS/2)[0],1)
        for ms in (RISE_MS,RISE_MS+HOLD_MS/2,RISE_MS+HOLD_MS):self.assertEqual(timeline(ms),(1,1),ms)
        self.assertEqual(HOLD_MS,4000);self.assertEqual(timeline(TOTAL_MS),(1,0))
        risen,opacity=timeline(RISE_MS+HOLD_MS+FADE_MS/2);self.assertEqual(risen,1);self.assertAlmostEqual(opacity,.5)


class FloatOnPetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)/'settings.json'
        save_atomic(self.path,dict(appearance=dict(audio_muted=True,turn_cost_show_time=False,celebrate_done=False)))
        self.patch=patch.object(module,'SETTINGS',self.path);self.patch.start()
        self.pet=module.Pet(offline=True);self.pet.timer.stop();self.pet.show();self.pet.update_layout()
        self.started=time.time();self.pet.quota_data=quota('45.00',self.started-30)

    def tearDown(self):
        self.pet.cost_float.animation.stop();self.pet.cost_float.hide();self.pet.hide();self.patch.stop();self.temp.cleanup()

    def active(self):
        self.pet.on_status(dict(state='thinking',message='',title='t',thread_id='a',turn_id='1',stale=False,active=True,started=self.started,events=[]))

    def end(self,usage=None):
        self.ended=time.time();event=dict(state='done',thread_id='a',turn_id='1',title='t',started=self.started,ended=self.ended,seq=1)
        if usage is not None:event['usage']=usage
        self.pet.on_status(dict(state='done',message='',title='t',thread_id='a',turn_id='1',stale=False,active=False,started=self.started,ended=self.ended,events=[event]))

    USAGE=dict(tokens=[dict(provider='deepseek-account',model='deepseek-flash',hour=0,hit=0,miss=0,out=1_000_000)],search=0,fetch=0)

    def test_token_usage_starts_the_float_with_the_completion_without_waiting(self):
        self.active();self.end(self.USAGE)
        self.assertEqual(self.pet.cost_hold_until,0)
        self.assertEqual(self.pet.notification['state'],'done');self.assertEqual(self.pet.controller.state,'done')
        self.assertTrue(self.pet.cost_float.isVisible());self.assertEqual(self.pet.cost_float.text,'-¥4.0000')
        # The balance arriving later does not start a second float or a second bubble.
        self.pet.cost_float.animation.stop();self.pet.cost_float.hide()
        self.pet.quota_data=quota('44.90',self.ended+1);self.idle()
        self.assertFalse(self.pet.cost_float.isVisible());self.assertIsNone(self.pet.turn_cost.pending)

    def test_bubble_style_uses_the_estimate_once(self):
        self.pet.set_option('turn_cost_style','bubble');self.active();self.end(self.USAGE)
        self.assertEqual(self.pet.cost_queue,['这一轮大约用了 ¥4.0000'])
        self.pet.quota_data=quota('44.90',self.ended+1);self.idle()
        self.assertEqual(self.pet.cost_queue,['这一轮大约用了 ¥4.0000']);self.assertFalse(self.pet.cost_float.isVisible())

    def test_unpriced_usage_falls_back_to_the_balance(self):
        self.active();self.end(dict(tokens=[dict(provider='other',model='x',hour=0,hit=1,miss=1,out=1)],search=0,fetch=0))
        self.assertIsNone(self.pet.notification);self.assertGreater(self.pet.cost_hold_until,0)
        self.pet.quota_data=quota('44.90',self.ended+1);self.idle()
        self.assertTrue(self.pet.cost_float.isVisible());self.assertEqual(self.pet.cost_float.text,'-¥0.1000')

    def idle(self):
        self.pet.on_status(dict(state='idle',message='',title='',thread_id='',turn_id='',stale=False,active=False,events=[]))

    def test_float_starts_in_the_same_step_as_the_completion(self):
        self.active();state=self.pet.controller.state;self.end()
        self.assertIsNone(self.pet.notification);self.assertFalse(self.pet.cost_float.isVisible());self.assertEqual(self.pet.controller.state,state)
        self.pet.quota_data=quota('44.90',self.ended+1);self.idle()
        self.assertEqual(self.pet.notification['state'],'done');self.assertEqual(self.pet.controller.state,'done')
        self.assertTrue(self.pet.cost_float.isVisible());self.assertEqual(self.pet.cost_float.text,'-¥0.1000')

    def test_slow_balance_starts_the_completion_without_a_late_float(self):
        self.active();self.end();self.pet.cost_hold_until=time.monotonic()-1;self.idle()
        self.assertEqual(self.pet.notification['state'],'done');self.assertFalse(self.pet.cost_float.isVisible())
        self.pet.quota_data=quota('44.90',self.ended+1);self.idle()
        self.assertFalse(self.pet.cost_float.isVisible());self.assertIsNone(self.pet.cost_float_report)

    def test_off_never_delays_the_completion(self):
        self.pet.set_option('turn_cost_style','off');self.active();self.end()
        self.assertEqual(self.pet.notification['state'],'done')

    def test_bubble_style_does_not_delay_the_completion(self):
        self.pet.set_option('turn_cost_style','bubble');self.active();self.end()
        self.assertEqual(self.pet.notification['state'],'done')

    def test_pet_in_every_corner_with_large_offsets(self):
        area=self.pet.screen_area();float_=self.pet.cost_float
        corners=[(area.left(),area.top()),(area.right()-self.pet.width()+1,area.top()),(area.left(),area.bottom()-self.pet.height()+1),(area.right()-self.pet.width()+1,area.bottom()-self.pet.height()+1)]
        for corner in corners:
            for offset in ((0,0),(-400,-400),(400,400),(-400,400),(400,-400)):
                self.pet.move(*corner);self.pet.set_cost_float_offset(*offset,save=False);float_.play('-¥123.4567')
                for ms in (0,RISE_MS/2,RISE_MS,TOTAL_MS):
                    float_.advance(ms);g=float_.geometry()
                    self.assertTrue(area.contains(g),(corner,offset,ms,g,area))
                float_.animation.stop()

    def test_float_follows_a_dragged_pet(self):
        float_=self.pet.cost_float;float_.play('-¥1.0000');float_.advance(0.);before=float_.x()
        self.pet.move(self.pet.x()-40,self.pet.y());float_.advance(0.);self.assertEqual(float_.x(),before-40)

    def test_font_and_size_are_used(self):
        self.pet.set_option('turn_cost_font_size',60);self.pet.set_option('turn_cost_font_family','LXGW WenKai')
        small=self.pet.cost_float;small.play('-¥1.0000')
        self.assertEqual(small.used.family(),'LXGW WenKai');self.assertEqual(small.used.pixelSize() if small.used.pixelSize()>0 else small.used.pointSize(),round(60*self.pet.scale_factor))
        self.assertFalse(small.used.bold())

    def test_default_size_and_outline(self):
        self.assertEqual(self.pet.options['turn_cost_font_size'],35);self.assertEqual(self.pet.options['turn_cost_outline'],'thin')
        self.pet.options['turn_cost_outline']='bogus';self.assertEqual(module.appearance(dict(appearance=dict(turn_cost_outline='bogus')))['turn_cost_outline'],'thin')

    def test_text_is_drawn_at_the_screen_pixel_density_and_outline_can_be_turned_off(self):
        float_=self.pet.cost_float;widths={}
        for outline in ('none','thin','thick'):
            self.pet.set_option('turn_cost_outline',outline);float_.play('-¥1.0000');widths[outline]=float_.width()
            self.assertEqual(float_.image.devicePixelRatio(),self.pet.devicePixelRatioF())
            self.assertEqual(float_.image.width(),round(float_.width()*self.pet.devicePixelRatioF()))
        self.assertLess(widths['none'],widths['thin']);self.assertLess(widths['thin'],widths['thick'])
        image=float_.image.toImage();self.assertTrue(any(image.pixelColor(x,y).alpha() for x in range(image.width()) for y in range(image.height())))

    def drag(self,placer,by):
        start=QPointF(placer.width()/2,placer.height()/2);origin=QPointF(placer.mapToGlobal(start.toPoint()))
        def event(kind,local,button,buttons):
            return QMouseEvent(kind,local,local+QPointF(placer.pos()),button,buttons,Qt.KeyboardModifier.NoModifier)
        placer.mousePressEvent(event(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
        target=start+QPointF(*by)
        placer.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove,target,origin+QPointF(*by),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
        placer.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease,target,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))

    def test_sample_sits_where_the_text_comes_to_rest(self):
        self.pet.move(300,300);self.pet.toggle_cost_float_placer();placer=self.pet.cost_float_placer
        float_=self.pet.cost_float;float_.play('-¥0.1234');float_.advance(TOTAL_MS-FADE_MS)
        self.assertEqual(placer.y()+placer.height(),float_.y()+float_.height())

    def test_dragging_saves_the_position(self):
        self.pet.move(300,300);self.pet.toggle_cost_float_placer();placer=self.pet.cost_float_placer
        self.drag(placer,(-60,30))
        saved=module.load_settings()['appearance'];s=self.pet.scale_factor
        self.assertEqual((saved['turn_cost_offset_x'],saved['turn_cost_offset_y']),(round(-60/s),round(30/s)))

    def test_dragging_cannot_pass_the_limit_or_the_screen(self):
        self.pet.toggle_cost_float_placer();placer=self.pet.cost_float_placer;area=self.pet.screen_area()
        self.drag(placer,(-5000,-5000))
        saved=module.load_settings()['appearance']
        self.assertGreaterEqual(saved['turn_cost_offset_x'],-OFFSET_LIMIT);self.assertGreaterEqual(saved['turn_cost_offset_y'],-OFFSET_LIMIT)
        self.assertTrue(area.contains(placer.geometry()));self.assertGreaterEqual(placer.y(),area.top())

    def start_edges(self):
        float_=self.pet.cost_float;float_.play('-¥0.1234');float_.advance(0)
        pet=self.pet.mapToGlobal(QPoint(0,0));s=self.pet.scale_factor;r=self.pet.pet_rect
        return float_,pet.x()+round(r.center().x()*s),pet.y()+round(r.top()*s),pet.y()+round(r.bottom()*s)

    def test_presets_are_centred_on_the_pet(self):
        self.pet.move(500,400);self.pet.set_cost_float_offset(37,-21)
        for preset in ('bottom','inside','above'):
            self.pet.set_cost_float_anchor(preset);float_,centre,top,bottom=self.start_edges()
            self.assertEqual(module.appearance(module.load_settings())['turn_cost_anchor'],preset)
            self.assertEqual((self.pet.options['turn_cost_offset_x'],self.pet.options['turn_cost_offset_y']),(0,0))
            self.assertLessEqual(abs(float_.x()+float_.width()//2-centre),1,preset)
            if preset=='bottom':self.assertEqual(float_.y()+float_.height(),bottom)
            if preset=='above':self.assertEqual(float_.y()+float_.height(),top)
            if preset=='inside':self.assertGreater(float_.y(),top);self.assertLess(float_.y(),top+float_.height())

    def test_preset_near_the_top_edge_stays_on_screen(self):
        area=self.pet.screen_area();self.pet.move(area.left()+200,area.top())
        self.pet.set_cost_float_anchor('above');float_=self.pet.cost_float;float_.play('-¥0.1234')
        for ms in (0,RISE_MS,TOTAL_MS):float_.advance(ms);self.assertTrue(area.contains(float_.geometry()),ms)

    def test_bad_preset_falls_back_to_inside_top(self):
        self.assertEqual(module.appearance(dict(appearance=dict(turn_cost_anchor='left')))['turn_cost_anchor'],'inside')
        self.assertEqual(module.appearance({})['turn_cost_anchor'],'inside')

    def test_position_survives_a_restart_and_can_be_reset(self):
        self.pet.set_cost_float_offset(120,-80)
        options=module.appearance(module.load_settings());self.assertEqual((options['turn_cost_offset_x'],options['turn_cost_offset_y']),(120,-80))
        self.pet.set_cost_float_offset(0,0)
        options=module.appearance(module.load_settings());self.assertEqual((options['turn_cost_offset_x'],options['turn_cost_offset_y']),(0,0))


if __name__=='__main__':
    unittest.main()
