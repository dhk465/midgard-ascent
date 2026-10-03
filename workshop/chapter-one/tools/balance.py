"""Read-only encounter diagnostics from authored references, never runtime balance."""
from __future__ import annotations
import json
from pathlib import Path


def validate_main_level_envelope(content):
    """Keep the current beginner roster envelope while theme work is pending.

    This is a source guard, not a recommended player level or combat model.
    Optional trials intentionally have a separate difficulty envelope.
    """
    monsters={m['id']:m for m in content['monsters']}
    for floor in content['floors']:
        for wave in floor['waves']:
            for group in wave:
                level=monsters[group['mob_id']].get('native_level_reference')
                forest_exception=(group['mob_id']==1077 and level==26
                                  and monsters[group['mob_id']].get('native_hp_reference')==379)
                if type(level) is not int or not (1<=level<=18 or forest_exception):
                    raise ValueError('Main floor native level exceeds reviewed Lv1-18 envelope or is unknown; audit balance before theme substitution')


def analyze(content):
    monsters = {m['id']: m for m in content['monsters']}
    maps = {m['id']: m for m in content['maps']}
    rows = []
    for encounter in content['floors'] + content['trials']:
        waves = []
        for wave in encounter['waves']:
            hp_values = [monsters[g['mob_id']].get('native_hp_reference') for g in wave]
            known_hp = all(type(hp) is int and hp > 0 for hp in hp_values)
            levels = [monsters[g['mob_id']].get('native_level_reference') for g in wave]
            skills = sorted({s for g in wave for s in monsters[g['mob_id']]['direct_skills_reviewed']})
            waves.append({
                'count': sum(g['count'] for g in wave),
                'species': [monsters[g['mob_id']]['label_ko'] for g in wave],
                'reference_hp_sum': sum(hp * g['count'] for hp, g in zip(hp_values, wave)) if known_hp else None,
                'reference_level_range': [min(levels), max(levels)] if all(type(v) is int for v in levels) else None,
                'direct_skills_reviewed': skills,
            })
        timing = content['timing_ms']
        # Configured deadlines only: timer ticks, combat, loot/dialog and native
        # slave settling can add time. Never label this measured clear time.
        normal = encounter in content['floors']
        rows.append({
            'id': encounter['id'], 'name': encounter['name_ko'],
            'kind': 'main' if normal else 'optional_trial',
            'theme': maps[encounter['map_id']]['theme_ko'], 'waves': waves,
            'root_count': sum(w['count'] for w in waves),
            'reference_hp_sum': sum(w['reference_hp_sum'] for w in waves) if all(w['reference_hp_sum'] is not None for w in waves) else None,
            'configured_delay_ms': timing['floor_transition'] + timing['first_wave' if normal else 'boss_ready'] + (len(waves)-1)*max(timing['between_waves'], timing['clear_notice']) + timing['clear_notice'],
            'effective_runtime_verified': all(monsters[g['mob_id']].get('effective_runtime_verified') is True for wave in encounter['waves'] for g in wave),
        })
    return {
        'priority': 'LEVEL_AND_BALANCE_BEFORE_VISUAL_THEME',
        'main_native_level_envelope': [1,18],
        'main_native_level_exceptions': {1077:26} if any(g['mob_id']==1077 for f in content['floors'] for w in f['waves'] for g in w) else {},
        'target_player_level_range': None,
        'combat_balance_status': 'TARGET_PLAYER_AND_RUNTIME_MEASUREMENTS_PENDING',
        'evidence_scope': 'AUTHORED_SOURCE_REFERENCES_NOT_RUNTIME_OR_PLAYTEST',
        'limitations': ['HP totals omit defense, damage reduction, healing and summons.',
                        'Monster levels are not recommended player levels.',
                        'EXP, job EXP, drops, active rates and clear times are unmeasured.'],
        'main_root_count': sum(r['root_count'] for r in rows if r['kind'] == 'main'),
        'main_configured_delay_ms': sum(r['configured_delay_ms'] for r in rows if r['kind'] == 'main'),
        'encounters': rows,
    }


if __name__ == '__main__':
    content = json.loads((Path(__file__).resolve().parents[1]/'content/chapter.json').read_text(encoding='utf-8-sig'))
    from wave_settings import combat_content
    print(json.dumps(analyze(combat_content(content)), ensure_ascii=False, indent=2))
