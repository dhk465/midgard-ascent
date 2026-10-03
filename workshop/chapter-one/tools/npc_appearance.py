"""Audited NPC appearances; changes sprite headers only."""
import json
import re
from pathlib import Path

PROFILE=Path(__file__).resolve().parents[1]/'content/npc-appearance.json'

def validate(profile):
    if profile.get('schema_version')!=1 or profile.get('status')!='LOCAL_ASSET_VERIFIED_GAME_NOT_RUN':
        raise ValueError('NPC appearance profile is not verified')
    rows=[profile['gateway']]+profile['ready']+profile['keeper']+profile['exit']
    for row in rows:
        if not re.fullmatch(r'[24]_[MF]_[A-Z0-9_]+',row['sprite']) or 'KAFRA' in row['sprite']:
            raise ValueError('Unaudited/Kafra NPC sprite')
        if type(row['id']) is not int or row['id']<=0: raise ValueError('NPC sprite identity required')
        if not all(re.fullmatch(r'[0-9a-f]{64}',row.get(k,'')) for k in ('spr_sha256','act_sha256')):
            raise ValueError('Client asset hash evidence required')
    if len({r['id'] for r in rows})!=len(rows): raise ValueError('NPC role cast must be varied')
    for role in ('ready','keeper','exit'):
        indices=profile['floor_variants'][role]
        if len(indices)!=10 or any(type(i) is not int or not 0<=i<len(profile[role]) for i in indices):
            raise ValueError('NPC floor cast is incomplete')
    return profile

def load(content):
    return validate(content.get('npc_appearance') or json.loads(PROFILE.read_text(encoding='utf-8')))

def sprite(content,role,floor=None):
    profile=load(content)
    if role=='gateway': return profile['gateway']['sprite']
    return profile[role][profile['floor_variants'][role][floor-1]]['sprite']
