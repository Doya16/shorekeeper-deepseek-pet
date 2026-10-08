"""Record only the app's own rendered widgets and its own voice clips.

No desktop/screen capture, system audio, account data or real chat is read.
The visible task is a labelled example. The real profile is never modified.
"""
import copy,json,pathlib,shutil,subprocess,sys,tempfile,time,wave
root=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
import numpy as np
import imageio_ffmpeg
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF,QRectF,QEvent
from PySide6.QtGui import QImage,QPainter,QColor,QPen,QMouseEvent,QPainterPath
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from shorekeeper_pet.appearance import font
from shorekeeper_pet.config_io import save_atomic
from shorekeeper_pet.presets import load_defaults
from shorekeeper_pet.media_library import import_images
from shorekeeper_pet import pet as module
WIDTH,HEIGHT,FPS,SECONDS=1600,1000,15,98
out=root/'docs/demo'; out.mkdir(parents=True,exist_ok=True)
work=tempfile.TemporaryDirectory(prefix='shorekeeper-demo-'); sandbox=pathlib.Path(work.name)
for folder in ('assets','fonts','defaults'): shutil.copytree(root/folder,sandbox/folder)
module.ROOT=sandbox; module.SETTINGS=sandbox/'settings.json'
settings=load_defaults(sandbox); settings['appearance']['volume']=0; settings['scale']=1.15
settings['position']=[80,360]; settings['quiet']=False
save_atomic(module.SETTINGS,settings,backup=False)
app=QApplication([]); app.setQuitOnLastWindowClosed(False)
pet=module.Pet(offline=True); pet.voice.gate.path=sandbox/'voice-history.json'; pet.show(); pet.hover_timer.stop()
pet.monitor.home=pathlib.Path('DeepSeek')
pet.quota_data=dict(windows=[dict(remaining=98,label='每周',name='DeepSeek',resets_at=None)],source='live',updated_at=time.time())
pet.update_layout(); pet.open_bindings(); editor=pet.binding_editor; editor.resize(1080,920); editor.hide()
pet.open_preferences(); prefs=pet.preferences; prefs.resize(790,780); prefs.hide()
pet.open_size(); size=pet.size_dialog; size.hide()
original_clips=copy.deepcopy(settings['bindings']['thinking']['audio_clips'])
pet.set_binding('idle',audio_enabled=False)
pet.set_binding('thinking',audio_clips=[c for c in original_clips if pathlib.Path(c['file']).name.startswith('011-')])
for state,prefix in [('pet','001-'),('drag','006-'),('drop','019-'),('doubleclick','021-')]:
    rows=[c for c in settings['bindings'][state]['audio_clips'] if pathlib.Path(c['file']).name.startswith(prefix)]
    pet.set_binding(state,audio_clips=rows)
