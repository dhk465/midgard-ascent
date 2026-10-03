"""Local-only RO field crop. No downloads, installation, or game-state writes.

Preserves source GND UVs/lightmaps/heights and source RSW model transforms.
Imported copyrighted bytes belong only in ignored build/local directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import zlib
from collections import deque
from pathlib import Path
import maps
import props
import rsm_bounds


def fixed(raw, size):
    if len(raw) >= size: raise ValueError('Asset path too long')
    return raw + bytes(size-len(raw))


def safe(raw):
    raw=raw.replace(b'\\',b'/').lower()
    if raw.startswith(b'/') or any(p in (b'',b'.',b'..') for p in raw.split(b'/')) or b':' in raw:
        raise ValueError('Unsafe asset path')
    return raw


class Archives:
    """Raw byte names prevent lossy Korean decoding; later archives take priority."""
    def __init__(self, paths):
        self.entries={}; self.paths=list(map(Path,paths))
        for path in self.paths:
            with path.open('rb') as f:
                h=f.read(46)
                if not h.startswith((b'Master of Magic',b'Event Horizon')): raise ValueError('GRF signature')
                version=struct.unpack_from('<I',h,42)[0]
                if version==0x300: offset=struct.unpack_from('<Q',h,30)[0];extra=4;fmt='<IIIBQ';step=22
                elif version==0x200:offset=struct.unpack_from('<I',h,30)[0];extra=0;fmt='<IIIBI';step=18
                else:raise ValueError('Unsupported GRF version')
                f.seek(46+offset+extra); packed,size=struct.unpack('<II',f.read(8));table=zlib.decompress(f.read(packed))
                if len(table)!=size:raise ValueError('GRF table size')
                p=0
                while p<len(table):
                    end=table.index(0,p);raw=table[p:end];fields=struct.unpack_from(fmt,table,end+1);p=end+step
                    self.entries[safe(raw)]=(path,fields)
    def read(self, raw):
        path,e=self.entries[safe(raw)]
        if e[3]!=1:raise ValueError('Encrypted/non-file GRF entry is unsupported')
        with path.open('rb') as f:f.seek(e[4]+46);out=zlib.decompress(f.read(e[0]))
        if len(out)!=e[2]:raise ValueError('GRF entry size')
        return out


def ground(raw):
    if raw[:6]!=b'GRGN\x01\x07':raise ValueError('Requires source GND 1.7')
    w,h,zoom,n,size=struct.unpack_from('<IIfII',raw,6)
    if size!=80:raise ValueError('Texture slot size')
    textures=[raw[26+i*size:26+(i+1)*size].split(b'\0')[0] for i in range(n)]
    p=26+n*size;count,lw,lh,cell=struct.unpack_from('<4i',raw,p)
    end=p+16+count*lw*lh*cell*4;lightmaps=raw[p:end];p=end
    count=struct.unpack_from('<I',raw,p)[0];p+=4
    tiles=[raw[p+i*40:p+(i+1)*40] for i in range(count)];p+=40*count
    surfaces=[raw[p+i*28:p+(i+1)*28] for i in range(w*h)]
    if p+w*h*28!=len(raw):raise ValueError('GND length')
    return dict(w=w,h=h,zoom=zoom,textures=textures,lights=lightmaps,tiles=tiles,cells=surfaces)


def world(raw):
    if raw[:6]!=b'GRSW\x02\x01':raise ValueError('Requires source RSW 2.1')
    count=struct.unpack_from('<I',raw,242)[0];p=246;models=[]
    for _ in range(count):
        kind=struct.unpack_from('<I',raw,p)[0]
        size={1:252,2:112,3:196,4:120}.get(kind)
        if size is None or p+size>len(raw):raise ValueError('RSW object/truncation')
        if kind==1:models.append(raw[p:p+size])
        p+=size
    return models


def collision(raw):
    if raw[:6]!=b'GRAT\x01\x02':raise ValueError('Requires GAT 1.2')
    w,h=struct.unpack_from('<II',raw,6)
    if len(raw)!=14+20*w*h:raise ValueError('GAT length')
    return w,h,[raw[14+i*20:34+i*20] for i in range(w*h)]


def reachable(cells, side, targets):
    walk={(x,y) for y in range(side) for x in range(side) if struct.unpack_from('<I',cells[y*side+x],16)[0]==0}
    if not set(targets)<=walk:return False
    # Keep every functional target clear of native collision by two cells.
    if any((x+dx,y+dy) not in walk for x,y in targets for dx in range(-2,3) for dy in range(-2,3)):return False
    seen={targets[0]};queue=deque(seen)
    while queue:
        x,y=queue.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p in walk and p not in seen:seen.add(p);queue.append(p)
    return set(targets)<=seen


def crop_gat(src,x,y,c):
    w,h,cells=src;side=c*2
    if x<0 or y<0 or (x+c)*2>w or (y+c)*2>h:raise ValueError('Crop outside GAT')
    out=[]
    for yy in range(side):
        for xx in range(side):
            cell=bytearray(cells[(y*2+yy)*w+x*2+xx])
            if xx in (0,side-1) or yy in (0,side-1):struct.pack_into('<I',cell,16,1)
            out.append(bytes(cell))
    return out


def select_crop(gnd,gat,models,m):
    """Choose a naturally open crop with scenery around the protected arena."""
    c=m['ground_cells'];targets=[tuple(m[k]) for k in ('entry','keeper','exit')]+list(map(tuple,m['spawn_points']))
    positions=[(struct.unpack_from('<f',o,216)[0]/5+gnd['w'],struct.unpack_from('<f',o,224)[0]/5+gnd['h']) for o in models]
    candidates=[]
    for y in range(4,gnd['h']-c-4,4):
        for x in range(4,gnd['w']-c-4,4):
            # Cheap central/functional clearance check before BFS.
            source=gat[2];sw=gat[0]
            if any(struct.unpack_from('<I',source[(2*y+ty+dy)*sw+2*x+tx+dx],16)[0]!=0 for tx,ty in targets for dx in range(-2,3) for dy in range(-2,3)):continue
            cells=crop_gat(gat,x,y,c)
            open_count=sum(struct.unpack_from('<I',v,16)[0]==0 for v in cells)
            if open_count<.88*(2*c-2)**2:continue
            scenery=[(px-2*x,py-2*y) for px,py in positions if 2*x+4<px<2*(x+c)-4 and 2*y+4<py<2*(y+c)-4]
            # No native props near arrival, spawn targets, or central battle rectangle.
            if any(20<px<60 and 20<py<56 or any(abs(px-tx)<7 and abs(py-ty)<7 for tx,ty in targets) for px,py in scenery):continue
            if not 3<=len(scenery)<=30:continue
            if reachable(cells,2*c,targets):candidates.append((len(scenery),open_count,x,y))
    if not candidates:raise ValueError('No naturally clear crop; explicit design decision required')
    _,_,x,y=max(candidates)
    return x,y


def build(archives, source, output, m, origin=None, policy='reviewed_tree', report_name='FIELD-IMPORT-REPORT.json'):
    output=Path(output).resolve()
    # Refuse writing imported assets outside known ignored artifact directories.
    root=Path(__file__).resolve().parents[3]
    if not any(output.parent.is_relative_to(root/p) for p in ('build','local')):raise ValueError('Imported assets and report require nested ignored build/local output')
    if policy not in ('reviewed_tree','outdoor','architecture'):raise ValueError('Unknown native model policy')
    if Path(report_name).name!=report_name:raise ValueError('Unsafe report name')
    assets=archives if isinstance(archives,Archives) else Archives(archives)
    prefix=b'data/'+source.encode('ascii');graw=assets.read(prefix+b'.gnd');wraw=assets.read(prefix+b'.rsw');araw=assets.read(prefix+b'.gat')
    g=ground(graw);objects=world(wraw);gat=collision(araw);c=m['ground_cells'];side=2*c
    if gat[:2]!=(g['w']*2,g['h']*2):raise ValueError('GND/GAT dimension mismatch')
    x,y=origin or select_crop(g,gat,objects,m);cells=crop_gat(gat,x,y,c)
    targets=[tuple(m[k]) for k in ('entry','keeper','exit')]+list(map(tuple,m['spawn_points']))
    if not reachable(cells,side,targets):raise ValueError('Crop functional clearance/connectivity failed')
    name=m['id'];namespace=name+'_field';files={};provenance=[]
    def include(rawpath,relative):
        content=assets.read(rawpath);files[relative]=content
        provenance.append(dict(source_raw_hex=rawpath.hex(),target=relative,sha256=hashlib.sha256(content).hexdigest()))
        return content
    chosen=[g['cells'][(y+yy)*g['w']+x+xx] for yy in range(c) for xx in range(c)]
    used=sorted({i for cell in chosen for i in struct.unpack_from('<3i',cell,16) if i>=0});tile_index={old:new for new,old in enumerate(used)}
    textures=sorted({struct.unpack_from('<H',g['tiles'][i],32)[0] for i in used});tex_index={old:new for new,old in enumerate(textures)}
    gout=bytearray(b'GRGN\x01\x07'+struct.pack('<IIfII',c,c,g['zoom'],len(textures),80))
    for i in textures:
        ext=Path(g['textures'][i].decode('latin1').replace('\\','/')).suffix.lower()
        rel=f'{namespace}/g{i}{ext}';include(b'data/texture/'+g['textures'][i],f'texture/{rel}');gout+=fixed(rel.replace('/','\\').encode(),80)
    gout+=g['lights']+struct.pack('<I',len(used))
    for i in used:
        tile=bytearray(g['tiles'][i]);struct.pack_into('<H',tile,32,tex_index[struct.unpack_from('<H',tile,32)[0]]);gout+=tile
    for cell in chosen:
        heights=struct.unpack_from('<4f',cell);idx=struct.unpack_from('<3i',cell,16)
        gout+=struct.pack('<4f3i',*heights,*(tile_index[i] if i>=0 else -1 for i in idx))
    models=[];model_cache={};omitted=0;bounds_cache={};unsupported=[]
    for obj in objects:
        px,py,pz=struct.unpack_from('<3f',obj,216);tx=px/5+g['w']-2*x;ty=pz/5+g['h']-2*y
        rawpath=obj[56:136].split(b'\0')[0]
        rawmodel=assets.read(b'data/model/'+rawpath) if rawpath not in bounds_cache else bounds_cache[rawpath]
        bounds_cache[rawpath]=rawmodel
        if policy=='reviewed_tree' and not (4<tx<side-4 and 4<ty<side-4):continue
        if policy!='reviewed_tree':
            try:
                left,right,top,bottom=rsm_bounds.instance_bounds(rawmodel,obj)
                left=left/5+g['w']-2*x;right=right/5+g['w']-2*x
                top=top/5+g['h']-2*y;bottom=bottom/5+g['h']-2*y
                if right<0 or left>side or bottom<0 or top>side:continue
                if policy=='outdoor' and any(left<a+3 and right>a-3 and top<b+3 and bottom>b-3 for a,b in targets):
                    omitted+=1;continue
            except rsm_bounds.UnsupportedModel as exc:
                # Retain every unsupported source instance. This deliberately
                # over-includes far-away animation rather than losing walls.
                unsupported.append(dict(source_raw_hex=rawpath.hex(),reason=str(exc)))
            # Native scenery and its collision stay together. Architecture may
            # cross the crop edge; its full model is retained without flattening.
        # Independently measured selected source-tree canopy radius <=6 cells,
        # including rotation. Reserve 6.5; do not let crowns cover arena/targets.
        if policy=='reviewed_tree' and (not (6.5<tx<side-6.5 and 6.5<ty<side-6.5) or (13.5<tx<66.5 and 13.5<ty<62.5) or any(abs(tx-a)<9 and abs(ty-b)<9 for a,b in targets)):
            omitted+=1;continue
        if rawpath not in model_cache:
            ident=len(model_cache);rel=f'{namespace}/m{ident}.rsm';rsm=bytearray(assets.read(b'data/model/'+rawpath))
            if policy=='reviewed_tree' and hashlib.sha256(rsm).hexdigest()!='4fb1b5d4964c3b260bb59b399efb1a8e15e50f7487f7636c023f7dd4051ab889':
                raise ValueError('Source model bounds require independent review before import')
            if rsm[:4]!=b'GRSM' or rsm[4:6] not in (b'\x01\x03',b'\x01\x04',b'\x01\x05',b'\x01\x06'):raise ValueError('Unsupported source RSM texture table')
            pos=30+(rsm[5]>=4);count=struct.unpack_from('<I',rsm,pos)[0];pos+=4
            for j in range(count):
                texture=rsm[pos+j*40:pos+(j+1)*40].split(b'\0')[0];ext=Path(texture.decode('latin1').replace('\\','/')).suffix.lower()
                dest=f'{namespace}/m{ident}t{j}{ext}';include(b'data/texture/'+texture,f'texture/{dest}');rsm[pos+j*40:pos+(j+1)*40]=fixed(dest.replace('/','\\').encode(),40)
            files[f'model/{rel}']=bytes(rsm);model_cache[rawpath]=rel
            provenance.append(dict(source_raw_hex=(b'data/model/'+rawpath).hex(),target=f'model/{rel}',source_sha256=hashlib.sha256(assets.read(b'data/model/'+rawpath)).hexdigest(),sha256=hashlib.sha256(rsm).hexdigest()))
        obj=bytearray(obj);obj[56:136]=fixed(model_cache[rawpath].replace('/','\\').encode(),80)
        struct.pack_into('<3f',obj,216,(tx-c)*5,py,(ty-c)*5);models.append(bytes(obj))
    header=bytearray(wraw[:242]);header[6:166]=b''.join(fixed(v,40) for v in (b'',(name+'.gnd').encode(),(name+'.gat').encode(),b''))
    files[name+'.rsw']=bytes(header)+struct.pack('<I',len(models))+b''.join(models)
    files[name+'.gnd']=bytes(gout);files[name+'.gat']=b'GRAT\x01\x02'+struct.pack('<II',side,side)+b''.join(cells)
    if not models:raise ValueError('No native scenery remains')
    for rel,content in files.items():p=output/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
    def pixel(mx,my):
        xx=min(side-1,int(mx/128*side));yy=min(side-1,int(my/128*side))
        return (85,125,63) if struct.unpack_from('<I',cells[yy*side+xx],16)[0]==0 else (61,64,49)
    maps.bmp(output/'texture/ui/map'/(name+'.bmp'),128,pixel)
    report=dict(status='LOCAL_SOURCE_CROP_RUNTIME_NOT_RUN',source_map=source,origin_ground_cells=[x,y],ground_size=c,model_instances=len(models),omitted_canopy_clearance=omitted,canopy_radius_reviewed=6.5,unique_models=len(model_cache),textures=len(textures),functional_clearance=2,source_map_sha256={k:hashlib.sha256(v).hexdigest() for k,v in [('gnd',graw),('rsw',wraw),('gat',araw)]},assets=provenance,files={k:hashlib.sha256(v).hexdigest() for k,v in files.items()})
    report.update(model_policy=policy,unsupported_bounds_retained=unsupported)
    if policy=='outdoor':report['omitted_functional_target_bounds']=omitted
    if policy!='reviewed_tree': report.pop('canopy_radius_reviewed')
    (output.parent/report_name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--grf',action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source',default='prt_fild08');p.add_argument('--origin',nargs=2,type=int)
    args=p.parse_args();m=json.loads((Path(__file__).resolve().parents[1]/'content/chapter.json').read_text(encoding='utf8'))['maps'][0]
    r=build(args.grf,args.source,args.output,m,args.origin);print(json.dumps({k:v for k,v in r.items() if k not in ('assets','files')},indent=2))
