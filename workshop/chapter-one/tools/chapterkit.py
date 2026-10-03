#!/usr/bin/env python3
"""Chapter authoring/build checks; stdlib only. Never installs or starts the game."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
import maps
import balance
import npc_appearance

ROOT=Path(__file__).resolve().parents[1]
from public_paths import BUILD
MOD='midgard-ascent'
CONFIRM=('isolated_test_home_confirmed','prontera_positions_checked','effective_roster_and_skills_reviewed',
         'native_boss_summons_reviewed','conflicting_map_mods_disabled_in_test_home')
IDENTITIES={1002:'PORING',1113:'DROPS',1063:'LUNATIC',1011:'CHONCHON',1010:'WILOW',1004:'HORNET',
            1009:'CONDOR',1012:'RODA_FROG',1052:'ROCKER',1014:'SPORE',1090:'MASTERING',1088:'VOCAL'}
MAIN_IDS=[1002,1113,1063,1011,1010,1004,1009,1012,1052,1014]


def need(condition, message):
    if not condition: raise ValueError(message)


def load(path: Path):
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    need(isinstance(value,dict),'JSON object required'); return value


def integer(v,low,high):return type(v) is int and low<=v<=high


def data():return load(ROOT/'content/chapter.json')


def validate(c: dict):
    need(type(c.get('schema_version')) is int and c.get('schema_version')==1 and c.get('version')=='0.3.0','Unsupported content schema/version')
    need(c.get('app_version')=='1.2.2' and c.get('era')=='renewal','Audit version changes first')
    need(c.get('app_requirement')=='>=1.2.2','Loader requirement drifted; re-audit app compatibility first')
    need(c.get('playtest_status')=='DEFERRED_BY_USER_NOT_RUN','Do not mark this candidate game-tested')
    need(c.get('rathena_commit')=='e985006171d2eb320ee512a653f4c83aea3d81b6','Unreviewed server revision')
    need({m['id']:m['aegis'] for m in c['monsters']}==IDENTITIES and len(c['monsters'])==len(IDENTITIES),'Identity audit changed')
    expected_maps=[f'ohkt{i:02}' for i in range(1,11)]
    need([m['id'] for m in c['maps']]==expected_maps,'Exactly 10 ordered map IDs required')
    for i,m in enumerate(c['maps'],1):
        compact=m.get('native_layout')=='COMPACT_FIELD_V1'
        size=20 if compact else (40 if i<=8 else 50)
        need(type(m['ground_cells']) is int and m['ground_cells']==size,'Map size contract')
        if m.get('native_layout'):
            need(compact or (m['id'] in ('ohkt04','ohkt07') and m['native_layout']=='SOURCE_CONNECTED_V1'),'Unreviewed native layout')
            points=[m[k] for k in ('entry','keeper','exit')]+m['spawn_points']
            need(len(m['spawn_points'])==8 and all(isinstance(p,list) and len(p)==2 and all(integer(v,3,2*size-4) for v in p) for p in points),'Native layout bounds')
            need(len(set(map(tuple,points)))==11,'Overlapping native targets')
            need(all(abs(p[0]-m['entry'][0])+abs(p[1]-m['entry'][1])>=10 for p in m['spawn_points']),'Native arrival clearance')
            need(all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))>=5 for j,a in enumerate(m['spawn_points']) for b in m['spawn_points'][j+1:]),'Native spawn separation')
        else:
            need(m['entry']==[size,12] and m['keeper']==[size-4,12] and m['exit']==[size+4,12],'Fixed NPC geometry changed')
            need(m['spawn_points']==[[size-8,32],[size,36],[size+8,32],[size-4,44],[size+4,44],[size-12,40],[size+12,40],[size,48]],'Spawn geometry contract')
        for key in ('base_rgb','accent_rgb'):need(len(m[key])==3 and all(integer(x,0,255) for x in m[key]),'Invalid RGB')
        need(m['pattern'] in ('grass','moss','sand','rock','ruins','crypt','ice','lava','fortress','sanctum'),'Unknown material')
        if i==1:
            need(m.get('theme_geometry')=='TRAINING_GROUND_V1' and m['art_status']=='ORIGINAL_TRAINING_GROUND_CANDIDATE_GAME_NOT_RUN','Training ground art status misrepresented')
        else:
            need('theme_geometry' not in m and m['art_status']=='PROCEDURAL_FLOOR_BLOCKOUT_NO_3D_PROPS','Art status misrepresented')
    need(all(type(f['id']) is int for f in c['floors']) and [f['id'] for f in c['floors']]==list(range(1,11)),'Missing/duplicate/reordered floor')
    for f in c['floors']:
        need(f['map_id']==expected_maps[f['id']-1] and len(f['waves'])==3,'Floor map/wave contract')
        for w in f['waves']:
            need(isinstance(w,list) and 1<=len(w)<=2,'Empty or oversized wave')
            need(all(set(g)=={'mob_id','count'} and g['mob_id'] in MAIN_IDS and integer(g['count'],1,8) for g in w),'Unaudited roster or invalid count')
            need(sum(g['count'] for g in w)<=8,'Wave exceeds spawn slots')
    need(all(type(t['id']) is int for t in c['trials']) and [t['id'] for t in c['trials']]==[101,102],'Exactly two optional trials')
    for t,mid,children,mp,mvp in zip(c['trials'],[1090,1088],[[1002,1113],[1052]],['ohkt09','ohkt10'],[False,False]):
        need(t['waves']==[[{'mob_id':mid,'count':1}]] and type(t['waves'][0][0]['count']) is int,'Native boss root contract')
        need(t['native_child_ids']==children and t['map_id']==mp and t['unlock_floor']==10 and t['mvp'] is mvp,'Native summon or unlock contract changed')
    keys={'first_wave','between_waves','clear_notice','floor_transition','boss_ready','native_settle_limit'}
    need(set(c['timing_ms'])==keys,'Unknown timing key')
    need(all(integer(v,1000,60000) for v in c['timing_ms'].values()),'Invalid timing')
    need(c['timing_ms']['first_wave']>=3000 and c['timing_ms']['native_settle_limit']>c['timing_ms']['clear_notice'],'Invalid preparation/settling windows')
    balance.validate_main_level_envelope(c)


# Local app versions a site may attest, each with a reviewed loader audit.
# 1.2.2: SOURCE_LOCK reviewed base. 1.3.0: installed locally 2026-09-17; audited
# same rathena upstream pin, mod folder contract and version-rule semantics in
# stack/src/mods.rs at tag v1.3.0. A new app version needs that audit first.
# 1.4.3: observed 2026-10-02; same upstream pin, installed mod-check
# accepts the candidate. This is loader evidence, not gameplay certification.
SITE_APP_VERSIONS=('1.2.2','1.3.0','1.4.3')


def validate_site(s,require_confirmations=True):
    need(type(s.get('schema_version')) is int and s.get('schema_version')==1 and s.get('app_version') in SITE_APP_VERSIONS and s.get('era')=='renewal','Unreviewed site version')
    for k in CONFIRM:
        need(type(s.get(k)) is bool,'Explicit local evidence flag required: '+k)
        if require_confirmations:need(s[k] is True,'Local evidence required: '+k)
    need(s.get('npc_encoding') in ('utf-8','cp949'),'Explicit verified NPC encoding required')
    need(isinstance(s.get('evidence_note'),str) and s['evidence_note'].strip(),'Missing local evidence note')
    for k in ('prontera_gate','prontera_return'):
        need(isinstance(s.get(k),dict) and all(integer(s[k].get(a),1,511) for a in ('x','y')),'Invalid '+k)
    need(tuple(s['prontera_gate'][a] for a in ('x','y')) != tuple(s['prontera_return'][a] for a in ('x','y')),'Return cannot overlap NPC')


def quote(value):
    need(isinstance(value,str) and '\n' not in value and '\r' not in value,'Invalid script string')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'


def tables(c):
    records=c['floors']+c['trials']
    monsters={m['id']:m for m in c['monsters']}
    themes={m['id']:m['theme_ko'] for m in c['maps']}
    import progression
    funcs=[progression.tables(c)]
    for name,key,kind in [('Map','map_id','s'),('Name','name_ko','s'),('Theme',None,'s'),('Waves',None,'n'),('MapNo',None,'n'),('Center',None,'n')]:
        lines=[f'function\tscript\tF_OHKC_{name}\t{{','\tswitch(getarg(0)) {']
        for r in records:
            if name=='Waves':v=str(len(r['waves']))
            elif name=='MapNo':v=str(int(r['map_id'][-2:]))
            elif name=='Center':v=str(c['maps'][int(r['map_id'][-2:])-1]['ground_cells'])
            elif name=='Theme':v=quote(r.get('theme_ko',themes[r['map_id']]))
            else:v=quote(r[key])
            lines.append(f'\tcase {r["id"]}: return {v};')
        lines+=['\t}', '\treturn '+('""' if kind=='s' else '0')+';', '}']
        funcs.append('\n'.join(lines))
    funcs.append('function\tscript\tF_OHKC_IsMap\t{\n\treturn '+' || '.join('getarg(0)=='+quote(m['id']) for m in c['maps'])+';\n}')
    for name,key in [('Entry','entry'),('Spawn','spawn_points')]:
        lines=[f'function\tscript\tF_OHKC_{name}X\t{{','\tswitch(getarg(0)) {']
        ylines=[f'function\tscript\tF_OHKC_{name}Y\t{{','\tswitch(getarg(0)) {']
        for r in records:
            m=c['maps'][int(r['map_id'][-2:])-1]
            points=[m[key]] if name=='Entry' else m[key]
            for axis,target in [(0,lines),(1,ylines)]:
                if name=='Entry':target.append(f'\tcase {r["id"]}: return {points[0][axis]};')
                else:
                    target.append(f'\tcase {r["id"]}:')
                    for j,p in enumerate(points):target.append(f'\t\tif (getarg(1)=={j}) return {p[axis]};')
                    target.append('\t\treturn -1;')
        funcs.extend('\n'.join(v+['\t}','\treturn -1;','}']) for v in (lines,ylines))
    catalog=c.get('settings_catalog', {})
    transforms=catalog.get('transforms', {})
    children=catalog.get('children', {})
    lines=['function\tscript\tF_OHKC_RootClass\t{', '\tif (getarg(0)==getarg(1)) return 1;']
    for original, targets in transforms.items():
        lines.append(f'\tif (getarg(0)=={int(original)}) return '+' || '.join(f'getarg(1)=={int(i)}' for i in targets)+';')
    if catalog: funcs.append('\n'.join(lines+['\treturn 0;','}']))
    lines=['function\tscript\tF_OHKC_Child\t{']
    for t in c['trials']:lines.append(f'\tif (getarg(0)=={t["id"]}) return '+' || '.join('getarg(1)=='+str(i) for i in t['native_child_ids'])+';')
    for original, targets in children.items():
        lines.append(f'\tif (callfunc("F_OHKC_IsNormal",getarg(0)) && getarg(2,0)=={int(original)}) return '+' || '.join(f'getarg(1)=={int(i)}' for i in targets)+';')
    funcs.append('\n'.join(lines+['\treturn 0;','}']))
    lines=['function\tscript\tF_OHKC_Warning\t{']
    for t in c['trials']:lines.append(f'\tif (getarg(0)=={t["id"]}) return '+quote(t['warning_ko'])+';')
    funcs.append('\n'.join(lines+['\treturn "";','}']))
    lines=['function\tscript\tF_OHKC_WaveInfo\t{','\tswitch(getarg(0)*100+getarg(1)) {']
    for r in records:
        for widx,w in enumerate(r['waves'],1):
            summary=f'{widx}웨이브: '+', '.join(f'{monsters[g["mob_id"]]["label_ko"]} {g["count"]}마리' for g in w)
            lines.append(f'\tcase {r["id"]*100+widx}: return {quote(summary)};')
    funcs.append('\n'.join(lines+['\t}','\treturn "";','}']))
    lines=['function\tscript\tF_OHKC_Roster\t{','\tswitch(getarg(0)*100+getarg(1)) {']
    for r in records:
        for widx,w in enumerate(r['waves'],1):
            ids=[g['mob_id'] for g in w for _ in range(g['count'])]
            lines+=[f'\tcase {r["id"]*100+widx}:',f'\t\tsetarray $@ohkc_roster[0],'+','.join(map(str,ids))+';',f'\t\t$@ohkc_expected={len(ids)};', '\t\treturn 1;']
    funcs.append('\n'.join(lines+['\t}','\treturn 0;','}']))
    return '\n\n'.join(funcs)


def map_npcs(c):
    chunks=[]
    for i,m in enumerate(c['maps'],1):
        mp=m['id']; kx,ky=m['keeper']; ex,ey=m['exit']
        for suffix,display,helper,role in [('r','도전 준비','ReadyMenu','ready'),('k','탑 기록관','KeeperMenu','keeper')]:
            appearance=npc_appearance.sprite(c,role,i)
            chunks.append(f'{mp},{kx},{ky},4\tscript\t{display}::ohkc_{suffix}{i}\t{appearance},{{\n\tcallfunc "F_OHKC_{helper}","{mp}";\n\tend;\n}}')
        chunks.append(f'{mp},{ex},{ey},4\tscript\t귀환 안내::ohkc_x{i}\t{npc_appearance.sprite(c,"exit",i)},{{\n\tif ($@ohkc_state==0 || $@ohkc_state==9) callfunc "F_OHKC_Return";\n\telse dispbottom "전투 후 기록관을 이용하세요. 기존 탈출 수단은 제한하지 않습니다.";\n\tend;\n}}')
        chunks.append(f'{mp}\tmapflag\tloadevent')
    return '\n\n'.join(chunks)


def strip(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',lambda m:' '*len(m.group()),text)


def lint(text,armed,mod_settings_bridge=False):
    need(not re.search(r'__[A-Z_]+__',text),'Unresolved token')
    code=strip(text); stack=[]
    for ch in code:
        if ch in '([{':stack.append(ch)
        elif ch in ')]}':need(bool(stack) and stack.pop()=={')':'(',']':'[','}':'{'}[ch],'Unbalanced delimiter')
    need(not stack,'Unclosed delimiter')
    names=[]
    for line in text.splitlines():
        if '\tscript\t' in line and not line.startswith('function\t'):
            parts=line.split('\t'); need(len(parts)==4,'NPC header tabs')
            display,_,unique=parts[2].partition('::'); name=unique or display
            need(len(display.encode('utf-8'))<=24 and len(name.encode('ascii'))<=24,'NPC name limits'); names.append(name)
    need(len(names)==len(set(names)),'Duplicate NPC')
    need(('ohkc_gate' in names)==armed and len(names)==31+int(armed),'Wrong NPC count or gateway state')
    defs=set(re.findall(r'^function\tscript\t(\w+)\t',text,re.M))
    calls=set(re.findall(r'callfunc(?:\s*\(\s*|\s+)"([^"]+)"',text))
    external={'F_ModSetting'} if mod_settings_bridge else set()
    need(calls<=defs|external,'Undefined function: '+str(calls-defs-external))
    for keyword in ('setunitdata','unitkill','killmonsterall','getexp','getitem','heal','percentheal','recovery','query_sql','setbattleflag','addtimer','sleep','sleep2','attachrid'):
        need(not re.search(r'\b'+keyword+r'\b',code),'Forbidden operation: '+keyword)
    need(text.count('OnNPCKillEvent:')==1,'Normal kill observer count')
    need(re.findall(r'^\s*monster ([^;]+);',text,re.M)==['$@ohkc_map$,.@x,.@y,"--ja--",$@ohkc_roster[.@i],1'],'Spawn overrides or private label')
    need(re.findall(r'^\s*killmonster ([^;]+);',text,re.M)==['$@ohkc_map$,"",0'],'Unsafe cleanup')
    need('$@mobid[0]=0;' in text and 'UMOB_MASTERAID' in code,'Ownership/spawn contract')
    need('getunitdata(' not in code,'Do not assume getunitdata returns a success value')
    # Actual text encodability is not a client rendering test.
    for enc in ('utf-8','cp949'):text.encode(enc)


def render(c=None,site=None,installation_candidate=False,settings_mod_name=None,extension=None,compiled_preset=None):
    c=data() if c is None else c; validate(c)
    import wave_settings
    c=wave_settings.combat_content(c)
    balance.validate_main_level_envelope(c)
    if extension is not None:
        import full_tower
        c=full_tower.prepare(c,extension)
    if compiled_preset is not None:
        import copy
        c['wave_preset']=copy.deepcopy(compiled_preset)
    need(not installation_candidate or site is not None,'Candidate requires explicit site')
    if site is not None:validate_site(site,require_confirmations=not installation_candidate)
    s=(ROOT/'src/engine.txt.in').read_text(encoding='utf-8')
    identities={m['id']:m['aegis'] for m in c['monsters']} if extension is not None else IDENTITIES
    identity='\n'.join(f'\tif (getmonsterinfo("{a}",MOB_ID)!={i}) {{ $@ohkc_site_ok=0; debugmes "[OHKC] ID mismatch: {a}"; }}' for i,a in identities.items())
    gate=(ROOT/'src/gateway.txt.in').read_text(encoding='utf-8').replace('__GATE_SPRITE__',npc_appearance.sprite(c,'gateway')) if site else ''
    times=c['timing_ms']
    if settings_mod_name is not None and not c.get('settings_catalog'):
        import wave_settings
        c=dict(c,settings_catalog=wave_settings.catalog_profile(c))
    functions=tables(c)
    if settings_mod_name is not None:
        import wave_settings
        need(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',settings_mod_name) is not None,'Invalid settings mod name')
        for name in ('Waves','Roster','WaveInfo'):
            functions=functions.replace('function\tscript\tF_OHKC_'+name+'\t{','function\tscript\tF_OHKC_Default'+name+'\t{')
        functions=wave_settings.default_tables(c,functions)
        functions+='\n\n'+wave_settings.runtime(c,settings_mod_name,compiled=compiled_preset is not None)
    s=wave_settings.adapt_engine(s)
    rep={'__DATA_FUNCTIONS__':functions,'__MAP_NPCS__':map_npcs(c),'__GATEWAY__':gate,'__SITE_OK__':str(int(site is not None)), '__IDENTITY_CHECKS__':identity,
         '__FIRST_MS__':str(times['first_wave']),'__BETWEEN_MS__':str(times['between_waves']),'__BOSS_MS__':str(times['boss_ready']),
         '__CLEAR_MS__':str(times['clear_notice']),'__TRANSITION_MS__':str(times['floor_transition']),'__SETTLE_LIMIT__':str(times['native_settle_limit'])}
    for typ in ('GATE','RETURN'):
        point=site['prontera_'+typ.lower()] if site else {'x':0,'y':0}
        for axis in ('x','y'):rep[f'__{typ}_{axis.upper()}__']=str(point[axis])
    for k,v in rep.items():s=s.replace(k,v)
    lint(s,site is not None,mod_settings_bridge=settings_mod_name is not None)
    return s


def archive(folder,path):
    need(not path.exists(),'Refusing existing ZIP')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                inf=zipfile.ZipInfo(folder.name+'/'+p.relative_to(folder).as_posix(),(2026,9,15,0,0,0))
                inf.compress_type=zipfile.ZIP_DEFLATED; inf.external_attr=0o100644<<16
                z.writestr(inf,p.read_bytes())


def build(site=None,installation_candidate=False):
    c=data(); text=render(c,site,installation_candidate=installation_candidate)
    BUILD.mkdir(parents=True,exist_ok=True)
    target=BUILD/('chapter-one-install-candidate' if installation_candidate else 'chapter-one-test' if site else 'chapter-one-review')
    need(not target.exists(),'Output exists; preserve it instead of overwriting')
    with tempfile.TemporaryDirectory(prefix='ch1-',dir=BUILD) as tmp:
        stage=Path(tmp); mod=stage/MOD; (mod/'npc').mkdir(parents=True)
        for n,m in enumerate(c['maps'],1):
            print(f'[map {n}/10] {m["id"]}: {m["theme_ko"]}',flush=True)
            maps.generate(mod/'data',m); maps.validate(mod/'data',m)
        encoding=site['npc_encoding'] if site else 'utf-8'
        (mod/'npc/chapter.txt').write_bytes(text.encode(encoding))
        meta={'name':MOD,'version':'0.3.0','author':'dhk465','description':'10-floor / 2-boss candidate. Game tests deferred. '+('Isolated test build.' if site else 'Review build: no Prontera gateway.'),'requires':{'app':c['app_requirement'],'era':'renewal'}}
        (mod/'mod.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (mod/'README.ko.md').write_text('일반 10층 / 공통 프리셋 웨이브 / 선택형 보스 2종 구현 후보.\n운영 설치 전 현장 확인과 실제 게임 검증이 필요합니다.\n'+('테스트 전용 입구가 포함되었습니다.\n' if site else '프론테라 입구와 입장이 잠긴 검토용입니다. 정상 플레이 배포본이 아닙니다.\n')+'1층은 원본 훈련장 장식 후보이며 실제 외형 검증 전입니다. 2–10층은 바닥 재질 blockout입니다.\n기존 F1/lab 모드와 같은 맵을 동시에 로드하지 마세요.\n',encoding='utf-8')
        hashes={p.relative_to(mod).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(mod.rglob('*')) if p.is_file()}
        report={'status':'BUILT_GAME_TESTS_DEFERRED','floors':10,'normal_waves':sum(len(f['waves']) for f in __import__('wave_settings').combat_content(c)['floors']),'optional_bosses':2,'maps':10,'armed':site is not None,'npc_encoding':encoding,'native_engine_tested':False,'art_status':{m['id']:m['art_status'] for m in c['maps']},'files_sha256':hashes}
        if installation_candidate:
            report.update(status='BUILT_INSTALL_CANDIDATE_GAME_NOT_RUN',site_evidence_verified=False,
                          site_app_version=site['app_version'],site_confirmations={k:site[k] for k in CONFIRM})
            meta['description']='Installation test candidate; site/game checks pending.'
            (mod/'mod.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (mod/'README.ko.md').write_text('사용자가 요청한 앱 설치 테스트 후보입니다. 입구 포함, 현장 검증/게임 테스트 미완료.\n기존 보상과 캐릭터 데이터를 임의 변경하지 않습니다. BATCH-TEST 목록으로 실제 결과를 확인하세요.\n',encoding='utf-8')
            report['files_sha256']={p.relative_to(mod).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(mod.rglob('*')) if p.is_file()}
        (mod/'BUILD-REPORT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        archive(mod,stage/(MOD+'.zip'))
        stage.rename(target)
    print('Built',target,'- not installed.');return target


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','build-review','build-test','build-install-candidate']);p.add_argument('--site',type=Path)
    a=p.parse_args(argv)
    try:
        if a.command=='check':render();print('PASS: structure/content only; not rAthena parsing.')
        elif a.command=='build-review':need(a.site is None,'Review does not use a site');build()
        else:need(a.site is not None,'--site required');build(load(a.site),installation_candidate=a.command=='build-install-candidate')
        return 0
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as e:
        print('BLOCKED:',e,file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
