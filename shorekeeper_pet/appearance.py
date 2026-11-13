import math
from PySide6.QtGui import QFont,QFontDatabase
DEFAULTS=dict(turn_cost_style='float',turn_cost_show_cost=True,turn_cost_show_time=True,turn_cost_order='cost,time',celebrate_done=True,edge_dock=True,fullscreen_hide=False,daily_recap=True,turn_cost_font_family='ZCOOL KuaiLe',turn_cost_font_size=35,turn_cost_outline='thin',turn_cost_anchor='inside',rest_reminder=True,rest_interval_minutes=60,rest_snooze_minutes=30,dock_tuck_seconds=60,turn_cost_cost_bold=False,turn_cost_cost_italic=False,turn_cost_cost_color='#e4572e',turn_cost_time_bold=False,turn_cost_time_italic=False,turn_cost_time_color='#2f6db5',turn_cost_offset_x=0,turn_cost_offset_y=0,check_updates_periodic=True,update_interval_hours=6,update_snoozed_date='',show_quota=True,exit_with_deepseek=True,update_source='auto',tray_icon_style='badged',locked_hover_transparency=70,lock_button_size=100,lock_button_transparency=35,audio_muted=False,interaction_locked=False,check_updates_on_start=True,ignored_update_version='',font_family='LXGW WenKai',bubble_font_family='ZCOOL KuaiLe',bubble_font_size=19,quota_font_size=17,ui_font_size=17,bubble_width=390,bubble_width_ratio=1.0,quota_scale=1.0,pet_size=230,volume=75,audio_enabled=False,audio_cooldown=12,audio_directory='audio',deepseek_home='',deepseek_executable='',launch_with_deepseek=False)

def load_fonts(root):
    families=[]
    for path in sorted((root/'fonts').glob('*')):
        if path.suffix.lower() not in ('.ttf','.otf','.ttc'): continue
        font_id=QFontDatabase.addApplicationFont(str(path))
        if font_id>=0: families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return list(dict.fromkeys(families))

def appearance(settings):
    result=dict(DEFAULTS); item=settings.get('appearance',{})
    if isinstance(item,dict): result.update({k:v for k,v in item.items() if k in DEFAULTS})
    for key,low,high in [('dock_tuck_seconds',10,600),('rest_interval_minutes',15,240),('rest_snooze_minutes',1,240),('turn_cost_font_size',14,72),('turn_cost_offset_x',-400,400),('turn_cost_offset_y',-400,400),('update_interval_hours',1,168),('locked_hover_transparency',0,95),('lock_button_size',50,200),('lock_button_transparency',0,90),('bubble_font_size',12,40),('quota_font_size',12,32),('ui_font_size',13,28),('bubble_width',300,650),('bubble_width_ratio',.75,4),('quota_scale',.5,2.5),('pet_size',140,420),('volume',0,100),('audio_cooldown',0,300)]:
        value=result[key]; result[key]=max(low,min(high,value)) if isinstance(value,(float,int)) and math.isfinite(value) else DEFAULTS[key]
    for key in ('font_family','bubble_font_family','turn_cost_font_family','audio_directory','deepseek_home','deepseek_executable'):
        if not isinstance(result[key],str): result[key]=DEFAULTS[key]
    result['launch_with_deepseek']=result['launch_with_deepseek'] is True
    for key in ('audio_muted','interaction_locked'): result[key]=result[key] is True
    result['check_updates_on_start']=result['check_updates_on_start'] is not False
    result['check_updates_periodic']=result['check_updates_periodic'] is not False
    result['update_interval_hours']=round(result['update_interval_hours'])
    if not isinstance(result['update_snoozed_date'],str):result['update_snoozed_date']=''
    result['show_quota']=result['show_quota'] is not False
    if result['turn_cost_style'] not in ('off','bubble','float','both'):result['turn_cost_style']=DEFAULTS['turn_cost_style']
    if result['turn_cost_outline'] not in ('none','thin','thick'):result['turn_cost_outline']=DEFAULTS['turn_cost_outline']
    if result['turn_cost_anchor'] not in ('bottom','inside','above'):result['turn_cost_anchor']=DEFAULTS['turn_cost_anchor']
    result['rest_reminder']=result['rest_reminder'] is not False
    result['rest_snooze_minutes']=round(result['rest_snooze_minutes'])
    for kind in ('cost','time'):
        for key in (f'turn_cost_{kind}_bold',f'turn_cost_{kind}_italic'):result[key]=result[key] is True
        colour=result[f'turn_cost_{kind}_color']
        if not (isinstance(colour,str) and len(colour)==7 and colour[0]=='#' and all(c in '0123456789abcdefABCDEF' for c in colour[1:])):result[f'turn_cost_{kind}_color']=DEFAULTS[f'turn_cost_{kind}_color']
    if result['turn_cost_order'] not in ('cost,time','time,cost'):result['turn_cost_order']=DEFAULTS['turn_cost_order']
    for key in ('turn_cost_show_cost','turn_cost_show_time','celebrate_done','edge_dock','daily_recap'):result[key]=result[key] is not False
    result['fullscreen_hide']=result['fullscreen_hide'] is True
    if not isinstance(result['ignored_update_version'],str) or len(result['ignored_update_version'])>32:result['ignored_update_version']=''
    if result['tray_icon_style'] not in ('clean','badged'):result['tray_icon_style']='badged'
    result['exit_with_deepseek']=result['exit_with_deepseek'] is not False
    if result['update_source'] not in ('auto','github','mirror'):result['update_source']='auto'
    return result

