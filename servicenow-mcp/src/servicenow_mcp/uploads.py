"""
Files a user attaches to a chat message.

The browser posts a file to /uploads; it lands in uploads/ next to the repo's
datasets/ and exports/, and the id that comes back is what the chat request
refers to. When the message runs, chat_agent turns each attachment into a
content block: an image becomes something Claude can actually look at, and a
text file is inlined so it can be read.

Only those two kinds are accepted. A .xlsx or .pdf would have to be parsed
before Claude could use it, and storing one it cannot open would be a button
that quietly does nothing - so they are refused at the door with a reason.
"""

from __future__ import annotations

import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
UPLOADS = ROOT / "uploads"

# Claude accepts these image types directly.
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Text this can inline into the prompt as-is.
TEXT_TYPES = {
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".log": "text/plain",
    ".xml": "application/xml",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".html": "text/html",
    ".js": "text/javascript",
    ".py": "text/x-python",
    ".sql": "text/plain",
}

MAX_BYTES = 8 * 1024 * 1024        # per file
MAX_TEXT_CHARS = 40_000            # inlined into the prompt; the rest is noted
MAX_ATTACHMENTS = 5


class UploadError(Exception):
    """Rejected before anything was written."""


def kind_of(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_TYPES:
        return "image"
    if suffix in TEXT_TYPES:
        return "text"
    return "unsupported"


def media_type_of(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return (
        IMAGE_TYPES.get(suffix)
        or TEXT_TYPES.get(suffix)
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )


def safe_name(filename: str) -> str:
    """The basename only, with anything awkward flattened."""
    base = Path(filename or "file").name.strip() or "file"
    keep = [c if (c.isalnum() or c in "._- ()") else "_" for c in base]
    return "".join(keep)[:120]


def save(filename: str, data: bytes) -> Dict[str, Any]:
    """Store one uploaded file and return its record."""
    name = safe_name(filename)
    kind = kind_of(name)
    if kind == "unsupported":
        raise UploadError(
            f"{name} cannot be used here. Attach an image (PNG, JPEG, GIF, WebP) or a "
            "text file (CSV, TXT, MD, JSON, XML, YAML, HTML). A PDF or Excel file would "
            "have to be converted first - export it as CSV and attach that."
        )
    if not data:
        raise UploadError(f"{name} is empty.")
    if len(data) > MAX_BYTES:
        raise UploadError(
            f"{name} is {len(data) / 1024 / 1024:.1f} MB; the limit is "
            f"{MAX_BYTES // 1024 // 1024} MB."
        )

    upload_id = uuid.uuid4().hex
    directory = UPLOADS / upload_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(data)

    record = {
        "id": upload_id,
        "name": name,
        "kind": kind,
        "media_type": media_type_of(name),
        "bytes": len(data),
        "uploaded_at": int(time.time()),
    }
    (directory / "meta.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def load(upload_id: str) -> Optional[Dict[str, Any]]:
    """The record for one upload, or None. Ids are hex, so no path games."""
    if not upload_id or not all(c in "0123456789abcdef" for c in upload_id):
        return None
    meta = UPLOADS / upload_id / "meta.json"
    if not meta.is_file():
        return None
    try:
        record = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    path = UPLOADS / upload_id / record.get("name", "")
    if not path.is_file():
        return None
    record["path"] = str(path)
    return record


def read(upload_id: str) -> Optional[bytes]:
    record = load(upload_id)
    return Path(record["path"]).read_bytes() if record else None


def resolve(ids: List[str]) -> List[Dict[str, Any]]:
    """Records for the given ids, skipping any that no longer exist."""
    found = []
    for upload_id in (ids or [])[:MAX_ATTACHMENTS]:
        record = load(str(upload_id))
        if record:
            found.append(record)
    return found
