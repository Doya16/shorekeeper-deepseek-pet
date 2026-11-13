"""Shorekeeper: a transparent Windows desktop companion for DeepSeek."""
from __future__ import annotations
import argparse, collections, json, math, os, pathlib, random, sys, threading, time
from datetime import datetime
from PIL import Image
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint, QSize, Signal, QObject, QLockFile, QEvent
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QImage, QPixmap, QIcon, QAction, QCursor
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox, QListWidget, QAbstractItemView,QScrollArea
from .bridge import Monitor, RateClient, ROOT
from .bindings import BindingMap,PlaybackController,MANUAL,playback_seconds
from .studio import BindingEditor
from .preferences import Preferences
from .appearance import appearance,load_fonts,stylesheet,font
from .audio_player import VoicePlayer
from .config_io import save_atomic,migrate_settings
from .renderer import PetRenderer,SpeechBubble
from .binding_editor import TRIGGERS
from .paths import VERSION,DSH_HOME
from .voice_pool import task_key,clip_bubble_text
from .sizing import normalize_scale
from .presentation_size import EdgeResize
from .media_library import load_catalog
from .presets import load_defaults,default_bindings
from .update_ui import UpdateController
from .lock_button import LockButton
from .pointer_mode import PointerMode

SETTINGS=ROOT/'settings.json'
STATES={
 'idle':('陪着你','我在这里，慢慢来就好。'),
 'thinking':('整理中','正在整理接下来的步骤，陪我等一小会儿。'),
 'reading':('查阅中','我去翻翻资料，马上回来。'),
 'writing':('编辑中','正在把想法写下来，一笔一笔来。'),
 'working':('执行中','工具还在工作，我替你守着。'),
 'waiting':('等你回应','有件事需要你看看，回到 DeepSeek 回复一下吧。'),
 'done':('完成啦','这一步做好了，去看看结果吧！'),
 'error':('遇到问题','这里有个小状况，回到 DeepSeek 看看详情吧。'),
 'paused':('已暂停','先歇一会儿，准备好再继续。'),
 'unknown':('等待更新','暂时没有新的状态，任务可能仍在运行。'),
 'pet':('摸摸头','唔……有你陪着，今天也要好好加油。'),
 'feed':('休息一下','谢谢你的奶茶！我会继续替你守着进度。'),
 'hover':('探出头来','在看我吗？我也在陪着你。'),
 'drag':('被拎起来了','轻轻的，带我去哪里呀？'),
 'drop':('落座啦','就坐在这里陪你吧。'),
 'doubleclick':('双击回应','我在呢，听到你的呼唤了。'),
}
PACKS={
 '163':dict(idle='p3-06',thinking='p3-10',reading='p3-02',writing='p3-02',working='p3-11',waiting='p3-20',done='p3-25',error='p3-03',paused='p3-19',unknown='p3-20',pet='p3-17',feed='p3-09'),
 'GB0227':dict(idle='p1-03',thinking='p1-07',reading='p2-07',writing='p2-06',working='p2-19',waiting='p2-16',done='p1-20',error='p2-03',paused='p1-05',unknown='p2-16',pet='p2-10',feed='p1-16'),
}
# Existing frames only. Reversible small motions use ping-pong; reactions play once.
PACKS['163'].update(hover='p3-20',drag='p3-05',drop='p3-14',doubleclick='p3-23')
PACKS['GB0227'].update(hover='p2-16',drag='p1-09',drop='p1-05',doubleclick='p2-08')
ONESHOT={'done','error','pet','feed','drop','doubleclick'}
CATALOG,ASSET_WARNINGS=load_catalog(ROOT)
ASSETS={row['id']:row for row in CATALOG}

def load_settings():
    for path in (SETTINGS,SETTINGS.with_suffix('.json.bak')):
        try:
            value=json.loads(path.read_text('utf-8'))
            if isinstance(value,dict): return migrate_settings(value)
        except (OSError,ValueError): pass
    return migrate_settings(load_defaults(ROOT))

def image_from_pil(im):
    rgba=im.convert('RGBA')
    return QImage(rgba.tobytes(),rgba.width,rgba.height,rgba.width*4,QImage.Format.Format_RGBA8888).copy()

class Animation:
    def __init__(self, asset_id):
        self.frames=[]; self.durations=[]
        with Image.open(ROOT/ASSETS[asset_id]['path']) as im:
            for index in range(im.n_frames):
                im.seek(index)
                self.frames.append(image_from_pil(im))
                self.durations.append(max(20,im.info.get('duration',40)))
        self.ping=list(range(len(self.frames)))+list(range(len(self.frames)-2,0,-1))

    def frame(self, elapsed, once=False, playback=None):
        mode=playback or ('once' if once else 'pingpong')
        once=mode=='once'
        seq=self.ping if mode=='pingpong' else list(range(len(self.frames)))
        total=sum(self.durations[i] for i in seq)
        t=min(elapsed,total-1) if once else elapsed%total
        for idx in seq:
            t-=self.durations[idx]
            if t<0: return self.frames[idx]
        return self.frames[seq[-1]]

class BridgeWorker(QObject):
    client_exited=Signal()
    status=Signal(dict)
    quota=Signal(dict)
    quota_read=Signal(int,dict)
    threads=Signal(list)

