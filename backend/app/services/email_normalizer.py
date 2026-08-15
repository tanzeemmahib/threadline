"""Conservative email normalization shared by retrieval and comparison."""

from __future__ import annotations

import re

_LOCAL_RE = re.compile(r"^[^\s@]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[^\s.@-](?:[^\s.@]*[^\s.@-])?$")


def normalize_valid_email(value: str) -> str | None:
    """Return a comparison form only for a syntactically complete address.

    This deliberately does not repair malformed evidence or apply provider-
    specific mailbox rules. Unicode mailbox/domain characters remain intact.
    """
    # Sentence-final punctuation is cosmetic formatting, not part of an email
    # address. Internal punctuation is preserved and never repaired.
    normalized = value.strip().rstrip(".,;:").casefold()
    if normalized.count("@") != 1:
        return None
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain or len(normalized) > 254:
        return None
    if not _LOCAL_RE.fullmatch(local) or local.startswith(".") or local.endswith("."):
        return None
    if ".." in local or "." not in domain:
        return None
    labels = domain.split(".")
    if any(not label or len(label) > 63 or not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        return None
    if len(labels[-1]) < 2:
        return None
    return normalized
