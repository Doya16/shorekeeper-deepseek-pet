"""Exercise folder opening, importing, previewing, resetting and relocating media."""
import json,pathlib,shutil,sys,tempfile
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
from PIL import Image
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from shorekeeper_pet.config_io import export_bundle,import_bundle
from shorekeeper_pet.presets import load_defaults
from shorekeeper_pet import pet as module
app=QApplication([]); app.setQuitOnLastWindowClosed(False)
original=(root/'settings.json').read_bytes() if (root/'settings.json').is_file() else None; checks=[]
with tempfile.TemporaryDirectory() as directory:
    temp=pathlib.Path(directory); local=temp/'pet'; local.mkdir()
    for folder in ('assets','fonts','defaults'): shutil.copytree(root/folder,local/folder)
    module.ROOT=local; module.SETTINGS=local/'settings.json'
    pet=module.Pet(offline=True); pet.options['audio_enabled']=False; pet.voice.gate.path=local/'voice-history.json'; pet.show(); pet.open_bindings(); editor=pet.binding_editor
    assert pet.requested_scale==load_defaults(local)['scale']
    assert pet.binding('thinking')['asset']==load_defaults(local)['bindings']['thinking']['asset']
    with patch('shorekeeper_pet.studio.QDesktopServices.openUrl',return_value=True) as opened:
        editor.directory_button.click(); assert pathlib.Path(opened.call_args.args[0].toLocalFile())==local/'assets/custom'
    source=temp/'my-picture.webp'; Image.new('RGB',(80,40),'#659bda').save(source)
    with patch('shorekeeper_pet.studio.QFileDialog.getOpenFileNames',return_value=([str(source)],'')): editor.import_button.click()
    aid=next(row['id'] for row in module.CATALOG if row['name']=='my-picture.webp')
    for i in range(editor.gallery.count()):
        if editor.gallery.item(i).data(Qt.ItemDataRole.UserRole)==aid: editor.gallery.setCurrentRow(i); break
    assert pet.binding('pet')['asset']==aid and editor.preview_animation.frames[0].width()==80
    editor.try_binding(); app.processEvents(); assert pet.animation_id==aid
    target=pet.image_rect(pet.animation.frames[0]); assert target.width()==target.height()*2
    checks.append('open folder points to assets/custom; import WebP, preview, select and display without distortion')
    Image.new('RGB',(40,80),'#dbc7ed').save(local/'assets/custom/direct.png'); editor.refresh_button.click()
    assert any(row['name']=='direct.png' for row in module.CATALOG)
    pet.save_settings(); archive=temp/'profile.zip'; export_bundle(archive,pet.settings,local)
    moved=temp/'moved'; restored=import_bundle(archive,moved)
    assert (moved/'assets/custom/my-picture.webp').read_bytes()==source.read_bytes()
    assert (moved/'defaults/settings.json').read_bytes()==(local/'defaults/settings.json').read_bytes()
    assert restored['bindings']['pet']['asset']==aid
    editor.reset_button.click(); assert pet.binding('pet')['asset']==load_defaults(local)['bindings']['pet']['asset']
    checks.append('manual folder additions refresh; selected asset and shipped defaults survive export/import; reset restores shipped preset')
    pet.timer.stop(); pet.voice.stop(); editor.hide(); pet.hide(); QFontDatabase.removeAllApplicationFonts()
assert ((root/'settings.json').read_bytes() if (root/'settings.json').is_file() else None)==original
result=dict(ok=True,checks=checks); (root/'qa/v08-ui-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(result))
