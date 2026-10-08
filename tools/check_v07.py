"""Exercise live resizing, state GIFs, persisted configuration and screen fitting."""
import copy,json,pathlib,sys,tempfile,time,os
root=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
from PySide6.QtCore import Qt,QPoint,QPointF,QRect
from PySide6.QtGui import QWheelEvent,QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from shorekeeper_pet import pet as module
from shorekeeper_pet.sizing import normalize_scale,fitted_scale
from shorekeeper_pet.config_io import save_atomic,export_bundle,import_bundle

app=QApplication([]); app.setQuitOnLastWindowClosed(False); checks=[]; prefix='v07-dpi'+os.environ['QT_SCALE_FACTOR'] if os.environ.get('QT_SCALE_FACTOR') else 'v07'
original=(root/'settings.json').read_bytes() if (root/'settings.json').is_file() else None
with tempfile.TemporaryDirectory() as directory:
    temp=pathlib.Path(directory); module.SETTINGS=temp/'settings.json'
    from shorekeeper_pet.presets import load_defaults
    data=json.loads(original) if original else load_defaults(root); data['appearance']['audio_enabled']=False; save_atomic(module.SETTINGS,data)
    pet=module.Pet(offline=True); pet.voice.gate.path=temp/'voice-history.json'; pet.show(); pet.hover_timer.stop()
    pet.quota_data=dict(windows=[dict(remaining=98,label='每周',name='deepseek',resets_at=time.time()+1000)],updated_at=time.time(),source='live')
    assert pet.quota_label(True)=='算力配额：98%'
    pet.open_size(); control=pet.size_dialog.control
    for percent in (50,75,100,145,200):
        control.slider.setValue(percent); app.processEvents()
        assert pet.requested_scale==percent/100 and control.percent.value()==percent
        assert pet.width()==round(pet.scene_width*pet.scale_factor)
        assert pet.screen_area().contains(pet.frameGeometry())
        assert pet.quota_rect.width()<=pet.scene_width
        assert pet.quota_rect.center().x()==pet.pet_rect.center().x()
        assert json.loads(module.SETTINGS.read_text('utf8'))['scale']==percent/100
    control.percent.setValue(125); assert control.slider.value()==125 and pet.requested_scale==1.25
    center=pet.rect().center(); global_center=pet.mapToGlobal(center)
    def wheel(modifiers):
        event=QWheelEvent(QPointF(center),QPointF(global_center),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,modifiers,Qt.ScrollPhase.NoScrollPhase,False)
        app.sendEvent(pet,event)
    state=pet.state; serial=pet.controller.serial
    wheel(Qt.KeyboardModifier.NoModifier); assert pet.requested_scale==1.25
    wheel(Qt.KeyboardModifier.ControlModifier); assert pet.requested_scale==1.3 and pet.controller.serial==serial
    checks.append('50–200% live slider, numeric entry, Ctrl-wheel, automatic save, ordinary wheel does not resize or trigger interaction')

    pet.open_preferences(); assert pet.preferences.size_control.percent.value()==130
    pet.preferences.size_control.slider.setValue(160); assert control.percent.value()==160
    saved=module.load_settings(); restored=module.Pet(offline=True); assert restored.requested_scale==1.6
    assert saved['bindings']==data['bindings'] and saved['appearance']==data['appearance']
    restored.timer.stop(); restored.voice.stop(); restored.hide()
    checks.append('quick slider and preferences stay synchronized; restart restores size and all prior customization')

    pet.set_bubble_preview('screen-test',True)
    actual_area=pet.screen_area
    for area in (QRect(0,0,800,600),QRect(0,0,1280,720),QRect(1920,0,2560,1440)):
        pet.screen_area=lambda area=area:area
        for base in (140,230,420):
            pet.options.update(pet_size=base,bubble_width=650)
            pet.set_scale(2); pet.controller.enter('thinking',time.monotonic(),'live'); pet.tick()
            pet.move(area.right(),area.bottom()); pet.clamp_position(); pet.update_layout(); app.processEvents()
            assert area.contains(pet.frameGeometry()),(area,pet.frameGeometry())
            assert area.contains(pet.bubble_window.frameGeometry()),(area,pet.bubble_window.frameGeometry())
            assert pet.requested_scale==2
    pet.screen_area=actual_area; pet.options.update(data['appearance']); pet.set_scale(1)
    pet.set_bubble_preview('screen-test',False)
    pet.move(actual_area().left(),actual_area().top()+200); pet.clamp_position(); pet.update_layout()
    assert normalize_scale(float('nan'))==1 and normalize_scale('bad')==1
    checks.append('simulated 800×600, 1280×720, 2560×1440 and second monitor: body/bubble fit, centered bar, requested size retained')

    pet.monitor.selected='old-pinned'; pet.select_thread('auto')
    assert pet.monitor.selected=='auto' and json.loads(module.SETTINGS.read_text('utf8'))['thread']=='auto'
    for state in ('thinking','reading','writing','thinking'):
        pet.on_status(dict(state=state,thread_id='test-chat',turn_id='same-turn',started=1,active=True,stale=False))
        assert pet.state==state and pet.animation_id==pet.binding(state)['asset'],(state,pet.state,pet.animation_id)
    assert pet.controller.owner=='live'
    checks.append('auto-follow selection saved; same task switches to every user-bound thinking/read/write GIF')

    pet.set_scale(1.35); pet.save_settings(); payload=copy.deepcopy(pet.settings)
    archive=temp/'profile.zip'; warnings=export_bundle(archive,payload,root)
    moved=import_bundle(archive,temp/'relocated'); assert moved['scale']==1.35 and not warnings
    pet.apply_settings(moved); assert pet.requested_scale==1.35
    checks.append('size survives actual ZIP profile export/import with all user assets and audio')
    pet.set_scale(1); pet.controller.enter('thinking',time.monotonic(),'live'); pet.tick(); pet.transition_old=None
    pet.size_dialog.control.refresh(); app.processEvents()
    pet.grab().save(str(root/'qa'/(prefix+'-pet.png'))); pet.size_dialog.grab().save(str(root/'qa'/(prefix+'-size-dialog.png')))
    pet.preferences.grab().save(str(root/'qa'/(prefix+'-preferences.png')))
    pet.timer.stop(); pet.voice.stop(); pet.hide(); pet.preferences.hide(); pet.size_dialog.hide()
assert ((root/'settings.json').read_bytes() if (root/'settings.json').is_file() else None)==original,'test modified live user configuration'
result=dict(ok=True,device_pixel_ratio=app.primaryScreen().devicePixelRatio(),checks=checks)
(root/'qa'/(prefix+'-checks.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=True))
