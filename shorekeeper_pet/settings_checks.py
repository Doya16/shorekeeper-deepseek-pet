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
        return dict(native_input_style_check=native_input,quota_click_check=quota_click,hover_fade_control=fade_control,compact_menu_check=menu_check,quota_tooltip_check=tooltip_check,lock_button_check=direct_lock,lock_pointer_check=locked,unlock_check=unlocked,mute_playback_check=muted)
    finally:
        pet.voice.stop();pet.options=original;pet.save_settings();pet.update_layout();pet.preferences.refresh_controls()
