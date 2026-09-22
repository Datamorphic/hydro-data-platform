
"""
For your token flow, the likely recovery decisions are:

missing cache -> retrieve new token
malformed cache -> fail or repair
storage unavailable -> fail or retry
permission/configuration problem -> fail fast
validation server unavailable -> retry or fail
retrieval/auth server unavailable -> retry or fail
"""

class TokenError(Exception):
    """Base exception for token credential failures."""

class TokenCacheMissingError(TokenError):
    """Raised when a token is missing from cache."""

class TokenServiceUnavailableError(TokenError):
    """Raised when a token service is unavailable/offline. Includes storage, retrieval, and validation services"""

class TokenConfigurationError(TokenError):
    """Raised when the environment used to interface with
    token servercies is invalid or when requests sent to
    the services are malformed or the information is out of date.
    """
