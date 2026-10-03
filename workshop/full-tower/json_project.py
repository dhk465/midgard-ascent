"""Create and compile an editable JSON project. Never writes to an installation."""
import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSHOP = HERE.parent
sys.path.insert(0, str(WORKSHOP / 'chapter-one/tools'))
import chapterkit
from public_paths import BUILD, require_output, sanitize
import wave_settings


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(sanitize(value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(source):
    source = Path(source).resolve()
    report = load(source / 'BUILD-REPORT.json')
    for name, digest in report['files_sha256'].items():
        file = (source / name).resolve()
        if not file.is_relative_to(source) or not file.is_file() or sha(file) != digest:
            raise ValueError('Source manifest mismatch: ' + name)
    return source


def seed(source, output):
    source = verified(source)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Project exists; refusing overwrite')
    require_output(output)
    content = load(source / 'FULL-TOWER-CONTENT.json')
    project = dict(project_schema=1, source_candidate='local-source/' + source.name,
                   wave_preset=copy.deepcopy(content['wave_preset']),
                   monsters=wave_settings.catalog_monsters(content),
                   provenance='Packaged defaults; not a readback of live app settings')
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, project)
    return output


def build(project_path, source, site, output):
    # Same validator as the editor, before any candidate is created.
    from editor.server import validate_project
    project_bytes = Path(project_path).read_bytes()
    project = json.loads(project_bytes.decode('utf-8-sig'))
    validate_project(project)
    source = verified(source)
    output = Path(output).resolve()
    if output == BUILD.resolve() or not output.is_relative_to(BUILD.resolve()) or output.exists() or output.with_suffix('.zip').exists():
        raise ValueError('Output must be a new path inside repository build/')
    if source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Source/output overlap')
    base = load(source / 'NATIVE-CONTENT.json')
    full = load(source / 'FULL-TOWER-CONTENT.json')
    preset = project.get('wave_preset', project)
    if [f['floor'] for f in preset['floors']] != [f['id'] for f in full['floors']]:
        raise ValueError('Project must cover exactly the authored floors in the candidate')
    allowed = {m['id'] for m in wave_settings.catalog_monsters(full)}
    if any(g['mob_id'] not in allowed for f in preset['floors'] for w in f['waves'] for g in w['groups']):
        raise ValueError('Unsupported monster in project, including hidden groups')
    config = load(site)
    text = chapterkit.render(base, config, installation_candidate=True,
        settings_mod_name='midgard-ascent',
        extension=load(HERE / 'content/floors11-20.json'), compiled_preset=preset)
    if 'F_ModSetting' in text:
        raise ValueError('Compiled candidate still reads native settings')
    # Copy only after validating every input and rendering successfully.
    shutil.copytree(source, output, ignore=shutil.ignore_patterns('settings', 'BUILD-REPORT.json'))
    meta = load(output / 'mod.json')
    meta.update(name='midgard-ascent', version='1.1.0', description='JSON-authored tower; single mod, external editor. Game tests pending.')
    meta.pop('settings', None)
    meta.pop('settingsPage', None)
    meta.get('requires', {}).pop('mods', None)
    write(output / 'mod.json', meta)
    (output / 'npc/chapter.txt').write_bytes(text.encode(config['npc_encoding']))
    write(output / 'tower-project.json', project)
    full['wave_preset'] = copy.deepcopy(preset)
    full.pop('settings_banks', None)
    for floor, configured in zip(full['floors'], preset['floors']):
        floor['waves'] = [[copy.deepcopy(g) for g in w['groups'][:w['group_count']] if g['count']]
                         for w in configured['waves'][:configured['wave_count']]]
    write(output / 'FULL-TOWER-CONTENT.json', full)
    write(output / 'RESOLVED-COMBAT.json', full)
    (output / 'README.ko.md').write_text('JSON 통합 설정 후보 1.1.0. 설정은 외부 편집기에서 수정 후 새 후보로 빌드합니다.\n'
        '이 ZIP은 단일 모드입니다. 이전 설정 동반 모듈은 사용하지 않습니다.\n'
        '기존 앱 저장 키는 읽지 않습니다. 설치 전 현재 사용자 설정을 프로젝트에 가져왔는지 확인해야 합니다.\n'
        '설치·Apply·게임 검증은 실행하지 않았습니다.\n', encoding='utf-8')
    assets = [p for p in (source / 'data').rglob('*') if p.is_file()]
    if not all(sha(p) == sha(output / p.relative_to(source)) for p in assets):
        raise ValueError('Asset preservation failed')
    report = dict(status='JSON_SINGLE_MOD_GAME_NOT_RUN', source_candidate='local-source/' + source.name,
        project_sha256=hashlib.sha256(project_bytes).hexdigest(), floors=len(preset['floors']),
        normal_waves=sum(f['wave_count'] for f in preset['floors']),
        preserved_asset_count=len(assets), native_engine_tested=False,
        files_sha256={p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    write(output / 'BUILD-REPORT.json', report)
    chapterkit.archive(output, output.with_suffix('.zip'))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--source', type=Path, required=True)
    init.add_argument('--output', type=Path, required=True)
    compile_parser = sub.add_parser('build')
    for name in ('project', 'source', 'site', 'output'):
        compile_parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(seed(args.source, args.output) if args.command == 'init'
          else build(args.project, args.source, args.site, args.output))


if __name__ == '__main__':
    main()
