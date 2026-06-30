"""URL cleanup + stable keys for matching profile links."""
from __future__ import annotations

import re
from typing import Optional


def clean_url(raw: object) -> Optional[str]:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    return text.rstrip("/")


def github_key(raw: object) -> Optional[str]:
    """Return the lowercased github login from a url/handle, else None."""
    if not raw:
        return None
    text = str(raw).strip().lower()
    m = re.search(r"github\.com/([a-z0-9-]+)", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-z0-9-]+", text):  # bare login
        return text
    return None


def linkedin_key(raw: object) -> Optional[str]:
    """Return the lowercased linkedin vanity id from a url, else None."""
    if not raw:
        return None
    text = str(raw).strip().lower()
    m = re.search(r"linkedin\.com/in/([a-z0-9-]+)", text)
    return m.group(1) if m else None
