"""Edge docking, full-screen hiding, confetti with the time line, and the daily recap."""
import datetime,pathlib,tempfile,time,unittest
from decimal import Decimal
from unittest.mock import patch
from PySide6.QtCore import QEvent,QPoint,QPointF,QRect,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.daily_recap import DailyStats,duration_text
from shorekeeper_pet.edge_dock import VISIBLE,WALL_SHOWN,EdgeDock,wall_fraction
from PySide6.QtGui import QColor,QImage

USAGE=dict(tokens=[dict(provider='deepseek-account',model='deepseek-flash',hour=0,hit=0,miss=0,out=1_000_000)],search=0,fetch=0)


class Base(unittest.TestCase):
    APPEARANCE={}

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)/'settings.json'
        save_atomic(self.path,dict(appearance=dict(audio_muted=True,**self.APPEARANCE)))
        self.patch=patch.object(module,'SETTINGS',self.path);self.patch.start()
        self.pet=module.Pet(offline=True);self.pet.timer.stop();self.pet.slow_timer.stop();self.pet.show();self.pet.update_layout()

    def tearDown(self):
        for w in (self.pet.cost_float,self.pet.confetti):w.hide()
        self.pet.cost_float.animation.stop();self.pet.confetti.timer.stop();self.pet.edge_dock.animation.stop()
        self.pet.hide();self.patch.stop();self.temp.cleanup()

    def finish(self,state='done',seconds=252,usage=USAGE):
        ended=time.time();started=ended-seconds
        self.pet.on_status(dict(state='thinking',message='',title='t',thread_id='a',turn_id='1',stale=False,active=True,started=started,events=[]))
        event=dict(state=state,thread_id='a',turn_id='1',title='t',started=started,ended=ended,seq=1)
        if usage is not None:event['usage']=usage
        self.pet.on_status(dict(state=state,message='',title='t',thread_id='a',turn_id='1',stale=False,active=False,started=started,ended=ended,events=[event]))
        return event


class TimeLineTests(Base):
    def test_amount_and_time_start_together_in_the_chosen_order(self):
        self.finish()
        self.assertEqual(self.pet.notification['state'],'done')
        self.assertEqual(self.pet.cost_float.text,'-¥4.0000\n用时 4分12秒')

    def test_time_can_come_first(self):
        self.pet.set_option('turn_cost_order','time,cost');self.finish()
        self.assertEqual(self.pet.cost_float.text,'用时 4分12秒\n-¥4.0000')

    def test_each_line_can_be_turned_off(self):
        self.pet.set_option('turn_cost_show_cost',False);self.finish()
        self.assertEqual(self.pet.cost_float.text,'用时 4分12秒')

    def test_time_only_still_floats_when_the_amount_is_unknown(self):
        self.finish(usage=None);self.pet.cost_hold_until=0;self.pet.tick()
        self.assertTrue(self.pet.cost_float.isVisible());self.assertEqual(self.pet.cost_float.text,'用时 4分12秒')

    def test_nothing_floats_with_both_lines_off(self):
        self.pet.set_option('turn_cost_show_cost',False);self.pet.set_option('turn_cost_show_time',False);self.finish()
        self.assertFalse(self.pet.cost_float.isVisible())

    def test_bubble_has_both_parts(self):
        self.pet.set_option('turn_cost_style','bubble');self.finish()
        self.assertEqual(self.pet.cost_queue,['这一轮大约用了 ¥4.0000，用时 4 分 12 秒'])

    def test_time_text(self):
        self.assertEqual(duration_text(38),'38 秒');self.assertEqual(duration_text(252,True),'4分12秒')
        self.assertEqual(duration_text(120),'2 分');self.assertEqual(duration_text(3780),'1 小时 3 分')

    def test_bad_order_is_reset(self):
        self.assertEqual(module.appearance(dict(appearance=dict(turn_cost_order='x')))['turn_cost_order'],'cost,time')


class ConfettiTests(Base):
    def test_confetti_with_a_completion(self):
        self.finish();self.assertTrue(self.pet.confetti.isVisible());self.assertEqual(len(self.pet.confetti.pieces),36)

    def test_no_confetti_for_an_error_or_when_off(self):
        self.finish('error');self.assertFalse(self.pet.confetti.isVisible())
        self.pet.set_option('celebrate_done',False);self.pet.notification=None;self.pet.notifications.clear()
        self.pet.on_status(dict(state='done',thread_id='a',turn_id='2',events=[dict(state='done',thread_id='a',turn_id='2',started=1,ended=time.time(),seq=2)]))
        self.assertFalse(self.pet.confetti.isVisible())

    def test_confetti_ends_by_itself(self):
        c=self.pet.confetti;c.burst();c.clock.restart();c.last=0
        with patch.object(c.clock,'elapsed',return_value=1600):c.step()
        self.assertFalse(c.isVisible())

    def test_confetti_independent_of_the_display_style(self):
        self.pet.set_option('turn_cost_style','off');self.finish();self.assertTrue(self.pet.confetti.isVisible())


