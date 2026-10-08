"""Queue LookinBody exports locally for source review, without a cloud API.

Run from the repository root: python -m scripts.local_export_bridge --help
This watches files; it does not implement the InBody hardware protocol or bind patients.
"""
import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from adapters.inbody.documents import MAX_BYTES, extract

EXTENSIONS = {'.csv', '.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.xls', '.xlsx'}


def collect(inbox, queue, settle_seconds=3):
    inbox, queue = Path(inbox).resolve(), Path(queue).resolve()
    if not inbox.is_dir():
        raise ValueError('Export folder does not exist; configure it in LookinBody first.')
    if inbox == queue or inbox in queue.parents or queue in inbox.parents:
        raise ValueError('Export and review folders must be separate, non-nested folders.')
    queue.mkdir(parents=True, exist_ok=True, mode=0o700)
    collected = []
    for source in sorted(inbox.iterdir()):
        if source.is_symlink() or not source.is_file() or source.suffix.lower() not in EXTENSIONS:
            continue
        before = source.stat()
        if time.time() - before.st_mtime < settle_seconds or before.st_size > MAX_BYTES:
            continue
        with source.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        after = source.stat()
        if len(data) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue
        digest = hashlib.sha256(data).hexdigest()
        destination = queue / digest
        if destination.exists():
            continue
        suffix = source.suffix.lower()
        evidence = {'measurements': [], 'warnings': []}
        if suffix in {'.png', '.jpg', '.jpeg', '.pdf'}:
            try:
                evidence = extract(data, 'pdf' if suffix == '.pdf' else 'image', allow_empty=True)
            except ValueError as error:
                evidence['warnings'].append(str(error))
        else:
            evidence['warnings'].append('Original export retained. CSV/Excel/BMP field mapping is not enabled; review or export a PNG/JPEG/PDF.')
        record = {'bridge_version': 'local-export-v1', 'status': 'awaiting_source_review',
                  'patient_id': None, 'encounter_id': None, 'review_required': True,
                  'hardware_connection_verified': False, 'source_sha256': digest,
                  'source_name': source.name, 'original_file': 'original' + suffix,
                  'extraction': evidence}
        # Publish complete packages atomically. Do not alter the vendor's export folder.
        with tempfile.TemporaryDirectory(prefix='.pending-', dir=queue) as temporary:
            package = Path(temporary) / 'package'
            package.mkdir(mode=0o700)
            original = package / record['original_file']
            original.write_bytes(data)
            original.chmod(0o600)
            manifest = package / 'review.json'
            manifest.write_text(json.dumps(record, indent=2), encoding='utf-8')
            manifest.chmod(0o600)
            os.rename(package, destination)
        collected.append(digest)
    return collected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', required=True, help='LookinBody automatic export folder')
    parser.add_argument('--queue', required=True, help='Separate local review folder')
    parser.add_argument('--watch', action='store_true', help='Continue checking for new exports')
    args = parser.parse_args()
    try:
        while True:
            found = collect(args.inbox, args.queue)
            print(f'Queued {len(found)} new source file(s). No patient records created.', flush=True)
            if not args.watch:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
