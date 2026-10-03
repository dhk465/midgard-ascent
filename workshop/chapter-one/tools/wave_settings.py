"""Declared app settings and defensive NPC bridge. No live state writes."""
import copy
import json
import re
import shutil
from pathlib import Path

MAX_WAVES = 20
MAX_ROOTS = 8
MAX_GROUPS = 4
BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
LEGACY_IDS = [1002,1113,1063,1011,1010,1004,1009,1012,1052,1014]

def catalog_profile(content):
    if content.get('settings_catalog'):
        return content['settings_catalog']
    import settings_catalog
    profile=json.loads((Path(__file__).resolve().parents[1]/'content/settings-catalog-20250402.json').read_text(encoding='utf-8'))
    return settings_catalog.validate(profile)


def catalog_monsters(content):
    return catalog_profile(content)['monsters']


def codec(content):
    record=content.get('settings_codec') or json.loads((Path(__file__).resolve().parents[1]/'content/settings-codec-c1.json').read_text(encoding='utf-8'))
    ids=record['monster_ids']
    if len(ids)>256 or len(set(ids))!=len(ids) or not {m['id'] for m in catalog_monsters(content)}<=set(ids):
        raise ValueError('Frozen codec dictionary does not cover catalog')
    record=dict(record,tag=record['tag'].replace('g4:','g5:'))
    return record


