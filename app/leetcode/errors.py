class LeetCodeError(Exception):
    """Base class for everything that can go wrong talking to LeetCode."""


class AuthExpiredError(LeetCodeError):
    """The session cookie is missing, invalid, or expired; the user needs a fresh one."""


class RateLimitedError(LeetCodeError):
    """LeetCode kept answering 429/403 after all retries."""


class SchemaChangedError(LeetCodeError):
    """LeetCode's response no longer matches what we expect (renamed query or field).

    Sync should stop and report "sync broken" instead of storing bad data.
    """
