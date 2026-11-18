"""Copy WordPress upload files into ResRef media storage (local disk or S3/R2).

Files keep their WordPress path under ``wp-content/uploads/`` so old links can
be redirected one-to-one. A file is never overwritten or deleted: if a file
with the same name but different bytes is already stored, it is reported as a
conflict (or, with --overwrite, stored under a new name next to it).
"""
import hashlib
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from redirects.targets import WP_UPLOADS_STORAGE_PREFIX

# Same delivery policy as resref/urls.py: only these types are ever served.
COPYABLE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'avif', 'pdf', 'doc', 'docx'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_FILE_BYTES = 50 * 1024 * 1024
DOWNLOAD_TIMEOUT = 30


class MediaSourceError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def relative_upload_path(attached_file='', url=''):
    """``2024/05/photo.jpg`` from ``_wp_attached_file`` or an uploads URL; '' if unsafe."""
    candidate = (attached_file or '').strip()
    if not candidate and url:
        path = unquote(urlsplit(url).path)
        if '/wp-content/uploads/' in path:
            candidate = path.split('/wp-content/uploads/', 1)[1]
    candidate = candidate.replace('\\', '/').lstrip('/')
    parts = PurePosixPath(candidate).parts
    if not candidate or any(part in {'', '.', '..'} for part in parts) or ':' in candidate:
        return ''
    return '/'.join(parts)


def extension(name):
    return PurePosixPath(name).suffix.lower().lstrip('.')


class MediaSource:
    """Reads upload files from a local copy of wp-content/uploads or a base URL."""

    def __init__(self, uploads_dir=None, base_url=None):
        self.uploads_dir = Path(uploads_dir).resolve() if uploads_dir else None
        self.base_url = (base_url or '').rstrip('/') + '/' if base_url else ''
        if self.uploads_dir and not self.uploads_dir.is_dir():
            raise MediaSourceError(f'Uploads folder not found: {self.uploads_dir}')
        if self.base_url and urlsplit(self.base_url).scheme not in {'http', 'https'}:
            raise MediaSourceError('--media-base-url must start with http:// or https://')

    @property
    def enabled(self):
        return bool(self.uploads_dir or self.base_url)

    def read(self, relative):
        if self.uploads_dir:
            path = (self.uploads_dir / relative).resolve()
            if self.uploads_dir not in path.parents:
                raise MediaSourceError('Path escapes the uploads folder.')
            if path.is_file():
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise MediaSourceError('File is larger than 50 MB.')
                return path.read_bytes()
            if not self.base_url:
                raise MediaSourceError('File not found in the uploads folder.')
        url = self.base_url + quote(relative)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ResRef-WordPress-Migration'}), timeout=DOWNLOAD_TIMEOUT) as response:  # noqa: S310 - scheme checked above
                data = response.read(MAX_FILE_BYTES + 1)
        except (urllib.error.URLError, OSError) as exc:
            raise MediaSourceError(f'Download failed: {exc}') from exc
        if len(data) > MAX_FILE_BYTES:
            raise MediaSourceError('File is larger than 50 MB.')
        return data

    def walk(self):
        """Every copyable file in the uploads folder (relative POSIX paths)."""
        if not self.uploads_dir:
            return [], {}
        files, skipped = [], {}
        for path in sorted(self.uploads_dir.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(self.uploads_dir).as_posix()
            ext = extension(relative)
            if ext in COPYABLE_EXTENSIONS:
                files.append(relative)
            else:
                skipped[ext or '(none)'] = skipped.get(ext or '(none)', 0) + 1
        return files, skipped


def store_file(relative, data, *, dry_run, overwrite):
    """Returns (outcome, storage_name, message). Outcomes: copied, exists, conflict."""
    name = WP_UPLOADS_STORAGE_PREFIX + relative
    checksum = sha256(data)
    if default_storage.exists(name):
        with default_storage.open(name, 'rb') as handle:
            existing = sha256(handle.read())
        if existing == checksum:
            return 'exists', name, 'identical file already stored'
        if not overwrite:
            return 'conflict', name, 'a different file with this name is already stored (kept; use --overwrite to store the new one beside it)'
        if dry_run:
            return 'copied', name, 'would store the new version under a new name'
        saved = default_storage.save(name, ContentFile(data))
        return 'copied', saved, 'stored beside the existing file'
    if dry_run:
        return 'copied', name, 'would copy'
    saved = default_storage.save(name, ContentFile(data))
    return 'copied', saved, 'copied'
