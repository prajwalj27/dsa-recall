"""LeetCode GraphQL client. All LeetCode-specific code lives in this package."""

from app.leetcode.client import LeetCodeClient
from app.leetcode.errors import (
    AuthExpiredError,
    LeetCodeError,
    RateLimitedError,
    SchemaChangedError,
)

__all__ = [
    "AuthExpiredError",
    "LeetCodeClient",
    "LeetCodeError",
    "RateLimitedError",
    "SchemaChangedError",
]
