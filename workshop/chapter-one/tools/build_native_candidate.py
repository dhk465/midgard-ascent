"""Build all ten native map crops from local GRFs; never install or start game."""
import argparse
import copy
import hashlib
import json
import shutil
import re
from pathlib import Path
import chapterkit
import import_field
import native_bgm

def build(site, grfs, destination, profiles_path=None, mod_name='midgard-ascent-native', bgm_baseline=None, bgm_dir=None):
    if not re.fullmatch(r'midgard-ascent(?:-[a-z0-9-]+)?', mod_name):
        raise ValueError('Invalid candidate mod name')
    destination=Path(destination).resolve()
    root=Path(__file__).resolve().parents[3]
    if not destination.is_relative_to(root/'build') or destination==root/'build' or destination.exists():
        raise ValueError('Choose fresh nested ignored build output')
    if (bgm_baseline is None) != (bgm_dir is None):
        raise ValueError('BGM baseline and BGM directory must be supplied together')
    profiles=chapterkit.load(profiles_path or chapterkit.ROOT/'content/field-ten-profiles.json')['maps']
    bgm = native_bgm.prepare(bgm_baseline, bgm_dir, profiles) if bgm_baseline is not None else None
    chapterkit.BUILD=destination
    base=chapterkit.build(chapterkit.load(site),installation_candidate=True)/chapterkit.MOD
    out=base.parent/mod_name;shutil.copytree(base,out)
    c=copy.deepcopy(chapterkit.data())
    if [p['id'] for p in profiles]!=[m['id'] for m in c['maps']]:raise ValueError('Incomplete ordered native profiles')
    import wave_settings
    resolved=wave_settings.combat_content(c)
    assets=import_field.Archives(grfs);reports=[]
    for m,p in zip(c['maps'],profiles):
        if 'layout' in p:
            m.update(p['layout']);m['native_layout']=p.get('native_layout','SOURCE_CONNECTED_V1')
        policy=p.get('policy', 'reviewed_tree' if m['id']=='ohkt01' else 'outdoor')
        if m['id']=='ohkt01' and m.get('native_layout')!='COMPACT_FIELD_V1':policy='reviewed_tree'
        if 'habitat_mob_ids' in p:
            used={g['mob_id'] for w in resolved['floors'][len(reports)]['waves'] for g in w}
            p['active_roster_native_habitat_verified']=used.issubset(set(p['habitat_mob_ids']))
        report=import_field.build(assets,p['source'],out/'data',m,p['origin'],policy=policy,report_name=m['id']+'-IMPORT-REPORT.json')
        reports.append(report)
        print(m['id'],p['source'],report['model_instances'],'models',flush=True)
    chapterkit.validate(c)
    (out/'npc/chapter.txt').write_bytes(chapterkit.render(c,chapterkit.load(site),installation_candidate=True).encode(chapterkit.load(site)['npc_encoding']))
    (out/'NATIVE-CONTENT.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    meta=chapterkit.load(out/'mod.json');meta.update(name=out.name,description='Ten local native RO map crops; runtime appearance and gameplay checks pending.')
    (out/'mod.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    (out/'README.ko.md').write_text('로컬 GRF에서 가져온 10층 후보. 게임 자산은 커밋/공유하지 않는다.\n층별 원본 통행 구역을 검사했다. 원본 몬스터 능력치·스킬·보상 규칙은 변경하지 않는다.\n외형·카메라 가림·공통 프리셋 게임 검증은 미완료. 같은 맵 ID의 다른 타워 모드와 함께 활성화하지 않는다.\n',encoding='utf8')
    report=chapterkit.load(out/'BUILD-REPORT.json')
    report.update(status='LOCAL_NATIVE_TEN_FLOOR_CANDIDATE_RUNTIME_NOT_RUN',native_engine_tested=False,
                  art_status={m['id']:'LOCAL_'+p['source'].upper()+'_CROP_RUNTIME_NOT_RUN' for m,p in zip(c['maps'],profiles)},
                  native_profiles=profiles,monsters='Shared opening roster; exact native habitat '+('verified' if all(p.get('active_roster_native_habitat_verified') for p in profiles) else 'not verified for all groups'),
                  model_instances=sum(r['model_instances'] for r in reports))
    if bgm is not None:
        (out/'data/mp3nametable.txt').write_bytes(bgm[0])
        report['bgm'] = bgm[1]
    report['files_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='BUILD-REPORT.json'}
    (out/'BUILD-REPORT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    chapterkit.archive(out,out.parent/(out.name+'.zip'))
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,required=True);parser.add_argument('--grf',action='append',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profiles',type=Path);parser.add_argument('--mod-name',default='midgard-ascent-native')
    parser.add_argument('--bgm-baseline',type=Path);parser.add_argument('--bgm-dir',type=Path)
    args=parser.parse_args();print(build(args.site,args.grf,args.output,args.profiles,args.mod_name,args.bgm_baseline,args.bgm_dir))
