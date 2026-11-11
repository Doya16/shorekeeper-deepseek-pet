"""Small looping previews beside each settings card, drawn from the current settings and the pet's own art.

Each preview is a self-contained scene: it never moves or changes the real pet. It only animates while visible.
"""
import math,random
from PySide6.QtCore import QElapsedTimer,QPointF,QRectF,Qt,QTimer
from PySide6.QtGui import QColor,QFont,QFontMetricsF,QImage,QPainter,QPainterPath,QPen
from PySide6.QtWidgets import QSizePolicy,QWidget
from .appearance import font

SIZE=(230,180)
FPS_MS=40
SCALE=.5            # preview pixels per real pixel, except where a screen is drawn to scale
INK=QColor('#3d5573');MUTED=QColor('#6f819b');DESK=QColor('#dfe8f3');BAR=QColor('#c9d6e6')
BUBBLE_FILL=QColor('#f9fcff');BUBBLE_EDGE=QColor('#6592c9');QUOTA_FILL=QColor('#edf5ff');QUOTA_EDGE=QColor('#6592c9')
LOOPS={'size':4000,'fonts':4000,'bubble':4000,'finish':7000,'desk':14000,'lock':6000,'rest':4000,'sound':4000}
CONFETTI=[(math.radians(random.Random(i).uniform(-150,-30)),random.Random(i+99).uniform(130,260),('#e4572e','#f2a541','#3fa37a','#3a78c2','#d4537e','#8c6bd6')[i%6]) for i in range(28)]