def font(family,size,bold=False):
    f=QFont(family); f.setPixelSize(round(size)); f.setBold(bold); return f

def stylesheet(options):
    family=options['font_family'].replace('"',''); size=int(options['ui_font_size'])
    return f'''QDialog,QWidget#settingsBody{{background:#f4f7fc;color:#304966;}}
    QLabel,QCheckBox,QGroupBox,QPushButton,QComboBox,QLineEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QListWidget,QTabBar{{font-family:"{family}";font-size:{size}px;color:#304966;}}
    QGroupBox{{border:1px solid #d4e0ee;border-radius:12px;margin-top:16px;padding:17px 12px 12px;}}
    QGroupBox::title{{subcontrol-origin:margin;left:14px;}}
    QLineEdit,QComboBox,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QPushButton{{background:white;border:1px solid #cbd9ec;border-radius:7px;padding:7px;min-height:22px;}}
    QPushButton:hover{{background:#e1edff;}} QComboBox QAbstractItemView{{background:white;color:#304966;selection-background-color:#dceaff;selection-color:#244a82;}}
    QSlider::groove:horizontal{{height:8px;background:#d2e0f1;border-radius:4px;}} QSlider::sub-page:horizontal{{background:#649ad8;border-radius:4px;}} QSlider::handle:horizontal{{background:#f8fcff;border:2px solid #4d83bd;width:22px;margin:-8px 0;border-radius:12px;}}
    QLineEdit:disabled,QComboBox:disabled,QPlainTextEdit:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled,QPushButton:disabled{{background:#e2e6ec;color:#7c8592;border-color:#cbd1d9;}}
    QSpinBox::up-button:disabled,QSpinBox::down-button:disabled,QDoubleSpinBox::up-button:disabled,QDoubleSpinBox::down-button:disabled{{background:#d7dde5;border-color:#c5cdd8;}}
    QCheckBox:disabled{{color:#858d98;}} QLabel#lockedHint{{color:#657386;}}
    QListWidget{{background:white;border:1px solid #d5e0ef;border-radius:10px;outline:0;}}
    QListWidget::item{{padding:5px;border-radius:6px;}} QListWidget::item:selected{{background:#dceaff;color:#244a82;}}
    QTabBar::tab{{background:#e5edf9;padding:10px 18px;}} QTabBar::tab:selected{{background:#cddffa;}}
    QTabWidget::pane{{border:1px solid #d4e0ee;background:#f4f7fc;}} QScrollBar:vertical{{background:#edf2fa;width:10px;margin:0;}} QScrollBar::handle:vertical{{background:#bfcee4;min-height:25px;border-radius:5px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
    QScrollArea{{border:0;background:transparent;}} QToolTip{{font-family:"{family}";font-size:{size}px;color:#304966;background:#f7fbff;border:1px solid #ccd9ea;}}'''
