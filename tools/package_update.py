"""Create a program-only update ZIP and its independently hashed file manifest."""
import argparse,hashlib,json,pathlib,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from shorekeeper_pet.paths import VERSION,UPDATE_REPOSITORY,EXECUTABLE_NAME
from shorekeeper_pet.update_package import names,program_file,HELPER,validate_manifest,digest

def package(full,destination):
    destination=pathlib.Path(destination);destination.mkdir(parents=True,exist_ok=True)
    zip_name,manifest_name=names(VERSION);output=destination/zip_name;files={}
    with zipfile.ZipFile(full) as source,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for entry in source.infolist():
            if entry.is_dir() or not program_file(entry.filename):continue
            data=source.read(entry);target.writestr(entry.filename,data)
            files[entry.filename]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    assert 'tools/'+HELPER in files
    manifest={'schema':1,'repository':UPDATE_REPOSITORY,'version':VERSION,'minimum_version':'0.0.0','bridge_protocol':1,
              'patch':{'name':zip_name,'bytes':output.stat().st_size,'sha256':digest(output)},'files':files}
    validate_manifest(manifest,VERSION,'0.0.0')
    file=destination/manifest_name;file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    return {'manifest':str(file),'archive':str(output),'bytes':output.stat().st_size,'files':len(files),'program':manifest}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('full');parser.add_argument('destination');args=parser.parse_args()
    result=package(args.full,args.destination);print(json.dumps({k:v for k,v in result.items() if k!='program'},ensure_ascii=False))
