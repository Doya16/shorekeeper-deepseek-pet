"""Regressions for package relocation and old profile compatibility."""
import hashlib,json,pathlib,subprocess,sys,tempfile,unittest,zipfile
from shorekeeper_pet.config_io import export_bundle,import_bundle
from shorekeeper_pet.paths import EXECUTABLE_NAME,PORTABLE_DIRNAME,ROOT

class LayoutTests(unittest.TestCase):
    def test_source_entry_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result=subprocess.run([sys.executable,str(ROOT/'tools/run_pet.py'),'--help'],
                cwd=folder,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--verify-package',result.stdout)

    def test_package_entry(self):
        result=subprocess.run([sys.executable,'-m','shorekeeper_pet','--help'],
            cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--verify-package',result.stdout)

    def test_new_layout_survives_portable_reexport(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)/'桌宠 with spaces';root.mkdir()
            files={EXECUTABLE_NAME:b'MZ test','_internal/qt.dll':b'qt',
                'shorekeeper_pet/__init__.py':b'', 'shorekeeper_pet/pet.py':b'# pet',
                'tools/run_pet.py':b'# entry','tools/创建桌面快捷方式.cmd':b'entry',
                'tools/install_deepseek_plugin.ps1':b'# install',
                'integrations/deepseek/index.js':b'// plugin',
                'integrations/deepseek/dsh-shorekeeper-pet-0.1.2.tgz':b'package',
                'docs/USAGE.md':b'guide','assets/originals/a.gif':b'GIF89a'}
            for name,data in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            cfg={'appearance':{},'bindings':{}}
            first=pathlib.Path(folder)/'one.zip';export_bundle(first,cfg,root,True)
            moved=pathlib.Path(folder)/'another pc';moved.mkdir()
            with zipfile.ZipFile(first) as z:z.extractall(moved)
            second=pathlib.Path(folder)/'two.zip'
            export_bundle(second,json.loads((moved/'settings.json').read_text()),moved,True)
            with zipfile.ZipFile(second) as z:
                for name,data in files.items():self.assertEqual(z.read(name),data)
                self.assertNotIn('Shorekeeper.exe',z.namelist())
                self.assertFalse(any('/' not in n and n.endswith('.py') for n in z.namelist()))

    def test_old_portable_import_never_replaces_new_program(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);archive=root/'legacy.zip';target=root/'new'
            target.mkdir();(target/EXECUTABLE_NAME).write_bytes(b'NEW PROGRAM')
            data=b'GIF89a';name='assets/originals/old.gif'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('settings.json',json.dumps({'schema_version':6,'scale':.75,'bindings':{}}))
                z.writestr('manifest.json',json.dumps({'format':'shorekeeper-portable','files':{name:{'sha256':hashlib.sha256(data).hexdigest()}}}))
                z.writestr(name,data);z.writestr('Shorekeeper.exe',b'OLD PROGRAM');z.writestr('source/pet.py',b'old code')
            cfg=import_bundle(archive,target)
            self.assertEqual(cfg['scale'],.75)
            self.assertEqual((target/name).read_bytes(),data)
            self.assertEqual((target/EXECUTABLE_NAME).read_bytes(),b'NEW PROGRAM')
            self.assertFalse((target/'Shorekeeper.exe').exists())
            self.assertFalse((target/'source').exists())

if __name__=='__main__':unittest.main()
