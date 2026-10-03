"""Public fork paths; proprietary build products must stay in ignored directories."""
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
BUILD = REPOSITORY / 'build'
LOCAL = REPOSITORY / 'local'


def require_output(path, roots=(BUILD, LOCAL)):
    path = Path(path).resolve()
    if not any(path != root.resolve() and path.is_relative_to(root.resolve()) for root in roots):
        raise ValueError('Choose a nested output inside repository build/ or local/')
    return path


def sanitize(value):
    """Retain evidence hashes/identities without personal filesystem locations."""
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        normalized = value.replace(chr(92), '/')
        if (len(normalized) > 2 and normalized[1] == ':' and normalized[2] == '/') or normalized.startswith('/') or normalized.startswith('tower-workshop/local/'):
            return 'local-source/' + normalized.rsplit('/', 1)[-1]
    return value
