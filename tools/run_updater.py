import pathlib,sys
if not getattr(sys,'frozen',False):sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from shorekeeper_pet.update_apply import main
if __name__=='__main__':raise SystemExit(main())
