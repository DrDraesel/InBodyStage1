"""Read content-addressed local bridge packages through an authenticated workspace."""
import hashlib
import json
import os
import re
from pathlib import Path
from backend.validation import Invalid
from adapters.inbody.documents import MAX_BYTES

KINDS = {'.pdf': 'pdf', '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.csv': 'csv', '.xlsx': 'xlsx', '.xls': 'xls'}
MEDIA = {'pdf': 'application/pdf', 'image': 'image/jpeg', 'csv': 'text/csv',
         'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xls': 'application/vnd.ms-excel'}


def root():
    return Path(os.getenv('INBODY_INBOX_DIR', 'runtime/inbox')).resolve()


def package(digest):
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise Invalid('Invalid inbox source hash')
    directory = root() / digest
    if directory.is_symlink() or not directory.is_dir():
        raise Invalid('Inbox package not found')
    manifest = directory / 'review.json'
    if manifest.is_symlink() or manifest.stat().st_size > 2_000_000:
        raise Invalid('Invalid inbox manifest')
    record = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(record,dict) or not isinstance(record.get('source_name'),str):
        raise Invalid('Invalid inbox record')
    name = record.get('original_file', '')
    kind = KINDS.get(Path(name).suffix.lower())
    if not kind or name != 'original' + Path(name).suffix.lower() or record.get('source_sha256') != digest:
        raise Invalid('Unsupported or invalid inbox source')
    source = directory / name
    if source.is_symlink() or source.stat().st_size > MAX_BYTES:
        raise Invalid('Invalid inbox source')
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise Invalid('Inbox source integrity mismatch')
    return record, data, kind


def listing():
    if not root().exists():
        return []
    entries = []
    for directory in sorted(root().iterdir()):
        if not re.fullmatch(r'[a-f0-9]{64}', directory.name):
            continue
        try:
            record, data, kind = package(directory.name)
        except (Invalid, OSError, ValueError, TypeError):
            continue
        entries.append({'sha256': directory.name, 'source_name': record['source_name'], 'kind': kind,
                        'status': 'awaiting_source_review', 'size_bytes': len(data)})
        if len(entries) >= 100:
            break
    return entries
