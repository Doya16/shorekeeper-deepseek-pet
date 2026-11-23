"""Install through the official packaged CLI, keeping account and chat files untouched.

The installer refuses while DeepSeek Harness runs (closing the window leaves it in the tray). Instead of failing at once,
the pet asks the user to quit from the tray and waits, then installs. A failure is explained in plain words; the full
installer output goes to plugin-install.log in the program folder, never into the settings window."""
import locale,pathlib,subprocess,time
from .paths import ROOT
from .bridge import discover_deepseek

WAIT_SECONDS=120
LOG='plugin-install.log'
MARKER='PET-INSTALL-ERROR: '
QUIT_HINT='请在任务栏右下角托盘里的 DeepSeek 图标上右键 → 退出（只关窗口不算，登录状态会保留）'
RUNNING=f'DeepSeek Harness 还在运行。{QUIT_HINT}，退出后会自动继续安装'
STILL_RUNNING=f'DeepSeek Harness 一直在运行，所以没有安装。{QUIT_HINT}，再点一次「安装 / 更新 Harness 连接插件」。'
MISSING='没有找到 DeepSeek Harness。请先安装并登录官方 DeepSeek Harness，或在下方「DeepSeek 程序」里选择 DeepSeek Harness.exe。'
FAILED=f'连接插件没有装上。请确认 DeepSeek Harness 已完全退出后再试一次；仍不行时，把程序文件夹里的 {LOG} 发给作者。'
EXPLAIN=[  # installer reason (English, from install_deepseek_plugin.ps1) -> what the user can do
    ('Install the official DeepSeek Harness desktop app first',MISSING),
    ('does not include the plugin installer','这个版本的 DeepSeek Harness 还不支持插件。请先把 DeepSeek Harness 更新到最新版本，再安装连接插件。'),
    ('Please quit DeepSeek Harness completely',STILL_RUNNING),
    ('Open DeepSeek Harness once','请先打开并登录一次 DeepSeek Harness，然后从托盘完全退出，再安装连接插件。'),
    ('The plugin package is missing','桌宠文件夹里缺少连接插件安装包。请重新完整解压桌宠完整包后再安装。'),
]


def harness_running():
    from .startup import deepseek_process_tree
    try: return bool(deepseek_process_tree())
    except OSError: return False


def decode(raw):
    """Installer output: UTF-8, or the console code page on systems where PowerShell ignored the UTF-8 request."""
    if not raw: return ''
    for encoding in ('utf-8',locale.getpreferredencoding(False),'mbcs'):
        try: return raw.decode(encoding)
        except (UnicodeDecodeError,LookupError): continue
    return raw.decode('utf-8','replace')


def explain(output):
    reason=next((line[len(MARKER):].strip() for line in output.splitlines() if line.startswith(MARKER)),'')
    return next((message for key,message in EXPLAIN if key in reason),FAILED)


def write_log(text):
    try: (ROOT/LOG).write_text(time.strftime('%Y-%m-%d %H:%M:%S')+'\n'+text,encoding='utf8')
    except OSError: pass


def install(options,progress=None,wait_seconds=WAIT_SECONDS,running=None,sleep=time.sleep,clock=time.monotonic,run=subprocess.run):
    running=running or harness_running
    client=discover_deepseek(options.get('deepseek_executable',''))
    if not client: raise OSError(MISSING)
    deadline=clock()+wait_seconds
    while running():
        left=int(deadline-clock())
        if left<=0: raise OSError(STILL_RUNNING)
        if progress: progress(f'{RUNNING}（最多再等 {left} 秒）。')
        sleep(1)
    if progress: progress('正在安装连接插件…')
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/install_deepseek_plugin.ps1'),'-ClientPath',client]
    if options.get('deepseek_home'): command+=['-DataHome',options['deepseek_home']]
    try:
        result=run(command,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180)
    except subprocess.TimeoutExpired:
        write_log('installer timed out after 180 s'); raise OSError(FAILED)
    output=decode(result.stdout)+'\n'+decode(result.stderr)
    write_log(f'exit {result.returncode}\n{output}')
    if result.returncode: raise OSError(explain(output))
    return '连接插件已安装。重新打开 DeepSeek Harness 后，状态和余额会自动同步。'