class EdgeDockTests(Base):
    def setUp(self):
        super().setUp();self.now=[100.];self.idle=[0.];d=self.pet.edge_dock;d.clock=lambda:self.now[0];d.idle=lambda:self.idle[0]

    def drag_to(self,x,y):
        p=self.pet;p.drag_offset=QPoint(10,10);p.drag_origin=QPoint(0,0);p.dragged=True;p.move(x,y)
        local=QPointF(10,10)
        p.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease,local,local+QPointF(p.pos()),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier))
        self.land()

    def land(self):
        d=self.pet.edge_dock;d.animation.stop()
        if d.docked:self.pet.move(d.target(d.tucked))

    def wait(self,seconds):
        """Seconds of quiet pass, one update a second as on the real pet."""
        for _ in range(int(seconds)):self.now[0]+=1;self.pet.edge_dock.update();self.land()

    def shown(self):
        """Width of the pet square left on screen: up to the cut through the art."""
        d=self.pet.edge_dock;r=self.pet.pet_rect;s=self.pet.scale_factor
        return (d.cut()-r.left())*s if d.side=='right' else (r.left()+r.width()-d.cut())*s

    def right_edge(self):
        area=self.pet.screen_area();self.drag_to(area.right()-self.pet.width()//2,300);return area

    def test_default_peek_art_keeps_a_strip_of_wall(self):
        art=self.pet.get_animation(self.pet.binding('hover')['asset']).frames[0]
        self.assertAlmostEqual(wall_fraction(art),196/300+WALL_SHOWN,delta=.01)

    def test_art_without_a_wall_keeps_the_default_share(self):
        plain=QImage(100,100,QImage.Format.Format_ARGB32);plain.fill(QColor(0,0,0,0));self.assertEqual(wall_fraction(plain),VISIBLE)
        walled=QImage(100,100,QImage.Format.Format_ARGB32);walled.fill(QColor(0,0,0,0))
        for x in range(70,100):
            for y in range(100):walled.setPixelColor(x,y,QColor(140,130,130))
        self.assertAlmostEqual(wall_fraction(walled),.7+WALL_SHOWN,delta=.001)

    def test_release_at_the_edge_waits_in_full_view_then_tucks_after_the_quiet_delay(self):
        area=self.right_edge();d=self.pet.edge_dock
        self.assertTrue(d.docked);self.assertFalse(d.tucked);g=d.pet_global();self.assertLessEqual(g.right(),area.right())
        self.assertEqual(module.load_settings()['dock'],dict(side='right'))
        self.wait(59);self.assertFalse(d.tucked)
        self.wait(2);self.assertTrue(d.tucked);g=d.pet_global()
        self.assertAlmostEqual(area.right()+1-g.left(),self.shown(),delta=2)

    def test_quiet_waiting_keeps_the_idle_art_and_tucked_uses_the_peek_art(self):
        self.right_edge();self.pet.controller.enter('idle',time.monotonic(),'live');self.pet.tick()
        self.assertEqual(self.pet.animation_id,self.pet.binding('idle')['asset'])
        self.wait(61);self.pet.tick();self.assertEqual(self.pet.animation_id,self.pet.binding('hover')['asset'])

    def test_left_edge_tucks_mirrored_and_out_is_not_mirrored(self):
        area=self.pet.screen_area();self.drag_to(area.left()-self.pet.width()//2,300);d=self.pet.edge_dock
        self.pet.controller.enter('idle',time.monotonic(),'live');self.pet.tick();self.assertFalse(self.pet.mirror_art)
        self.wait(61);self.pet.tick();self.assertEqual(d.side,'left');self.assertTrue(self.pet.mirror_art)
        g=d.pet_global();self.assertAlmostEqual(g.right()+1-area.left(),self.shown(),delta=2);self.pet.grab()
        self.pet.react('pet');self.assertFalse(self.pet.mirror_art)

    def test_a_running_task_comes_out_at_once_and_stays_out(self):
        self.right_edge();d=self.pet.edge_dock;self.wait(61);self.assertTrue(d.tucked)
        self.pet.on_status(dict(state='thinking',message='',title='t',thread_id='a',turn_id='1',stale=False,active=True,started=time.time(),events=[]))
        self.land();self.assertFalse(d.tucked)
        self.wait(300);self.assertFalse(d.tucked)
        self.pet.on_status(dict(state='idle',message='',title='',thread_id='',turn_id='',stale=False,active=False,events=[]))
        self.wait(59);self.assertFalse(d.tucked);self.wait(2);self.assertTrue(d.tucked)

    def test_working_poses_are_never_cut(self):
        self.right_edge();self.wait(61)
        self.pet.on_status(dict(state='writing',message='',title='t',thread_id='a',turn_id='1',stale=False,active=True,started=time.time(),events=[]))
        self.land();self.assertTrue(self.pet.screen_area().contains(self.pet.edge_dock.pet_global()))

    def test_a_completion_comes_out(self):
        self.right_edge();self.wait(61);self.finish();self.land()
        self.assertFalse(self.pet.edge_dock.tucked)

    def test_a_pointer_peek_slides_back_soon(self):
        self.right_edge();d=self.pet.edge_dock;self.wait(61)
        d.hover_in();self.land();self.assertFalse(d.tucked);self.assertTrue(d.peeking);self.assertTrue(d.showing_peek_art())
        with patch.object(self.pet,'underMouse',return_value=False):d.peek_over()
        self.land();self.assertTrue(d.tucked)

    def test_comes_out_while_the_user_is_away_and_tucks_after_they_return(self):
        self.right_edge();d=self.pet.edge_dock;self.wait(61);self.assertTrue(d.tucked)
        self.idle[0]=400;self.wait(1);self.assertFalse(d.tucked)
        self.idle[0]=0;self.wait(59);self.assertFalse(d.tucked);self.wait(2);self.assertTrue(d.tucked)

    def test_the_delay_comes_from_the_settings(self):
        self.pet.set_option('dock_tuck_seconds',10);self.right_edge();d=self.pet.edge_dock
        self.wait(9);self.assertFalse(d.tucked);self.wait(2);self.assertTrue(d.tucked)
        self.assertEqual(module.appearance(dict(appearance=dict(dock_tuck_seconds=5)))['dock_tuck_seconds'],10)

    def test_release_away_from_edges_does_not_dock(self):
        area=self.pet.screen_area();self.drag_to(area.center().x()-200,300)
        self.assertFalse(self.pet.edge_dock.docked);self.assertIsNone(module.load_settings()['dock'])

    def test_a_neighbouring_monitor_blocks_that_edge(self):
        class Screen:
            def __init__(self,*rect):self.rect=QRect(*rect)
            def geometry(self):return self.rect
        main=QRect(0,0,1707,1000)
        # Mixed scaling: the right-hand monitor starts at 2560 while the first ends at 1707.
        screens=[Screen(0,0,1707,1040),Screen(2560,0,1920,1080)]
        self.assertFalse(EdgeDock.outer(main,'right',screens));self.assertTrue(EdgeDock.outer(main,'left',screens))
        touching=[Screen(0,0,1707,1040),Screen(-1920,200,1920,1080)]
        self.assertFalse(EdgeDock.outer(main,'left',touching));self.assertTrue(EdgeDock.outer(main,'right',touching))
        above=[Screen(0,0,1707,1040),Screen(1800,-1200,1920,1080)]
        self.assertTrue(EdgeDock.outer(main,'right',above))

    def test_turning_the_option_off_brings_it_back(self):
        area=self.right_edge();self.wait(61);self.pet.set_option('edge_dock',False)
        self.assertFalse(self.pet.edge_dock.docked);self.assertTrue(area.contains(self.pet.geometry()))

    def test_dock_survives_a_restart_tucked(self):
        self.right_edge();self.pet.hide()
        again=module.Pet(offline=True);again.timer.stop();again.slow_timer.stop()
        try:self.assertEqual(again.edge_dock.side,'right');self.assertTrue(again.edge_dock.tucked)
        finally:again.hide()

    def test_scale_change_keeps_it_docked(self):
        area=self.right_edge();self.wait(61);self.pet.set_scale(1.3)
        g=self.pet.edge_dock.pet_global();self.assertAlmostEqual(area.right()+1-g.left(),self.shown(),delta=2)


class FullscreenTests(Base):
    APPEARANCE=dict(fullscreen_hide=True)

    def guard(self,covered):
        g=self.pet.fullscreen_guard;g.detect=lambda:covered;g.locate=lambda w:'screen-1';return g

    def test_hides_for_full_screen_on_its_monitor_and_comes_back(self):
        g=self.guard('screen-1');g.check();self.assertFalse(self.pet.isVisible())
        g.detect=lambda:None;g.check();self.assertTrue(self.pet.isVisible())

    def test_ignores_other_monitors(self):
        self.guard('screen-2').check();self.assertTrue(self.pet.isVisible())

    def test_off_by_default_and_turning_it_off_restores(self):
        self.assertFalse(module.appearance({})['fullscreen_hide'])
        g=self.guard('screen-1');g.check();self.pet.set_option('fullscreen_hide',False);self.assertTrue(self.pet.isVisible())

    def test_does_not_reopen_a_pet_the_user_put_away(self):
        self.pet.hide();g=self.guard('screen-1');g.check();g.detect=lambda:None;g.check();self.assertFalse(self.pet.isVisible())

    def test_menu_text_says_what_a_click_does(self):
        self.assertEqual(self.pet.fullscreen_label(),'点击关闭全屏时隐藏')
        self.pet.set_option('fullscreen_hide',False);self.assertEqual(self.pet.fullscreen_label(),'点击开启全屏时隐藏')
        menu=self.pet.context_menu();self.assertIn('点击开启全屏时隐藏',[a.text() for a in menu.actions()]);menu.deleteLater()


class DailyRecapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)/'daily-stats.json'
        self.now=datetime.datetime(2026,11,11,20,0).timestamp()

    def tearDown(self):self.temp.cleanup()

    def stats(self,now=None):return DailyStats(self.path,clock=lambda:now or self.now)

    def test_counts_and_recap_text(self):
        s=self.stats();end=self.now-3600
        s.record(dict(state='done',thread_id='a',turn_id='1',started=end-1080,ended=end))
        s.record(dict(state='done',thread_id='a',turn_id='1',started=end-1080,ended=end))
        s.record(dict(state='error',thread_id='a',turn_id='2',started=end-60,ended=end))
        s.record(dict(state='paused',thread_id='a',turn_id='3',started=end-60,ended=end))
        s.add_cost(end,Decimal('1.234'))
        self.assertEqual(s.today(),'今天到现在\n完成 1 轮，出错 1 次\n花费约 ¥1.23，最长一轮 18 分')

    def test_yesterday_once_a_day(self):
        s=self.stats();s.record(dict(state='done',thread_id='a',turn_id='1',started=self.now-100,ended=self.now-60))
        tomorrow=self.stats(self.now+86400)
        self.assertTrue(tomorrow.due().startswith('昨天的小结\n完成 1 轮'));self.assertIsNone(tomorrow.due())
        self.assertIsNone(self.stats(self.now+86400).due())

    def test_older_day_is_named_by_date(self):
        s=self.stats();s.record(dict(state='done',thread_id='a',turn_id='1',started=self.now-100,ended=self.now-60))
        self.assertTrue(self.stats(self.now+3*86400).due().startswith('11月11日的小结'))

    def test_nothing_to_say_without_activity(self):
        self.assertIsNone(self.stats().due());self.assertEqual(self.stats().today(),'今天还没有完成的任务。')

    def test_old_days_are_dropped(self):
        s=self.stats();s.record(dict(state='done',thread_id='a',turn_id='1',started=self.now-100,ended=self.now-60))
        later=self.stats(self.now+40*86400);later.save();self.assertEqual(later.days,{})

    def test_damaged_file_starts_empty(self):
        self.path.write_text('{bad','utf8');self.assertEqual(self.stats().days,{})


class RecapOnPetTests(Base):
    def test_pet_counts_turns_and_estimated_cost(self):
        self.finish();row=self.pet.daily.days[datetime.date.today().isoformat()]
        self.assertEqual((row['turns'],Decimal(row['cost']),row['longest']),(1,Decimal(4),252))
        self.assertTrue(self.path.with_name('daily-stats.json').exists())

    def test_recap_uses_a_bubble_without_changing_the_animation(self):
        self.pet.show_today_recap();state=self.pet.state
        self.pet.present_turn_cost(time.monotonic());self.assertTrue(self.pet.cost_text.startswith('今天'))
        self.assertEqual(self.pet.state,state);self.assertGreater(self.pet.cost_until-time.monotonic(),10)

    def test_recap_can_be_turned_off(self):
        self.pet.set_option('daily_recap',False);self.pet.daily.due=lambda:'x';self.pet.show_due_recap();self.assertEqual(self.pet.cost_queue,[])

    def test_menu_has_todays_recap(self):
        menu=self.pet.context_menu();self.assertIn('今日小结',[a.text() for a in menu.actions()]);menu.deleteLater()


class CompanionSettingsTests(Base):
    def test_order_and_switches_are_saved(self):
        self.pet.open_preferences('桌面与声音');d=self.pet.preferences;o=d.order
        o.list.setCurrentRow(0);o.move(1)
        self.assertEqual(module.appearance(module.load_settings())['turn_cost_order'],'time,cost')
        o.list.item(1).setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(module.appearance(module.load_settings())['turn_cost_show_cost'])
        d.refresh_controls();self.assertEqual(o.order(),['time','cost']);self.assertEqual(o.enabled(),dict(time=True,cost=False))
        d.hide()

    def test_feature_switches_exist_and_save(self):
        self.pet.open_preferences('桌面与声音');d=self.pet.preferences
        for key in ('celebrate_done','edge_dock','daily_recap','fullscreen_hide'):
            box=d.controls[key];box.setChecked(not box.isChecked())
            self.assertEqual(module.appearance(module.load_settings())[key],box.isChecked(),key)
        d.hide()

    def test_menu_switch_updates_the_open_settings(self):
        self.pet.open_preferences();self.pet.set_option('fullscreen_hide',True)
        self.assertTrue(self.pet.preferences.controls['fullscreen_hide'].isChecked());self.pet.preferences.hide()


class RestReminderTests(Base):
    def setUp(self):
        super().setUp();self.now=[1000.];self.idle=[0.]
        r=self.pet.rest_reminder;r.clock=lambda:self.now[0];r.idle=lambda:self.idle[0];r.since=self.now[0];r.restart()

    def tearDown(self):
        if self.pet.rest_reminder.card:self.pet.rest_reminder.card.hide()
        super().tearDown()

    def advance(self,seconds):self.now[0]+=seconds;self.pet.rest_reminder.check()

    def test_on_by_default_every_hour_with_milk_tea(self):
        r=self.pet.rest_reminder;self.assertTrue(self.pet.options['rest_reminder']);self.assertEqual(self.pet.options['rest_interval_minutes'],60)
        self.advance(3599);self.assertFalse(r.active)
        self.advance(2);self.assertTrue(r.active);self.assertEqual(self.pet.state,'feed')
        self.assertIn('60 分钟',r.card.text.text())
        self.pet.controller.enter('idle',time.monotonic(),'live');self.pet.tick()
        self.assertEqual(self.pet.animation_id,self.pet.binding('feed')['asset'])

    def test_card_stays_ten_seconds_then_counts_as_got_it(self):
        r=self.pet.rest_reminder;self.advance(3601);self.advance(9);self.assertTrue(r.active)
        self.advance(2);self.assertFalse(r.active);self.assertEqual(r.due,self.now[0]+3600)

    def test_later_waits_thirty_minutes(self):
        r=self.pet.rest_reminder;self.advance(3601);r.card.buttons['later'].click()
        self.assertFalse(r.active);self.assertEqual(r.due,self.now[0]+1800)

    def test_got_it_uses_the_interval_from_the_settings(self):
        self.pet.set_option('rest_interval_minutes',45);r=self.pet.rest_reminder;self.advance(2701);r.card.buttons['ok'].click()
        self.assertEqual(r.due,self.now[0]+2700)

    def test_switch_off_stays_off_until_the_settings(self):
        r=self.pet.rest_reminder;self.advance(3601);r.card.buttons['off'].click()
        self.assertFalse(module.appearance(module.load_settings())['rest_reminder']);self.advance(99999);self.assertFalse(r.active)

    def test_away_from_the_computer_starts_again(self):
        r=self.pet.rest_reminder;self.advance(3000);self.idle[0]=400;self.advance(1);self.idle[0]=0
        self.advance(1000);self.assertFalse(r.active)

    def test_waits_for_a_completion_or_full_screen(self):
        r=self.pet.rest_reminder;self.pet.notification=dict(state='done');self.advance(3601);self.assertFalse(r.active)
        self.pet.notification=None;self.pet.fullscreen_guard.hidden=True;self.advance(1);self.assertFalse(r.active)
        self.pet.fullscreen_guard.hidden=False;self.advance(1);self.assertTrue(r.active)

    def test_settings_rows(self):
        self.pet.open_preferences('桌面与声音');d=self.pet.preferences
        d.controls['rest_interval_minutes'].setValue(30);self.assertEqual(module.appearance(module.load_settings())['rest_interval_minutes'],30)
        d.controls['rest_reminder'].setChecked(False);self.assertFalse(module.appearance(module.load_settings())['rest_reminder']);d.hide()


if __name__=='__main__':
    unittest.main()
