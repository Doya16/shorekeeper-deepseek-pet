"""The end of a line is played, not thrown away when the output stops."""
import pathlib,tempfile,time,unittest,wave
from PySide6.QtCore import QEventLoop,QTimer,QUrl
from PySide6.QtMultimedia import QAudioFormat,QMediaDevices,QMediaPlayer
from PySide6.QtWidgets import QApplication
from shorekeeper_pet.pcm_player import PcmPlayer,TAIL_SECONDS,with_tail


class TailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_silence_follows_every_line_in_the_sinks_own_format(self):
        for rate,channels,sample,size in ((48000,1,QAudioFormat.SampleFormat.Int16,2),(44100,2,QAudioFormat.SampleFormat.Float,4),
                                          (48000,2,QAudioFormat.SampleFormat.Int32,4)):
            fmt=QAudioFormat();fmt.setSampleRate(rate);fmt.setChannelCount(channels);fmt.setSampleFormat(sample)
            data=b'\x01\x02'*(channels*size)*10;out=with_tail(data,fmt)
            self.assertTrue(out.startswith(data));self.assertEqual(out[len(data):],bytes(round(rate*TAIL_SECONDS)*channels*size))
            self.assertGreaterEqual(TAIL_SECONDS,0.35)

    def test_a_line_ends_only_after_it_has_been_played(self):
        if QMediaDevices.defaultAudioOutput().isNull():self.skipTest('no audio output')
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'line.wav'
            with wave.open(str(path),'wb') as f:f.setparams((1,2,48000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*14400)
            player=PcmPlayer();player.setVolume(0);loop=QEventLoop();ended=[]
            def status(value):
                if value==QMediaPlayer.MediaStatus.EndOfMedia:ended.append((time.perf_counter()-start,player.position()));loop.quit()
            player.mediaStatusChanged.connect(status);QTimer.singleShot(5000,loop.quit)
            player.setSource(QUrl.fromLocalFile(str(path)));start=time.perf_counter();player.play();loop.exec()
            player.stop()
        self.assertEqual(len(ended),1);elapsed,position=ended[0]
        self.assertEqual(position,300)
        # The 0.3 s line has been handed out and played; what the device still held when it stopped was silence.
        self.assertGreater(elapsed,0.3+TAIL_SECONDS-0.26)


if __name__=='__main__':unittest.main()
