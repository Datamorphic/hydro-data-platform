from typing import Protocol
from enum import Enum, auto


class TokenValidationResult(Enum):
    VALID = auto()
    INVALID = auto()
    UNKNOWN = auto()

class TokenStore(Protocol):
    """
    token-specific behavior and a narrow interface for retrieval and overwriting
    
    ***Reads/writes cached tokens***
    """
    def get_token(self) -> str:
        ...

    def put_token(self, token: str) -> None:
        ...

class TokenValidator(Protocol):
    """
    1. Performs HTTP networking requests to validate token against server.
    2. Classifies token validity.
    """

    def validate_token(self, token: str) -> TokenValidationResult:
        ...

class TokenRetriever(Protocol):
    """Retrieves a valid token from a target server using login credentials"""

    def retrieve_token(self) -> str:
        ...

class TokenProvider(Protocol):
    """Coordinates caching, retrieval, validation, and error handling of credential tokens"""

    def __init__(self,
        token_store: TokenStore,
        token_validator: TokenValidator,
        token_retriever: TokenRetriever
    ):
        ...

    def get_token(self) -> str:
        ...