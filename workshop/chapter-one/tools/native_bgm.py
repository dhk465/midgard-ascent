"""Preserve a local native music table and append validated tower mappings."""
import hashlib
import re
from pathlib import Path


def prepare(baseline, bgm_dir, profiles):
    baseline, bgm_dir = Path(baseline).resolve(), Path(bgm_dir).resolve()
    raw = baseline.read_bytes()
    mappings, duplicates = {}, set()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(b'//'):
            continue
        match = re.fullmatch(rb'([A-Za-z0-9_@-]+\.rsw)#([^#]+)#', line)
        if not match:
            raise ValueError('Malformed native BGM table record')
        key = match[1].decode('ascii').lower()
        if key in mappings:
            duplicates.add(key)
        mappings[key] = match[2]
    if [p['id'] for p in profiles] != ['ohkt%02d' % i for i in range(1, 11)]:
        raise ValueError('BGM requires all ten ordered tower profiles')
    additions, provenance, tracks = [], [], {}
    for profile in profiles:
        key = profile['id'] + '.rsw'
        source = profile['source'] + '.rsw'
        if key in mappings:
            raise ValueError('Tower BGM key already exists: ' + key)
        if source not in mappings:
            raise ValueError('Missing native BGM source: ' + source)
        if source in duplicates:
            raise ValueError('Duplicate native BGM source key: ' + source)
        # Native renderer extracts a basename from the optional bgm prefix.
        match = re.fullmatch(rb'(?:bgm[\\/]+)?([0-9]+\.mp3)', mappings[source], re.I)
        if not match:
            raise ValueError('Unsupported native BGM track: ' + source)
        track = match[1].decode('ascii')
        path = bgm_dir / track
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing or empty native BGM track: ' + track)
        tracks[track] = hashlib.sha256(path.read_bytes()).hexdigest()
        additions.append((key + '#' + track + '#\r\n').encode('ascii'))
        provenance.append({'map': profile['id'], 'source_map': profile['source'], 'track': track})
    # Keep even non-ASCII comments and original newline bytes untouched.
    separator = b'' if not raw or raw.endswith(b'\n') else b'\r\n'
    output = raw + separator + b''.join(additions)
    report = {'baseline_path': str(baseline), 'baseline_bytes': len(raw),
              'baseline_sha256': hashlib.sha256(raw).hexdigest(),
              'baseline_keys': len(mappings), 'baseline_duplicate_keys': sorted(duplicates),
              'bgm_directory': str(bgm_dir),
              'track_sha256': tracks, 'mappings': provenance,
              'table_sha256': hashlib.sha256(output).hexdigest(),
              'runtime_tested': False}
    return output, report