def base36_id(value):
    if not 1 <= value <= 46655: raise ValueError("Monster ID exceeds codec range")
    alphabet="0123456789abcdefghijklmnopqrstuvwxyz"
    return "".join(alphabet[(value // (36**n)) % 36] for n in (2,1,0))



def key(floor, wave=None, group=None, field=None):
    return f'f{floor}_waves' if wave is None else f'f{floor}_w{wave}_g{group}_{field}'


def default_preset():
    """Single captured source for every future configurable build, including hidden values."""
    preset=json.loads((Path(__file__).resolve().parents[1]/'content/wave-default-preset.json').read_text(encoding='utf-8'))
    if preset.get('schema_version')!=3 or len(preset['floors'])!=10:
        raise ValueError('Invalid shared wave preset')
    for fid,floor in enumerate(preset['floors'],1):
        if floor['floor']!=fid or type(floor['wave_count']) is not int or not 1<=floor['wave_count']<=20 or len(floor['waves'])!=20:
            raise ValueError('Invalid preset floor')
        for wid,wave in enumerate(floor['waves'],1):
            if wave['wave']!=wid or type(wave['group_count']) is not int or not 1<=wave['group_count']<=4 or len(wave['groups'])!=4:
                raise ValueError('Invalid preset wave')
            for group in wave['groups']:
                if type(group['mob_id']) is not int or not 1<=group['mob_id']<=200000 or type(group['count']) is not int or not 0<=group['count']<=8:
                    raise ValueError('Invalid preset group')
            if not 1<=sum(g['count'] for g in wave['groups'][:wave['group_count']])<=8:
                raise ValueError('Invalid preset active total')
    return preset


def combat_content(content):
    """Resolve every build's opening encounters from the shared preset.

    Legacy authored geometry remains compatible. Never mutate callers or copy
    combat from an old asset package. Catalog references are not live DB values.
    """
    result=copy.deepcopy(content)
    profile=catalog_profile(content)
    result['settings_catalog']=profile
    monsters={m['id']:m for m in result['monsters']}
    for m in profile['monsters']:
        if m['id'] not in monsters:
            monsters[m['id']]=dict(id=m['id'],aegis=m['aegis_name'],label_ko=m.get('label_ko',m['label']),
                native_level_reference=m['level'],native_hp_reference=m['hp'],
                direct_skills_reviewed=m.get('direct_skills_reviewed',[]),effective_runtime_verified=False,
                reference_source='settings-catalog-20250402.json; skills not restated here')
    result['monsters']=list(monsters.values())
    for authored,preset in zip(result['floors'],default_preset()['floors']):
        if authored['id']!=preset['floor']:
            raise ValueError('Shared baseline floor mismatch')
        authored['waves']=[copy.deepcopy([g for g in w['groups'][:w['group_count']] if g['count']])
                           for w in preset['waves'][:preset['wave_count']]]
        if any(g['mob_id'] not in {m['id'] for m in profile['monsters']}
               for w in authored['waves'] for g in w):
            raise ValueError('Shared baseline uses unavailable catalog monster')
    result['combat_baseline']='shared-opening-20261003'
    return result


def preset_for(content):
    return content.get('wave_preset') or default_preset()


def flat_defaults(content):
    settings=[]
    for floor in preset_for(content)['floors']:
        fid=floor['floor']
        if fid not in {f['id'] for f in content['floors']}:continue
        settings.append(dict(key=key(fid),type='number',default=floor['wave_count'],min=1,max=20,label=f'Floor {fid} wave count'))
        for wave in floor['waves']:
            wid=wave['wave']
            settings.append(dict(key=f'f{fid}_w{wid}_groups',type='number',default=wave['group_count'],min=1,max=4,label=f'Floor {fid}, wave {wid}: active groups'))
            for gid,group in enumerate(wave['groups'],1):
                for field,low,high in [('mob_id',1,200000),('count',0,8)]:
                    settings.append(dict(key=key(fid,wid,gid,field),type='number',default=group[field],min=low,max=high,label=f'Floor {fid}, wave {wid}, group {gid}: {field}'))
    return settings


def default_tables(content, text):
    """Override normal-floor wave counts only; boss and unconfigured tables stay authored."""
    head,tail=text.split('function\tscript\tF_OHKC_DefaultWaves\t{',1)
    body,rest=tail.split('}',1)
    for floor in preset_for(content)['floors']:
        fid=floor['floor']
        body=re.sub(rf'(case {fid}: return )\d+(;)',rf'\g<1>{floor["wave_count"]}\2',body)
    return head+'function\tscript\tF_OHKC_DefaultWaves\t{'+body+'}'+rest


def encode_floor(content, fid):
    record=codec(content);ids=record['monster_ids']
    values={s['key']:s['default'] for s in flat_defaults(content)}
    roster=record['tag']
    for w in range(1,MAX_WAVES+1):
        roster+=str(values[f'f{fid}_w{w}_groups'])
        for g in range(1,MAX_GROUPS+1):
            value=ids.index(values[key(fid,w,g,'mob_id')])*16+values[key(fid,w,g,'count')]
            roster+=BASE64[value//64]+BASE64[value%64]
    return roster


def manifest(content):
    settings=[]
    for f in content['floors']:
        fid=f['id']
        settings.append(dict(key=key(fid),type='number',default=preset_for(content)['floors'][fid-1]['wave_count'],min=1,max=20,label=f'Floor {fid} wave count'))
        settings.append(dict(key=f'f{fid}_roster',type='string',default=encode_floor(content,fid),label=f'Floor {fid} monster roster'))
    return settings


def runtime(content, mod_name, compiled=False):
    """Reads values baked by app Apply, never updates during an encounter."""
    record=codec(content)
    floor_count=len(content['floors'])
    quote = lambda s: json.dumps(s, ensure_ascii=False)
    lines = ['function\tscript\tF_OHKC_Setting\t{',
             f'\treturn callfunc("F_ModSetting",{quote(mod_name)},getarg(0),getarg(1));', '}']
    if content.get('settings_banks'):
        lines=['function\tscript\tF_OHKC_Setting\t{','\t.@f=getarg(2,1);']
        for bank in content['settings_banks']:
            lines.append(f'\tif (.@f>={bank["start"]} && .@f<={bank["end"]}) return callfunc("F_ModSetting",{quote(bank["mod"])},getarg(0),getarg(1));')
        lines+=['\treturn getarg(1);','}']
    if compiled:
        # JSON-generated candidates never read stale native per-floor overrides.
        lines=['function\tscript\tF_OHKC_Setting\t{','\treturn getarg(1);','}']
    # Native string lookup avoids a script comparison per catalog entry. Delimiters
    # ensure a full numeric token match (e.g. 1002 cannot match 21002).
    allowed={m['id'] for m in catalog_monsters(content)}
    retired=set(record['monster_ids'])-allowed
    for name,ids in [('AllowedMob',allowed),('RetiredMob',retired)]:
        table='|'+'|'.join(map(str,sorted(ids)))+'|'
        lines += [f'function\tscript\tF_OHKC_{name}\t{{',
                  f'\treturn strpos({quote(table)},"|"+getarg(0)+"|")>=0;', '}']
    counts=''.join(str(w['group_count']) for f in preset_for(content)['floors'] for w in f['waves'])
    lines += ['function\tscript\tF_OHKC_DefaultGroupCount\t{',
              '\t.@f=getarg(0); .@w=getarg(1);',
              f'\tif (.@f<1 || .@f>{floor_count} || .@w<1 || .@w>20) return 1;',
              '\t.@offset=(.@f-1)*20+.@w-1;',
              f'\treturn atoi(substr({quote(counts)},.@offset,.@offset));','}']
    lines += ['function\tscript\tF_OHKC_Waves\t{', '\t.@f=getarg(0);',
              '\t.@default=callfunc("F_OHKC_DefaultWaves",.@f);',
              f'\tif (.@f<1 || .@f>{floor_count}) return .@default;',
              '\t.@n=callfunc("F_OHKC_Setting","f"+.@f+"_waves",.@default);',
              f'\tif (.@n<1 || .@n>{MAX_WAVES}) return .@default;', '\treturn .@n;', '}']
    lines += ['function\tscript\tF_OHKC_Group\t{',
              '\t.@f=getarg(0); .@w=getarg(1); .@g=getarg(2); .@field$=getarg(3);',
              '\t.@encoded$=getarg(4,"");',
              '\tif (.@encoded$=="") .@encoded$=callfunc("F_OHKC_Setting","f"+.@f+"_roster",callfunc("F_OHKC_DefaultEncoded",.@f));',
              '\tif (getstrlen(.@encoded$)==80) {',
              '\t\tif (.@g>2) return callfunc("F_OHKC_DefaultGroup",.@f,.@w,.@g,.@field$);',
              '\t\t.@offset=(.@w-1)*4+(.@g-1)*2;',
              '\t\tif (.@field$=="count") .@offset++;',
              '\t\t.@char$=substr(.@encoded$,.@offset,.@offset);',
              '\t\t.@digit=atoi(.@char$);',
              '\t\tif (.@char$!=""+.@digit) return -1;',
              '\t\tif (.@field$=="count") return .@digit;',
              '\t\treturn callfunc("F_OHKC_IndexMob",.@digit);',
              '\t}',
              f'\tif ((getstrlen(.@encoded$)=={len(record["tag"])+180} && substr(.@encoded$,0,{len(record["tag"])-1})=={quote(record["tag"])}) || (getstrlen(.@encoded$)=={len(record["tag"])+160} && substr(.@encoded$,0,{len(record["tag"])-1})=={quote(record["tag"].replace("g5:","g4:"))})) {{',
              f'\t\t.@new=getstrlen(.@encoded$)=={len(record["tag"])+180};',
              f'\t\t.@offset={len(record["tag"])}+(.@w-1)*(.@new ? 9 : 8)+(.@new ? 1 : 0)+(.@g-1)*2;',
              '\t\t.@value=0;',
              f'\t\t.@alphabet$={quote(BASE64)};',
              '\t\tfor (.@i=0; .@i<2; .@i++) {',
              '\t\t\t.@char$=substr(.@encoded$,.@offset+.@i,.@offset+.@i);',
              '\t\t\t.@digit=strpos(.@alphabet$,.@char$);',
              '\t\t\tif (.@digit<0) return -1;',
              '\t\t\t.@value=.@value*64+.@digit;',
              '\t\t}',
              '\t\treturn .@field$=="count" ? .@value%16 : callfunc("F_OHKC_CodecMob",.@value/16);',
              '\t}',
              '\tif (getstrlen(.@encoded$)!=163 || substr(.@encoded$,0,2)!="b3:") return -1;',
              '\tif (.@g>2) return callfunc("F_OHKC_DefaultGroup",.@f,.@w,.@g,.@field$);',
              '\t.@offset=3+((.@w-1)*2+.@g-1)*4;',
              '\t.@id=0;',
              '\tfor (.@i=0; .@i<4; .@i++) {',
              '\t\t.@char$=substr(.@encoded$,.@offset+.@i,.@offset+.@i);',
              '\t\t.@alphabet$="0123456789abcdefghijklmnopqrstuvwxyz";',
              '\t\t.@digit=strpos(.@alphabet$,.@char$);',
              '\t\tif (.@digit<0 || (.@i==3 && .@digit>8)) return -1;',
              '\t\tif (.@i<3) .@id=.@id*36+.@digit;',
              '\t}',
              '\treturn .@field$=="count" ? .@digit : .@id;', '}']
    packed_ids=''.join(f'{mid:06d}' for mid in record['monster_ids'])
    lines += ['function\tscript\tF_OHKC_CodecMob\t{',
              f'\tif (getarg(0)<0 || getarg(0)>={len(record["monster_ids"])}) return -1;',
              '\t.@offset=getarg(0)*6;',
              f'\treturn atoi(substr({quote(packed_ids)},.@offset,.@offset+5));','}']
    lines += ['function\tscript\tF_OHKC_IndexMob\t{','\tswitch(getarg(0)) {']
    lines += [f'\tcase {i}: return {mid};' for i,mid in enumerate(LEGACY_IDS)]
    lines += ['\t}','\treturn -1;','}']
    lines += ['function\tscript\tF_OHKC_DefaultEncoded\t{','\tswitch(getarg(0)) {']
    lines += [f'\tcase {f["id"]}: return {quote(encode_floor(content,f["id"]))};' for f in content['floors']]
    lines += ['\t}','\treturn "";','}']
    # 800 records, fixed seven digits per record: six-digit mob + count.
    packed_groups=''.join(f'{g["mob_id"]:06d}{g["count"]}' for f in preset_for(content)['floors'] for w in f['waves'] for g in w['groups'])
    lines += ['function\tscript\tF_OHKC_DefaultGroup\t{',
              '\t.@f=getarg(0); .@w=getarg(1); .@g=getarg(2);',
              f'\tif (.@f<1 || .@f>{floor_count} || .@w<1 || .@w>20 || .@g<1 || .@g>4) return 0;',
              '\t.@offset=((.@f-1)*80+(.@w-1)*4+.@g-1)*7;',
              f'\t.@table$={quote(packed_groups)};',
              '\tif (getarg(3)=="mob_id") return atoi(substr(.@table$,.@offset,.@offset+5));',
              '\treturn atoi(substr(.@table$,.@offset+6,.@offset+6));','}']
    lines += ['function\tscript\tF_OHKC_GroupCount\t{',
              '\t.@f=getarg(0); .@w=getarg(1);',
              '\t.@encoded$=getarg(2,"");',
              '\tif (.@encoded$=="") .@encoded$=callfunc("F_OHKC_Setting","f"+.@f+"_roster",callfunc("F_OHKC_DefaultEncoded",.@f));',
              f'\tif (getstrlen(.@encoded$)=={len(record["tag"])+180} && substr(.@encoded$,0,{len(record["tag"])-1})=={quote(record["tag"])}) {{',
              f'\t\t.@offset={len(record["tag"])}+(.@w-1)*9;',
              '\t\t.@char$=substr(.@encoded$,.@offset,.@offset);',
              '\t\t.@n=atoi(.@char$);',
              '\t\tif (.@n<1 || .@n>4 || .@char$!=""+.@n) return -1;',
              '\t\treturn .@n;', '\t}',
              f'\tif (getstrlen(.@encoded$)=={len(record["tag"])+160} && substr(.@encoded$,0,{len(record["tag"])-1})=={quote(record["tag"].replace("g5:","g4:"))}) return 4;',
              '\tif (getstrlen(.@encoded$)==80 || (getstrlen(.@encoded$)==163 && substr(.@encoded$,0,2)=="b3:")) return 2;',
              '\treturn -1;', '}']
    lines += ['function\tscript\tF_OHKC_ConfigRoster\t{',
              '\t.@f=getarg(0); .@w=getarg(1);',
              f'\tif (.@f<1 || .@f>{floor_count}) return callfunc("F_OHKC_DefaultRoster",.@f,.@w);',
              f'\tif (.@w<1 || .@w>{MAX_WAVES}) return 0;',
              '\t.@encoded$=callfunc("F_OHKC_Setting","f"+.@f+"_roster",callfunc("F_OHKC_DefaultEncoded",.@f));',
              '\t.@groups=callfunc("F_OHKC_GroupCount",.@f,.@w,.@encoded$);',
              '\t.@total=0; .@valid=(.@groups>=1 && .@groups<=4);',
              '\tfor (.@g=1; .@g<=4; .@g++) {',
              '\t\t.@id[.@g]=callfunc("F_OHKC_Group",.@f,.@w,.@g,"mob_id",.@encoded$);',
              '\t\t.@n[.@g]=callfunc("F_OHKC_Group",.@f,.@w,.@g,"count",.@encoded$);',
              f'\t\tif (.@n[.@g]<0 || .@n[.@g]>{MAX_ROOTS} || (!callfunc("F_OHKC_AllowedMob",.@id[.@g]) && !callfunc("F_OHKC_RetiredMob",.@id[.@g]))) .@valid=0;',
              '\t\tif (.@g<=.@groups) .@total+=.@n[.@g];', '\t}',
              f'\tif (.@valid && .@total>=1 && .@total<={MAX_ROOTS}) {{',
              '\t\t.@total=0;',
              '\t\tfor (.@g=1; .@g<=4; .@g++) {',
              '\t\t\tif (callfunc("F_OHKC_RetiredMob",.@id[.@g])) {',
              '\t\t\t\t.@id[.@g]=callfunc("F_OHKC_DefaultGroup",.@f,.@w,.@g,"mob_id");',
              '\t\t\t\t.@n[.@g]=0;', '\t\t\t}',
              '\t\t\tif (.@g<=.@groups) .@total+=.@n[.@g];', '\t\t}', '\t}',
              f'\tif (!.@valid || .@total<1 || .@total>{MAX_ROOTS}) {{',
              '\t\t.@groups=callfunc("F_OHKC_DefaultGroupCount",.@f,.@w);',
              '\t\tfor (.@g=1; .@g<=4; .@g++) {',
              '\t\t\t.@id[.@g]=callfunc("F_OHKC_DefaultGroup",.@f,.@w,.@g,"mob_id");',
              '\t\t\t.@n[.@g]=callfunc("F_OHKC_DefaultGroup",.@f,.@w,.@g,"count");', '\t\t}', '\t}',
              '\t$@ohkc_expected=0;', '\tfor (.@g=1; .@g<=.@groups; .@g++)',
              '\t\tfor (.@i=0; .@i<.@n[.@g]; .@i++) {',
              '\t\t\t$@ohkc_roster[$@ohkc_expected]=.@id[.@g];', '\t\t\t$@ohkc_expected++;', '\t\t}', '\treturn 1;', '}']
    lines += ['function\tscript\tF_OHKC_Roster\t{', '\treturn callfunc("F_OHKC_ConfigRoster",getarg(0),getarg(1));', '}']
    # Preview uses the exact same validated roster as spawning, then restores scratch state.
    lines += ['function\tscript\tF_OHKC_WaveInfo\t{',
              f'\tif (getarg(0)>{floor_count}) return callfunc("F_OHKC_DefaultWaveInfo",getarg(0),getarg(1));',
              '\t.@old=$@ohkc_expected;', '\tcopyarray .@oldids[0],$@ohkc_roster[0],8;',
              '\tcallfunc "F_OHKC_ConfigRoster",getarg(0),getarg(1);',
              '\t.@s$=getarg(1)+"웨이브: ";',
              '\tfor (.@i=0; .@i<$@ohkc_expected; .@i++) {',
              '\t\tif (.@i>0) .@s$+=", ";',
              '\t\t.@s$+=callfunc("F_OHKC_MobLabel",$@ohkc_roster[.@i]);', '\t}',
              '\tcopyarray $@ohkc_roster[0],.@oldids[0],8;', '\t$@ohkc_expected=.@old;', '\treturn .@s$;', '}']
    lines += ['function\tscript\tF_OHKC_MobLabel\t{', '\tswitch(getarg(0)) {']
    labels={m['id']:m['label_ko'] for m in content['monsters']}
    labels.update({m['id']:m['label'] for m in catalog_monsters(content)})
    lines += [f'\tcase {mid}: return {quote(label)};' for mid,label in labels.items()]
    lines += ['\t}', '\treturn "?";', '}']
    result='\n'.join(lines)
    if content.get('settings_banks'):
        result=result.replace('"f"+.@f+"_waves",.@default)', '"f"+.@f+"_waves",.@default,.@f)')
        result=result.replace('callfunc("F_OHKC_DefaultEncoded",.@f));', 'callfunc("F_OHKC_DefaultEncoded",.@f),.@f);')
        # Bound literal size independently of the eventual 200-floor prefix.
        # Each group table is only one floor (560 ASCII bytes), each count table 20.
        for name,counts_only in [('DefaultGroup',False),('DefaultGroupCount',True)]:
            chunk=[f'function\tscript\tF_OHKC_{name}\t{{', '\t.@f=getarg(0); .@w=getarg(1);',
                   '\tif (.@w<1 || .@w>20) return 0;']
            if not counts_only:
                chunk += ['\t.@g=getarg(2);', '\tif (.@g<1 || .@g>4) return 0;']
            chunk += ['\tswitch(.@f) {']
            for f in preset_for(content)['floors']:
                value=(''.join(str(w['group_count']) for w in f['waves']) if counts_only else
                       ''.join(f'{g["mob_id"]:06d}{g["count"]}' for w in f['waves'] for g in w['groups']))
                chunk.append(f'\tcase {f["floor"]}: .@table$={quote(value)}; break;')
            chunk += ['\tdefault: return 0;', '\t}']
            if counts_only:
                chunk += ['\treturn atoi(substr(.@table$,.@w-1,.@w-1));','}']
            else:
                chunk += ['\t.@offset=((.@w-1)*4+.@g-1)*7;',
                          '\tif (getarg(3)=="mob_id") return atoi(substr(.@table$,.@offset,.@offset+5));',
                          '\treturn atoi(substr(.@table$,.@offset+6,.@offset+6));','}']
            start=result.index(f'function\tscript\tF_OHKC_{name}\t{{')
            end=result.index('\n}',start)+2
            result=result[:start]+'\n'.join(chunk)+result[end:]
    return result


def attach(folder, content):
    """Attach sandbox page and declarations to an uninstalled candidate."""
    meta_path = folder / 'mod.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.update(settings=manifest(content), settingsPage='settings/index.html')
    meta['requires']['app'] = '>=1.3.4'
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    target = folder / 'settings'
    shutil.copytree(Path(__file__).resolve().parents[1] / 'settings', target, dirs_exist_ok=True)
    monsters={m['id']:m for m in content['monsters']}
    (target / 'defaults.json').write_text(json.dumps(dict(schema_version=3, max_groups=MAX_GROUPS, codec_tag=codec(content)["tag"], codec_monster_ids=codec(content)["monster_ids"],
        monsters=catalog_monsters(content), legacy_monster_ids=LEGACY_IDS,
        client_profile=catalog_profile(content).get('client_profile'),
        excluded=catalog_profile(content).get('excluded',[]),
        floor_start=content['floors'][0]['id'],floor_count=len(content['floors']),
        floors=copy.deepcopy(content['floors']), settings=flat_defaults(content)), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def adapt_engine(text):
    """Enable audited transforms only for explicit catalog candidates."""
    changes = [('.@u[UMOB_CLASS]==$@ohkc_class[.@j]', 'callfunc("F_OHKC_RootClass",$@ohkc_class[.@j],.@u[UMOB_CLASS])'), ('.@u[UMOB_CLASS]!=$@ohkc_class[.@j]', '!callfunc("F_OHKC_RootClass",$@ohkc_class[.@j],.@u[UMOB_CLASS])'), ('.@u[UMOB_CLASS]!=$@ohkc_class[.@i]', '!callfunc("F_OHKC_RootClass",$@ohkc_class[.@i],.@u[UMOB_CLASS])'), ('.@u[UMOB_CLASS]!=$@ohkc_class[.@idx]', '!callfunc("F_OHKC_RootClass",$@ohkc_class[.@idx],.@u[UMOB_CLASS])'), ('killedrid==$@ohkc_class[.@i]', 'callfunc("F_OHKC_RootClass",$@ohkc_class[.@i],killedrid)'), ('callfunc("F_OHKC_Child",$@ohkc_enc,.@u[UMOB_CLASS])', 'callfunc("F_OHKC_Child",$@ohkc_enc,.@u[UMOB_CLASS],$@ohkc_class[.@j])')]
    for old,new in changes: text=text.replace(old,new)
    return text
