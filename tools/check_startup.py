"""Exercise the real Windows Run entry and watcher with an isolated test launcher."""
import json,pathlib,sys,tempfile,time,winreg
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from shorekeeper_pet import startup
assert startup.deepseek_processes(),'Open DeepSeek before running this integration check'
previous=None;process=None
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,startup.RUN_KEY) as key:previous=winreg.QueryValueEx(key,startup.RUN_NAME)
except FileNotFoundError:pass
with tempfile.TemporaryDirectory(prefix='pet-startup-') as temp:
    target=pathlib.Path(temp)/'中文 with spaces';(target/'tools').mkdir(parents=True)
    marker=target/'launched.txt'
    stub=f'''import pathlib,sys
sys.path.insert(0,{str(root)!r})
from shorekeeper_pet.startup import watch
if '--watch-deepseek' in sys.argv:
    raise SystemExit(watch(pathlib.Path({str(target)!r})))
with pathlib.Path({str(marker)!r}).open('a') as f:f.write('launch\\n')
'''
    (target/'tools/run_pet.py').write_text(stub,encoding='utf8')
    try:
        process=startup.configure(True,target)
        assert '--watch-deepseek' in startup.registered_command() and str(target) in startup.registered_command()
        end=time.monotonic()+12
        while not marker.exists() and time.monotonic()<end:time.sleep(.1)
        assert marker.exists(),'Watcher did not launch on the running DeepSeek desktop'
        time.sleep(3)
        assert marker.read_text().splitlines()==['launch'],'Watcher repeatedly launched during the same desktop run'
        startup.configure(False,target);assert startup.registered_command()==''
        assert process.wait(timeout=6)==0
    finally:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,startup.RUN_KEY) as key:
            if previous is None:
                try:winreg.DeleteValue(key,startup.RUN_NAME)
                except FileNotFoundError:pass
            else:winreg.SetValueEx(key,startup.RUN_NAME,0,previous[1],previous[0])
        if process is not None and process.poll() is None:
            process.terminate();process.wait(timeout=5)
        assert startup.registered_command()==(previous[0] if previous else '')
report=dict(ok=True,desktop_detected=True,unicode_paths=True,native_run_registration=True,launch_once=True,disable_stops_watcher=True,previous_registration_restored=True)
(root/'qa/v091-startup-checks.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
