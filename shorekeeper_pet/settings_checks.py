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
        return dict(lock_pointer_check=locked,unlock_check=unlocked,mute_playback_check=muted)
    finally:
        pet.voice.stop();pet.options=original;pet.save_settings();pet.preferences.refresh_controls()
