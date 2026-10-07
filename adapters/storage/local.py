import hashlib
import os
from pathlib import Path

class LocalSourceStorage:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)

    def put(self, data):
        digest = hashlib.sha256(data).hexdigest()
        path = self.directory / digest
        try:
            with path.open('xb') as stream:
                stream.write(data)
            os.chmod(path, 0o600)
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Source integrity mismatch')
        return digest

    def get(self, digest):
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid source hash')
        data = (self.directory/digest).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Source integrity mismatch')
        return data

class GoogleDriveStorage:
    """Future governed export adapter; never the database."""
    def put(self, data):
        raise NotImplementedError('Google Drive export disabled in Stage 1')
