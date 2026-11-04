"""Maintainer tool: create the offline release key or sign a release's update manifest.
Needs `cryptography` from tools/requirements-build.txt, which never ships with the pet."""
import argparse,base64,pathlib,sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from shorekeeper_pet.update_signature import PUBLIC_KEYS,verify_manifest

def public_hex(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()

def generate(path):
    key=Ed25519PrivateKey.generate()
    pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    with pathlib.Path(path).open('xb') as out:out.write(pem)
    print(public_hex(key))

def sign(key_path,manifest,allow_other_key=False):
    key=serialization.load_pem_private_key(pathlib.Path(key_path).read_bytes(),None)
    if not allow_other_key and bytes.fromhex(public_hex(key)) not in PUBLIC_KEYS:raise SystemExit('This key is not trusted by this version of the pet')
    manifest=pathlib.Path(manifest);raw=manifest.read_bytes()
    text=base64.b64encode(key.sign(raw)).decode('ascii')
    if not allow_other_key:verify_manifest(raw,text)
    target=manifest.with_name(manifest.name+'.sig');target.write_text(text+'\n',encoding='ascii',newline='\n')
    print(target)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--generate',metavar='KEY');parser.add_argument('--key');parser.add_argument('manifest',nargs='?')
    args=parser.parse_args()
    if args.generate:generate(args.generate)
    elif args.key and args.manifest:sign(args.key,args.manifest)
    else:parser.error('use --generate KEY or --key KEY MANIFEST')
