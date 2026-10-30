import json,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
from shorekeeper_pet import shortcuts
from shorekeeper_pet.appearance import appearance
from shorekeeper_pet.paths import EXECUTABLE_NAME

class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name)
        self.root=self.base/'安装目录 中文';self.root.mkdir();(self.root/EXECUTABLE_NAME).touch()
        (self.root/'tools').mkdir();(self.root/'tools/create_shortcut.ps1').touch()
        self.desktop=self.base/'重定向桌面';self.desktop.mkdir();self.state=self.base/'local-state'
        self.link=self.desktop/(pathlib.Path(EXECUTABLE_NAME).stem+'.lnk')
    def tearDown(self):self.temp.cleanup()
    def result(self,*args,**kwargs):
        self.link.write_bytes(b'test-link')
        return subprocess.CompletedProcess(args[0],0,json.dumps({'shortcut':str(self.link)},ensure_ascii=False).encode(),b'')
    def first(self,root=None,**kw):
        return shortcuts.ensure_first_launch_shortcut(root or self.root,state_root=self.state,destination=self.desktop,frozen=True,**kw)
    def test_first_launch_once_and_manual_recreation(self):
        with patch.object(shortcuts.subprocess,'run',side_effect=self.result) as run:
            self.assertEqual(self.first(),self.link);self.link.unlink()
            self.assertIsNone(self.first());self.assertFalse(self.link.exists());self.assertEqual(run.call_count,1)
            self.assertEqual(shortcuts.create_desktop_shortcut(self.root,self.desktop,state_root=self.state),self.link)
            self.assertTrue(self.link.exists());self.assertEqual(run.call_count,2)
            args=run.call_args.args[0];self.assertIn(str(self.root/EXECUTABLE_NAME),args)
            self.assertIn(str(self.desktop),args);self.assertNotIn('shell',run.call_args.kwargs)
    def test_moved_install_and_new_machine_have_independent_markers(self):
        with patch.object(shortcuts.subprocess,'run',side_effect=self.result) as run:
            self.first();moved=self.base/'新电脑 新目录';moved.mkdir();(moved/EXECUTABLE_NAME).touch()
            (moved/'tools').mkdir();(moved/'tools/create_shortcut.ps1').touch();self.first(moved)
            self.assertEqual(run.call_count,2)
            self.assertNotEqual(shortcuts.marker_path(self.root,self.state),shortcuts.marker_path(moved,self.state))
            self.assertFalse(shortcuts.marker_path(self.root,self.base/'another-user').exists())
    def test_source_preview_and_verification_never_create_shortcuts(self):
        with patch.object(shortcuts.subprocess,'run') as run:
            self.assertIsNone(self.first(normal=False))
            self.assertIsNone(shortcuts.ensure_first_launch_shortcut(self.root,frozen=False,state_root=self.state))
            run.assert_not_called()
    def test_failure_nonfatal_and_next_launch_can_retry(self):
        for failure in (OSError('denied'),subprocess.TimeoutExpired('powershell',25)):
            with patch.object(shortcuts.subprocess,'run',side_effect=failure):self.assertIsNone(self.first())
            self.assertFalse(shortcuts.marker_path(self.root,self.state).exists())
        with patch.object(shortcuts.subprocess,'run',side_effect=self.result):self.assertEqual(self.first(),self.link)
    def test_invalid_settings_default_to_badged(self):
        for value in (None,[],{},True,'invalid'):
            self.assertEqual(appearance({'appearance':{'tray_icon_style':value}})['tray_icon_style'],'badged')
        self.assertEqual(appearance({'appearance':{'tray_icon_style':'clean'}})['tray_icon_style'],'clean')
