from pathlib import Path


def insert_path_part(path: str, part: str) -> str:
    """Insert `part` before all suffixes, eg. insert_path_part("a/speech.mono.wav", "fast") -> "a/speech.fast.mono.wav"."""
    p = Path(path)
    suffixes = "".join(p.suffixes)
    stem = p.name[: len(p.name) - len(suffixes)] if suffixes else p.name
    return str(p.with_name(f"{stem}.{part}{suffixes}"))


def modify_path(path: str, directory: str | None = None, suffix: str | None = None, part: str | None = None) -> str:
    """Return path with its directory, last suffix and/or inserted part changed."""
    p = Path(path)
    if suffix:
        p = p.with_suffix(suffix if suffix.startswith(".") else f".{suffix}")
    if part:
        p = Path(insert_path_part(str(p), part))
    if directory:
        p = Path(directory) / p.name
    return str(p)
