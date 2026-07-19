"""IRC output helpers."""


def limit_utf8(text: str, max_bytes: int, suffix: str = "…") -> str:
    """Return *text* within *max_bytes* without splitting UTF-8 characters."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) > max_bytes:
        return encoded[:max_bytes].decode("utf-8", errors="ignore")
    prefix = encoded[: max_bytes - len(suffix_bytes)]
    return prefix.decode("utf-8", errors="ignore") + suffix
