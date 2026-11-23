"""Installing the Harness connection plugin: wait for Harness to quit, explain failures plainly, keep raw output in a log."""
import pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from shorekeeper_pet import integration_setup as setup

REPO=pathlib.Path(__file__).resolve().parents[1]


class Result:
    def __init__(self,code,out=b'',err=b''): self.returncode=code; self.stdout=out; self.stderr=err


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name)
        self.patches=[patch.object(setup,'ROOT',self.root),patch.object(setup,'discover_deepseek',return_value=r'C:\DSH\DeepSeek Harness.exe')]
        for p in self.patches: p.start()
        self.now=[0.0]; self.messages=[]; self.commands=[]

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def install(self,running,result):
        def run(command,**kw): self.commands.append(command); return result
        return setup.install({},progress=self.messages.append,wait_seconds=120,running=running,
                             sleep=lambda s:self.now.__setitem__(0,self.now[0]+s),clock=lambda:self.now[0],run=run)

    def test_waits_for_harness_to_quit_then_installs(self):
        states=iter([True,True,True,False])
        text=self.install(lambda:next(states),Result(0,b'Shorekeeper plugin installed.'))
        self.assertIn('连接插件已安装',text); self.assertEqual(len(self.commands),1)
        self.assertTrue(self.messages[0].startswith('DeepSeek Harness 还在运行')); self.assertIn('托盘',self.messages[0]); self.assertIn('最多再等 120 秒',self.messages[0])
        self.assertEqual(self.messages[-1],'正在安装连接插件…')

    def test_gives_up_with_a_plain_hint_if_harness_never_quits(self):
        with self.assertRaises(OSError) as error: self.install(lambda:True,Result(0))
        self.assertEqual(str(error.exception),setup.STILL_RUNNING); self.assertEqual(self.commands,[])

    def test_installer_errors_are_explained_and_logged_not_dumped(self):
        gbk='所在位置 行:8 字符: 75'.encode('gbk')
        for reason,expect in (('Open DeepSeek Harness once before installing this plugin.','请先打开并登录一次'),
                              ('This Harness installation does not include the plugin installer.','更新到最新版本'),
                              ('Please quit DeepSeek Harness completely, then retry. Your login will be retained.','一直在运行'),
                              ('Plugin installation failed. Configuration backup: C:\\x','plugin-install.log'),
                              ('something unexpected','plugin-install.log')):
            with self.assertRaises(OSError) as error:
                self.install(lambda:False,Result(1,b'',b'PET-INSTALL-ERROR: '+reason.encode()+b'\r\n'+gbk))
            message=str(error.exception)
            self.assertIn(expect,message); self.assertNotIn('PET-INSTALL-ERROR',message); self.assertNotIn('CategoryInfo',message)
            log=(self.root/setup.LOG).read_text('utf8')
            self.assertIn(reason,log); self.assertIn('所在位置',log)   # the console code page is decoded, not garbled

    def test_no_harness_found(self):
        with patch.object(setup,'discover_deepseek',return_value=''), self.assertRaises(OSError) as error: self.install(lambda:False,Result(0))
        self.assertIn('没有找到 DeepSeek Harness',str(error.exception))


@unittest.skipUnless(sys.platform=='win32','PowerShell installer')
class InstallerScriptTests(unittest.TestCase):
    def test_a_failure_is_one_clean_line_with_exit_code_one(self):
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(REPO/'tools/install_deepseek_plugin.ps1'),
                               '-ClientPath',str(REPO/'no-such-folder/DeepSeek Harness.exe')],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,1)
        err=setup.decode(result.stderr).strip()
        self.assertEqual(err,'PET-INSTALL-ERROR: Install the official DeepSeek Harness desktop app first, then specify its executable path.')
        self.assertEqual(setup.explain(err),setup.MISSING)


if __name__=='__main__':
    unittest.main()
