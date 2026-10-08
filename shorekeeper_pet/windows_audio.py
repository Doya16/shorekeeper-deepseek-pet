"""Name this process's Windows mixer sessions without changing their audio."""
import ctypes
import os
import sys
import uuid
from contextlib import contextmanager


class _GUID(ctypes.Structure):
    _fields_ = [('data1', ctypes.c_uint32), ('data2', ctypes.c_uint16),
                ('data3', ctypes.c_uint16), ('data4', ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(uuid.UUID(str(value)).bytes_le)


_DEVICE_ENUMERATOR = _GUID.parse('BCDE0395-E52F-467C-8E3D-C4579291692E')
_ENUMERATOR_IID = _GUID.parse('A95664D2-9614-4F35-A746-DE8DB63617E6')
_MANAGER_IID = _GUID.parse('77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F')
_CONTROL2_IID = _GUID.parse('BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D')
_PTR = ctypes.c_void_p
_OUT = ctypes.POINTER(_PTR)
_HRESULT = ctypes.c_int32


def _check(result):
    if result < 0:
        raise OSError(f'Core Audio HRESULT 0x{result & 0xffffffff:08X}')


def _call(pointer, index, argument_types, *arguments):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(_PTR))).contents
    function = ctypes.WINFUNCTYPE(_HRESULT, _PTR, *argument_types)(table[index])
    return function(pointer, *arguments)


@contextmanager
def _owned():
    pointer = _PTR()
    try:
        yield pointer
    finally:
        if pointer:
            _call(pointer, 2, ())  # IUnknown::Release


def _visit_sessions(visitor):
    """Visit render sessions; every COM reference stays on the calling thread."""
    if sys.platform != 'win32':
        return
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [_PTR, ctypes.c_uint32]
    ole.CoInitializeEx.restype = _HRESULT
    ole.CoCreateInstance.argtypes = [_PTR, _PTR, ctypes.c_uint32, _PTR, _OUT]
    ole.CoCreateInstance.restype = _HRESULT
    initialized = ole.CoInitializeEx(None, 2)  # STA; Qt may already own an apartment.
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        _check(initialized)
    try:
        with _owned() as enumerator, _owned() as devices:
            _check(ole.CoCreateInstance(ctypes.byref(_DEVICE_ENUMERATOR), None, 23,
                                       ctypes.byref(_ENUMERATOR_IID), ctypes.byref(enumerator)))
            _check(_call(enumerator, 3, (ctypes.c_int, ctypes.c_uint32, _OUT),
                         0, 1, ctypes.byref(devices)))  # eRender / DEVICE_STATE_ACTIVE
            count = ctypes.c_uint32()
            _check(_call(devices, 3, (ctypes.POINTER(ctypes.c_uint32),), ctypes.byref(count)))
            for device_index in range(count.value):
                try:
                    with _owned() as device, _owned() as manager, _owned() as sessions:
                        _check(_call(devices, 4, (ctypes.c_uint32, _OUT), device_index, ctypes.byref(device)))
                        _check(_call(device, 3, (_PTR, ctypes.c_uint32, _PTR, _OUT),
                                     ctypes.byref(_MANAGER_IID), 23, None, ctypes.byref(manager)))
                        _check(_call(manager, 5, (_OUT,), ctypes.byref(sessions)))
                        session_count = ctypes.c_int()
                        _check(_call(sessions, 3, (ctypes.POINTER(ctypes.c_int),), ctypes.byref(session_count)))
                        for index in range(session_count.value):
                            with _owned() as control, _owned() as control2:
                                _check(_call(sessions, 4, (ctypes.c_int, _OUT), index, ctypes.byref(control)))
                                _check(_call(control, 0, (_PTR, _OUT),
                                             ctypes.byref(_CONTROL2_IID), ctypes.byref(control2)))
                                process_id = ctypes.c_uint32()
                                result = _call(control2, 14, (ctypes.POINTER(ctypes.c_uint32),), ctypes.byref(process_id))
                                # S_FALSE is a cross-process session: never relabel it.
                                if result == 0:
                                    visitor(process_id.value, control)
                except OSError:
                    # An unplugged endpoint must not prevent labeling other outputs.
                    continue
    finally:
        if initialized >= 0:
            ole.CoUninitialize()


def set_session_identity(name, icon_path, app_id):
    """Best effort, only our PID; no volume, mute, or stream changes."""
    changed = 0
    if sys.platform != 'win32':
        return changed
    own_pid = os.getpid()
    group = _GUID.parse(uuid.uuid5(uuid.NAMESPACE_URL, app_id))

    def label(process_id, control):
        nonlocal changed
        if process_id != own_pid:
            return
        _check(_call(control, 5, (ctypes.c_wchar_p, _PTR), name, None))
        changed += 1
        # Missing icons / older mixer implementations must not affect playback.
        if os.path.isfile(icon_path):
            _call(control, 7, (ctypes.c_wchar_p, _PTR), os.fspath(icon_path), None)
        _call(control, 9, (_PTR, _PTR), ctypes.byref(group), None)

    try:
        _visit_sessions(label)
    except (OSError, AttributeError):
        pass
    return changed
