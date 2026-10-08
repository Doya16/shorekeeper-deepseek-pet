import os,pathlib,subprocess,sys,shutil
sys.stdout.reconfigure(encoding='utf8')
root=pathlib.Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(root/'tools/package_plugin.py')],check=True)
sys.path.insert(0,str(root))
from shorekeeper_pet.paths import APP_NAME,PORTABLE_DIRNAME
args=[sys.executable,'-m','PyInstaller','--clean','--noconfirm','--onedir','--windowed','--name',APP_NAME,'--icon',str(root/'assets/shorekeeper.ico'),'--version-file',str(root/'tools/windows_version.txt'),'--paths',str(root),'--distpath',str(root/'dist'),'--workpath',str(root/'build'),'--specpath',str(root/'build')]
for module in ('pandas','scipy','matplotlib','tkinter','PySide6.QtWebEngineCore','PySide6.QtQml'): args+=['--exclude-module',module]
args+=[str(root/'tools/run_pet.py')]
# Do not let unrelated developer tools supply DLLs with system-library names.
# In particular, Poppler's ICU exports versioned symbols incompatible with Qt.
env=os.environ.copy()
windows=pathlib.Path(env.get('SystemRoot','C:/Windows'))
env['PATH']=os.pathsep.join(map(str,(windows/'System32',windows,pathlib.Path(sys.executable).parent)))
subprocess.run(args,cwd=root,env=env,check=True)
dest=root/'dist'/APP_NAME
named=root/'dist'/PORTABLE_DIRNAME
if named.exists():
    assert named.resolve().parent==(root/'dist').resolve()
    shutil.rmtree(named)
dest.rename(named); dest=named
for folder in ('assets','fonts','licenses','defaults'):
    if (root/folder).is_dir(): shutil.copytree(root/folder,dest/folder,dirs_exist_ok=True)
(dest/'audio').mkdir(exist_ok=True)
for name in ('README.md','MIGRATION.txt','THIRD_PARTY.txt','requirements.txt'): shutil.copy2(root/name,dest/name)
shutil.copytree(root/'shorekeeper_pet',dest/'shorekeeper_pet',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(root/'docs',dest/'docs')
(dest/'tools').mkdir()
for name in ('创建桌面快捷方式.cmd','run_pet.py','create_shortcut.ps1','install_deepseek_plugin.ps1'): shutil.copy2(root/'tools'/name,dest/'tools'/name)
shutil.copytree(root/'integrations',dest/'integrations',ignore=shutil.ignore_patterns('*.test.js'))
subprocess.run([sys.executable,str(root/'tools/verify_portable.py'),str(dest)],cwd=root,check=True)
print('Built '+str(dest))
