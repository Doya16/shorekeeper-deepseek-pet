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
    status=Signal(dict)
    quota=Signal(dict)
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
        self.voice=VoicePlayer(ROOT,self); self.preview_audio_clip=None
        self.bubble_window=SpeechBubble(self); self.voice.changed.connect(self.on_voice_changed)
        self.worker.status.connect(self.on_status); self.worker.quota.connect(self.on_quota); self.worker.threads.connect(self.on_threads)
        self.drag_offset=None; self.drag_origin=None; self.dragged=False
        self.hovered=False; self.ignore_release=False
        self.click_timer=QTimer(self); self.click_timer.setSingleShot(True); self.click_timer.timeout.connect(lambda:self.react('pet'))
        self.hover_timer=QTimer(self); self.hover_timer.setSingleShot(True); self.hover_timer.timeout.connect(self.hover_react)
        self.quota_press=None; self.quota_click_cancelled=False
        self.lock_button=LockButton(self)
        self.pointer_mode=PointerMode(self)
        icon_im=self.animation.frames[0].scaled(64,64,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        self.icon=QIcon(str(ROOT/'assets/shorekeeper.ico'))
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

    def watch_status(self):
        while not self.stop_event.is_set():
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
            self.refresh_event.clear()
            try:
                if (self.rate_client.executable,self.rate_client.deepseek_home)!=(self.options['deepseek_executable'],self.options['deepseek_home']):
                    self.rate_client.close(); self.rate_client=RateClient(self.options['deepseek_executable'],self.options['deepseek_home'])
                self.worker.quota.emit(self.rate_client.read())
            except Exception:
                self.worker.quota.emit(dict(error='刷新暂时失败，显示最近记录。'))
            self.refresh_event.wait(120)

    def refresh_quota(self):
        self.refresh_event.set()
        self.bubble_until=time.monotonic()+10

    def on_status(self, status):
        changed=status.get('state')!=self.live_status.get('state') or status.get('thread_id')!=self.live_status.get('thread_id')
        self.live_status=status
        for event in status.get('events',[]):
            identity=(event.get('state'),task_key(event) or (event.get('thread_id'),event.get('ended')))
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
        self.controller.set_live(state,key,time.monotonic()); self.tick(); self.update_layout()
        if changed:
            self.bubble_until=time.monotonic()+(20 if status.get('state') in ('done','error','waiting') else 10)
        if self.panel: self.panel.refresh()

    def on_quota(self, quota):
        # A slow cache read must never replace a newer live response.
        if quota.get('updated_at',0) and quota.get('updated_at',0)<self.quota_data.get('updated_at',0): return
        if 'windows' in quota: self.quota_data=quota
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
            self.notification=None; self.controller.resume(now)
        if not self.notification and self.notifications and not self.voice.busy and self.controller.owner!='preview' and self.drag_offset is None:
            self.notification=self.notifications.popleft()
            state=self.notification['state']; b=self.binding(state)
            duration=playback_seconds(b,*self.animation_duration(b['asset']))
            self.notification_until=now+max(1,duration or 6)
            self.preview_id=None; self.override_text=''
            self.controller.enter(state,now,'notification')
            self.bubble_until=self.notification_until
        if not self.notification: self.controller.tick(now)
        entered=self.controller.serial!=self.last_serial
        if entered:
            self.last_serial=self.controller.serial; self.state=self.controller.state; self.anim_start=self.controller.started
            if self.controller.owner=='live': self.override=None; self.preview_id=None; self.override_text=''
            else: self.override=self.state
        aid=self.preview_id or self.binding(self.state)['asset']
        self.switch_animation(aid)
        if entered:
            binding=self.binding(self.state)
            if self.controller.owner=='preview' and self.preview_audio_clip is not None:
                binding=dict(binding,audio_clips=[dict(self.preview_audio_clip,enabled=True)])
            self.voice.trigger(self.state,binding,self.options,preview=self.controller.owner=='preview',task=task_key(self.notification or self.live_status),notification=self.controller.owner=='notification'); self.update_layout()
        self.lock_button.refresh_visibility()
        self.pointer_mode.refresh()
        self.update_bubble()
        self.update()

    def quota_label(self,compact=False):
        from .bridge import balance_label
        return balance_label(self.quota_data,compact)

    def quota_details(self):
        return '*表示额度未更新\n拖动余额框修改大小\n点击余额框刷新余额'

    def bubble_text(self):
        if hasattr(self,'bubble_window') and self.bubble_window.edge_resize.active: return self.bubble_window.edge_resize.text
        if self.presentation_previews: return '这是气泡宽度预览。\n拖动左右边缘试试看，长台词会自动换行。'
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
        if self.quota_press is not None:
            if (event.globalPosition()-self.quota_press).manhattanLength()>QApplication.startDragDistance(): self.quota_click_cancelled=True
            event.accept(); return
        if self.locked: event.accept(); return
        if self.quota_resize.move(event,self.quota_hit_rect()): return
        if self.drag_offset is not None and event.buttons()&Qt.MouseButton.LeftButton:
            if (event.globalPosition().toPoint()-self.drag_origin).manhattanLength()>6:
                if not self.dragged: self.react('drag')
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
            self.clamp_position(); self.settings['position']=[self.x(),self.y()]; self.save_settings()
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
        if not self.locked: self.hover_timer.start(1000)
        super().enterEvent(event)

    def leaveEvent(self,event):
        if self.quota_resize.active: super().leaveEvent(event); return
        self.unsetCursor()
        self.hover_timer.stop(); self.hovered=False
        if self.override=='hover': self.clear_override()
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
        for label,key in [('安静陪伴（静音）','audio_muted')]:
            action=menu.addAction(label); action.setCheckable(True); action.setChecked(self.options[key])
            action.triggered.connect(lambda checked,key=key:self.set_option(key,checked))
        def refresh():
            for action in menu.actions():
                if action.text()=='安静陪伴（静音）': action.setChecked(self.options['audio_muted'])
                elif action.text() in ('摸摸头','递一杯奶茶'): action.setEnabled(not self.locked)
        menu.aboutToShow.connect(refresh)
        menu.addSeparator()
        menu.addAction('刷新余额',self.refresh_quota)
        menu.addSeparator()
        if not tray: menu.addAction('暂时收起（托盘恢复）',self.hide)
        menu.addAction('关闭守岸人',self.shutdown); return menu

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
        if key=='launch_with_deepseek' and not self.offline:
            from .startup import configure
            configure(bool(value),ROOT)
        self.options[key]=value; self.settings['appearance']=dict(self.options); self.options=appearance(self.settings)
        ok=self.save_settings(); self.apply_style(); self.update_layout(); self.update()
        if (key=='audio_enabled' and not value) or (key=='audio_muted' and value): self.voice.stop()
        if key=='interaction_locked' and value: self.cancel_pointer_interaction()
        if key in ('audio_muted','interaction_locked') and self.preferences: self.preferences.refresh_controls()
        if key.startswith('deepseek'): self.refresh_event.set()
        return ok

    def quota_hit_rect(self):
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
        self.set_top(bool(data.get('on_top',True))); self.save_settings(); self.clear_override(); self.apply_style(); self.update_layout(); self.refresh_quota()
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
        screen=QApplication.screenAt(self.frameGeometry().center()) or QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def clamp_position(self):
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
        data.update(audio_muted=self.options['audio_muted'],interaction_locked=self.locked)
        data.update(update_status=self.updates.status,update_check_pending=self.updates.busy)
        data.update(follow=self.monitor.selected,thread_id=self.live_status.get('thread_id'),live_state=self.live_status.get('state'),owner=self.controller.owner,scale=self.requested_scale,display_scale=self.scale_factor,window_size=[self.width(),self.height()])
        try:
            (ROOT/'runtime.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError: pass

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--preview',action='store_true'); parser.add_argument('--smoke-test',action='store_true'); parser.add_argument('--capture-after',type=int,default=0); parser.add_argument('--bindings',action='store_true'); parser.add_argument('--settings',action='store_true'); parser.add_argument('--verify-package',action='store_true'); parser.add_argument('--verify-update-check',action='store_true'); parser.add_argument('--verify-connection',action='store_true'); args=parser.parse_args()
    if args.verify_update_check:
        from .updates import check_latest
        result=check_latest()
        report=dict(ok=result.status!='unavailable',status=result.status,latest=result.version,url=result.url,version=VERSION,frozen=bool(getattr(sys,'frozen',False)))
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
        if appearance(load_settings())['launch_with_deepseek']:
            try:configure(True,ROOT)
            except OSError:pass
    pet=Pet(offline=args.preview or args.smoke_test or args.verify_package); pet.show()
    if args.bindings: pet.open_bindings()
    if args.settings: pet.open_preferences()
    health_timer=QTimer(); health_timer.timeout.connect(pet.write_health)
    if not args.preview and not args.smoke_test: health_timer.start(5000)
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
