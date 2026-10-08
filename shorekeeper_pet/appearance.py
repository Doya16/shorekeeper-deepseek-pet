import math
from PySide6.QtGui import QFont,QFontDatabase
DEFAULTS=dict(font_family='LXGW WenKai',bubble_font_family='ZCOOL KuaiLe',bubble_font_size=19,quota_font_size=17,ui_font_size=17,bubble_width=390,bubble_width_ratio=1.0,quota_scale=1.0,pet_size=230,volume=75,audio_enabled=False,audio_cooldown=12,audio_directory='audio',deepseek_home='',deepseek_executable='',launch_with_deepseek=False)

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
    for key,low,high in [('bubble_font_size',12,40),('quota_font_size',12,32),('ui_font_size',13,28),('bubble_width',300,650),('bubble_width_ratio',.75,4),('quota_scale',.5,2.5),('pet_size',140,420),('volume',0,100),('audio_cooldown',0,300)]:
        value=result[key]; result[key]=max(low,min(high,value)) if isinstance(value,(float,int)) and math.isfinite(value) else DEFAULTS[key]
    for key in ('font_family','bubble_font_family','audio_directory','deepseek_home','deepseek_executable'):
        if not isinstance(result[key],str): result[key]=DEFAULTS[key]
    result['launch_with_deepseek']=result['launch_with_deepseek'] is True
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
