"""Older program versions and update snapshots are removed once the new version runs, and only then."""
import json,os,pathlib,stat,sys,tempfile,unittest,uuid
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from shorekeeper_pet import program_cleanup as cleanup
from shorekeeper_pet.update_recovery import JOURNAL,POINTER


def write(path,data=b'x'*1000):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data); return path


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name)/'桌宠'
        for v in ('1.0.0','1.0.1','1.0.2'):
            write(self.root/'.programs'/v/'pet.exe'); write(self.root/'.programs'/v/'_internal/lib.dll',b'y'*5000)
        self.snapshot=str(uuid.uuid4()); write(self.root/'.update-backups'/self.snapshot/'settings.json')
        (self.root/POINTER).write_text(json.dumps({'version':'1.0.2'}),'utf8')
        write(self.root/'assets/imported/画师/合集/a.gif'); write(self.root/'settings.json')

    def tearDown(self): self.temp.cleanup()

    def names(self,folder): return sorted(p.name for p in (self.root/folder).iterdir()) if (self.root/folder).exists() else []

    def test_only_the_running_version_and_personal_files_stay(self):
        result=cleanup.prune(self.root,'1.0.2')
        self.assertEqual(self.names('.programs'),['1.0.2']); self.assertEqual(self.names('.update-backups'),[])
        self.assertEqual(sorted(result['removed']),['.programs/1.0.0','.programs/1.0.1','.update-backups/'+self.snapshot])
        self.assertEqual(result['freed_bytes'],2*6000+1000); self.assertEqual(result['failed'],[])
        self.assertTrue((self.root/'assets/imported/画师/合集/a.gif').exists()); self.assertTrue((self.root/'settings.json').exists())
        self.assertEqual(json.loads((self.root/cleanup.REPORT).read_text('utf8'))['freed_bytes'],13000)

    def test_nothing_is_removed_during_an_update(self):
        for marker in (JOURNAL,cleanup.LOCK):
            path=write(self.root/marker,b'{}')
            self.assertEqual(cleanup.prune(self.root,'1.0.2'),dict(skipped='update in progress'))
            self.assertEqual(self.names('.programs'),['1.0.0','1.0.1','1.0.2']); path.unlink()

    def test_nothing_is_removed_by_a_program_that_is_not_the_active_one(self):
        self.assertEqual(cleanup.prune(self.root,'1.0.1'),dict(skipped='not the active program'))
        (self.root/POINTER).unlink(); self.assertEqual(cleanup.prune(self.root,'1.0.2'),dict(skipped='not the active program'))
        self.assertEqual(self.names('.programs'),['1.0.0','1.0.1','1.0.2'])

    def test_unknown_folders_and_read_only_files(self):
        write(self.root/'.programs/notes/keep.txt'); write(self.root/'.update-backups/not-a-uuid/keep.txt')
        locked=self.root/'.programs/1.0.0/pet.exe'; os.chmod(locked,stat.S_IREAD)
        cleanup.prune(self.root,'1.0.2')
        self.assertEqual(self.names('.programs'),['1.0.2','notes']); self.assertEqual(self.names('.update-backups'),['not-a-uuid'])

    @unittest.skipUnless(sys.platform=='win32','junctions are Windows-only')
    def test_a_junction_is_never_followed(self):
        import _winapi
        outside=pathlib.Path(self.temp.name)/'outside'; keep=write(outside/'precious.txt')
        _winapi.CreateJunction(str(outside),str(self.root/'.programs/0.9.0'))
        result=cleanup.prune(self.root,'1.0.2')
        self.assertTrue(keep.exists()); self.assertNotIn('.programs/0.9.0',result['removed'])

    def test_a_folder_that_cannot_be_removed_is_reported_and_finished_next_time(self):
        with patch.object(cleanup,'_remove',side_effect=PermissionError('in use')):
            result=cleanup.prune(self.root,'1.0.2')
        self.assertEqual(sorted(result['failed']),['.programs/1.0.0','.programs/1.0.1','.update-backups/'+self.snapshot])
        self.assertEqual(self.names('.programs'),['.removing-1.0.0','.removing-1.0.1','1.0.2'])
        result=cleanup.prune(self.root,'1.0.2')
        self.assertEqual(self.names('.programs'),['1.0.2']); self.assertEqual(result['failed'],[])

    def test_checking_a_folder_deletes_nothing(self):
        folder=self.root/'.programs/1.0.1'; before=sorted(p.relative_to(folder) for p in folder.rglob('*'))
        self.assertFalse(cleanup._in_use(folder))
        self.assertEqual(sorted(p.relative_to(folder) for p in folder.rglob('*')),before)
        self.assertEqual((folder/'_internal/lib.dll').read_bytes(),b'y'*5000)

    @unittest.skipUnless(sys.platform=='win32','process images are read on Windows')
    def test_a_version_that_a_process_still_runs_from_is_kept_whole(self):
        import shutil,subprocess
        folder=self.root/'.programs/1.0.0'; exe=folder/'ping.exe'; shutil.copy2(r'C:\Windows\System32\ping.exe',exe)
        child=subprocess.Popen([str(exe),'-n','30','127.0.0.1'],stdout=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            import time; time.sleep(.5)
            self.assertIn('1.0.0',cleanup.running_versions(self.root))
            result=cleanup.prune(self.root,'1.0.2')
            self.assertNotIn('.programs/1.0.0',result['removed']+result['failed'])
            self.assertTrue((folder/'_internal/lib.dll').exists()); self.assertTrue(exe.exists())
            # Even unseen by the process check, a folder with a file in use is left whole: nothing in it is removed.
            with patch.object(cleanup,'running_versions',return_value=set()): result=cleanup.prune(self.root,'1.0.2')
            self.assertIn('.programs/1.0.0',result['failed']); self.assertTrue((folder/'_internal/lib.dll').exists())
            self.assertIn('1.0.0',self.names('.programs'))
        finally:
            child.kill(); child.wait()
        cleanup.prune(self.root,'1.0.2'); self.assertEqual(self.names('.programs'),['1.0.2'])


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_the_cleanup_waits_for_a_running_update_then_tries_once_more(self):
        from PySide6.QtCore import QEventLoop,QTimer
        calls=[]
        with tempfile.TemporaryDirectory() as temp, patch.object(cleanup,'prune',side_effect=lambda root,v:calls.append(v)):
            root=pathlib.Path(temp); write(root/JOURNAL,b'{}')
            cleanup.prune_later(root,'1.0.2',first=10,retry=50)
            loop=QEventLoop(); QTimer.singleShot(30,lambda:((root/JOURNAL).unlink(),None)); QTimer.singleShot(300,loop.quit); loop.exec()
            import time; time.sleep(.1)
        self.assertEqual(calls,['1.0.2'])

    def test_the_cleanup_is_skipped_for_good_when_an_update_never_ends(self):
        from PySide6.QtCore import QEventLoop,QTimer
        calls=[]
        with tempfile.TemporaryDirectory() as temp, patch.object(cleanup,'prune',side_effect=lambda root,v:calls.append(v)):
            root=pathlib.Path(temp); write(root/JOURNAL,b'{}')
            cleanup.prune_later(root,'1.0.2',first=10,retry=20)
            loop=QEventLoop(); QTimer.singleShot(200,loop.quit); loop.exec()
        self.assertEqual(calls,[])


if __name__=='__main__':
    unittest.main()
