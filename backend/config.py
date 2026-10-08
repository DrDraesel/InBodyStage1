"""Load literal .env settings without evaluating shell expressions or logging secrets."""
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path=None, environ=None):
    target = os.environ if environ is None else environ
    path = Path(path or ROOT / '.env')
    if not path.exists():
        return
    if path.stat().st_size > 65536:
        raise ValueError('.env exceeds size limit')
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', line)
        if not match:
            raise ValueError(f'Invalid .env syntax on line {number}')
        value = match[2]
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Unclosed .env quote on line {number}')
            value = value[1:-1]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        target.setdefault(match[1], value)


def readiness(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get('AI_ENABLED', 'false').lower() == 'true'
    base = env.get('AI_BASE_URL', 'https://api.openai.com/v1')
    local = base.startswith(('http://127.0.0.1:', 'http://localhost:'))
    missing = [key for key in ('AI_MODEL',) if not env.get(key)]
    if not local and not env.get('AI_API_KEY'):
        missing.append('AI_API_KEY')
    return {'mode': 'synthetic-only', 'ocr': {'available': bool(shutil.which('tesseract'))},
            'ai': {'enabled': enabled, 'configured': enabled and not missing,
                   'missing_settings': missing if enabled else [], 'live_verified': False,
                   'fallback': 'deterministic recommendation drafts'},
            'authentication': {'enabled': bool(env.get('INBODY_CLINICIAN_TOKEN') and env.get('INBODY_OPERATOR_TOKEN'))},
            'inbody_api': {'status': 'deferred_pending_credentials_and_validated_mapping'},
            'local_inbox': {'enabled': True}, 'deployment': 'local_backend; separate synthetic static preview'}
