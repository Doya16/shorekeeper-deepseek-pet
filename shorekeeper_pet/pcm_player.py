"""Play complete PCM buffers through QAudioSink, bypassing Media Foundation."""
import wave
from PySide6.QtCore import QObject,Signal,QUrl,QBuffer,QByteArray,QIODevice,QTimer
from PySide6.QtMultimedia import QAudioSink,QAudioFormat,QMediaDevices,QAudio,QMediaPlayer
from .paths import ROOT,AUDIO_SESSION_NAME,APPLICATION_ID
from .windows_audio import set_session_identity

class PcmPlayer(QObject):
    mediaStatusChanged=Signal(object)
    errorOccurred=Signal(object,str)
    def __init__(self,parent=None):
        super().__init__(parent); self.sink=None; self.buffer=None; self.running=False
        self._duration=0; self._position=0; self._volume=.75; self._error=QMediaPlayer.Error.NoError; self._source=QUrl(); self.samples=b''
        self._identity_timer=QTimer(self); self._identity_timer.setSingleShot(True)
        self._identity_timer.timeout.connect(self._label_session); self._identity_attempts=0
    def source(self): return self._source
    def error(self): return self._error
    def duration(self): return self._duration
    def position(self): return min(self._duration,round(self.sink.processedUSecs()/1000)) if self.running else self._position
    def playbackState(self): return QMediaPlayer.PlaybackState.PlayingState if self.running else QMediaPlayer.PlaybackState.StoppedState
    def setVolume(self,value):
        self._volume=max(0,min(1,value))
        if self.sink: self.sink.setVolume(self._volume)
    def stop(self):
        self._identity_timer.stop()
        self.running=False; self._position=0
        if self.sink: self.sink.stop(); self.sink.deleteLater(); self.sink=None
        if self.buffer: self.buffer.close(); self.buffer.deleteLater(); self.buffer=None
    def fail(self,message):
        self.stop(); self._error=QMediaPlayer.Error.ResourceError; self.errorOccurred.emit(self._error,message)
    def setSource(self,url):
        self.stop(); self._source=url; self.samples=b''; self._error=QMediaPlayer.Error.NoError; self._duration=0
        if url.isEmpty(): self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.NoMedia); return
        try:
            with wave.open(url.toLocalFile(),'rb') as audio:
                if audio.getsampwidth()!=2 or audio.getnchannels() not in (1,2): raise ValueError('需要 PCM16 单声道或双声道音频')
                self.rate=audio.getframerate(); self.channels=audio.getnchannels()
                self._duration=round(audio.getnframes()*1000/self.rate)
                if audio.getnframes()==0: raise ValueError('音频文件没有声音帧')
                if self._duration>600000: raise ValueError('音频超过 10 分钟')
                self.samples=audio.readframes(audio.getnframes())
            self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
        except Exception as exc: self.fail(str(exc))
    def play(self):
        if not self.samples: return
        device=QMediaDevices.defaultAudioOutput()
        if device.isNull(): self.fail('未找到音频输出设备'); return
        fmt=QAudioFormat(); fmt.setSampleRate(self.rate); fmt.setChannelCount(self.channels); fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        data=self.samples
        if not device.isFormatSupported(fmt):
            # Adapt only when a different computer's output requires it.
            import numpy as np
            target=device.preferredFormat(); rate=target.sampleRate(); channels=target.channelCount()
            if rate<=0 or channels<1 or target.sampleFormat() not in (QAudioFormat.SampleFormat.Int16,QAudioFormat.SampleFormat.Float,QAudioFormat.SampleFormat.Int32):
                self.fail('音频输出设备不支持常用 PCM 格式'); return
            values=np.frombuffer(data,dtype='<i2').reshape(-1,self.channels).astype(np.float32)/32768
            if channels!=self.channels:
                mono=values.mean(axis=1,keepdims=True); values=np.repeat(mono,channels,axis=1)
            if rate!=self.rate:
                count=max(1,round(len(values)*rate/self.rate)); positions=np.arange(count)*self.rate/rate
                values=np.stack([np.interp(positions,np.arange(len(values)),values[:,i]) for i in range(channels)],axis=1)
            dtype,scale={QAudioFormat.SampleFormat.Int16:('<i2',32767),QAudioFormat.SampleFormat.Float:('<f4',1),QAudioFormat.SampleFormat.Int32:('<i4',2147483647)}[target.sampleFormat()]
            data=(np.clip(values,-1,1)*scale).astype(dtype).tobytes(); fmt=target
        self.buffer=QBuffer(self); self.buffer.setData(QByteArray(data)); self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.sink=QAudioSink(device,fmt,self); self.sink.setVolume(self._volume); self.sink.stateChanged.connect(self._state)
        self.running=True; self.sink.start(self.buffer)
        self._identity_attempts=0; self._label_session()
    def _label_session(self):
        if not self.running: return
        self._identity_attempts+=1
        named=set_session_identity(AUDIO_SESSION_NAME,ROOT/'assets/shorekeeper.ico',APPLICATION_ID)
        if not named and self._identity_attempts<3: self._identity_timer.start(150)
    def _state(self,state):
        if not self.running: return
        if state==QAudio.State.IdleState and self.buffer.atEnd():
            self.running=False; self._position=self._duration; self.sink.stop()
            self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
        elif state==QAudio.State.StoppedState and self.sink.error()!=QAudio.Error.NoError:
            self.fail('音频输出设备中断：'+str(self.sink.error()))

def verify_output(directory):
    from PySide6.QtCore import QEventLoop,QTimer
    import pathlib
    path=pathlib.Path(directory)/'output-check.wav'
    with wave.open(str(path),'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000); audio.writeframes(b'\0\0'*4000)
    player=PcmPlayer(); player.setVolume(0); loop=QEventLoop(); ended=[]
    def status(value):
        if value==QMediaPlayer.MediaStatus.EndOfMedia: ended.append(player.position()); loop.quit()
    player.mediaStatusChanged.connect(status); player.errorOccurred.connect(lambda *_:loop.quit())
    timeout=QTimer(); timeout.setSingleShot(True); timeout.timeout.connect(loop.quit); timeout.start(4000)
    player.setSource(QUrl.fromLocalFile(str(path))); player.play()
    if player.error()==QMediaPlayer.Error.NoError: loop.exec()
    result=ended==[250]; player.stop(); timeout.stop(); return result
