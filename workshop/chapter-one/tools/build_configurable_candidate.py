"""Reuse verified native map assets; add app UI/server settings. Never installs."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
import chapterkit
from public_paths import BUILD
import wave_settings
import npc_appearance

MOD = 'midgard-ascent'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, destination, site, catalog=None, extension=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    root = BUILD.resolve()
    chapterkit.need(destination != root and destination.is_relative_to(root), 'Output must be nested inside repository build/')
    chapterkit.need(not destination.exists(), 'Output exists; preserve it')
    chapterkit.need(not destination.with_suffix('.zip').exists(), 'ZIP exists; preserve it')
    chapterkit.need(not destination.is_relative_to(source) and not source.is_relative_to(destination), 'Source/output overlap')
    c = chapterkit.load(source / 'NATIVE-CONTENT.json')
    # Reuse only verified geometry/assets; combat always comes from current source.
    authored=chapterkit.data()
    c['monsters']=authored['monsters']
    c['trials']=authored['trials']
    chapterkit.validate(c)
    if catalog is None:
        catalog=chapterkit.ROOT/'content/settings-catalog-20250402.json'
    if catalog is not None:
        import settings_catalog
        profile=chapterkit.load(catalog)
        settings_catalog.validate(profile)
        c['settings_catalog']=profile
    if not c.get('settings_catalog'):
        c['settings_catalog']=wave_settings.catalog_profile(c)
    c['npc_appearance']=npc_appearance.load(c)
    s = chapterkit.load(site)
    chapterkit.validate_site(s, require_confirmations=False)
    chapterkit.need(tuple(map(int,s['app_version'].split('.'))) >= (1,3,4), 'settingsPage/F_ModSetting needs app >=1.3.4')
    previous = chapterkit.load(source / 'BUILD-REPORT.json')
    for name, expected in previous['files_sha256'].items():
        path = (source / name).resolve()
        chapterkit.need(path.is_relative_to(source) and path.is_file() and digest(path)==expected,
                        'Source manifest mismatch: '+name)
    import full_tower
    resolved=wave_settings.combat_content(c)
    if extension is not None:
        resolved=full_tower.prepare(resolved,extension)
        for bank in resolved['settings_banks'][1:]:
            path=destination.parent/bank['mod']
            chapterkit.need(not path.exists() and not path.with_suffix('.zip').exists(),'Settings bank output exists; preserve it')
    text = chapterkit.render(c,s,installation_candidate=True,settings_mod_name=MOD,extension=extension)
    shutil.copytree(source,destination)
    meta = chapterkit.load(destination / 'mod.json')
    meta.update(name=MOD,version='0.9.0',description='Shared opening baseline with Vocal trial; full-tower development foundation. Per-wave groups and JSON presets; Apply restarts the server.')
    (destination / 'mod.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination / 'npc/chapter.txt').write_bytes(text.encode(s['npc_encoding']))
    (destination / 'NATIVE-CONTENT.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination / 'RESOLVED-COMBAT.json').write_text(json.dumps(resolved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if extension is None:
        wave_settings.attach(destination,c)
    else:
        banks=resolved['settings_banks']
        meta=chapterkit.load(destination/'mod.json')
        meta['version']='1.0.0'
        meta['description']='Authored floors 1-20, two optional trials; 200-floor capacity. Ten-floor settings modules. Game tests pending.'
        meta['requires']['mods']=[b['mod'] for b in banks[1:]]
        (destination/'mod.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        wave_settings.attach(destination,full_tower.bank_content(resolved,banks[0]))
        (destination/'FULL-TOWER-CONTENT.json').write_text(json.dumps(resolved,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (destination/'README.ko.md').write_text('전체 타워 1.0.0 검토 후보: 일반 1–20층 / 기본 62웨이브 / 선택 보스 2종.\n'
            '200층은 진행·편집 구조의 지원 용량이며, 21–200층 콘텐츠는 아직 제작되지 않았습니다.\n'
            '기존 10개 맵·좌표·BGM을 재사용합니다. 11–20층 전투 테마를 새 맵 외형 검증으로 간주하지 않습니다.\n'
            '이 주 모드와 ohk-tower-settings-02를 함께 설치해야 합니다. 현재 패키지는 설치하지 않았습니다.\n'
            '주 모드 설정 창은 1–10층, 동반 모듈 설정 창은 11–20층을 편집합니다. 각각 숨긴 20웨이브·4그룹을 유지합니다.\n'
            '기존 주 모드 이름·1–10층 저장 키·코덱 번호·보스 완료 슬롯 0/1은 유지합니다.\n'
            'Save는 앱 설정 저장, Apply는 서버 재시작입니다. 운영 설치·Apply는 별도 승인 후 수행합니다.\n'
            '자동 검사와 앱 mod-check는 실제 서버 파서·게임·난이도 검증을 대신하지 않습니다. 게임 검증 NOT_RUN.\n',encoding='utf8')
        for bank in banks[1:]:
            path=destination.parent/bank['mod'];path.mkdir()
            meta=dict(name=bank['mod'],version='1.0.0',author='dhk465',description=f"Wave editor for floors {bank['start']}-{bank['end']}; requires the full tower package for gameplay.",requires=dict(app='>=1.3.4',era='renewal'))
            (path/'mod.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            wave_settings.attach(path,full_tower.bank_content(resolved,bank))
            (path/'README.ko.md').write_text(f"{bank['start']}–{bank['end']}층 설정 전용 모듈. 주 모드 {MOD}와 함께 사용합니다.\n"
                '몬스터·웨이브·수량 편집 창만 제공하며 게임 맵·NPC를 추가하지 않습니다. Save와 Apply는 별개입니다.\n',encoding='utf8')
            hashes={p.relative_to(path).as_posix():digest(p) for p in sorted(path.rglob('*')) if p.is_file()}
            (path/'BUILD-REPORT.json').write_text(json.dumps(dict(status='SETTINGS_BANK_GAME_NOT_RUN',floor_start=bank['start'],floor_end=bank['end'],files_sha256=hashes),indent=2)+'\n',encoding='utf8')
            chapterkit.archive(path,path.with_suffix('.zip'))
    assets = {p.relative_to(source).as_posix():digest(p) for p in (source/'data').rglob('*') if p.is_file()}
    chapterkit.need(all(digest(destination/name)==sha for name,sha in assets.items()), 'Map/BGM assets changed')
    report = dict(previous)
    report.update(status='CONFIGURABLE_CANDIDATE_APP_GAME_NOT_RUN',source_candidate=str(source),
                  default_normal_waves=sum(f['wave_count'] for f in wave_settings.preset_for(resolved)['floors']),
                  normal_waves=sum(f['wave_count'] for f in wave_settings.preset_for(resolved)['floors']),
                  floors=len(resolved['floors']),target_floor_capacity=resolved.get('target_floor_capacity',10),settings_banks=resolved.get('settings_banks',[]),
                  configurable_wave_range=[1,20],configurable_group_range=[1,4],max_monsters_per_wave=8,max_groups_per_wave=4,
                  settings_persistence='app state/mod-settings.json; changes take effect on Apply/server start',
                  preserved_asset_count=len(assets),native_engine_tested=False,
                  catalog_profile=c.get('settings_catalog',{}).get('client_profile'),
                  catalog_count=len(wave_settings.catalog_monsters(resolved)),
                  catalog_selection_scope=c.get('settings_catalog',{}).get('selection_scope'),
                  npc_appearance=c['npc_appearance'],
                  catalog_exclusions=c.get('settings_catalog',{}).get('excluded',[]))
    report['files_sha256']={p.relative_to(destination).as_posix():digest(p) for p in sorted(destination.rglob('*')) if p.is_file() and p.name!='BUILD-REPORT.json'}
    (destination / 'BUILD-REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    chapterkit.archive(destination,destination.with_suffix('.zip'))
    return destination


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--site',type=Path,required=True)
    p.add_argument('--catalog',type=Path)
    a=p.parse_args()
    try:
        print(build(a.source,a.output,a.site,a.catalog));return 0
    except (ValueError,OSError,KeyError,TypeError) as e:
        print('BLOCKED:',e,file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
