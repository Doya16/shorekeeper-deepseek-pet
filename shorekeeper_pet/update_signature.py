"""Ed25519 verification (RFC 8032) for update manifests. Verify-only and public data, so no secrets here."""
import base64,hashlib

# The private key stays offline with the maintainer. Add a new key here before retiring an old one.
PUBLIC_KEYS=(bytes.fromhex('9be8119315df30387bb0b91b11774a49e4be3b17cb6c815d75f89937d183ecc1'),)
P=2**255-19;L=2**252+27742317777372353535851937790883648493
D=-121665*pow(121666,P-2,P)%P;I=pow(2,(P-1)//4,P)

def _decode(raw):
    if len(raw)!=32:return None
    value=int.from_bytes(raw,'little');sign=value>>255;y=value&((1<<255)-1)
    if y>=P:return None
    x2=(y*y-1)*pow(D*y*y+1,P-2,P)%P
    if x2==0:
        if sign:return None
        x=0
    else:
        x=pow(x2,(P+3)//8,P)
        if (x*x-x2)%P:x=x*I%P
        if (x*x-x2)%P:return None
        if x&1!=sign:x=P-x
    return (x,y,1,x*y%P)

def _encode(point):
    inverse=pow(point[2],P-2,P);x=point[0]*inverse%P;y=point[1]*inverse%P
    return (y|(x&1)<<255).to_bytes(32,'little')

def _add(a,b):
    A=(a[1]-a[0])*(b[1]-b[0])%P;B=(a[1]+a[0])*(b[1]+b[0])%P
    C=2*a[3]*b[3]*D%P;E=2*a[2]*b[2]%P
    e,f,g,h=B-A,E-C,E+C,B+A
    return (e*f%P,g*h%P,f*g%P,e*h%P)

def _mul(scalar,point):
    result=(0,1,1,0)
    while scalar:
        if scalar&1:result=_add(result,point)
        point=_add(point,point);scalar>>=1
    return result

BASE=_decode((4*pow(5,P-2,P)%P).to_bytes(32,'little'))

def verify(message,signature,public_key):
    if len(signature)!=64:return False
    A=_decode(public_key);R=_decode(signature[:32]);S=int.from_bytes(signature[32:],'little')
    if A is None or R is None or S>=L:return False
    h=int.from_bytes(hashlib.sha512(signature[:32]+public_key+message).digest(),'little')%L
    return _encode(_mul(S,BASE))==_encode(_add(R,_mul(h,A)))

def verify_manifest(raw,text):
    # The mirror may carry these bytes, but only the release key can make them valid.
    try:signature=base64.b64decode(text.strip(),validate=True)
    except ValueError:signature=b''
    if not any(verify(raw,signature,key) for key in PUBLIC_KEYS):raise ValueError('更新清单签名校验失败，已取消更新')
