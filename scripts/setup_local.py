"""Create missing local configuration and report readiness without printing secrets."""
import argparse
import json
import secrets
from pathlib import Path
from backend.config import ROOT, load_env, readiness


def initialize(path):
    path = Path(path)
    if path.exists():
        return False
    content = (ROOT / '.env.example').read_text()
    for key in ('INBODY_CLINICIAN_TOKEN', 'INBODY_OPERATOR_TOKEN'):
        content = content.replace(key + '=\n', key + '=' + secrets.token_urlsafe(40) + '\n')
    with path.open('x', encoding='utf-8') as stream:
        stream.write(content)
    path.chmod(0o600)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check only; do not create .env')
    args = parser.parse_args()
    created = False if args.check else initialize(ROOT / '.env')
    load_env()
    print(json.dumps({'config_created': created, 'readiness': readiness()}, indent=2))
    print('Local configuration is .env. Existing settings were preserved. Start with python -m backend.server --seed.')


if __name__ == '__main__':
    main()
