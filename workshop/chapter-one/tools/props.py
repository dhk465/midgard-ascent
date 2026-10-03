"""Original static RSM 1.4 geometry; pinned roBrowser Node/RSW layouts.

No imported assets. Coordinates are renderer units (one GAT cell); up is -Y.
"""
from __future__ import annotations
import math
import struct

THEME = 'TRAINING_GROUND_V1'


def fixed(value, length):
    raw = value.encode('ascii')
    if len(raw) >= length: raise ValueError('Overlong asset name')
    return raw + bytes(length-len(raw))


def themed(m):
    return m.get('theme_geometry') == THEME and m['id'] == 'ohkt01'


def instances(m):
    """Small obstacles at the perimeter, leaving a 58-cell-wide arena."""
    side = m['ground_cells']*2
    result=[]
    for x in range(8,side-8,8):
        for y in (5,side-6): result.append(('stone',x,y))
    for y in range(14,side-12,8):
        for x in (5,side-6): result.append(('stone',x,y))
    for x in (11,side-12):
        for y in (22,40,58): result.append(('post',x,y))
    for x in (15,side-16):
        for y in (18,side-19): result.append(('flag',x,y))
    return result


def dimensions(kind):
    return {'stone':(2.6,1.15,1.6),'post':(.7,3.2,.7),'flag':(1.5,4.0,.7)}[kind]


def footprint(kind,x,y):
    w,_,d=dimensions(kind)
    # Intersection of the horizontal bounding box with unit GAT cells.
    return {(a,b) for a in range(math.floor(x+.5-w/2),math.ceil(x+.5+w/2))
            for b in range(math.floor(y+.5-d/2),math.ceil(y+.5+d/2))}


def blocked(m):
    cells=set()
    for kind,x,y in instances(m):
        f=footprint(kind,x,y)
        if cells & f: raise ValueError('Overlapping prop footprints')
        cells |= f
    targets=[m[k] for k in ('entry','keeper','exit')]+m['spawn_points']
    if any((x+dx,y+dy) in cells for x,y in targets for dx in range(-2,3) for dy in range(-2,3)):
        raise ValueError('Prop touches functional coordinate clearance')
    return cells


def mesh(kind):
    vertices=[]; faces=[]
    def box(w,h,d,cy=0):
        n=len(vertices)
        vertices.extend([(x,y+cy,z) for x,y,z in
            [(-w/2,0,-d/2),(w/2,0,-d/2),(w/2,-h,-d/2),(-w/2,-h,-d/2),
             (-w/2,0,d/2),(w/2,0,d/2),(w/2,-h,d/2),(-w/2,-h,d/2)]])
        for a,b,c,d0 in ((0,1,2,3),(5,4,7,6),(4,0,3,7),(1,5,6,2),(3,2,6,7),(4,5,1,0)):
            faces.extend([(n+a,n+b,n+c),(n+a,n+c,n+d0)])
    if kind=='flag':
        box(.35,4,.35)
        # Small double-wound pennant; actual triangles, not ignored twoSide flag.
        n=len(vertices);vertices.extend([(-.1,-3.8,0),(1.15,-3.45,0),(-.1,-2.9,0)])
        faces.extend([(n,n+1,n+2),(n+2,n+1,n)])
    else: box(*dimensions(kind))
    return vertices,faces


def rsm(name,kind):
    vertices,faces=mesh(kind)
    out=bytearray(b'GRSM\x01\x04'+struct.pack('<iiB',0,1,255)+bytes(16))
    out+=struct.pack('<i',1)+fixed(name+'\\'+kind+'.bmp',40)+fixed('root',40)+struct.pack('<i',1)
    out+=fixed('root',40)+fixed('',40)+struct.pack('<ii',1,0)
    out+=struct.pack('<9f',1,0,0,0,1,0,0,0,1)+struct.pack('<3f',0,0,0)
    out+=struct.pack('<3ff3f3f',0,0,0,0,0,1,0,1,1,1)
    out+=struct.pack('<i',len(vertices))+b''.join(struct.pack('<3f',*v) for v in vertices)
    out+=struct.pack('<i',3)+b''.join(struct.pack('<4B2f',255,255,255,255,*uv) for uv in ((0,0),(1,0),(1,1)))
    out+=struct.pack('<i',len(faces))+b''.join(struct.pack('<8H2i',*f,0,1,2,0,0,0,0) for f in faces)
    out+=struct.pack('<iii',0,0,0)
    return bytes(out)


def rsw_object(name,kind,x,y,c,index):
    return (struct.pack('<i',1)+fixed('training_'+str(index),40)+struct.pack('<ifi',0,1,0)
            +fixed(name+'\\'+kind+'.rsm',80)+fixed('root',80)
            +struct.pack('<9f',(x+.5-c)*5,0,(y+.5-c)*5,0,0,0,5,5,5))


def parse_rsm(raw):
    """Independent field reader for corruption/indices/finite geometry checks."""
    p=0
    def take(fmt):
        nonlocal p
        fmt='<'+fmt; size=struct.calcsize(fmt)
        if p+size>len(raw): raise ValueError('Truncated RSM')
        value=struct.unpack_from(fmt,raw,p);p+=size
        return value
    def string():
        s=take('40s')[0]
        if b'\0' not in s or any(s[s.index(0):]): raise ValueError('RSM string padding')
        return s.split(b'\0')[0].decode('ascii')
    if take('4s2B')!=(b'GRSM',1,4) or take('iiB')!=(0,1,255): raise ValueError('RSM header')
    if take('16s')[0]!=bytes(16) or take('i')[0]!=1: raise ValueError('RSM texture count')
    texture=string();root=string()
    if take('i')[0]!=1 or string()!=root or string()!='' or take('ii')!=(1,0): raise ValueError('RSM node')
    transforms=take('22f')
    if transforms!=(1,0,0,0,1,0,0,0,1,0,0,0,0,0,0,0,0,1,0,1,1,1): raise ValueError('RSM transform')
    nv=take('i')[0]
    if not 3<=nv<=1000: raise ValueError('RSM vertex count')
    vertices=[take('3f') for _ in range(nv)]
    if not all(math.isfinite(v) for row in vertices for v in row): raise ValueError('RSM finite vertices')
    nt=take('i')[0]
    if not 3<=nt<=1000: raise ValueError('RSM UV count')
    uv=[take('4B2f') for _ in range(nt)]
    if not all(math.isfinite(v) and 0<=v<=1 for row in uv for v in row[4:]): raise ValueError('RSM UV range')
    nf=take('i')[0]
    if not 1<=nf<=1000: raise ValueError('RSM face count')
    faces=[take('8H2i') for _ in range(nf)]
    for face in faces:
        if any(i>=nv for i in face[:3]) or any(i>=nt for i in face[3:6]) or face[6:]!=(0,0,0,0): raise ValueError('RSM face indices')
        a,b,c=(vertices[i] for i in face[:3]);u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        if sum((u[(i+1)%3]*v[(i+2)%3]-u[(i+2)%3]*v[(i+1)%3])**2 for i in range(3))<1e-10: raise ValueError('Degenerate face')
    if take('iii')!=(0,0,0) or p!=len(raw): raise ValueError('RSM trailing data')
    if not texture or '..' in texture or texture.startswith(('data','/','\\')): raise ValueError('RSM texture path')
    return {'texture':texture,'vertices':vertices,'faces':faces}