pet.voice.stop(); pet.clear_override()

ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
silent=sandbox/'silent.mp4'; log=(sandbox/'encode.log').open('w')
encoder=subprocess.Popen([ffmpeg,'-y','-f','rawvideo','-pixel_format','rgba','-video_size',f'{WIDTH}x{HEIGHT}','-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p',str(silent)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
frame_index=0; written_frames=0; last_frame=None; next_scene=0; current_scene=''; title=''; instruction=''; visible_panel=None; clips=[]; active_clip=None; states=[]; cursor=None
original_play=pet.voice.player.play; original_stop=pet.voice.player.stop
def begin_voice():
    global active_clip
    original_play(); player=pet.voice.player
    if player.running:
        active_clip=dict(start=max(0,time.monotonic()-record_started),state=pet.voice.selected_state,samples=player.samples,rate=player.rate,channels=player.channels,end=None,natural=False)
        clips.append(active_clip)
def end_voice():
    global active_clip
    if active_clip and active_clip['end'] is None: active_clip['end']=max(0,time.monotonic()-record_started)
    active_clip=None; original_stop()
pet.voice.player.play=begin_voice; pet.voice.player.stop=end_voice
def audio_status(status):
    if status==QMediaPlayer.MediaStatus.EndOfMedia and active_clip: active_clip['natural']=True
pet.voice.player.mediaStatusChanged.connect(audio_status)

def select_state(state):
    for i in range(editor.triggers.count()):
        if editor.triggers.item(i).data(Qt.ItemDataRole.UserRole)==state: editor.triggers.setCurrentRow(i); break
def task(state):
    pet.on_status(dict(state=state,thread_id='demo-task',turn_id='demo-turn',started=1,active=state!='done',ended=2 if state=='done' else 0,stale=False,title='示例任务：整理旅行清单',message=''))
def mouse(kind,local,global_pos,button,buttons):
    app.sendEvent(pet,QMouseEvent(kind,QPointF(local),QPointF(global_pos),button,buttons,Qt.KeyboardModifier.NoModifier))

scenes=[
 (0,'cover','守岸人 DeepSeek 桌宠','把喜欢的表情、台词和声音，留在桌面上。'),
 (5,'thinking','跟随 DeepSeek · 思考','任务开始时，播放思考表情与一条开场语音。'),
 (11,'reading','跟随 DeepSeek · 查阅','开始查阅资料时，切换到绑定的查阅 GIF。'),
 (16,'writing','跟随 DeepSeek · 编辑','开始编辑内容时，切换到绑定的编辑 GIF。'),
 (21,'thinking-again','同一任务 · 开场语音只播一次','回到思考状态，继续播放 GIF，不重复开场语音。'),
 (24,'done','任务完成 · 语音与气泡','完成时显示对应表情、语音和配对文案。'),
 (28,'drag','按住拖动 · 换个位置','拖动时播放专属动作，也可以配上自己的声音。'),
 (32,'drop','松开放下 · 又一种回应','拖动和放下可以分别绑定 GIF、语音与气泡。'),
 (35,'double','双击互动 · 直接回应','双击触发表情和声音，继续陪在桌面上。'),
 (39,'pet','单击摸头 · 听她说完','动画结束后，当前语音仍会完整播放。'),
 (45,'gallery','每种交互 · 自选 GIF','右键 → 交互工作室 → 选择动作 → 点击喜欢的素材。'),
 (52,'import','添加自己的图片','打开素材目录 → 放入文件 → 刷新素材 → 预览并选中。'),
 (59,'playback','播放节奏 · 自己决定','设置循环方式、播放速度、停留时间和下一个状态。'),
 (66,'voice','多条语音 · 各自配一句台词','选择一条语音，填写它自己的气泡文案；可以逐条试听。'),
 (76,'size','大小与字体 · 实时调整','右键 → 调整大小；也可以按住 Ctrl 滚轮缩放。'),
 (85,'transfer','保存配置 · 带到新电脑','外观、声音与迁移 → 保存与迁移 → 导出 Windows 便携完整包。'),
 (94,'outro','开始你的桌面陪伴','下载完整包，解压后运行 守岸人DeepSeek桌宠启动.exe。'),
]
def enter_scene(name,new_title,new_instruction):
    global current_scene,title,instruction,visible_panel,cursor
    current_scene=name; title=new_title; instruction=new_instruction; visible_panel=None; cursor=None
    for dialog in (editor,prefs,size): dialog.hide()
    if name=='thinking': task('thinking')
    elif name=='reading': task('reading')
    elif name=='writing': task('writing')
    elif name=='thinking-again': task('thinking')
    elif name=='done': task('done')
    elif name=='drag':
        task('idle')
        pet.clear_override(); pet.move(80,360); pos=pet.rect().center(); mouse(QEvent.Type.MouseButtonPress,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
    elif name=='drop':
        pos=pet.rect().center(); mouse(QEvent.Type.MouseButtonRelease,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
    elif name=='double':
        pos=pet.rect().center(); mouse(QEvent.Type.MouseButtonDblClick,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
        mouse(QEvent.Type.MouseButtonRelease,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
    elif name=='pet':
        pos=pet.rect().center(); mouse(QEvent.Type.MouseButtonPress,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
        mouse(QEvent.Type.MouseButtonRelease,pos,pet.mapToGlobal(pos),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
    elif name in ('gallery','import','playback','voice'):
        visible_panel=editor; editor.show(); select_state('thinking' if name=='voice' else 'reading')
        editor.tabs.setCurrentIndex({'gallery':0,'import':0,'playback':1,'voice':3}[name])
        if name=='import':
            source=sandbox/'我的守岸人.gif'; shutil.copy2(sandbox/'assets/originals/p2-06.gif',source)
            import_images([source],sandbox); editor.refresh_gallery(); editor.search.setText('我的守岸人')
            for i in range(editor.gallery.count()):
                if '我的守岸人' in editor.gallery.item(i).text(): editor.gallery.setCurrentRow(i); break
            editor.try_binding()
        if name=='playback': editor.search.clear(); editor.controls['speed'].setValue(1.25)
        if name=='voice':
            pet.set_binding('thinking',audio_clips=original_clips); editor.load_selection(); editor.voice_pool.list.setCurrentRow(1); editor.voice_pool.preview_selected()
    elif name=='size': visible_panel=prefs; prefs.tabs.setCurrentIndex(0); prefs.show()
    elif name=='transfer': visible_panel=prefs; prefs.tabs.setCurrentIndex(2); prefs.show(); prefs.save_now()
    pet.hover_timer.stop(); states.append(dict(time=frame_index/FPS,scene=name))

def text(p,x,y,w,h,string,size=24,color='#355475',bold=False):
    p.setFont(font('LXGW WenKai',size,bold)); p.setPen(QColor(color)); p.drawText(QRectF(x,y,w,h),Qt.TextFlag.TextWordWrap,string)
def rounded(p,rect,color,radius=24):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color)); p.drawRoundedRect(rect,radius,radius)
def render():
    global cursor
    image=QImage(WIDTH,HEIGHT,QImage.Format.Format_RGBA8888); image.fill(QColor('#e9f0f8')); p=QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rounded(p,QRectF(24,24,1552,940),'#f8fbff',30)
    text(p,55,40,1200,55,title,36,'#244d7a',True)
    text(p,55,100,1450,62,instruction,24)
    text(p,1285,48,240,38,'功能演示 · 示例任务',18,'#607e9e')
    panel=visible_panel
    # Capture this application's widgets only; never the surrounding screen.
    px,py=(74,460) if panel else (240,450)
    if current_scene in ('drag','drop'):
        px=155+max(0,min(1,(frame_index/FPS-28)/3.2))*150; py=475-max(0,min(1,(frame_index/FPS-28)/3.2))*80
    if pet.bubble_visible():
        bubble=pet.bubble_window.grab(); bw=min(470 if panel else 550,bubble.width()); bh=bubble.height()*bw/bubble.width()
        p.drawPixmap(QRectF(max(42,px-90),py-bh-24,bw,bh),bubble,QRectF(bubble.rect()))
    pix=pet.grab(); p.drawPixmap(round(px),round(py),pix)
    text(p,50 if panel else 195,850 if panel else 810,390,42,'当前状态：'+pet.state_title(),23,'#3c638d',True)
    if current_scene=='drag':
        cursor=QPointF(px+pix.width()*.55,py+pix.height()*.48)
        p.setPen(QPen(QColor('#5b8ac2'),3)); p.setBrush(QColor('#e5f1ff')); p.drawEllipse(cursor,13,13)
    if panel:
        shot=panel.grab(); target=QRectF(470,167,1080,720)
        scale=min(target.width()/shot.width(),target.height()/shot.height()); w,h=shot.width()*scale,shot.height()*scale
        rounded(p,QRectF(target.x()-7,target.y()-7,w+14,h+14),'#d1deee',16)
        p.drawPixmap(QRectF(target.x(),target.y(),w,h),shot,QRectF(shot.rect()))
    else:
        rounded(p,QRectF(780,250,690,555),'#eaf2fc',26)
        text(p,825,292,590,60,'属于你的每一次回应',32,'#315b88',True)
        rows=['16 种交互，各自选择 GIF','多条语音，逐条配对气泡','循环、速度、停留时间可调','Ctrl + 滚轮，随手调整大小','配置、素材、声音，一起打包']
        for i,row in enumerate(rows):
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#74a2d5')); p.drawEllipse(QPointF(837,394+i*72),5,5)
            text(p,860,370+i*72,570,58,row,26)
    p.setPen(QPen(QColor('#cedeed'),2)); p.drawLine(55,907,1540,907)
    text(p,55,927,1320,35,'守岸人 DeepSeek 桌宠  ·  Windows  ·  GIF / 语音 / 气泡 / 字体 / 便携配置',21,'#507398')
    text(p,1450,927,100,35,f'{frame_index/FPS:02.0f} / {SECONDS}',18,'#7590ab')
    p.end(); return image

snapshots={'cover':'cover','thinking':'thinking','reading':'reading','writing':'writing','drag':'drag','gallery':'gif-library','import':'import-image','playback':'playback','voice':'voice-pairs','size':'size-fonts','transfer':'save-transfer'}
captured=set(); failures=[]
def tick():
    global frame_index,written_frames,last_frame,next_scene
    try:
        target=min(FPS*SECONDS-1,int((time.monotonic()-record_started)*FPS))
        if target<written_frames: return
        while written_frames<target and last_frame is not None:
            encoder.stdin.write(last_frame); written_frames+=1
        frame_index=target
        t=frame_index/FPS
        while next_scene<len(scenes) and scenes[next_scene][0]<=t:
            start,name,heading,note=scenes[next_scene]; enter_scene(name,heading,note); next_scene+=1
        if current_scene=='drag':
            progress=min(1,(t-28)/3.2); target=QPoint(round(180+150*progress),round(460-80*progress)); mouse(QEvent.Type.MouseMove,pet.mapFromGlobal(target),target,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton)
        if current_scene=='size':
            value=round(90+35*(1+np.sin((t-76)*1.3))/2); prefs.size_control.slider.setValue(value)
        pet.hover_timer.stop(); pet.tick(); image=render()
        start=next(s[0] for s in scenes if s[1]==current_scene)
        if current_scene in snapshots and current_scene not in captured and t-start>=1.4:
            image.save(str(out/(snapshots[current_scene]+'.png')))
            if visible_panel: visible_panel.grab().save(str(out/(snapshots[current_scene]+'-panel.png')))
            captured.add(current_scene)
        last_frame=bytes(image.constBits()); encoder.stdin.write(last_frame); written_frames+=1
        if written_frames% (FPS*10)==0: print(json.dumps({'recorded_seconds':written_frames/FPS}),flush=True)
        if written_frames>=FPS*SECONDS: timer.stop(); app.quit()
    except Exception:
        import traceback
        failures.append(traceback.format_exc()); timer.stop(); app.quit()
record_started=time.monotonic(); timer=QTimer(); timer.setInterval(20); timer.timeout.connect(tick); timer.start(); app.exec()
end_voice(); pet.timer.stop(); editor.timer.stop()
for widget in (editor,prefs,size,pet): widget.hide()
encoder.stdin.close(); encoder.wait(timeout=40); log.close()
if failures: raise RuntimeError(failures[0])
if encoder.returncode: raise RuntimeError((sandbox/'encode.log').read_text())
track=np.zeros((SECONDS*48000,2),dtype=np.float32); voice_report=[]
for clip in clips:
    samples=np.frombuffer(clip['samples'],dtype='<i2').reshape(-1,clip['channels']).astype(np.float32)/32768
    if clip['channels']==1: samples=np.repeat(samples,2,axis=1)
    stop=clip['end'] if clip['end'] is not None else SECONDS
    full_duration=len(samples)/clip['rate']; duration=full_duration if clip['natural'] else min(full_duration,max(0,stop-clip['start'])); count=round(duration*48000)
    positions=np.arange(count)*clip['rate']/48000
    converted=np.stack([np.interp(positions,np.arange(len(samples)),samples[:,i]) for i in range(2)],axis=1)
    start=round(clip['start']*48000); count=min(count,len(track)-start)
    if count>0: track[start:start+count]+=converted[:count]
    voice_report.append(dict(state=clip['state'],start=round(clip['start'],2),seconds=round(duration,2),source_seconds=round(full_duration,2),complete=clip['natural']))
peak=float(np.max(np.abs(track)))
if peak>0: track*=.85/peak
audio=sandbox/'voices.wav'
with wave.open(str(audio),'wb') as stream:
    stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(48000); stream.writeframes((np.clip(track,-1,1)*32767).astype('<i2').tobytes())
subprocess.run([ffmpeg,'-y','-i',str(silent),'-i',str(audio),'-c:v','copy','-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(out/'shorekeeper-demo.mp4')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
# A small looping excerpt helps preview the project directly in the README.
subprocess.run([ffmpeg,'-y','-ss','5','-t','17','-i',str(silent),'-filter_complex','[0:v]fps=7,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer','-loop','0',str(out/'preview.gif')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
report=dict(seconds=SECONDS,width=WIDTH,height=HEIGHT,fps=FPS,example_task=True,desktop_capture=False,system_audio=False,voices=voice_report,scenes=states)
(out/'demo-scenes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'ok':True,'video':str(out/'shorekeeper-demo.mp4'),'voice_events':len(clips),'thinking_voice_events':sum(c['state']=='thinking' and c['start']<24 for c in clips)}),flush=True)
work.cleanup()
