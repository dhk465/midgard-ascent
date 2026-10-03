"""Assemble audited extensions and ten-floor settings banks; source only."""
import copy
import json
from pathlib import Path
import progression
import settings_catalog
import wave_settings

MAIN_MOD='midgard-ascent'


def prepare(opening, extension):
    content=progression.extend(opening,extension)
    profile=copy.deepcopy(wave_settings.catalog_profile(opening))
    additions=extension['monsters']
    profile['extension_source_audits']={str(m['id']):copy.deepcopy(m['source_evidence']) for m in additions}
    for m in additions:
        spawn=m['source_evidence']['base_spawn']
        profile['monsters'].append(dict(id=m['id'],label=m['label_ko'],level=m['native_level_reference'],hp=m['native_hp_reference'],aegis_name=m['aegis'],
            base_spawn=dict(script='rathena/npc/re/mobs/fields/'+Path(spawn['path']).name,line=spawn['line'],map=spawn['record'].split(',')[0],sha256=spawn['sha256'])))
        profile['verified_asset_ids'].append(m['id'])
    ids={m['id'] for m in additions}
    removed=[r for r in profile['excluded'] if r['id'] in ids]
    profile['excluded']=[r for r in profile['excluded'] if r['id'] not in ids]
    # Previously excluded identities count in the original audited scope already.
    profile['audited_scope_extensions']+=sorted(ids-{r['id'] for r in removed})
    content['settings_catalog']=settings_catalog.validate(profile)
    dictionary=copy.deepcopy(wave_settings.codec(opening))
    dictionary['monster_ids'] += sorted(ids-set(dictionary['monster_ids']))
    content['settings_codec']=dictionary
    wave_settings.codec(content)
    preset=copy.deepcopy(wave_settings.default_preset())
    for f in extension['floors']:
        waves=[]
        for w in range(1,21):
            authored=f['waves'][min(w,len(f['waves']))-1]
            groups=copy.deepcopy(authored)
            while len(groups)<4:groups.append(dict(mob_id=authored[0]['mob_id'],count=0))
            waves.append(dict(wave=w,group_count=len(authored),groups=groups))
        preset['floors'].append(dict(floor=f['id'],wave_count=len(f['waves']),waves=waves))
    content['wave_preset']=preset
    content['settings_banks']=[dict(start=start,end=min(start+9,len(content['floors'])),
        mod=MAIN_MOD if start==1 else f'ohk-tower-settings-{(start-1)//10+1:02}') for start in range(1,len(content['floors'])+1,10)]
    return content


def bank_content(content,bank):
    result=copy.deepcopy(content)
    result['floors']=[f for f in result['floors'] if bank['start']<=f['id']<=bank['end']]
    return result
