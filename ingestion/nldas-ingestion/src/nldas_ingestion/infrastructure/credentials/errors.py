# Token Store Errors
class TokenStoreError(RuntimeError):
    """Base exception for token store failures."""
class TokenStoreCacheMissingError(TokenStoreError):
    """Raised when token cache file in storage is missing."""
class TokenStoreReadingError(TokenStoreError):
    """Raised when reading from a token cache throws an IO error."""
class TokenStoreWritingError(TokenStoreError):
    """Raised when writing to a token cache throws an IO error."""

# Token Validation Errors
class TokenValidationError(RuntimeError):
    """Base exception for token validator failures."""
class TokenValidationServerError(TokenValidationError):
    """Raised when a token validation server is not behaving as intended or is offline."""

# Token Retrieval Errors
class TokenRetrievalError(RuntimeError):
    """Base exception for token retriever failures."""
class TokenRetrievalServerError(RuntimeError):
    """
    Raised when the authentication server being accessed to retrieve a token is
        not behaving as intended or is offline.
    """

# Token Provider Errors
class TokenProviderError(RuntimeError):
    """Base exception for token provider failures."""

class EnvironmentError(RuntimeError):
    """Base exception for process environment issues"""