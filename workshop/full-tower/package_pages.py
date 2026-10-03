"""Stage an explicit static-only allowlist for GitHub Pages. No publish or installs."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / 'editor'
FILES = ('index.html', 'app.js', 'i18n.js', 'browser-store.js', 'style.css',
         'monster-names.ko.json', 'monster-names.ko.sources.json', 'sample-project.json', 'LOCALIZATION.md')


def package(output):
    output = Path(output).resolve()
    root = SOURCE.parents[2] / 'build'
    if output == root.resolve() or not output.is_relative_to(root.resolve()) or output.exists():
        raise ValueError('Use a new output directory inside repository build/')
    for name in FILES:
        if not (SOURCE / name).is_file():
            raise ValueError('Missing static file: ' + name)
    page = (SOURCE / 'index.html').read_text(encoding='utf-8')
    if '<html lang="en">' not in page:
        raise ValueError('Expected English HTML root before static packaging')
    output.mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(SOURCE / name, output / name)
    # Explicit static default also makes previews work on localhost.
    page = page.replace('<html lang="en">', '<html lang="en" data-mode="file">')
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    (output / 'README.md').write_text('# Midgard Ascent JSON editor\n\nEnglish and Korean editor; select a language without losing staged edits. '
        'Open a project locally or load the example. Download edited JSON. Files stay in your browser; '
        'there is no upload endpoint, analytics or runtime dependency download.\n\n'
        'This website does not compile or install the game mod. Use the local workshop compiler for that step. '
        'Downloaded JSON does not automatically overwrite its original file.\n', encoding='utf-8')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}
    (output.parent / (output.name + '-manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    print(package(parser.parse_args().output))
