"""Check the built icon resources and the icon returned by Windows Shell."""
import ctypes,json,pathlib,struct,sys
from ctypes import wintypes
import pefile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from shorekeeper_pet.paths import EXECUTABLE_NAME,VERSION

def verify(folder):
    exe=pathlib.Path(folder).resolve()/EXECUTABLE_NAME
    pe=pefile.PE(str(exe))
    group=next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id==14)
    entry=group.directory.entries[0].directory.entries[0].data.struct
    blob=pe.get_data(entry.OffsetToData,entry.Size)
    count=struct.unpack_from('<H',blob,4)[0]
    sizes=[(blob[6+i*14] or 256,blob[7+i*14] or 256) for i in range(count)]
    assert {16,24,32,48,64,128,256}=={s[0] for s in sizes},sizes
    strings={k.decode():v.decode('utf8') for info in pe.FileInfo for block in info if hasattr(block,'StringTable') for table in block.StringTable for k,v in table.entries.items()}
    assert strings['OriginalFilename']==EXECUTABLE_NAME and strings['FileVersion']==VERSION.split('-')[0],strings
    extract=ctypes.windll.shell32.ExtractIconExW
    extract.argtypes=[wintypes.LPCWSTR,ctypes.c_int,ctypes.POINTER(wintypes.HICON),ctypes.POINTER(wintypes.HICON),wintypes.UINT]
    extract.restype=wintypes.UINT
    large=wintypes.HICON();small=wintypes.HICON()
    count=extract(str(exe),0,ctypes.byref(large),ctypes.byref(small),1)
    try:assert count in (1,2) and large.value and small.value,'Windows Shell could not extract the embedded icon'
    finally:
        destroy=ctypes.windll.user32.DestroyIcon;destroy.argtypes=[wintypes.HICON]
        for handle in (large,small):
            if handle.value:destroy(handle)
    pe.close()
    return dict(ok=True,icon_sizes=[s[0] for s in sizes],windows_shell_icons=True,version=VERSION)

if __name__=='__main__':print(json.dumps(verify(sys.argv[1])))
