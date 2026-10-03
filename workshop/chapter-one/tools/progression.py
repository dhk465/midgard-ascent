"""Logical floor and optional trial contracts; never reads or writes live saves."""
from __future__ import annotations
import copy

TARGET_FLOORS = 200
TRIAL_BASE = 1000


def trial_index(trial):
    legacy=trial.get('legacy_id',trial['id'])
    expected={101:0,102:1}.get(legacy)
    index=trial.get('save_index',expected)
    if type(index) is not int or index<0 or (expected is not None and index!=expected):
        raise ValueError('Legacy trial save slot meaning changed or new trial index missing')
    if expected is None and index<2:
        raise ValueError('Legacy trial save slots are reserved')
    return index


def extend(opening, extension):
    """Append audited content, keeping opening combat and legacy save indexes."""
    if extension.get('schema_version')!=1 or extension.get('target_floor_capacity')!=TARGET_FLOORS:
        raise ValueError('Unsupported full-tower extension')
    result=copy.deepcopy(opening)
    expected=len(result['floors'])+1
    records=extension['floors']
    if not records or [r['id'] for r in records]!=list(range(expected,expected+len(records))):
        raise ValueError('Extension must append contiguous authored floors')
    existing={m['id']:m for m in result['monsters']}
    for m in extension['monsters']:
        if m['id'] in existing:
            raise ValueError('Extension cannot replace opening monster metadata')
        evidence=m.get('source_evidence',{})
        if (type(m.get('id')) is not int or type(m.get('native_level_reference')) is not int
                or type(m.get('native_hp_reference')) is not int
                or not evidence.get('db_sha256') or not evidence.get('base_spawn')
                or len(evidence.get('assets',[]))!=2
                or any(a.get('readable') is not True or a.get('signature_matches') is not True for a in evidence['assets'])
                or m.get('effective_runtime_verified') is not False):
            raise ValueError('Extension monster source/asset evidence missing')
        existing[m['id']]=copy.deepcopy(m)
    for f in records:
        for wave in f['waves']:
            if not isinstance(wave,list) or not 1<=len(wave)<=4:
                raise ValueError('Invalid extension wave groups')
            if any(set(g)!={'mob_id','count'} or g['mob_id'] not in existing
                   or type(g['count']) is not int or not 1<=g['count']<=8 for g in wave):
                raise ValueError('Unaudited extension monster or count')
            if sum(g['count'] for g in wave)>8:
                raise ValueError('Extension wave exceeds eight roots')
    result['monsters']=list(existing.values())
    result['floors']+=copy.deepcopy(records)
    for t in result['trials']:
        index=trial_index(t)
        t.update(legacy_id=t['id'], id=TRIAL_BASE+index+1, save_index=index)
    result['target_floor_capacity']=TARGET_FLOORS
    return validate(result)


def validate(content):
    floors = content['floors']
    ids = [f['id'] for f in floors]
    if not ids or any(type(i) is not int for i in ids) or ids != list(range(1, len(ids)+1)) or len(ids)>TARGET_FLOORS:
        raise ValueError('Normal floors must be a contiguous authored prefix within 1–200')
    maps = [m['id'] for m in content['maps']]
    if len(maps)!=10 or len(set(maps))!=10:
        raise ValueError('Exactly ten physical maps required')
    for f in floors:
        if f['map_id']!=maps[(f['id']-1)%10] or not 1<=len(f['waves'])<=20:
            raise ValueError('Logical floor map/wave contract')
    trial_ids = [t['id'] for t in content['trials']]
    if len(set(ids+trial_ids))!=len(ids+trial_ids):
        raise ValueError('Normal floor and trial encounter IDs collide')
    indexes = [trial_index(t) for t in content['trials']]
    if len(set(indexes))!=len(indexes) or any(type(i) is not int or i<0 for i in indexes):
        raise ValueError('Duplicate or invalid legacy trial save index')
    for t in content['trials']:
        if type(t['id']) is not int or t['id']<=TARGET_FLOORS and not (len(ids)<=100 and t['id'] in (101,102)):
            raise ValueError('Trial ID must be outside normal floor namespace')
        if type(t['unlock_floor']) is not int or t['unlock_floor'] not in ids:
            raise ValueError('Trial unlock floor must be authored')
        if t['map_id'] not in maps or not 1<=len(t['waves'])<=20:
            raise ValueError('Trial map/wave contract')
    for r in floors+content['trials']:
        for w in r['waves']:
            if not isinstance(w,list) or not 1<=len(w)<=4 or any(type(g.get('count')) is not int or not 1<=g['count']<=8 for g in w) or sum(g['count'] for g in w)>8:
                raise ValueError('Encounter roster exceeds group/root limits')
    return content


def tables(content):
    validate(content)
    lines=['function\tscript\tF_OHKC_IsNormal\t{', '\tswitch(getarg(0)) {']
    lines += [f'\tcase {f["id"]}: return 1;' for f in content['floors']]
    lines += ['\t}', '\treturn 0;', '}',
              'function\tscript\tF_OHKC_MaxFloor\t{', f'\treturn {len(content["floors"])};', '}',
              'function\tscript\tF_OHKC_TrialIndex\t{', '\tswitch(getarg(0)) {']
    lines += [f'\tcase {t["id"]}: return {trial_index(t)};' for t in content['trials']]
    lines += ['\t}', '\treturn -1;', '}', 'function\tscript\tF_OHKC_TrialUnlock\t{', '\tswitch(getarg(0)) {']
    lines += [f'\tcase {t["id"]}: return {t["unlock_floor"]};' for t in content['trials']]
    lines += ['\t}', '\treturn 0;', '}', 'function\tscript\tF_OHKC_TrialPick\t{', '\tswitch(getarg(0)) {']
    lines += [f'\tcase {n+1}: return {t["id"]};' for n,t in enumerate(content['trials'])]
    lines += ['\t}', '\treturn 0;', '}']
    return '\n'.join(lines)
