"""Reusable editor for a state's random audio candidates and paired captions."""
import json,pathlib
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QLineEdit,QPlainTextEdit,QPushButton,QFileDialog,QLabel,QInputDialog
from .voice_pool import clean_clips,clip_bubble_text

class VoicePoolEditor(QWidget):
    changed=Signal(list)
    def __init__(self,pet,state,parent=None):
        super().__init__(parent); self.pet=pet; self.state=state; self.clips=[]; self.loading=False
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0)
        intro=QLabel('每一行 = 一条语音 + 它自己的气泡文案。先添加文件，再选中一行编辑；随机抽取时整对一起选。'); intro.setWordWrap(True); box.addWidget(intro)
        self.list=QListWidget(); self.list.setFixedHeight(140); self.list.setWordWrap(True); box.addWidget(self.list)
        self.list.currentRowChanged.connect(self.select); self.list.itemChanged.connect(self.toggle)
        row=QHBoxLayout(); box.addLayout(row)
        for label,fn in [('添加多个文件',self.add_files),('填写文件名',self.add_name),('移除',self.remove),('导入语音清单',self.import_manifest)]:
            button=QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        self.title=QLineEdit(); self.title.setPlaceholderText('这条语音的名称（可选）')
        self.path=QLineEdit(); self.path.setPlaceholderText('完整路径，或相对于音频目录的文件名')
        self.caption_label=QLabel('这条语音的配对气泡文案'); box.addWidget(self.caption_label)
        self.caption=QPlainTextEdit(); self.caption.setPlaceholderText('只配对当前选中的这一条语音，可与原台词不同。\n留空：此条语音不显示配对气泡。支持 {state}、{quota}、{task}、{progress}。'); self.caption.setFixedHeight(110); box.addWidget(self.caption)
        self.title.textEdited.connect(self.edit); self.path.textEdited.connect(self.edit); self.caption.textChanged.connect(self.edit)
        row=QHBoxLayout(); box.addLayout(row)
        for label,fn in [('预览选中语音 + 气泡',self.preview_selected),('随机预览一对',self.preview_random),('停止声音',pet.voice.stop)]:
            button=QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        self.pair_hint=QLabel(); self.pair_hint.setWordWrap(True); box.addWidget(self.pair_hint)
        box.addWidget(QLabel('选中语音的名称')); box.addWidget(self.title)
        box.addWidget(QLabel('选中语音的音频文件')); box.addWidget(self.path)
        self.status=QLabel('勾选条目参与抽取。导入的字幕会自动填入配对文案；空列表保持安静，缺失文件跳过。'); self.status.setWordWrap(True); box.addWidget(self.status)
        pet.voice.status.connect(self.status.setText)
    def set_clips(self,clips):
        self.clips=clean_clips(clips); self.refresh(0)
    def refresh(self,index):
        self.loading=True; self.list.clear()
        for clip in self.clips:
            item=QListWidgetItem(self.row_text(clip))
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if clip['enabled'] else Qt.CheckState.Unchecked)
            item.setToolTip(clip['file']+'\n配对气泡：'+clip_bubble_text(clip)); self.list.addItem(item)
        self.list.setCurrentRow(min(index,len(self.clips)-1)); self.loading=False; self.select(self.list.currentRow())
    def select(self,index):
        self.loading=True; clip=self.clips[index] if 0<=index<len(self.clips) else {}
        self.title.setText(clip.get('title','')); self.path.setText(clip.get('file','')); self.caption.setPlainText(clip_bubble_text(clip))
        self.caption_label.setText('这条语音的配对气泡文案'+(f' · 第 {index+1} 条' if clip else ''))
        for control in (self.title,self.path,self.caption):
            control.setEnabled(bool(clip)); control.setToolTip('未选中语音条目时无法修改；请先添加或选择一条语音。' if not clip else '')
        self.loading=False
    def row_text(self,clip):
        title=clip['title'] or pathlib.Path(clip['file']).name
        text=clip_bubble_text(clip).replace('\n',' / ')
        return title+'\n气泡：'+(text[:66]+('…' if len(text)>66 else '') if text else '无配对气泡（可在下方填写）')
    def update_hint(self,binding,options):
        hints=[]
        if options.get('audio_muted'): hints.append('安静陪伴（静音）已开启，自动播报和试听均不发声；可在右键菜单或设置中取消。')
        if binding['bubble_mode']!='audio': hints.append('配对文案暂不显示：请在“气泡与字体 → 气泡内容”选择“自定义音频+字幕”。')
        if not options['audio_enabled'] or not binding['audio_enabled']: hints.append('自动语音当前关闭，仍可使用预览按钮；开启声音后参与实际交互。')
        self.pair_hint.setText('\n'.join(hints) or '当前已开启配对显示；抽中哪条语音，就显示这一条的文案。')
    def save(self): self.changed.emit(clean_clips(self.clips))
    def edit(self):
        index=self.list.currentRow()
        if self.loading or not 0<=index<len(self.clips): return
        path=self.path.text().strip()
        if not path: self.status.setText('文件名不能为空；不想使用这一条时可移除或取消勾选。'); return
        self.clips[index].update(file=path,title=self.title.text(),bubble_text=self.caption.toPlainText())
        self.loading=True; item=self.list.item(index); item.setText(self.row_text(self.clips[index])); item.setToolTip(path+'\n配对气泡：'+self.caption.toPlainText()); self.loading=False; self.save()
    def toggle(self,item):
        if self.loading: return
        self.clips[self.list.row(item)]['enabled']=item.checkState()==Qt.CheckState.Checked; self.save()
    def append(self,rows):
        old=len(self.clips); self.clips=clean_clips(self.clips+rows); self.refresh(old); self.save()
    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'添加语音候选',str(self.pet.audio_directory()),'音频 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac)')
        rows=[]
        for value in paths:
            path=pathlib.Path(value); caption=''
            try:
                sidecar=path.with_suffix('.txt')
                if sidecar.is_file(): caption=sidecar.read_text('utf-8-sig')
            except (OSError,UnicodeError): pass
            rows.append(dict(file=value,title=path.stem,subtitle=caption))
        if rows: self.append(rows)
    def add_name(self):
        name,ok=QInputDialog.getText(self,'添加相对路径','相对于全局音频目录的文件名：')
        if ok and name.strip(): self.append([{'file':name.strip()}])
    def remove(self):
        index=self.list.currentRow()
        if index>=0: self.clips.pop(index); self.refresh(max(0,index-1)); self.save()
    def import_manifest(self):
        filename,_=QFileDialog.getOpenFileName(self,'导入音频与字幕清单','','JSON (*.json)')
        if not filename: return
        try:
            path=pathlib.Path(filename)
            if path.stat().st_size>2_000_000: raise ValueError('清单过大')
            data=json.loads(path.read_text('utf-8-sig')); rows=data if isinstance(data,list) else data.get('clips',[])
            rows=clean_clips(rows)
            for clip in rows:
                p=pathlib.Path(clip['file'])
                if not p.is_absolute(): clip['file']=str((path.parent/p).resolve())
            self.append(rows); self.status.setText(f'已导入 {len(rows)} 条音频与字幕。')
        except (OSError,ValueError,AttributeError) as error: self.status.setText('导入失败：'+str(error))
    def preview_selected(self):
        index=self.list.currentRow()
        if index<0: return
        self.pet.preview_binding(self.state(),clip=self.clips[index])
    def preview_random(self): self.pet.preview_binding(self.state())
