"""Build an installable bundle with a strict source allowlist."""
import pathlib,tarfile
root=pathlib.Path(__file__).resolve().parents[1]
folder=root/'integrations/deepseek'
with tarfile.open(folder/'dsh-shorekeeper-pet-0.1.1.tgz','w:gz') as archive:
    for name in ('package.json','index.js','state.js','cordis.patch.yml'):
        archive.add(folder/name,arcname='package/'+name)
