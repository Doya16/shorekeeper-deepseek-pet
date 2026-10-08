"""Real Qt media completion, caption provenance, compact layout and migration."""
import json,pathlib,sys,tempfile,time,wave
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from shorekeeper_pet.audio_player import VoicePlayer
from shorekeeper_pet.audio_player import resolve_audio
from shorekeeper_pet.presets import load_defaults
from shorekeeper_pet.config_io import migrate_settings
from shorekeeper_pet import pet as module
app=QApplication([]); app.setQuitOnLastWindowClosed(False)
checks=[]
def wait_until(predicate,seconds=8):
    end=time.monotonic()+seconds
    while not predicate() and time.monotonic()<end: QTest.qWait(25); time.sleep(.005)
    assert predicate(),'timeout'

with tempfile.TemporaryDirectory() as td:
    root=pathlib.Path(td); module.SETTINGS=root/'settings.json'
    for name,length in [('long',1.2),('next',.3)]:
        with wave.open(str(root/(name+'.wav')),'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000); audio.writeframes(b'\0\0'*round(16000*length))
    companion=module.Pet(offline=True); companion.options.update(audio_enabled=False,volume=0,audio_cooldown=0)
    companion.voice.gate.path=root/'history.json'; companion.quiet=True; companion.show()
    long=dict(file=str(root/'long.wav'),bubble_text='这句话会完整说完，标题跟随它的状态。')
    short=dict(file=str(root/'next.wav'),bubble_text='接下来的一句。')
    for state,clip in [('pet',long),('idle',short),('drop',short),('thinking',long)]:
        companion.set_binding(state,audio_clips=[clip],bubble_mode='audio',bubble_seconds=.1)
    companion.set_binding('pet',playback='loop',loop_seconds=.15)
    companion.options['audio_enabled']=True
    finished=[]
    companion.voice.player.mediaStatusChanged.connect(lambda status:finished.append(companion.voice.selected_state) if status==QMediaPlayer.MediaStatus.EndOfMedia else None)
    companion.react('pet'); generation=companion.voice.generation
    QTest.qWait(350)
    assert companion.state=='idle' and companion.voice.selected_state=='pet'
    assert companion.voice.generation==generation and companion.voice.busy
    assert companion.bubble_visible() and companion.bubble_state()=='pet'
    assert companion.state_title(companion.bubble_state())=='单击 / 摸头'
    companion.react('drop'); QTest.qWait(100)
    assert companion.voice.generation==generation and companion.voice.queued['state']=='drop'
    wait_until(lambda:len(finished)>=2)
    assert finished[:2]==['pet','drop'],finished
    checks.append('GIF ending and idle do not cut speech; next interaction waits for EndOfMedia; paired bubble keeps its source state')

    companion.voice.stop(); companion.react('pet'); generation=companion.voice.generation
    companion.voice.trigger('thinking',companion.binding('thinking'),companion.options,task=('test','turn'))
    assert not companion.voice.gate.contains('thinking',('test','turn'))
    assert companion.voice.generation==generation
    wait_until(lambda:companion.voice.gate.contains('thinking',('test','turn')))
    assert companion.voice.selected_state=='thinking'
    checks.append('task-once bookkeeping happens at actual playback after waiting')
    companion.voice.stop(); companion.react('pet'); companion.react('drop'); assert companion.voice.queued
    companion.voice.stop(); QTest.qWait(100)
    assert not companion.voice.busy and companion.voice.queued is None
    checks.append('explicit stop clears playback and deferred voice')

    companion.set_binding('idle',asset='p2-31',audio_clips=[],bubble_mode='custom',bubble_text='守岸人，这个称呼就很好。它表示，某种因你而有的意义和决心。',bubble_seconds=0)
    companion.options['audio_enabled']=False; companion.react('idle')
    companion.quota_data=dict(windows=[dict(remaining=65,label='每周',name='deepseek',resets_at=time.time()+600)],updated_at=time.time(),source='live')
    companion.update_layout(); area=app.primaryScreen().availableGeometry()
    for x in [area.left(),area.right()]:
        companion.move(x,area.top()+300); companion.clamp_position(); companion.update_bubble(); app.processEvents()
        assert companion.width()==round(companion.scene_width*companion.scale_factor)
        assert companion.quota_rect.width()<=companion.scene_width
        assert companion.quota_rect.center().x()==companion.pet_rect.center().x()
        assert area.contains(companion.bubble_window.frameGeometry())
    companion.move(area.left(),area.top()+300); companion.update_bubble(); app.processEvents()
    companion.transition_old=None
    companion.grab().save(str(module.ROOT/'qa/v06-compact-pet.png'))
    companion.bubble_window.grab().save(str(module.ROOT/'qa/v06-state-bubble.png'))
    canvas=QImage(410,510,QImage.Format.Format_ARGB32); canvas.fill(QColor('#202631'))
    painter=QPainter(canvas); painter.drawPixmap(0,10,companion.bubble_window.grab()); painter.drawPixmap(5,200,companion.grab()); painter.end()
    canvas.save(str(module.ROOT/'qa/v06-preview.png'))
    companion.hide(); assert not companion.bubble_window.isVisible(); companion.show(); app.processEvents()
    assert companion.bubble_window.isVisible()
    checks.append('body width follows character only; centered compact quota; bubble remains on screen at both edges and follows visibility')

    menu=companion.context_menu(); actions={action.text():action for action in menu.actions()}
    assert '刷新额度' in actions and not any('查看额度' in label for label in actions)
    state=companion.state; companion.refresh_event.clear(); actions['刷新额度'].trigger()
    assert companion.refresh_event.is_set() and companion.state==state and companion.panel is None
    QTest.mouseClick(companion,Qt.MouseButton.LeftButton,pos=(companion.quota_rect.center()*companion.scale_factor).toPoint())
    QTest.qWait(app.doubleClickInterval()+40)
    assert companion.state==state and companion.panel is None
    companion.open_bindings(); assert companion.binding_editor.triggers.count()==16
    assert 'quota' not in companion.bindings.states
    assert migrate_settings({'bindings':{'quota':{},'pet':{'next_state':'quota'}}})['bindings']=={'pet':{'next_state':'auto'}}
    checks.append('quota state removed; bar click is passive; refresh menu updates data without animation or panel')
    companion.timer.stop(); companion.voice.stop(); companion.binding_editor.hide(); companion.hide()

if '--audio-library' in sys.argv or '--unbound-audio' in sys.argv:
    import soundfile
    settings=load_defaults(module.ROOT)
    paths=sorted({str(resolve_audio(clip['file'],settings['appearance']['audio_directory'],module.ROOT)) for binding in settings['bindings'].values() for clip in binding.get('audio_clips',[])})
    if '--unbound-audio' in sys.argv:
        from shorekeeper_pet.audio_player import AUDIO_EXTS
        bound=set(paths)
        paths=sorted(str(p) for p in (module.ROOT/settings['appearance']['audio_directory']).rglob('*') if p.suffix.lower() in AUDIO_EXTS and str(p) not in bound)
    report=[]
    with tempfile.TemporaryDirectory() as td:
        voice=VoicePlayer(pathlib.Path(td)); errors=[]
        voice.player.errorOccurred.connect(lambda code,message:errors.append(str(message)))
        for index,path in enumerate(paths):
            duration=soundfile.info(path).duration; ended=[]
            def record(status):
                if status==QMediaPlayer.MediaStatus.EndOfMedia: ended.append(voice.player.position())
            voice.player.mediaStatusChanged.connect(record)
            assert voice.trigger('pet',dict(audio_clips=[{'file':path}]),dict(volume=0,audio_enabled=True),preview=True)
            generation=voice.generation
            end=time.monotonic()+duration+10
            while not ended and not errors and time.monotonic()<end:
                voice.trigger('idle',dict(audio_clips=[{'file':path}]),dict(volume=0,audio_enabled=True,audio_cooldown=0))
                QTest.qWait(80)
                time.sleep(.005)  # Let the Python decoder thread run as app.exec() normally does.
                assert voice.generation==generation,'passive event interrupted voice'
            assert ended and not errors,(path,errors,ended)
            assert abs(voice.player.duration()/1000-duration)<.25,(path,voice.player.duration(),duration)
            voice.player.mediaStatusChanged.disconnect(record)
            report.append(dict(file=pathlib.Path(path).name,expected_seconds=duration,end_ms=ended[0]))
            if (index+1)%5==0: print(json.dumps(dict(verified=index+1,total=len(paths))),flush=True)
        voice.stop()
    name='v06-unbound-audio.json' if '--unbound-audio' in sys.argv else 'v06-all-audio.json'
    (module.ROOT/'qa'/name).write_text(json.dumps(dict(ok=True,clips=report),ensure_ascii=False,indent=2),encoding='utf8')
    checks.append(f'all {len(report)} imported clips reached real player EndOfMedia with matching full duration')

result=dict(ok=True,checks=checks)
(module.ROOT/'qa/v06-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=True),flush=True)
