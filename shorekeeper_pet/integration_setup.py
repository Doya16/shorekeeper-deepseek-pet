"""Install through the official packaged CLI, keeping account and chat files untouched."""
import pathlib,subprocess
from .paths import ROOT
from .bridge import discover_deepseek

def install(options):
    client=discover_deepseek(options.get('deepseek_executable',''))
    if not client: raise OSError('请先安装官方 DeepSeek Harness，或选择正确的程序路径。')
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/install_deepseek_plugin.ps1'),'-ClientPath',client]
    if options.get('deepseek_home'): command+=['-DataHome',options['deepseek_home']]
    result=subprocess.run(command,capture_output=True,encoding='utf8',errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
    if result.returncode:
        raise OSError('安装未完成。请从 DeepSeek 托盘菜单完全退出客户端后重试。\n'+result.stderr[-1200:])
    return '连接插件已安装。重新打开 DeepSeek Harness 后，状态和余额会自动同步。'
