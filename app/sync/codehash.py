import hashlib


def code_hash(code: str) -> str:
    """Hash of code ignoring whitespace-only differences.

    Used to skip re-analysing a re-solve whose code is effectively identical to one already
    analysed. Indentation is collapsed too, so this is for change detection, not semantics.
    """
    lines = (" ".join(line.split()) for line in code.splitlines())
    normalized = "\n".join(line for line in lines if line)
    return hashlib.sha256(normalized.encode()).hexdigest()
