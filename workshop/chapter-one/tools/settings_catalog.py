"""Validate an explicit audited client catalog; no online or live writes."""
from wave_settings import LEGACY_IDS

def validate(profile):
    if profile.get('schema_version')!=1: raise ValueError('Unsupported catalog schema')
    client=profile.get('client_profile',{})
    if client.get('packetver')!='20250402' or client.get('historical_20221005_verified') is not False:
        raise ValueError('Only the audited current client profile is supported')
    if client.get('era')!='renewal': raise ValueError('Renewal profile required')
    rows=profile.get('monsters',[]);ids={m['id'] for m in rows}
    excluded=profile.get('excluded',[]);excluded_ids={m['id'] for m in excluded}
    if len(excluded_ids)!=len(excluded) or ids & excluded_ids: raise ValueError('Catalog selection/exclusions overlap or duplicate')
    if not rows or len(ids)!=len(rows) or not set(LEGACY_IDS)<=ids: raise ValueError('Invalid/missing catalog roots')
    for m in rows:
        audited_forest=(m['id']==1077 and m['level']==26 and m.get('hp')==379
                        and 1077 in profile.get('audited_scope_extensions',[]))
        evidence=profile.get('extension_source_audits',{}).get(str(m['id']))
        audited_extension=(isinstance(evidence,dict) and len(evidence.get('db_sha256',''))==64
                           and evidence.get('base_spawn') and len(evidence.get('assets',[]))==2
                           and all(a.get('readable') is True and a.get('signature_matches') is True for a in evidence['assets']))
        if type(m['id']) is not int or not 1<=m['id']<=46655 or type(m['level']) is not int or not (1<=m['level']<=18 or audited_forest or audited_extension):
            raise ValueError('Catalog outside level/codec scope')
        if type(m.get('hp')) is not int or not 0<=m['hp']<=4294967295: raise ValueError('Catalog base HP missing or invalid')
        if not isinstance(m['label'],str) or not m['label'] or any('가'<=c<='힣' for c in m['label']): raise ValueError('English catalog label required')
        if profile.get('selection_scope')=='base_field_dungeon':
            evidence=m.get('base_spawn',{})
            if not m.get('aegis_name') or not evidence.get('map') or not evidence.get('script','').startswith('rathena/npc/re/') or type(evidence.get('line')) is not int or evidence['line']<1 or len(evidence.get('sha256',''))!=64:
                raise ValueError('Base field/dungeon spawn evidence missing')
    verified=set(profile.get('verified_asset_ids',[]))
    if not ids<=verified: raise ValueError('Root asset coverage missing')
    for graph in ('transforms','children'):
        for source,targets in profile.get(graph,{}).items():
            if int(source) not in ids or not isinstance(targets,list) or not targets or not set(targets)<=verified:
                raise ValueError('Unaudited skill dependency')
    if 3026 in ids: raise ValueError('Unowned DEATHSUMMON is not supported')
    extensions=profile.get('audited_scope_extensions',[])
    if len(set(extensions))!=len(extensions) or not set(extensions)<=ids or not set(extensions)<={1077}|{int(i) for i in profile.get('extension_source_audits',{})}:
        raise ValueError('Unaudited catalog extension')
    if len(rows)+len(profile.get('excluded',[]))-len(extensions)!=profile.get('level_scope_record_count'):
        raise ValueError('Catalog coverage accounting mismatch')
    return profile