class CardPreview(QWidget):
    def __init__(self,pet,mode):
        super().__init__();self.pet=pet;self.mode=mode;self.clock=QElapsedTimer();self.fixed_ms=None
        self.setFixedSize(*SIZE);self.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
        self.setAccessibleName('效果预览');self.setToolTip('按当前设置循环演示的效果预览，不会改动桌宠')
        self.timer=QTimer(self);self.timer.setInterval(FPS_MS);self.timer.timeout.connect(self.update)

    def showEvent(self,event):
        self.clock.start();self.timer.start();super().showEvent(event)

    def hideEvent(self,event):
        self.timer.stop();super().hideEvent(event)

    def elapsed(self):
        if self.fixed_ms is not None:return self.fixed_ms
        return (self.clock.elapsed() if self.clock.isValid() else 0)%LOOPS[self.mode]

    def render_at(self,ms):
        """The scene at a given moment of the loop, as an image (used by tests and to check a setting)."""
        self.fixed_ms=ms;image=QImage(self.width(),self.height(),QImage.Format.Format_ARGB32);image.fill(0)
        p=QPainter(image);self.draw(p);p.end();self.fixed_ms=None;return image

    def paintEvent(self,event):
        p=QPainter(self);self.draw(p);p.end()

    # Drawing helpers.
    def art(self,state,ms):
        b=self.pet.binding(state);return self.pet.get_animation(b['asset']).frame(ms*b['speed'],playback='loop' if b['playback']=='once' else b['playback'])

    def draw_art(self,p,rect,state,ms,opacity=1.,mirror=False):
        image=self.art(state,ms)
        if mirror:image=image.flipped(Qt.Orientation.Horizontal)
        ratio=min(rect.width()/image.width(),rect.height()/image.height());w,h=image.width()*ratio,image.height()*ratio
        p.save();p.setOpacity(opacity);p.drawImage(QRectF(rect.center().x()-w/2,rect.bottom()-h,w,h),image);p.restore()

    def bubble(self,p,anchor,text,family,px,max_width=None):
        f=font(family,max(8,round(px)));metrics=QFontMetricsF(f);pad=7
        width=min(max_width or self.width()-12,max(metrics.horizontalAdvance(line) for line in text.split('\n'))+2*pad)
        lines=[];words=text.split('\n')
        for line in words:
            current=''
            for ch in line:
                if metrics.horizontalAdvance(current+ch)>width-2*pad and current:lines.append(current);current=ch
                else:current+=ch
            lines.append(current)
        height=len(lines)*metrics.height()+2*pad
        x=max(6,min(anchor.x()-width/2,self.width()-6-width));y=max(4,anchor.y()-height)
        box=QRectF(x,y,width,height)
        p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(BUBBLE_EDGE,1.4));p.setBrush(BUBBLE_FILL);p.drawRoundedRect(box,8,8)
        p.setFont(f);p.setPen(INK)
        for i,line in enumerate(lines):p.drawText(QPointF(x+pad,y+pad+metrics.ascent()+i*metrics.height()),line)
        p.restore();return box

    def quota(self,p,center_x,top,scale=1.):
        o=self.pet.options
        if not o['show_quota']:return None
        f=font(o['font_family'],max(7,round(o['quota_font_size']*SCALE*scale)));metrics=QFontMetricsF(f);text=self.pet.quota_label(compact=True)
        width=metrics.horizontalAdvance(text)+16*scale;height=metrics.height()+10*scale
        box=QRectF(center_x-width/2,top,width,height)
        p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QUOTA_EDGE,1.2));p.setBrush(QUOTA_FILL);p.drawRoundedRect(box,6,6)
        p.setFont(f);p.setPen(QColor('#204e7d'));p.drawText(box,Qt.AlignmentFlag.AlignCenter,text);p.restore();return box

    def caption(self,p,text):
        f=QFont(self.font());f.setPixelSize(11);p.save();p.setFont(f);p.setPen(MUTED)
        p.drawText(QRectF(8,self.height()-18,self.width()-16,16),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,text);p.restore()

    def desk(self,p,rect=None):
        rect=rect or QRectF(0,0,self.width(),self.height())
        p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor('#c4d3e5'),1));p.setBrush(DESK);p.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),10,10)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(BAR);p.drawRect(QRectF(rect.left()+1,rect.bottom()-11,rect.width()-2,10));p.restore()

    def pet_box(self,height,bottom=None,center=None):
        side=height;cx=self.width()/2 if center is None else center;bottom=self.height()-26 if bottom is None else bottom
        return QRectF(cx-side/2,bottom-side,side,side)

    # Scenes.
    def draw(self,p):
        p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        getattr(self,'draw_'+self.mode)(p,self.elapsed())

    def draw_size(self,p,ms):
        # The whole screen, scaled to fit above the caption, with the pet at its real share of it.
        area=self.pet.screen_area();room_w,room_h=self.width()-20,self.height()-30
        f=min(room_w/max(1,area.width()),room_h/max(1,area.height()));w,h=area.width()*f,area.height()*f
        screen=QRectF((self.width()-w)/2,6+(room_h-h)/2,w,h);self.desk(p,screen)
        side=self.pet.pet_rect.height()*self.pet.scale_factor*f;box=QRectF(screen.right()-12-side,screen.bottom()-14-side-(10 if self.pet.options['show_quota'] else 0),side,side)
        self.draw_art(p,box,'idle',ms);self.quota(p,box.center().x(),box.bottom()+1,scale=f/SCALE*self.pet.scale_factor)
        self.caption(p,f'按当前屏幕比例 · {round(self.pet.requested_scale*100)}%')

    def draw_fonts(self,p,ms):
        self.desk(p);o=self.pet.options;box=self.pet_box(104,bottom=self.height()-44,center=70)
        self.draw_art(p,box,'idle',ms);self.quota(p,box.center().x(),box.bottom()+2)
        self.bubble(p,QPointF(self.width()-70,box.top()+40),'今天也辛苦啦～\n任务完成了哦',o['bubble_font_family'],o['bubble_font_size']*SCALE*1.15,max_width=150)
        self.caption(p,'气泡字体 · 额度框字体')

    def draw_bubble(self,p,ms):
        self.desk(p);o=self.pet.options;box=self.pet_box(100,bottom=self.height()-46)
        self.draw_art(p,box,'idle',ms);self.quota(p,box.center().x(),box.bottom()+2,scale=o['quota_scale'])
        width=min(self.width()-12,118*o['bubble_width_ratio'])
        self.bubble(p,QPointF(box.center().x(),box.top()+14),'气泡宽度会影响长台词怎么换行，太窄会多占几行。',o['bubble_font_family'],o['bubble_font_size']*SCALE,max_width=width)
        self.caption(p,f"气泡宽度 {round(o['bubble_width_ratio']*100)}% · 余额框 {round(o['quota_scale']*100)}%")

    def float_lines(self):
        from .cost_float import sample_lines
        o=self.pet.options;lines=sample_lines(o)
        return [(('-¥0.0731' if kind=='cost' else '用时 4分12秒'),kind) for text,kind in lines]

    def draw_finish(self,p,ms):
        from .cost_float import OUTLINES,render,timeline
        self.desk(p);o=self.pet.options;box=self.pet_box(120,bottom=self.height()-26)
        done=ms>=1200;self.draw_art(p,box,'done' if done else 'thinking',ms)
        style=o['turn_cost_style']
        if not done or style=='off':
            self.caption(p,'完成时' if style!='off' else '完成播报已关闭');return
        t=ms-1200
        if o['celebrate_done'] and t<1500:
            origin=QPointF(box.center().x(),box.top()+12);s=t/1000;fade=max(0.,min(1.,(1500-t)/400))
            p.save();p.setOpacity(fade);p.setPen(Qt.PenStyle.NoPen)
            for angle,speed,color in CONFETTI:
                x=origin.x()+math.cos(angle)*speed*s;y=origin.y()+math.sin(angle)*speed*s+220*s*s
                p.setBrush(QColor(color));p.save();p.translate(x,y);p.rotate(t*.4+speed);p.drawRect(QRectF(-2.5,-3.5,5,7));p.restore()
            p.restore()
        if style in ('float','both') and t<5600:
            used=font(o['turn_cost_font_family'],max(9,round(o['turn_cost_font_size']*SCALE)))
            lines=self.float_lines()
            if lines:
                image=render(used,lines,OUTLINES.get(o['turn_cost_outline'],0)*SCALE,1.)
                risen,opacity=timeline(t);anchor=o['turn_cost_anchor']
                if anchor=='above':base=box.top()
                elif anchor=='inside':base=box.top()+box.height()*.08+image.height()
                else:base=box.bottom()
                x=box.center().x()+o['turn_cost_offset_x']*SCALE-image.width()/2;y=base+o['turn_cost_offset_y']*SCALE-image.height()-78*SCALE*risen
                x=max(0,min(x,self.width()-image.width()));y=max(0,min(y,self.height()-image.height()))
                p.save();p.setOpacity(opacity);p.drawPixmap(QPointF(x,y),image);p.restore()
        if style in ('bubble','both') and t>4200:
            parts=[('大约用了 ¥0.0731' if kind=='cost' else '用时 4 分 12 秒') for text,kind in self.float_lines()]
            if parts:self.bubble(p,QPointF(box.center().x(),box.top()+6),'这一轮'+'，'.join(parts),o['bubble_font_family'],o['bubble_font_size']*SCALE,max_width=200)
        self.caption(p,{'float':'飘字','bubble':'气泡','both':'飘字和气泡'}[style]+(' · 撒花' if o['celebrate_done'] else ''))

    def draw_desk(self,p,ms):
        o=self.pet.options;screen=QRectF(4,4,self.width()-8,self.height()-26);self.desk(p,screen)
        side=110;bottom=screen.bottom()-14;edge=screen.right()
        out_box=QRectF(edge-6-side,bottom-side,side,side)
        def tucked_box():
            from .edge_dock import wall_fraction
            frac=wall_fraction(self.art('hover',0));return QRectF(edge-side*frac,bottom-side,side,side)
        label=''
        if o['fullscreen_hide'] and ms>=11500:
            self.draw_art(p,out_box,'idle',ms,opacity=0.)
            p.save();p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(30,36,48));p.drawRoundedRect(screen,10,10)
            p.setPen(QColor('#dbe4f0'));p.drawText(screen,Qt.AlignmentFlag.AlignCenter,'全屏视频播放中');p.restore()
            self.caption(p,'全屏时隐藏');return
        if not o['edge_dock']:
            self.draw_art(p,QRectF(screen.center().x()-side/2,bottom-side,side,side),'idle',ms);label='贴边藏起已关闭'
        elif ms<2500:self.draw_art(p,out_box,'idle',ms);label='靠边待机'
        elif ms<3000:
            k=(ms-2500)/500;a,b=out_box,tucked_box();self.draw_art(p,QRectF(a.left()+(b.left()-a.left())*k,a.top(),side,side),'hover',ms);label=f"安静 {o['dock_tuck_seconds']} 秒后藏起"
        elif ms<6000:self.draw_art(p,tucked_box(),'hover',ms);label=f"安静 {o['dock_tuck_seconds']} 秒后藏起"
        elif ms<6400:
            k=(ms-6000)/400;a,b=tucked_box(),out_box;self.draw_art(p,QRectF(a.left()+(b.left()-a.left())*k,a.top(),side,side),'writing',ms);label='有任务时出来'
        else:self.draw_art(p,out_box,'writing' if ms<9000 else 'idle',ms);label='有任务时出来' if ms<9000 else '靠边待机'
        if o['daily_recap'] and 9000<=ms<11500:
            self.bubble(p,QPointF(screen.center().x()-24,screen.top()+52),'昨天的小结\n完成 12 轮，最长一轮 18 分钟',o['bubble_font_family'],o['bubble_font_size']*SCALE*.95,max_width=170);label='每日小结'
        self.caption(p,label)

    def draw_lock(self,p,ms):
        o=self.pet.options;self.desk(p)
        # Reference windows behind the pet, so transparency is visible against real content.
        for rect,title,colour in ((QRectF(10,10,150,118),'编辑器','#2f3a4c'),(QRectF(self.width()-150,38,142,112),'浏览器','#ffffff')):
            p.save();p.setPen(QPen(QColor('#9fb2c9'),1));p.setBrush(QColor(colour));p.drawRoundedRect(rect,6,6)
            p.setBrush(QColor('#d6e2f0'));p.drawRoundedRect(QRectF(rect.left(),rect.top(),rect.width(),16),6,6);p.drawRect(QRectF(rect.left(),rect.top()+8,rect.width(),8))
            f=QFont(self.font());f.setPixelSize(10);p.setFont(f);p.setPen(QColor('#445b78'));p.drawText(QRectF(rect.left()+6,rect.top(),rect.width(),16),Qt.AlignmentFlag.AlignVCenter,title)
            dark=colour!='#ffffff'
            for i in range(6):
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(['#7fc7ff','#ffcf70','#9be29b','#ff9a9a','#c5a3ff','#8fd3d0'][i] if dark else '#c9d3df'))
                p.drawRoundedRect(QRectF(rect.left()+8,rect.top()+24+i*13,(rect.width()-20)*(.45+.08*((i*3)%5)),6),3,3)
            p.restore()
        box=self.pet_box(112,bottom=self.height()-24,center=self.width()*.58);hover=2000<=ms<5000
        opacity=1-o['locked_hover_transparency']/100 if hover else 1.
        self.draw_art(p,box,'idle',ms,opacity=opacity)
        side=max(6,round(28*o['lock_button_size']/100*SCALE*1.4));lock=QRectF(box.right()-side-6,box.top()+8,side,side)
        p.save();p.setOpacity(1-o['lock_button_transparency']/100);p.setPen(QPen(QColor('#3a6fb0'),1.2));p.setBrush(QColor('#eef5ff'));p.drawEllipse(lock)
        p.setPen(QPen(QColor('#3a6fb0'),max(1.,side/12)));p.setBrush(Qt.BrushStyle.NoBrush)
        body=lock.adjusted(side*.3,side*.45,-side*.3,-side*.22);p.drawRoundedRect(body,1.5,1.5);p.drawArc(QRectF(body.left()+body.width()*.12,lock.top()+side*.2,body.width()*.76,side*.5),0,180*16);p.restore()
        if hover:
            path=QPainterPath();x,y=box.center().x()-6,box.center().y()+6
            for dx,dy in ((0,0),(0,16),(4,12),(7,19),(9,18),(6,11),(11,11)):path.lineTo(x+dx,y+dy) if path.elementCount() else path.moveTo(x,y)
            path.closeSubpath();p.save();p.setPen(QPen(QColor('#ffffff'),1.2));p.setBrush(QColor('#1d2a3a'));p.drawPath(path);p.restore()
        self.caption(p,f"锁定后鼠标移上去：透明 {o['locked_hover_transparency']}%" if hover else '锁定后：点击穿透到下方窗口')

    def draw_rest(self,p,ms):
        o=self.pet.options;self.desk(p);box=self.pet_box(112,bottom=self.height()-24,center=62)
        self.draw_art(p,box,'feed' if o['rest_reminder'] else 'idle',ms)
        if not o['rest_reminder']:self.caption(p,'休息提醒已关闭');return
        card=QRectF(self.width()-124,12,118,140)
        p.save();p.setPen(QPen(BUBBLE_EDGE,1.4));p.setBrush(QColor('#f4f9ff'));p.drawRoundedRect(card,10,10)
        f=font(o['font_family'],10);p.setFont(f);p.setPen(INK)
        p.drawText(card.adjusted(8,8,-8,-90),Qt.TextFlag.TextWordWrap,f"已经陪你坐了 {o['rest_interval_minutes']} 分钟。\n喝口水，伸个懒腰吧。")
        for i,label in enumerate(('30 分钟后再提醒','知道了','关闭提醒')):
            b=QRectF(card.left()+8,card.top()+58+i*26,card.width()-16,20);p.setPen(QPen(QColor('#b9cde4'),1));p.setBrush(QColor('#ffffff'));p.drawRoundedRect(b,5,5)
            p.setPen(INK);p.drawText(b,Qt.AlignmentFlag.AlignCenter,label)
        p.restore();self.caption(p,f"每 {o['rest_interval_minutes']} 分钟 · 卡片停留 10 秒")

    def draw_sound(self,p,ms):
        o=self.pet.options;self.desk(p);box=self.pet_box(112,bottom=self.height()-24,center=78)
        muted=o['audio_muted'] or not o['audio_enabled'];self.draw_art(p,box,'pet' if not muted else 'idle',ms)
        if not muted:
            self.bubble(p,QPointF(self.width()-62,box.top()+30),'我是守岸人，\n黑海岸的代行者。',o['bubble_font_family'],o['bubble_font_size']*SCALE*1.05,max_width=120)
        icon=QRectF(self.width()-46,self.height()-58,22,22)
        p.save();p.setPen(QPen(INK,1.6));p.setBrush(Qt.BrushStyle.NoBrush)
        speaker=QPainterPath();speaker.moveTo(icon.left(),icon.top()+7);speaker.lineTo(icon.left()+6,icon.top()+7);speaker.lineTo(icon.left()+12,icon.top()+1)
        speaker.lineTo(icon.left()+12,icon.bottom()-1);speaker.lineTo(icon.left()+6,icon.bottom()-7);speaker.lineTo(icon.left(),icon.bottom()-7);speaker.closeSubpath();p.drawPath(speaker)
        if muted:p.setPen(QPen(QColor('#c0392b'),2));p.drawLine(QPointF(icon.left()+14,icon.top()+5),QPointF(icon.right(),icon.bottom()-5))
        else:
            for r in (5,9):p.drawArc(QRectF(icon.left()+12-r,icon.center().y()-r,2*r,2*r),-45*16,90*16)
        track=QRectF(self.width()-90,self.height()-30,70,5);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#c1d3e7'));p.drawRoundedRect(track,2,2)
        if not muted:p.setBrush(QColor('#3a78c2'));p.drawRoundedRect(QRectF(track.left(),track.top(),track.width()*o['volume']/100,track.height()),2,2)
        p.restore()
        self.caption(p,'静音' if o['audio_muted'] else ('语音提醒已关闭' if not o['audio_enabled'] else f"音量 {o['volume']}%"))