class Pet(PetRenderer,QWidget):
    size_changed=Signal()
    def __init__(self, offline=False):
        super().__init__()
        self.settings=load_settings()
        self.options=appearance(self.settings); self.font_families=load_fonts(ROOT)
        self.position_ready=False; self.preferences=None; self.size_dialog=None; self.offline=offline
        self.presentation_previews=set(); self.quota_resize=EdgeResize(self,self,'quota_scale')
        self.requested_scale=normalize_scale(self.settings.get('scale',1.0)); self.scale_factor=self.requested_scale
        self.pack=self.settings.get('pack','163')
        if self.pack not in PACKS: self.pack='163'
        self.bindings=BindingMap(PACKS,ASSETS,ONESHOT,self.settings.get('bindings'),baseline=default_bindings(ROOT))
        self.on_top=self.settings.get('on_top',True)
        self.show_notes=self.settings.get('show_notes',True)
        flags=Qt.WindowType.FramelessWindowHint|Qt.WindowType.Tool
        if self.on_top: flags|=Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('守岸人 · DeepSeek 桌宠')
        self.setMouseTracking(True)
        self.resize(round(340*self.scale_factor),round(438*self.scale_factor))
        self.cache=collections.OrderedDict(); self.animation_id=self.binding('idle')['asset']; self.animation=self.get_animation(self.animation_id)
        self.anim_start=time.monotonic(); self.last_image=self.animation.frames[0]
        self.controller=PlaybackController(self.binding,self.animation_duration,time.monotonic()); self.last_serial=-1
        self.transition_old=None; self.transition_start=0
        self.state='idle'; self.override=None; self.override_until=0; self.override_text=''; self.preview_id=None
        self.bubble_until=time.monotonic()+12
        self.live_status={'state':'idle','message':'','title':''}
        self.notifications=collections.deque(); self.notification=None; self.notification_until=0; self.notification_seen=set()
        self.quota_data={}; self.thread_list=[]; self.panel=None; self.binding_editor=None
        self.monitor=Monitor(self.options['deepseek_home'] or DSH_HOME); self.monitor.selected=self.settings.get('thread','auto')
        self.rate_client=RateClient(self.options['deepseek_executable'],self.options['deepseek_home']); self.worker=BridgeWorker(); self.stop_event=threading.Event(); self.refresh_event=threading.Event()
        from .quota_refresh import QuotaRefresh
        self.quota_refresh=QuotaRefresh(self.refresh_event)
        from .turn_cost import TurnCost
        self.turn_cost=TurnCost(self.refresh_quota_quietly); self.cost_queue=[]; self.cost_text=''; self.cost_until=0
        self.cost_hold_until=0; self.cost_hold_for=None; self.cost_float_report=None; self.cost_float_placer=None; self.cost_events={}
        self.worker.quota_read.connect(self.on_quota_read)
        from .client_lifetime import ClientLifetime
        self.client_lifetime=ClientLifetime()
        self.worker.client_exited.connect(self.on_client_exit)
        self.voice=VoicePlayer(ROOT,self); self.preview_audio_clip=None
        self.bubble_window=SpeechBubble(self); self.voice.changed.connect(self.on_voice_changed)
        from .cost_float import CostFloat
        self.cost_float=CostFloat(self)
        from .celebrate import Confetti
        self.confetti=Confetti(self)
        from .edge_dock import EdgeDock
        self.edge_dock=EdgeDock(self)
        from .fullscreen_guard import FullscreenGuard
        self.fullscreen_guard=FullscreenGuard(self)
        from .rest_reminder import RestReminder
        self.rest_reminder=RestReminder(self); self.mirror_art=False; self.mirror_cache=None
        from .daily_recap import DailyStats
        self.daily=DailyStats(SETTINGS.with_name('daily-stats.json')); self.slow_count=0
        self.worker.status.connect(self.on_status); self.worker.quota.connect(self.on_quota); self.worker.threads.connect(self.on_threads)
        self.drag_offset=None; self.drag_origin=None; self.dragged=False
        self.hovered=False; self.ignore_release=False
        self.click_timer=QTimer(self); self.click_timer.setSingleShot(True); self.click_timer.timeout.connect(lambda:self.react('pet'))
        self.hover_timer=QTimer(self); self.hover_timer.setSingleShot(True); self.hover_timer.timeout.connect(self.hover_react)
        self.quota_press=None; self.quota_click_cancelled=False
        self.lock_button=LockButton(self)
        self.pointer_mode=PointerMode(self)
        icon_im=self.animation.frames[0].scaled(64,64,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        from .app_icons import application_icon
        self.icon=application_icon(ROOT,self.options['tray_icon_style'])
        if self.icon.isNull(): self.icon=QIcon(QPixmap.fromImage(icon_im))
        self.setWindowIcon(self.icon); QApplication.instance().setWindowIcon(self.icon)
        self.updates=UpdateController(self)
        self.tray=QSystemTrayIcon(self.icon,self); self.tray.setToolTip('守岸人 · DeepSeek · 点击唤醒/隐藏')
        self.tray.setContextMenu(self.context_menu(tray=True))
        self.tray.activated.connect(lambda reason:self.toggle_visible() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        if not offline: self.tray.show()
        self.timer=QTimer(self); self.timer.setInterval(25); self.timer.timeout.connect(self.tick); self.timer.start()
        self.update_layout()
        area=QApplication.primaryScreen().availableGeometry()
        pos=self.settings.get('position',[area.right()-self.width()-35,area.bottom()-self.height()-18])
        self.move(*pos); self.clamp_position(); self.position_ready=True; self.apply_style()
        dock=self.settings.get('dock')
        if isinstance(dock,dict): self.edge_dock.restore(dock.get('side'),self.screen_area())
        self.slow_timer=QTimer(self); self.slow_timer.setInterval(1000); self.slow_timer.timeout.connect(self.slow_tick); self.slow_timer.start()
        if not offline:
            threading.Thread(target=self.watch_status,daemon=True).start()
            threading.Thread(target=self.watch_quota,daemon=True).start()
            self.updates.schedule()

    def get_animation(self, aid):
        if aid not in self.cache:
            self.cache[aid]=Animation(aid)
            while len(self.cache)>10: self.cache.popitem(last=False)
        self.cache.move_to_end(aid)
        return self.cache[aid]

    def refresh_assets(self):
        records,warnings=load_catalog(ROOT); updated={row['id']:row for row in records}
        for aid in list(self.cache):
            if aid not in updated or updated[aid].get('sha256')!=ASSETS.get(aid,{}).get('sha256'): self.cache.pop(aid,None)
        CATALOG[:]=records; ASSETS.clear(); ASSETS.update(updated); self.bindings.assets=set(ASSETS)
        aid=self.binding(self.state)['asset']; self.animation_id=aid; self.animation=self.get_animation(aid); self.preview_id=None
        if self.panel:
            self.panel.gallery.blockSignals(True); self.panel.gallery.clear()
            for asset in CATALOG: self.panel.gallery.addItem(asset['name'],asset['id'])
            self.panel.gallery.blockSignals(False)
        self.tick(); return warnings

    def binding(self,state): return self.bindings.resolve(self.pack,state)

    def state_title(self,state=None): return TRIGGERS.get(state or self.state,TRIGGERS['unknown'])[0]

    def voice_bubble(self):
        v=self.voice
        return bool(v.busy and v.selected_clip and v.selected_state in STATES and self.binding(v.selected_state)['bubble_mode']=='audio' and clip_bubble_text(v.selected_clip))

    def bubble_state(self):
        if hasattr(self,'bubble_window') and self.bubble_window.edge_resize.active: return self.bubble_window.edge_resize.state
        return self.voice.selected_state if self.voice_bubble() else self.state
    def bubble_binding(self): return self.binding(self.bubble_state())
    def on_voice_changed(self):
        if hasattr(self,'bubble_window'): self.update_layout(); self.update()

    def animation_duration(self,aid):
        asset=ASSETS[aid]; durations=asset['durations_ms']; return asset['duration_ms'],2*asset['duration_ms']-durations[0]-durations[-1]

    def set_binding(self,state,**changes):
        self.bindings.set(state,**changes)
        self.settings['bindings']=self.bindings.to_dict(); ok=self.save_settings()
        if state==self.controller.state and set(changes)&{'asset','playback','speed'}: self.controller.enter(state,time.monotonic(),self.controller.owner)
        self.update_layout(); self.tick(); return ok

    def reset_binding(self,state):
        self.bindings.reset(state)
        self.settings['bindings']=self.bindings.to_dict(); ok=self.save_settings()
        if state==self.state: self.controller.enter(state,time.monotonic(),self.controller.owner)
        self.update_layout(); self.tick(); return ok

    def on_client_exit(self):
        if not self.offline and self.options['exit_with_deepseek']:self.shutdown()

    def watch_status(self):
        from .startup import deepseek_process_tree
        next_client_check=0
        while not self.stop_event.is_set():
            now=time.monotonic()
            if now>=next_client_check:
                next_client_check=now+2
                enabled=self.options['exit_with_deepseek']
                try:parents=deepseek_process_tree() if enabled else {}
                except OSError:parents=None
                if self.client_lifetime.observe(parents,now,enabled):self.worker.client_exited.emit()
            try:
                target=pathlib.Path(self.options['deepseek_home'] or DSH_HOME)
                if self.monitor.home!=target:
                    self.monitor=Monitor(target); self.monitor.selected=self.settings.get('thread','auto')
                self.worker.status.emit(self.monitor.poll())
                self.worker.threads.emit(self.monitor.threads.copy())
                if self.monitor.cached_rate(): self.worker.quota.emit(self.monitor.cached_rate())
            except Exception:
                self.worker.status.emit(dict(state='unknown',message='',title='',stale=True))
            self.stop_event.wait(1)

    def watch_quota(self):
        while not self.stop_event.is_set():
            ticket=self.quota_refresh.begin_read()
            try:
                if (self.rate_client.executable,self.rate_client.deepseek_home)!=(self.options['deepseek_executable'],self.options['deepseek_home']):
                    self.rate_client.close(); self.rate_client=RateClient(self.options['deepseek_executable'],self.options['deepseek_home'])
                self.worker.quota_read.emit(ticket,self.rate_client.read())
            except Exception:
                self.worker.quota_read.emit(ticket,dict(error='刷新暂时失败，显示最近记录。'))
            self.refresh_event.wait(120)

    def refresh_quota(self):
        self.quota_refresh.request((self.options['deepseek_executable'],self.options['deepseek_home']))
        self.update()

    def refresh_quota_quietly(self):
        # Turn tracking must not make the balance box flicker on every task.
        self.quota_refresh.request(self.options['deepseek_home'],silent=True)

    def quota_display_label(self):
        return self.quota_refresh.label() or self.quota_label(compact=True)

    def on_quota_read(self,ticket,result):
        self.on_quota(result)
        self.quota_refresh.finish(ticket,result)
        self.update()

    def update_quota_cursor(self,local=None):
        from .presentation_size import edge_at
        if not hasattr(self,'quota_rect'):return
        if local is None:local=self.mapFromGlobal(QCursor.pos())
        rect=self.quota_hit_rect()
        if self.quota_resize.active or (not self.locked and edge_at(local,rect)):
            shape=Qt.CursorShape.SizeHorCursor
        elif rect.contains(local):shape=Qt.CursorShape.PointingHandCursor
        else:shape=Qt.CursorShape.ArrowCursor
        if self.cursor().shape()!=shape:self.setCursor(shape)

    def on_status(self, status):
        changed=status.get('state')!=self.live_status.get('state') or status.get('thread_id')!=self.live_status.get('thread_id')
        self.live_status=status
        for event in status.get('events',[]):
            identity=(event.get('state'),task_key(event) or (event.get('thread_id'),event.get('ended')))
            if self.daily.record(event):
                from .pricing import turn_report
                estimate=turn_report(event)
                if estimate: self.daily.add_cost(event.get('ended'),estimate['amount'])
            if event.get('state') in ('done','error','paused') and identity not in self.notification_seen:
                self.notification_seen.add(identity); self.notifications.append(dict(event))
        # Polling may first observe reading/writing after the initial thinking
        # event. Offer the start notice once as soon as this turn is discovered.
        if not self.notification and not self.notifications and status.get('active') and not status.get('stale') and self.binding('thinking')['audio_policy']=='turn':
            self.voice.trigger('thinking',self.binding('thinking'),self.options,task=task_key(status))
        state=status.get('state','idle')
        if state not in STATES: state='unknown'
        # Terminal events are presented through the queue exactly once, even
        # while another project's conversation remains active.
        if 'events' in status and state in ('done','error','paused'): state='idle'
        key=(status.get('thread_id'),state,status.get('started'),status.get('ended'))
        self.observe_turn_cost(status)
        # A task at work comes out from the edge at once, so every working pose is seen whole.
        if status.get('active') and not status.get('stale'): self.edge_dock.reveal()
        # Keep the working animation while the completion waits for its amount.
        if time.monotonic()>=self.cost_hold_until: self.controller.set_live(state,key,time.monotonic())
        self.tick(); self.update_layout()
        if changed:
            self.bubble_until=time.monotonic()+(20 if status.get('state') in ('done','error','waiting') else 10)
        if self.panel: self.panel.refresh()

    def on_quota(self, quota):
        # A slow cache read must never replace a newer live response.
        if quota.get('updated_at',0) and quota.get('updated_at',0)<self.quota_data.get('updated_at',0): return
        if quota.get('error') and quota.get('status')!='signed-out' and self.quota_data: self.quota_data.update(error=quota['error'])
        elif 'windows' in quota: self.quota_data=quota
        else: self.quota_data.update(quota)
        if self.panel: self.panel.refresh()
        self.update()
        self.update_layout()

    def on_threads(self, rows):
        changed=[(r['id'],r['title']) for r in rows]!=[(r['id'],r['title']) for r in self.thread_list]
        self.thread_list=rows
        if changed and self.panel: self.panel.update_threads(rows)
        if changed and self.preferences: self.preferences.refresh_threads()

    def select_thread(self,thread):
        self.monitor.selected=thread; self.settings['thread']=thread; ok=self.save_settings()
        self.clear_override()
        if self.panel: self.panel.update_threads(self.thread_list)
        if self.preferences: self.preferences.refresh_threads()
        return ok

    def switch_animation(self, aid):
        if aid==self.animation_id: return
        self.transition_old=self.last_image
        self.transition_start=time.monotonic()
        self.animation_id=aid; self.animation=self.get_animation(aid); self.anim_start=time.monotonic()

    def tick(self):
        now=time.monotonic()
        if self.notification and self.controller.owner!='notification': self.notification=None
        if self.notification and now>=self.notification_until and not self.voice.busy:
            self.notification=None; self.controller.resume(now); self.edge_dock.tuck_later()
        if not self.notification and self.notifications and now>=self.cost_hold_until and not self.voice.busy and self.controller.owner!='preview' and self.drag_offset is None:
            self.notification=self.notifications.popleft()
            state=self.notification['state']; b=self.binding(state)
            duration=playback_seconds(b,*self.animation_duration(b['asset']))
            self.notification_until=now+max(1,duration or 6)
            self.preview_id=None; self.override_text=''
            self.controller.enter(state,now,'notification'); self.edge_dock.reveal()
            self.play_cost_float(self.notification)
            self.bubble_until=self.notification_until
        if not self.notification: self.controller.tick(now)
        self.present_turn_cost(now)
        placer=self.cost_float_placer
        if placer and placer.isVisible():
            placer.hide() if not self.isVisible() else placer.sync()
        entered=self.controller.serial!=self.last_serial
        if entered:
            self.last_serial=self.controller.serial; self.state=self.controller.state; self.anim_start=self.controller.started
            if self.controller.owner=='live': self.override=None; self.preview_id=None; self.override_text=''
            else: self.override=self.state
        # A rest reminder keeps the cup of milk tea in hand; tucked against an edge, the resting pose is the
        # one shown when the pointer is over the pet, flipped on the left edge.
        art=self.state
        if self.state=='idle' and self.rest_reminder.active: art='feed'
        elif self.state=='idle' and self.edge_dock.showing_peek_art(): art='hover'
        aid=self.preview_id or self.binding(art)['asset']
        self.mirror_art=not self.preview_id and self.edge_dock.mirrored(aid)
        self.switch_animation(aid)
        if entered:
            binding=self.binding(self.state)
            if self.controller.owner=='preview' and self.preview_audio_clip is not None:
                binding=dict(binding,audio_clips=[dict(self.preview_audio_clip,enabled=True)])
            if not self.fullscreen_guard.hidden: self.voice.trigger(self.state,binding,self.options,preview=self.controller.owner=='preview',task=task_key(self.notification or self.live_status),notification=self.controller.owner=='notification'); self.update_layout()
        self.lock_button.refresh_visibility()
        self.pointer_mode.refresh()
        self.update_bubble()
        self.update()

    def observe_turn_cost(self,status):
        from .turn_cost import HOLD_SECONDS
        from .pricing import turn_report
        o=self.options;style=o['turn_cost_style']
        if style=='off':return
        floating=style in ('float','both');bubbling=style in ('bubble','both');show_cost=o['turn_cost_show_cost'];priced=set()
        # Token counts and times arrive with the completion itself, so these lines are ready at once.
        for event in status.get('events',[]):
            if event.get('state') not in ('done','error','paused'):continue
            key=(event.get('thread_id'),event.get('turn_id'));estimate=turn_report(event) if show_cost else None
            if estimate or not show_cost:priced.add(key)
            self.cost_events[key]=dict(event=event,report=estimate)
            while len(self.cost_events)>32:self.cost_events.pop(next(iter(self.cost_events)))
            if bubbling and key in priced:self.queue_turn_bubble(event,estimate)
        if not show_cost:return
        # Older plugins send no token counts: fall back to the balance difference.
        others=max(0,sum(1 for row in self.monitor.last.get('sessions',[]) if row.get('active'))-1)
        report=self.turn_cost.observe(status,self.quota_data,others,skip=priced)
        now=time.monotonic(); source=report or self.turn_cost.pending
        # The completion waits briefly so the amount can start together with it.
        if source and floating and self.notifications and source['ended']!=self.cost_hold_for:
            self.cost_hold_for=source['ended']; self.cost_hold_until=now+HOLD_SECONDS
        if not report:return
        self.daily.add_cost(report['ended'],report['amount'])
        entry=self.cost_events.get(report.get('key'))
        if bubbling:self.queue_turn_bubble(entry['event'] if entry else None,report)
        if floating and now<self.cost_hold_until:self.cost_float_report=report
        self.cost_hold_until=0

    def turn_lines(self,event,report,compact):
        """The amount and the time taken, in the order and with the parts chosen in the settings."""
        from .turn_cost import money
        from .daily_recap import duration_text
        o=self.options;lines=[]
        for kind in o['turn_cost_order'].split(','):
            if kind=='cost' and o['turn_cost_show_cost'] and report:
                lines.append(('-'+money(report) if compact else ('大约用了 ' if report.get('estimate') else '用了 ')+money(report),'cost'))
            if kind=='time' and o['turn_cost_show_time'] and event:
                started,ended=event.get('started'),event.get('ended')
                if isinstance(started,(int,float)) and isinstance(ended,(int,float)) and ended>=started:
                    lines.append(('用时 '+duration_text(ended-started,compact),'time'))
        return lines

    def queue_turn_bubble(self,event,report):
        lines=self.turn_lines(event,report,False)
        if not lines:return
        text='这一轮'+'，'.join(line for line,kind in lines)
        if report and report.get('shared'):text+='\n期间还有其他任务在跑，这是合计。'
        self.cost_queue.append(text)

    def play_cost_float(self,event):
        entry=self.cost_events.pop((event.get('thread_id'),event.get('turn_id')),None)
        balance,self.cost_float_report=self.cost_float_report,None
        report=(entry or {}).get('report') or balance
        if self.options['celebrate_done'] and event.get('state')=='done' and self.isVisible():self.confetti.burst()
        if self.options['turn_cost_style'] not in ('float','both') or not self.isVisible():return
        lines=self.turn_lines(event,report,True)
        if lines:self.cost_float.play(lines)

    def slow_tick(self):
        self.fullscreen_guard.check();self.rest_reminder.check();self.edge_dock.update();self.slow_count+=1
        if not self.offline and self.slow_count%60==15:self.show_due_recap()

    def show_due_recap(self):
        if not self.options['daily_recap']:return
        text=self.daily.due()
        if text:self.cost_queue.append((text,14))

    def show_today_recap(self):
        self.cost_queue.append((self.daily.today(),12))

    def cost_float_anchor(self,height):
        """Where the bottom of the text starts, centred on the pet, for the chosen preset."""
        from .cost_float import INSIDE_MARGIN
        rect=self.pet_rect; s=self.scale_factor; preset=self.options['turn_cost_anchor']
        if preset=='above':y=rect.top()*s
        elif preset=='inside':y=(rect.top()+rect.height()*INSIDE_MARGIN)*s+height
        else:y=rect.bottom()*s
        point=self.mapToGlobal(QPoint(round(rect.center().x()*s),round(y)))
        return point.x(),point.y()

    def set_cost_float_anchor(self,preset):
        # A preset is an exact, symmetric position: any dragged adjustment is cleared.
        self.set_option('turn_cost_anchor',preset); self.set_cost_float_offset(0,0)
        placer=self.cost_float_placer
        if placer and placer.isVisible():placer.sync()

    def cost_float_position(self,size,rise,progress):
        from .cost_float import place
        a=self.screen_area(); s=self.scale_factor
        offset=round(self.options['turn_cost_offset_x']*s),round(self.options['turn_cost_offset_y']*s)
        return place(self.cost_float_anchor(size[1]),size,offset,(a.left(),a.top(),a.right(),a.bottom()),rise,progress)

    def cost_float_offset_for(self,x,y,width,height):
        from .cost_float import clamp_offset
        ax,ay=self.cost_float_anchor(height); s=self.scale_factor
        return clamp_offset((x+width//2-ax)/s,(y+height-ay)/s)

    def set_cost_float_offset(self,dx,dy,save=True):
        if save:
            self.set_option('turn_cost_offset_x',dx); return self.set_option('turn_cost_offset_y',dy)
        self.options['turn_cost_offset_x']=dx; self.options['turn_cost_offset_y']=dy

    def toggle_cost_float_placer(self):
        from .cost_float import CostFloatPlacer
        if self.cost_float_placer is None:self.cost_float_placer=CostFloatPlacer(self)
        placer=self.cost_float_placer
        if placer.isVisible():placer.hide()
        else:placer.sync();placer.show()

    def present_turn_cost(self,now):
        if self.cost_text and now>=self.cost_until:
            self.cost_text='';self.update_layout();self.edge_dock.tuck_later()
        # Wait for the completion line so the cost never covers a subtitle.
        if self.cost_queue and not self.cost_text and not self.notification and not self.voice.busy and self.controller.owner!='preview':
            item=self.cost_queue.pop(0); text,seconds=item if isinstance(item,tuple) else (item,8)
            self.cost_text=text;self.cost_until=now+seconds;self.edge_dock.reveal();self.update_layout()

    def quota_label(self,compact=False):
        from .bridge import balance_label
        return balance_label(self.quota_data,compact)

    def quota_details(self):
        if not self.options['show_quota']: return ''
        return '*表示额度未更新\n拖动余额框修改大小\n点击余额框刷新余额'

    def bubble_text(self):
        if hasattr(self,'bubble_window') and self.bubble_window.edge_resize.active: return self.bubble_window.edge_resize.text
        if self.presentation_previews: return '这是气泡宽度预览。\n拖动左右边缘试试看，长台词会自动换行。'
        if self.cost_text: return self.cost_text
        b=self.binding(self.state)
        if self.voice_bubble():
            paired=clip_bubble_text(self.voice.selected_clip)
            if paired: return self.format_bubble(paired)
        if b['bubble_mode'] in ('audio','off'): return ''
        if self.preview_id and self.override_text: return self.override_text
        if b['bubble_mode']=='custom':
            return self.format_bubble(b['bubble_text'])
        if self.override: return STATES[self.state][1]
        if self.live_status.get('stale'): return STATES['unknown'][1]
        note=self.live_status.get('message','')
        if self.show_notes and note and self.state in ('reading','writing','working','thinking','waiting'):
            return note
        return STATES.get(self.state,STATES['idle'])[1]

    def format_bubble(self,text):
        context=self.notification or self.live_status
        for key,value in {'state':self.state_title(self.bubble_state()),'quota':self.quota_label(),'task':context.get('title',''),'progress':context.get('message','')}.items(): text=text.replace('{'+key+'}',value)
        return text

    def event(self,event):
        if event.type()==QEvent.Type.ToolTip:
            self.setToolTip(self.quota_details())
        return super().event(event)

    def mousePressEvent(self, event):
        self.quota_press=None; self.quota_click_cancelled=False
        if self.quota_resize.begin(event,self.quota_hit_rect(),self.quota_base_width*self.scale_factor):
            self.drag_offset=None; return
        if event.button()==Qt.MouseButton.LeftButton and self.quota_hit_rect().contains(event.position()):
            self.hover_timer.stop(); self.click_timer.stop(); self.drag_offset=None
            self.quota_press=event.globalPosition(); event.accept(); return
        if self.locked: event.accept(); return
        if event.button()==Qt.MouseButton.LeftButton:
            if not self.pet_rect.contains(event.position()/self.scale_factor): event.accept(); return
            self.hover_timer.stop(); self.click_timer.stop(); self.ignore_release=False
            self.drag_offset=event.globalPosition().toPoint()-self.pos(); self.drag_origin=event.globalPosition().toPoint(); self.dragged=False

    def mouseMoveEvent(self, event):
        self.lock_button.refresh_visibility()
        self.pointer_mode.refresh()
        self.update_quota_cursor(event.position())
        if self.quota_press is not None:
            if (event.globalPosition()-self.quota_press).manhattanLength()>QApplication.startDragDistance(): self.quota_click_cancelled=True
            event.accept(); return
        if self.locked: event.accept(); return
        if self.quota_resize.move(event,self.quota_hit_rect()): return
        self.update_quota_cursor(event.position())
        if self.drag_offset is not None and event.buttons()&Qt.MouseButton.LeftButton:
            if (event.globalPosition().toPoint()-self.drag_origin).manhattanLength()>6:
                if not self.dragged: self.edge_dock.undock(); self.react('drag')
                self.dragged=True; self.move(event.globalPosition().toPoint()-self.drag_offset)
        elif not self.hovered and not self.hover_timer.isActive(): self.hover_timer.start(1000)

    def mouseReleaseEvent(self, event):
        if self.quota_resize.finish(event): return
        if event.button()==Qt.MouseButton.LeftButton and self.quota_press is not None:
            moved=(event.globalPosition()-self.quota_press).manhattanLength()>QApplication.startDragDistance()
            refresh=not moved and not self.quota_click_cancelled and self.quota_hit_rect().contains(event.position())
            self.quota_press=None
            if refresh: self.refresh_quota()
            event.accept(); return
        if self.locked: event.accept(); return
        if event.button()!=Qt.MouseButton.LeftButton: return
        if self.ignore_release:
            self.ignore_release=False; self.drag_offset=None; return
        if self.dragged:
            area=(QApplication.screenAt(QCursor.pos()) or self.screen()).availableGeometry()
            if self.edge_dock.try_dock(area): target=self.edge_dock.target(False); self.settings['position']=[target.x(),target.y()]
            else: self.clamp_position(); self.settings['position']=[self.x(),self.y()]
            self.settings['dock']=self.edge_dock.state(); self.save_settings()
            self.react('drop')
        else:
            local=event.position()/self.scale_factor
            if self.pet_rect.contains(local): self.click_timer.start(QApplication.doubleClickInterval()+20)
        self.drag_offset=None

    def mouseDoubleClickEvent(self, event):
        if self.locked: event.accept(); return
        if event.button()==Qt.MouseButton.LeftButton and self.pet_rect.contains(event.position()/self.scale_factor):
            self.click_timer.stop(); self.ignore_release=True
            self.hover_timer.stop(); self.react('doubleclick')

    def wheelEvent(self,event):
        if self.locked: event.accept(); return
        if event.modifiers()&Qt.KeyboardModifier.ControlModifier and event.angleDelta().y():
            self.hover_timer.stop(); self.click_timer.stop()
            self.set_scale(round((self.requested_scale+event.angleDelta().y()/120*.05)*100)/100)
            event.accept()
        else: event.ignore()

    def enterEvent(self,event):
        self.lock_button.refresh_visibility()
        self.update_quota_cursor()
        if not self.locked: self.hover_timer.start(1000)
        self.edge_dock.hover_in()
        super().enterEvent(event)

    def leaveEvent(self,event):
        if self.quota_resize.active: super().leaveEvent(event); return
        self.unsetCursor()
        self.hover_timer.stop(); self.hovered=False
        if self.override=='hover': self.clear_override()
        self.edge_dock.hover_out()
        super().leaveEvent(event)

    def hover_react(self):
        if self.locked or self.lock_button.geometry().contains(self.mapFromGlobal(QCursor.pos())): return
        local=self.mapFromGlobal(QCursor.pos())/self.scale_factor
        if not self.quota_resize.active and self.drag_offset is None and not self.override and not self.hovered and self.underMouse() and self.pet_rect.contains(local):
            self.hovered=True; self.react('hover')

    @property
    def locked(self): return self.options.get('interaction_locked',False)

    def context_menu(self,tray=False):
        menu=QMenu(self)
        if tray: menu.addAction('显示 / 隐藏',self.toggle_visible)
        else:
            for label,state in [('摸摸头','pet'),('递一杯奶茶','feed')]:
                action=menu.addAction(label,lambda checked=False,state=state:self.react(state)); action.setEnabled(not self.locked)
        menu.addAction('设置…',self.open_preferences)
        fullscreen_action=menu.addAction(self.fullscreen_label(),lambda:self.set_option('fullscreen_hide',not self.options['fullscreen_hide']))
        menu.addAction('今日小结',self.show_today_recap)
        for label,key in [('安静陪伴（静音）','audio_muted')]:
            action=menu.addAction(label); action.setCheckable(True); action.setChecked(self.options[key])
            action.triggered.connect(lambda checked,key=key:self.set_option(key,checked))
        def refresh():
            balance_action.setText('隐藏余额框' if self.options['show_quota'] else '显示余额框')
            fullscreen_action.setText(self.fullscreen_label())
            for action in menu.actions():
                if action.text()=='安静陪伴（静音）': action.setChecked(self.options['audio_muted'])
                elif action.text() in ('摸摸头','递一杯奶茶'): action.setEnabled(not self.locked)
        menu.aboutToShow.connect(refresh)
        menu.addSeparator()
        menu.addAction('刷新余额',self.refresh_quota)
        balance_action=menu.addAction('隐藏余额框' if self.options['show_quota'] else '显示余额框',
            lambda:self.set_option('show_quota',not self.options['show_quota']))
        menu.addSeparator()
        if not tray: menu.addAction('暂时收起（托盘恢复）',self.hide)
        menu.addAction('关闭守岸人',self.shutdown); return menu

    def fullscreen_label(self):
        return '点击关闭全屏时隐藏' if self.options['fullscreen_hide'] else '点击开启全屏时隐藏'

    def contextMenuEvent(self,event):
        menu=self.context_menu(); menu.exec(event.globalPos()); menu.deleteLater()

    def react(self,state,duration=None):
        if self.locked: return
        self.preview_id=None; self.override_text=''; self.controller.enter(state,time.monotonic(),'interaction',hard_limit=duration); self.tick()

    def preview(self,aid):
        self.override='pet'; self.preview_id=aid; self.override_text=ASSETS[aid]['name'].removesuffix('.gif')+' · 原始表情预览'
        self.controller.enter('pet',time.monotonic(),'preview',hard_limit=max(5,ASSETS[aid]['duration_ms']/1000+2)); self.tick()
        self.show()

    def clear_override(self):
        self.override=None; self.preview_id=None; self.override_text=''; self.controller.resume(time.monotonic()); self.tick()

    def preview_binding(self,state,clip=None):
        self.preview_audio_clip=clip
        try:
            self.preview_id=None; self.override_text=''; self.controller.enter(state,time.monotonic(),'preview'); self.tick(); self.show(); self.raise_()
        finally: self.preview_audio_clip=None

    def open_bindings(self): self.open_preferences('交互工作室')

    def open_preferences(self,page=None):
        if not self.preferences:
            self.preferences=Preferences(self,CATALOG,ASSETS,ROOT); self.binding_editor=self.preferences.editor
        self.preferences.refresh_controls()
        if isinstance(page,str): self.preferences.select_page(page)
        self.preferences.show(); self.preferences.raise_(); self.preferences.activateWindow()

    def open_size(self): self.open_preferences('字体与大小')

    def audio_directory(self):
        path=pathlib.Path(self.options['audio_directory'] or 'audio'); return path if path.is_absolute() else ROOT/path

    def set_option(self,key,value):
        if key=='show_quota' and value is False:
            self.quota_press=None; self.quota_click_cancelled=True
            self.quota_resize.finish(); self.unsetCursor()
        if key=='launch_with_deepseek' and not self.offline:
            from .startup import configure
            configure(bool(value),ROOT)
        self.options[key]=value; self.settings['appearance']=dict(self.options); self.options=appearance(self.settings)
        ok=self.save_settings(); self.apply_style(); self.update_layout(); self.update()
        if key=='tray_icon_style':self.apply_icon()
        if (key=='audio_enabled' and not value) or (key=='audio_muted' and value): self.voice.stop()
        if key=='interaction_locked' and value: self.cancel_pointer_interaction()
        if key=='edge_dock' and not value and self.edge_dock.docked:
            self.edge_dock.undock(); self.clamp_position(); self.settings['dock']=None; self.settings['position']=[self.x(),self.y()]; self.save_settings()
        if key=='fullscreen_hide': self.fullscreen_guard.check()
        if key in ('rest_reminder','rest_interval_minutes'): self.rest_reminder.options_changed()
        if key=='rest_snooze_minutes': self.rest_reminder.snooze_changed()
        if key in ('audio_muted','interaction_locked','fullscreen_hide','rest_reminder') and self.preferences: self.preferences.refresh_controls()
        if key.startswith('deepseek'): self.refresh_event.set()
        if key in ('check_updates_periodic','update_interval_hours','ignored_update_version','update_snoozed_date'):
            self.updates.reconfigure()
        return ok

    def quota_hit_rect(self):
        if not self.options['show_quota']: return QRectF()
        r=self.quota_rect; s=self.scale_factor
        return QRectF(r.x()*s,r.y()*s,r.width()*s,r.height()*s)

    def set_presentation_size(self,key,value,save=True):
        if key not in ('bubble_width_ratio','quota_scale'): raise ValueError('Unknown size control')
        self.options[key]=round(value,4); self.settings['appearance']=dict(self.options); self.options=appearance(self.settings)
        self.update_layout(); self.update()
        return self.save_settings() if save else True

    def set_bubble_preview(self,source,on):
        if on: self.presentation_previews.add(source)
        else: self.presentation_previews.discard(source)
        self.update_layout(); self.update()
        if on: self.show()

    def apply_icon(self):
        from .app_icons import application_icon
        icon=application_icon(ROOT,self.options['tray_icon_style'])
        if icon.isNull():return
        self.icon=icon;QApplication.instance().setWindowIcon(icon);self.tray.setIcon(icon)
        for window in QApplication.topLevelWidgets():window.setWindowIcon(icon)

    def apply_style(self):
        QApplication.instance().setFont(font(self.options['font_family'],self.options['ui_font_size']))
        for dialog in (self.panel,self.binding_editor,self.preferences,self.size_dialog):
            if dialog: dialog.apply_style()

    def apply_settings(self,data):
        data=migrate_settings(data)
        self.voice.stop()
        if not self.offline:
            from .startup import configure
            configure(appearance(data)['launch_with_deepseek'],ROOT)
        self.settings=data; self.pack=data.get('pack','163')
        if self.pack not in PACKS: self.pack='163'
        self.refresh_assets()
        self.bindings=BindingMap(PACKS,ASSETS,ONESHOT,data.get('bindings'),baseline=default_bindings(ROOT)); self.options=appearance(data); self.show_notes=bool(data.get('show_notes',True))
        if self.locked: self.cancel_pointer_interaction()
        self.requested_scale=normalize_scale(data.get('scale',1)); self.scale_factor=self.requested_scale
        self.font_families=load_fonts(ROOT); self.monitor.selected=data.get('thread','auto'); self.cache.clear(); self.animation=self.get_animation(self.binding(self.state)['asset']); self.animation_id=self.binding(self.state)['asset']
        self.set_top(bool(data.get('on_top',True))); self.save_settings(); self.clear_override(); self.apply_style(); self.apply_icon(); self.update_layout(); self.refresh_quota()
        if self.binding_editor: self.binding_editor.populate_gallery(); self.binding_editor.load_selection()

    def set_pack(self,pack):
        self.pack=pack; self.settings['pack']=pack; self.save_settings(); self.clear_override()
        if self.binding_editor: self.binding_editor.load_selection()
    def cancel_pointer_interaction(self):
        self.hover_timer.stop(); self.click_timer.stop(); self.hovered=False
        self.quota_press=None
        self.drag_offset=None; self.drag_origin=None; self.dragged=False; self.ignore_release=True
        self.quota_resize.finish(); self.bubble_window.edge_resize.finish(); self.unsetCursor(); self.bubble_window.unsetCursor()
        if self.controller.owner=='interaction': self.clear_override()

    def set_notes(self,value): self.show_notes=value; self.settings['show_notes']=value; self.save_settings(); self.update()
    def set_scale(self,value):
        self.requested_scale=normalize_scale(value); self.update_layout(); self.clamp_position(); self.update()
        self.settings['position']=[self.x(),self.y()]; return self.save_settings()
    def set_top(self,value):
        self.on_top=value; self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,value); self.bubble_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,value); self.show(); self.settings['on_top']=value; self.save_settings()

    def moveEvent(self,event):
        if hasattr(self,'bubble_window'):
            self.update_bubble()
            if getattr(self,'position_ready',False) and self.screen_area()!=getattr(self,'layout_area',None): QTimer.singleShot(0,self.update_layout)
        super().moveEvent(event)
    def showEvent(self,event):
        self.update_bubble(); super().showEvent(event)
    def hideEvent(self,event):
        self.quota_resize.finish()
        self.bubble_window.hide(); super().hideEvent(event)

    def screen_area(self):
        dock=getattr(self,'edge_dock',None)
        if dock and dock.docked: return dock.area
        screen=QApplication.screenAt(self.frameGeometry().center()) or QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def clamp_position(self):
        dock=getattr(self,'edge_dock',None)
        if dock and dock.docked: dock.place(dock.tucked,animate=False); return
        area=self.screen_area()
        self.move(max(area.left(),min(self.x(),area.right()-self.width()+1)),max(area.top(),min(self.y(),area.bottom()-self.height()+1)))

    def save_settings(self):
        try:
            self.settings['schema_version']=7; self.settings['bindings']=self.bindings.to_dict(); self.settings['appearance']=dict(self.options); self.settings['scale']=self.requested_scale
            save_atomic(SETTINGS,self.settings); return True
        except OSError: return False

    def open_panel(self): self.open_preferences()

    def open_deepseek(self):
        import subprocess
        from .bridge import discover_deepseek
        executable=discover_deepseek(self.options['deepseek_executable'])
        if executable: subprocess.Popen([executable])

    def toggle_visible(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.raise_()

    def shutdown(self):
        self.updates.close()
        self.stop_event.set(); self.refresh_event.set(); self.timer.stop(); self.tray.hide()
        self.voice.stop(); self.save_settings()
        self.rate_client.close(); QApplication.instance().exit(0)

    def closeEvent(self,event):
        event.ignore(); self.hide()

    def write_health(self):
        data=dict(version=VERSION,pid=os.getpid(),updated_at=time.time(),state=self.state,visible=self.isVisible(),quota_source=self.quota_data.get('source'),quota_updated_at=self.quota_data.get('updated_at'),quota_available=bool(self.quota_data.get('wallets')),rate_error=self.quota_data.get('error'),thread_count=len(self.thread_list),animation=self.animation_id,custom_bindings=len(self.bindings.overrides),font=self.options['bubble_font_family'])
        data.update(audio_muted=self.options['audio_muted'],interaction_locked=self.locked,quota_refresh_status=self.quota_refresh.label())
        data['update_token']=os.environ.get('SHOREKEEPER_UPDATE_TOKEN','')
        data.update(update_status=self.updates.status,update_check_pending=self.updates.busy,client_seen=self.client_lifetime.seen,client_exit_pending=self.client_lifetime.missing_since is not None)
        data.update(follow=self.monitor.selected,thread_id=self.live_status.get('thread_id'),live_state=self.live_status.get('state'),owner=self.controller.owner,scale=self.requested_scale,display_scale=self.scale_factor,window_size=[self.width(),self.height()])
        try:
            (ROOT/'runtime.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError: pass

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--preview',action='store_true'); parser.add_argument('--smoke-test',action='store_true'); parser.add_argument('--capture-after',type=int,default=0); parser.add_argument('--bindings',action='store_true'); parser.add_argument('--settings',action='store_true'); parser.add_argument('--verify-package',action='store_true'); parser.add_argument('--verify-update-check',action='store_true'); parser.add_argument('--verify-connection',action='store_true'); args=parser.parse_args()
    if args.verify_update_check:
        from .updates import check_latest
        result=check_latest(source=appearance(load_settings())['update_source'])
        report=dict(ok=result.status!='unavailable',status=result.status,source=result.source,latest=result.version,url=result.url,version=VERSION,frozen=bool(getattr(sys,'frozen',False)))
        (ROOT/'update-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        return 0 if report['ok'] else 1
    if args.verify_connection:
        from .bridge import discover_deepseek
        opts=appearance(load_settings()); monitor=Monitor(opts['deepseek_home'] or DSH_HOME); client=RateClient(opts['deepseek_executable'],opts['deepseek_home'])
        try:
            status=monitor.poll(); quota=client.read()
            report=dict(version=VERSION,frozen=bool(getattr(sys,'frozen',False)),deepseek_detected=bool(discover_deepseek(opts['deepseek_executable'])),quota_available=bool(quota.get('wallets')),thread_count=len(monitor.threads),state=status['state'],follow=monitor.selected)
            (ROOT/'connection-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            return 0 if report['deepseek_detected'] and report['quota_available'] else 1
        finally: client.close()
    app=QApplication(sys.argv); app.setApplicationName('Shorekeeper'); app.setQuitOnLastWindowClosed(False)
    lock=QLockFile(str(ROOT/'pet.lock')); lock.setStaleLockTime(0)
    if not args.preview and not args.smoke_test and not args.verify_package and not lock.tryLock(100): return 0
    if not args.preview and not args.smoke_test and not args.verify_package:
        from .startup import configure
        if not os.environ.get('SHOREKEEPER_UPDATE_TOKEN') and appearance(load_settings())['launch_with_deepseek']:
            try:configure(True,ROOT)
            except OSError:pass
    pet=Pet(offline=args.preview or args.smoke_test or args.verify_package); pet.show()
    if not pet.offline and getattr(sys,'frozen',False):
        from .shortcuts import ensure_first_launch_shortcut
        threading.Thread(target=ensure_first_launch_shortcut,args=(ROOT,),daemon=True).start()
    if args.bindings: pet.open_bindings()
    if args.settings: pet.open_preferences()
    health_timer=QTimer(); health_timer.timeout.connect(pet.write_health)
    if os.environ.get('SHOREKEEPER_UPDATE_TOKEN'): health_timer.start(1000)
    elif not args.preview and not args.smoke_test: health_timer.start(5000)
    if args.capture_after:
        (ROOT/'qa').mkdir(exist_ok=True)
        QTimer.singleShot(args.capture_after*1000,lambda:pet.grab().save(str(ROOT/'qa/live-preview.png')))
    if args.verify_package:
        def verify():
            import copy
            saved_settings=copy.deepcopy(pet.settings)
            code=0
            try:
                pet.options['volume']=0
                pet.preview_binding('pet'); pet.open_bindings(); pet.open_preferences(); pet.open_size(); pet.write_health()
                pet.voice.stop()
                import tempfile
                from .audio_convert import verify_decoder
                from .pcm_player import verify_output
                with tempfile.TemporaryDirectory() as directory:
                    decoder_ok=verify_decoder(directory); output_ok=verify_output(directory)
                bubble_bounds=pet.bubble_window.width()<=pet.screen_area().width()
                audio_mode=pet.binding_editor.controls['bubble_mode'].findText('自定义音频+字幕')>=0
                resize_controls=all(key in pet.preferences.presentation_control.controls for key in ('bubble_width_ratio','quota_scale'))
                from .startup import deepseek_processes
                frequency_controls=all(pet.binding_editor.controls['audio_policy'].findData(mode)>=0 for mode in ('entry','session','occasional','turn'))
                startup_control='launch_with_deepseek' in pet.preferences.controls
                update_controls='check_updates_on_start' in pet.preferences.controls and not pet.updates.timer.isActive()
                unified_settings=pet.binding_editor.window() is pet.preferences and not pet.binding_editor.isWindow()
                safety_controls=all(key in pet.preferences.controls for key in ('audio_muted','interaction_locked'))
                from .settings_checks import verify_controls
                interaction_checks=verify_controls(pet)
                desktop_detected=bool(deepseek_processes())
                report=dict(ok=all(interaction_checks.values()) and unified_settings and safety_controls and len(pet.font_families)>=2 and decoder_ok and output_ok and bubble_bounds and audio_mode and resize_controls and frequency_controls and startup_control and update_controls,unified_settings=unified_settings,safety_controls=safety_controls,update_controls=update_controls,audio_decoder=decoder_ok,audio_output=output_ok,bubble_bounds=bubble_bounds,audio_subtitle_mode=audio_mode,resize_controls=resize_controls,voice_frequency_controls=frequency_controls,startup_control=startup_control,desktop_detected=desktop_detected,version=VERSION,fonts=pet.font_families,assets=len(ASSETS),bindings=len(pet.bindings.overrides),root=str(ROOT),frozen=bool(getattr(sys,'frozen',False)),scale=pet.requested_scale,size_control_percent=pet.preferences.size_control.percent.value())
                report.update(interaction_checks)
                (ROOT/'package-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            except Exception:
                import traceback
                (ROOT/'startup-error.log').write_text(traceback.format_exc(),encoding='utf8'); code=1
            finally:
                pet.timer.stop(); pet.voice.stop()
                save_atomic(SETTINGS,saved_settings,backup=False)
                app.exit(code)
        QTimer.singleShot(500,verify)
    if args.smoke_test:
        (ROOT/'qa').mkdir(exist_ok=True)
        pet.live_status=dict(state='working',message='正在整理素材并检查动画循环。',title='守岸人桌宠',stale=False)
        pet.quota_data=dict(windows=[dict(remaining=81,label='每周',name='deepseek',resets_at=1791655436)],updated_at=time.time(),source='demo',wallets=[dict(currency='CNY',balance='12.34',bonus=False)])
        def capture():
            pet.transition_old=None; pet.tick(); pet.grab().save(str(ROOT/'qa/desktop-preview.png'))
            pet.open_panel(); pet.preferences.grab().save(str(ROOT/'qa/panel-preview.png')); app.exit(0)
        QTimer.singleShot(700,capture)
    app.aboutToQuit.connect(pet.updates.close)
    app.aboutToQuit.connect(pet.stop_event.set)
    app.aboutToQuit.connect(pet.refresh_event.set)
    app.aboutToQuit.connect(pet.rate_client.close)
    app.aboutToQuit.connect(pet.voice.stop)
    return app.exec()

if __name__=='__main__': sys.exit(main())
