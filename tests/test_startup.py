import pathlib,tempfile,unittest
from unittest.mock import patch
from shorekeeper_pet.startup import LaunchEdges,is_deepseek_desktop,launch_args

class StartupTests(unittest.TestCase):
    def test_detect_desktop_but_not_codex_or_cli(self):
        self.assertTrue(is_deepseek_desktop('C:/Apps/DeepSeek Harness/DeepSeek Harness.exe'))
        self.assertFalse(is_deepseek_desktop('C:/Apps/Codex/Codex.exe'))
        self.assertFalse(is_deepseek_desktop('C:/Apps/dsh.exe'))
    def test_launch_once_per_desktop_session_and_again_after_restart(self):
        edges=LaunchEdges();self.assertFalse(edges.update([]));self.assertTrue(edges.update([10]))
        self.assertFalse(edges.update([10,11]));self.assertFalse(edges.update([10]));self.assertFalse(edges.update([]))
        self.assertTrue(edges.update([20]));self.assertTrue(edges.update([30]));self.assertFalse(edges.update([30]))
    def test_source_and_frozen_commands_preserve_unicode_spaces(self):
        root=pathlib.Path('D:/我的 桌宠')
        with patch('shorekeeper_pet.startup.sys.frozen',False,create=True):
            args=launch_args(root,True);self.assertEqual(args[-2],str(root/'tools/run_pet.py'));self.assertEqual(args[-1],'--watch-deepseek')
        with patch('shorekeeper_pet.startup.sys.frozen',True,create=True),patch('shorekeeper_pet.startup.sys.executable',str(root/'守岸人DeepSeek桌宠启动.exe')):
            self.assertEqual(launch_args(root,True),[str((root/'守岸人DeepSeek桌宠启动.exe').resolve()),'--watch-deepseek'])

if __name__=='__main__':unittest.main()
