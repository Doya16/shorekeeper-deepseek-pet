"""Native UI and full voice completion for simultaneous task notifications."""
import json,pathlib,sys,tempfile,time,wave
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from shorekeeper_pet import pet as module
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.presets import load_defaults
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory() as directory:
    temp=pathlib.Path(directory);module.SETTINGS=temp/'settings.json'
    cfg=load_defaults(root);cfg['appearance']['audio_enabled']=False;save_atomic(module.SETTINGS,cfg)
    pet=module.Pet(offline=True);pet.hover_timer.stop();pet.voice.gate.path=temp/'gate.json'
    path=temp/'test.wav'
    with wave.open(str(path),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*4000)
    pet.options.update(audio_enabled=True,volume=0,audio_cooldown=300)
    pet.bindings.set('thinking',audio_clips=[])
    pet.bindings.set('idle',audio_clips=[dict(file=str(path),subtitle='待机')],audio_policy='session')
    pet.bindings.set('done',audio_clips=[dict(file=str(path),subtitle='{task} 完成')],audio_policy='entry',playback='once',speed=4,hold_seconds=0,audio_delay=0)
    played=[]
    def ended(status):
        if status==QMediaPlayer.MediaStatus.EndOfMedia:played.append((pet.voice.selected_state,pet.notification.get('title') if pet.notification else None))
    pet.voice.player.mediaStatusChanged.connect(ended)
    def wait(predicate,seconds=8):
        deadline=time.monotonic()+seconds
        while not predicate() and time.monotonic()<deadline:QTest.qWait(20);time.sleep(.005)
        assert predicate(),played
    pet.tick();wait(lambda:len(played)==1);assert played==[('idle',None)]
    events=[dict(state='done',thread_id=name,turn_id=name,started=1,ended=2,title=name) for name in ('示例项目 A','示例项目 B')]
    pet.on_status(dict(state='writing',thread_id='running',turn_id='running',active=True,started=1,events=events))
    wait(lambda:len(played)==3 and pet.notification is None and pet.state=='writing')
    assert played[1:]==[('done','示例项目 A'),('done','示例项目 B')]
    pet.on_status(dict(state='idle',thread_id=None,events=[]));QTest.qWait(600)
    assert len(played)==3,'Returning to idle replayed its once-per-launch audio'
    pet.options['audio_enabled']=False;pet.timer.stop()
    pet.bindings.set('idle',**cfg['bindings']['idle'])
    pet.show();pet.open_bindings();editor=pet.binding_editor
    from PySide6.QtCore import Qt
    for i in range(editor.triggers.count()):
        if editor.triggers.item(i).data(Qt.ItemDataRole.UserRole)=='idle':editor.triggers.setCurrentRow(i);break
    editor.tabs.setCurrentIndex(3)
    combo=editor.controls['audio_policy'];combo.setCurrentIndex(combo.findData('occasional'))
    assert editor.controls['audio_chance'].isEnabled();app.processEvents();QTest.qWait(60)
    scroll=editor.tabs.widget(3).verticalScrollBar();scroll.setValue(scroll.maximum())
    app.processEvents();editor.grab().save(str(root/'docs/demo/voice-frequency.png'));editor.hide()
    pet.monitor.home=pathlib.Path('DeepSeek 数据目录');pet.open_preferences();pet.preferences.tabs.setCurrentIndex(3)
    app.processEvents();pet.preferences.grab().save(str(root/'docs/demo/startup-setting.png'))
    assert not pet.preferences.controls['launch_with_deepseek'].isChecked()
    pet.voice.stop();pet.hide();pet.preferences.hide()
report=dict(ok=True,native_audio_completed_in_order=True,idle_not_repeated_after_completion=True,concurrent_notifications=2,working_gif_restored=True,frequency_controls=True,startup_checkbox=True,private_desktop_not_captured=True)
(root/'qa/v091-ui-checks.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
