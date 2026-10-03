"""Original deterministic terrain blockouts using the pinned app's map layout.

No GRF extraction, third-party assets, external dependencies or image service.
GAT 1.2 / GND 1.7 / RSW 2.1 fields follow the already-reviewed mkmap format.
Floor1 includes original training-ground props; other floors retain terrain blockouts.
"""
from __future__ import annotations
import struct
import props
from collections import deque
from pathlib import Path


def bmp(path: Path, size: int, pixel) -> None:
    rows=[]
    for y in reversed(range(size)):
        row=bytearray()
        for x in range(size):
            r,g,b=pixel(x,y)
            row.extend((max(0,min(255,b)),max(0,min(255,g)),max(0,min(255,r))))
        row.extend(b'\0'*((-len(row))%4)); rows.append(row)
    pixels=b''.join(rows)
    out=b'BM'+struct.pack('<IHHI',54+len(pixels),0,0,54)
    out+=struct.pack('<IiiHHIIiiII',40,size,size,1,24,0,len(pixels),2835,2835,0,0)+pixels
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(out)


def material(m: dict):
    base=m['base_rgb']; accent=m['accent_rgb']; p=m['pattern']
    def pixel(x,y):
        noise=((x*73856093)^(y*19349663))%19-9
        if p in ('grass','moss'): mark=((x//4*7+y//7*11)%23==0)
        elif p=='sand': mark=(y+x//12)%24 in (0,1)
        elif p=='rock': mark=(x*3+y*2)%71 in (0,1)
        elif p=='ruins': mark=x%64<3 or y%64<3 or (x+y)%97<2
        elif p=='crypt': mark=x%32<2 or (y+16*(x//32%2))%64<2
        elif p=='ice': mark=(x+y)%53<2 or (x-y)%79<2
        elif p=='lava': mark=(x*3+y)%113<3 or (x-y*2)%151<2
        elif p=='fortress': mark=y%48<3 or (x+24*(y//48%2))%64<3
        elif p=='sanctum': mark=x%64<2 or y%64<2 or abs(x%64-32)+abs(y%64-32)<5
        else: raise ValueError('Unknown material')
        color=accent if mark else base
        return tuple(max(0,min(255,v+noise)) for v in color)
    return pixel


def generate(data: Path, m: dict) -> None:
    if props.themed(m):
        generate_theme(data,m)
        return
    name=m['id']; c=m['ground_cells']; side=c*2
    data.mkdir(parents=True,exist_ok=True)
    gat=bytearray(b'GRAT\x01\x02'+struct.pack('<II',side,side))
    for y in range(side):
        for x in range(side):
            gat.extend(struct.pack('<ffffI',0,0,0,0,int(x in (0,side-1) or y in (0,side-1))))
    (data/(name+'.gat')).write_bytes(gat)
    texture=(name+'\\ground.bmp').encode('ascii')
    gnd=bytearray(b'GRGN\x01\x07'+struct.pack('<IIf',c,c,10.0))
    gnd.extend(struct.pack('<II',1,80)+texture+b'\0'*(80-len(texture)))
    gnd.extend(struct.pack('<iiii',1,8,8,1)+b'\xff'*64+b'\0'*192)
    gnd.extend(struct.pack('<I8fHH4B',1,0,1,0,1,0,0,1,1,0,0,255,255,255,255))
    gnd.extend(struct.pack('<ffffiii',0,0,0,0,0,-1,-1)*(c*c))
    (data/(name+'.gnd')).write_bytes(gnd)
    rsw=bytearray(b'GRSW\x02\x01')
    for value in ('',name+'.gnd',name+'.gat',''):
        b=value.encode('ascii'); rsw.extend(b+b'\0'*(40-len(b)))
    rsw.extend(struct.pack('<fi',5000000.0,0))
    rsw.extend(struct.pack('<fffi',5.0,2.0,50.0,3))
    rsw.extend(struct.pack('<ii',45,45)+struct.pack('<fffffff',1,1,1,.3,.3,.3,1))
    rsw.extend(struct.pack('<iiiii',-500,500,-500,500,0))
    (data/(name+'.rsw')).write_bytes(rsw)
    bmp(data/'texture'/name/'ground.bmp',256,material(m))
    entry=m['entry']; ex=int(entry[0]/side*128); ey=int(entry[1]/side*128)
    def mini(x,y):
        if x<3 or y<3 or x>=125 or y>=125:return (32,32,32)
        if abs(x-ex)<=2 and abs(y-ey)<=2:return (240,235,215)
        return tuple(m['base_rgb'])
    bmp(data/'texture/ui/map'/(name+'.bmp'),128,mini)


def validate(data: Path, m: dict) -> None:
    name=m['id']; c=m['ground_cells']; side=2*c
    gat=(data/(name+'.gat')).read_bytes()
    if gat[:6]!=b'GRAT\x01\x02' or len(gat)!=14+side*side*20: raise ValueError('GAT header/size')
    if struct.unpack_from('<II',gat,6)!=(side,side): raise ValueError('GAT dimension')
    blocked=props.blocked(m) if props.themed(m) else set()
    walk=set()
    for y in range(side):
        for x in range(side):
            h=struct.unpack_from('<ffff',gat,14+(y*side+x)*20)
            typ=struct.unpack_from('<I',gat,30+(y*side+x)*20)[0]
            if h!=(0,0,0,0) or typ!=int(x in (0,side-1) or y in (0,side-1) or (x,y) in blocked): raise ValueError('GAT cell')
            if typ==0: walk.add((x,y))
    targets=[tuple(m[k]) for k in ('entry','keeper','exit')]+[tuple(p) for p in m['spawn_points']]
    if not set(targets)<=walk: raise ValueError('Unwalkable functional coordinate')
    start=targets[0]; reached={start}; queue=deque([start])
    while queue:
        x,y=queue.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p in walk and p not in reached: reached.add(p); queue.append(p)
    if not set(targets)<=reached: raise ValueError('Disconnected functional coordinate')
    if any(max(abs(x-start[0]),abs(y-start[1]))<10 for x,y in targets[3:]): raise ValueError('Spawn too close to arrival')
    gnd=(data/(name+'.gnd')).read_bytes()
    if props.themed(m):
        validate_theme(data,m,gnd)
        return
    if gnd[:6]!=b'GRGN\x01\x07' or struct.unpack_from('<II',gnd,6)!=(c,c) or len(gnd)!=422+c*c*28: raise ValueError('GND structure')
    if gnd[26:106].split(b'\0')[0]!=(name+'\\ground.bmp').encode(): raise ValueError('GND texture link')
    if gnd[122:186]!=b'\xff'*64 or gnd[186:378]!=b'\0'*192: raise ValueError('GND additive light')
    rsw=(data/(name+'.rsw')).read_bytes()
    if len(rsw)!=246 or rsw[:6]!=b'GRSW\x02\x01': raise ValueError('RSW structure')
    for off,suffix in ((46,'.gnd'),(86,'.gat')):
        if rsw[off:off+40].split(b'\0')[0]!=(name+suffix).encode(): raise ValueError('RSW link')
    for rel,size in [(f'texture/{name}/ground.bmp',256),(f'texture/ui/map/{name}.bmp',128)]:
        b=(data/rel).read_bytes()
        if b[:2]!=b'BM' or struct.unpack_from('<I',b,2)[0]!=len(b) or struct.unpack_from('<ii',b,18)!=(size,size): raise ValueError('BMP structure')


def terrain(m,x,y):
    """GND cell coordinates; central open grass with a short arrival path."""
    c=m['ground_cells']
    if abs(x-c//2)<=3 and y<10: return 2 if y<7 else 1
    if (x-c/2)**2+(y-c/2)**2 < 10**2: return 3
    return 0


def theme_gnd(m):
    name=m['id'];c=m['ground_cells']
    textures=['ground','dirt','paving','arena']
    out=bytearray(b'GRGN\x01\x07'+struct.pack('<IIfII',c,c,10,4,80))
    for texture in textures: out+=props.fixed(name+'\\'+texture+'.bmp',80)
    out+=struct.pack('<4i',1,8,8,1)+b'\xff'*64+bytes(192)
    out+=struct.pack('<I',4)
    for t in range(4): out+=struct.pack('<8fHH4B',0,1,0,1,0,0,1,1,t,0,255,255,255,255)
    for y in range(c):
        for x in range(c): out+=struct.pack('<4f3i',0,0,0,0,terrain(m,x,y),-1,-1)
    return bytes(out)


def theme_rsw(m):
    name=m['id'];c=m['ground_cells'];items=props.instances(m)
    out=bytearray(b'GRSW\x02\x01')
    for s in ('',name+'.gnd',name+'.gat',''): out+=props.fixed(s,40)
    out+=struct.pack('<fi',5000000,0)+struct.pack('<fffi',5,2,50,3)
    out+=struct.pack('<ii7f',45,45,1,1,1,.3,.3,.3,1)
    out+=struct.pack('<5i',-500,500,-500,500,len(items))
    for i,(kind,x,y) in enumerate(items):out+=props.rsw_object(name,kind,x,y,c,i)
    return bytes(out)


def generate_theme(data,m):
    data.mkdir(parents=True,exist_ok=True);name=m['id'];side=m['ground_cells']*2
    blocked=props.blocked(m)
    gat=bytearray(b'GRAT\x01\x02'+struct.pack('<II',side,side))
    for y in range(side):
        for x in range(side): gat+=struct.pack('<4fI',0,0,0,0,int(x in (0,side-1) or y in (0,side-1) or (x,y) in blocked))
    (data/(name+'.gat')).write_bytes(gat)
    (data/(name+'.gnd')).write_bytes(theme_gnd(m));(data/(name+'.rsw')).write_bytes(theme_rsw(m))
    bmp(data/'texture'/name/'ground.bmp',256,material(m))
    palette={'dirt':(134,104,69),'paving':(151,153,134),'arena':(85,124,61),
             'stone':(132,139,125),'post':(139,95,54),'flag':(213,159,60)}
    for kind,color in palette.items():
        def pixel(x,y,color=color,kind=kind):
            noise=((x*17+y*31)%13)-6
            line=(x%32<2 or y%32<2) if kind in ('stone','paving') else (x%11<2 if kind=='post' else False)
            return tuple(max(0,min(255,v+noise-(24 if line else 0))) for v in color)
        bmp(data/'texture'/name/(kind+'.bmp'),256,pixel)
    for kind in ('stone','post','flag'):
        target=data/'model'/name/(kind+'.rsm');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(props.rsm(name,kind))
    def mini(x,y):
        gx=int(x/128*side);gy=int(y/128*side)
        if gx in (0,side-1) or gy in (0,side-1) or (gx,gy) in blocked:return (72,69,60)
        if abs(gx-m['entry'][0])<2 and abs(gy-m['entry'][1])<2:return (240,235,215)
        return [(69,112,54),(134,104,69),(151,153,134),(85,124,61)][terrain(m,gx//2,gy//2)]
    bmp(data/'texture/ui/map'/(name+'.bmp'),128,mini)


def validate_theme(data,m,gnd):
    name=m['id'];c=m['ground_cells']
    if gnd[:6]!=b'GRGN\x01\x07' or len(gnd)<26 or struct.unpack_from('<IIfII',gnd,6)!=(c,c,10,4,80):raise ValueError('GND theme header')
    # Read the variable texture table before locating the lightmap; do not use
    # legacy fixed offsets. Also require canonical zero-padded texture slots.
    pos=26
    for kind in ('ground','dirt','paving','arena'):
        if gnd[pos:pos+80]!=props.fixed(name+'\\'+kind+'.bmp',80):raise ValueError('GND texture link/padding')
        pos+=80
    if gnd[pos:pos+16]!=struct.pack('<4i',1,8,8,1):raise ValueError('GND lightmap dimensions')
    pos+=16
    if gnd[pos:pos+64]!=b'\xff'*64 or gnd[pos+64:pos+256]!=bytes(192):raise ValueError('GND additive light')
    if gnd!=theme_gnd(m):raise ValueError('GND tile/surface contract')
    rsw=(data/(name+'.rsw')).read_bytes()
    if rsw!=theme_rsw(m):raise ValueError('RSW model placement/link')
    for kind in ('stone','post','flag'):
        raw=(data/'model'/name/(kind+'.rsm')).read_bytes();parsed=props.parse_rsm(raw)
        if raw!=props.rsm(name,kind) or parsed['texture']!=name+'\\'+kind+'.bmp':raise ValueError('RSM authored geometry')
    for rel,size in [(f'texture/{name}/{k}.bmp',256) for k in ('ground','dirt','paving','arena','stone','post','flag')]+[(f'texture/ui/map/{name}.bmp',128)]:
        raw=(data/rel).read_bytes()
        if len(raw)!=54+size*size*3 or raw[:2]!=b'BM' or struct.unpack_from('<I',raw,2)[0]!=len(raw) or struct.unpack_from('<ii',raw,18)!=(size,size):raise ValueError('BMP structure')


def preview(data,m,path):
    """Orthographic design preview, explicitly not a game render."""
    side=m['ground_cells']*2;s=7;items=[]
    for y in range(side//2):
        for x in range(side//2):
            color=['#457036','#866845','#979986','#557c3d'][terrain(m,x,y)]
            items.append(f'<rect x="{x*2*s}" y="{y*2*s}" width="{2*s}" height="{2*s}" fill="{color}"/>')
    for kind,x,y in props.instances(m):
        w,h,d=props.dimensions(kind);color={'stone':'#919780','post':'#936338','flag':'#e7ad3b'}[kind]
        items.append(f'<rect x="{(x+.5-w/2)*s}" y="{(y+.5-d/2)*s}" width="{w*s}" height="{d*s}" fill="{color}" stroke="#30291f"/>')
    for label,points in [('entry',[m['entry']]),('NPC',[m['keeper'],m['exit']]),('spawn',m['spawn_points'])]:
        for x,y in points:items.append(f'<circle cx="{(x+.5)*s}" cy="{(y+.5)*s}" r="4" fill="white"/><text x="{(x+1)*s}" y="{(y+1)*s}" fill="white" font-size="10">{label}</text>')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('<!doctype html><meta charset="utf-8"><title>Original training ground design preview</title><body style="background:#20241e;color:white;font-family:sans-serif"><h2>TRAINING_GROUND_V1 — orthographic design preview</h2><p>Original geometry layout. Not a game render; placement and appearance await runtime verification. Stone boundary, wooden posts and small gold pennants surround an open grass arena.</p><svg viewBox="0 0 '+str(side*s)+' '+str(side*s)+'" width="700">'+''.join(items)+'</svg>',encoding='utf-8')
