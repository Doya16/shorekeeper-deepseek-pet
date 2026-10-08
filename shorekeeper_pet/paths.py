import os,pathlib,sys
ROOT=pathlib.Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else pathlib.Path(__file__).resolve().parents[1]
DSH_HOME=pathlib.Path(os.environ.get('DSH_HOME',pathlib.Path.home()/'.dsh'))
VERSION='0.1.0'
APP_NAME='守岸人DeepSeek桌宠启动'
EXECUTABLE_NAME=APP_NAME+'.exe'
PORTABLE_DIRNAME='守岸人DeepSeek桌宠'
