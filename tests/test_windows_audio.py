import os
import unittest
from unittest.mock import patch
from shorekeeper_pet import windows_audio as audio


class MixerIdentityTests(unittest.TestCase):
    def test_only_own_process_is_changed(self):
        def sessions(visitor):
            visitor(os.getpid() + 1, 'other-app')
            visitor(os.getpid(), 'our-app')
        with patch.object(audio.sys, 'platform', 'win32'), \
             patch.object(audio, '_visit_sessions', side_effect=sessions), \
             patch.object(audio.os.path, 'isfile', return_value=True), \
             patch.object(audio, '_call', return_value=0) as call:
            self.assertEqual(audio.set_session_identity('Pet', 'pet.ico', 'test.pet'), 1)
        self.assertEqual([c.args[0] for c in call.call_args_list], ['our-app'] * 3)
        self.assertEqual([c.args[1] for c in call.call_args_list], [5, 7, 9])

    def test_missing_icon_still_sets_name(self):
        with patch.object(audio.sys, 'platform', 'win32'), \
             patch.object(audio, '_visit_sessions', side_effect=lambda visitor: visitor(os.getpid(), 'own')), \
             patch.object(audio.os.path, 'isfile', return_value=False), \
             patch.object(audio, '_call', return_value=0) as call:
            self.assertEqual(audio.set_session_identity('Pet', 'absent.ico', 'test.pet'), 1)
        self.assertEqual([c.args[1] for c in call.call_args_list], [5, 9])

    def test_audio_service_failure_is_nonfatal(self):
        with patch.object(audio.sys, 'platform', 'win32'), \
             patch.object(audio, '_visit_sessions', side_effect=OSError('unplugged')):
            self.assertEqual(audio.set_session_identity('Pet', '', 'test.pet'), 0)

    def test_other_platform_is_noop(self):
        with patch.object(audio.sys, 'platform', 'linux'), patch.object(audio, '_visit_sessions') as visit:
            self.assertEqual(audio.set_session_identity('Pet', '', 'test.pet'), 0)
        visit.assert_not_called()
