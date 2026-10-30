"""Offline controls smoke check used by --verify-package in the frozen app."""
import copy,pathlib,tempfile,wave
from PySide6.QtCore import Qt,QEvent,QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


def verify_controls(pet):
    original=copy.deepcopy(pet.options)
    try:
        pet.set_option('interaction_locked',True)
        before=(pet.pos(),pet.controller.serial)
        point=pet.pet_rect.center()*pet.scale_factor
        for kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseMove,QEvent.Type.MouseButtonRelease,QEvent.Type.MouseButtonDblClick):
            event=QMouseEvent(kind,point,QPointF(pet.mapToGlobal(point.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(pet,event)
        locked=(pet.pos(),pet.controller.serial)==before and pet.drag_offset is None and not pet.click_timer.isActive()
        pet.set_option('interaction_locked',False);pet.react('pet')
        unlocked=pet.controller.owner=='interaction' and pet.state=='pet'
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'test.wav'
            with wave.open(str(path),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*800)
            pet.set_option('audio_muted',False)
            binding=dict(pet.binding('pet'),audio_clips=[{'file':str(path),'enabled':True}],audio_delay=20)
            started=pet.voice.trigger('pet',binding,pet.options,preview=True)
            pet.set_option('audio_muted',True)
            muted=started and not pet.voice.busy and not pet.voice.pending.isActive() and pet.voice.queued is None and not pet.voice.trigger('pet',binding,pet.options,preview=True)
        pet.set_option('interaction_locked',False);pet.lock_button.click()
        direct_lock=pet.locked and pet.lock_button.toolTip()=='点击解锁'
        pet.lock_button.click()
        direct_lock=direct_lock and not pet.locked and pet.lock_button.toolTip()=='点击锁定'
        # Run the quota click path in the actual frozen executable, including lock.
        pet.set_option('interaction_locked',True);pet.refresh_event.clear()
        point=pet.quota_hit_rect().center()
        for kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease):
            QApplication.sendEvent(pet,QMouseEvent(kind,point,QPointF(pet.mapToGlobal(point.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier))
        quota_click=pet.refresh_event.is_set() and pet.quota_press is None
        fade_control='locked_hover_transparency' in pet.preferences.controls
        menu=[a.text() for a in pet.context_menu().actions()]
        menu_check='关闭守岸人' in menu and '锁定桌宠' not in menu and '退出守岸人' not in menu
        tip=pet.quota_details()
        tooltip_check=all(text in tip for text in ('*表示额度未更新','拖动余额框修改大小','点击余额框刷新余额')) and 'credits' not in tip and '最近读取' not in tip
        from .pointer_mode import set_input_transparent
        import sys,ctypes
        native_input=True
        if sys.platform=='win32':
            get=ctypes.windll.user32.GetWindowLongPtrW
            get.argtypes=[ctypes.c_void_p,ctypes.c_int];get.restype=ctypes.c_ssize_t
            for transparent in (True,False,True,False):
                set_input_transparent(pet,transparent)
                style=get(int(pet.winId()),-20)
                native_input=native_input and bool(style&0x80000) and bool(style&0x20)==transparent
        from .app_icons import application_icon
        from .paths import ROOT
        clean=application_icon(ROOT,'clean').pixmap(32,32).toImage()
        badged=application_icon(ROOT,'badged').pixmap(32,32).toImage()
        icon_check=not clean.isNull() and not badged.isNull() and clean!=badged
        control=pet.preferences.controls['tray_icon_style']
        for style,expected in (('clean',clean),('badged',badged)):
            control.setCurrentIndex(control.findData(style))
            icon_check=icon_check and pet.tray.icon().pixmap(32,32).toImage()==expected and pet.preferences.windowIcon().pixmap(32,32).toImage()==expected
        from .shortcuts import ensure_first_launch_shortcut,create_desktop_shortcut,marker_path
        with tempfile.TemporaryDirectory(prefix='shortcut-check-') as directory:
            directory=pathlib.Path(directory);desktop=directory/'Desktop 中文';desktop.mkdir();state=directory/'state'
            link=ensure_first_launch_shortcut(ROOT,frozen=True,destination=desktop,state_root=state)
            shortcut_check=link is not None and link.is_file() and marker_path(ROOT,state).is_file()
            if link:
                link.unlink()
                shortcut_check=shortcut_check and ensure_first_launch_shortcut(ROOT,frozen=True,destination=desktop,state_root=state) is None and not link.exists()
                shortcut_check=shortcut_check and create_desktop_shortcut(ROOT,desktop,state_root=state).is_file()
        from .client_lifetime import ClientLifetime
        from .process_scan import process_tree
        import subprocess,os,time
        probe=pathlib.Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/ping.exe'
        # A private native child exercises process start/exit without closing
        # the user's real client or interrupting its active conversations.
        child=subprocess.Popen([str(probe),'-t','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            tree=process_tree(('ping.exe',),lambda path:pathlib.Path(path)==probe)
            tree={pid:parent for pid,parent in tree.items() if pid==child.pid}
            guard=ClientLifetime();lifecycle_check=child.pid in tree and not guard.observe(tree,0) and not guard.observe(tree,20)
            child.terminate();child.wait(timeout=5)
            tree=process_tree(('ping.exe',),lambda path:pathlib.Path(path)==probe)
            tree={pid:parent for pid,parent in tree.items() if pid==child.pid}
            lifecycle_check=lifecycle_check and not tree and not guard.observe(tree,22) and guard.observe(tree,30)
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=5)
        exit_key=next(key for key in ('exit_with_codex','exit_with_deepseek') if key in pet.options)
        # Deliver the same Qt signal as the worker. Capture shutdown here so
        # the remainder of this independent package verification can finish.
        original_shutdown=pet.shutdown;original_offline=pet.offline;called=[]
        try:
            pet.shutdown=lambda:called.append(True);pet.offline=False
            pet.options[exit_key]=False;pet.worker.client_exited.emit();lifecycle_check=lifecycle_check and not called
            pet.options[exit_key]=True;pet.worker.client_exited.emit();lifecycle_check=lifecycle_check and called==[True]
        finally:pet.shutdown=original_shutdown;pet.offline=original_offline
        from .updates import check_latest,ReleaseAsset,source_url,MIRROR
        from .paths import UPDATE_REPOSITORY
        import json
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return json.dumps(dict(tag_name='v9.9.9',draft=False,prerelease=False,body='test')).encode()
        requests=[]
        def read(request,timeout):
            requests.append(request.full_url)
            if len(requests)==1:raise TimeoutError()
            return Response()
        result=check_latest(opener=read)
        source_check=result.status=='available' and result.source=='mirror' and len(requests)==2
        control=pet.preferences.controls['update_source']
        control.setCurrentIndex(control.findData('mirror'))
        source_check=source_check and pet.options['update_source']=='mirror' and exit_key in pet.preferences.controls
        return dict(client_lifecycle_check=lifecycle_check,update_sources_check=source_check,icon_switch_check=icon_check,desktop_shortcut_check=shortcut_check,native_input_style_check=native_input,quota_click_check=quota_click,hover_fade_control=fade_control,compact_menu_check=menu_check,quota_tooltip_check=tooltip_check,lock_button_check=direct_lock,lock_pointer_check=locked,unlock_check=unlocked,mute_playback_check=muted)
    finally:
        pet.voice.stop();pet.options=original;pet.apply_icon();pet.save_settings();pet.update_layout();pet.preferences.refresh_controls()
