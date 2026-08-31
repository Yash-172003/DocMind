"""Local disk storage for uploaded document bytes.

An UploadFile's underlying stream is tied to the request — it's gone
by the time a background task runs. So the request handler must save
the bytes to disk synchronously before returning, and the background
task reads them back by document ID. Each document gets its own
subdirectory (keyed by UUID) so two uploads named "invoice.pdf" never
collide.

Local disk is a Phase 0/1 shortcut, not a production design — Phase 4
replaces this with object storage (Azure Blob / S3-compatible) once
the app runs on more than one machine and a local filesystem can no
longer be assumed shared between the API and its workers.
"""

import uuid
from pathlib import Path

from docmind.core.config import settings


def _document_dir(document_id: uuid.UUID) -> Path:
    return Path(settings.upload_dir) / str(document_id)


def save_upload(document_id: uuid.UUID, filename: str, content: bytes) -> Path:
    """Write uploaded bytes to disk and return the path they were saved to."""
    directory = _document_dir(document_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(content)
    return path


def read_upload(document_id: uuid.UUID, filename: str) -> bytes:
    """Read back previously saved upload bytes for a document."""
    return (_document_dir(document_id) / filename).read_bytes()


def delete_upload(document_id: uuid.UUID) -> None:
    """Remove a document's entire upload directory, if it exists."""
    directory = _document_dir(document_id)
    if not directory.exists():
        return
    for child in directory.iterdir():
        child.unlink()
    directory.rmdir()
