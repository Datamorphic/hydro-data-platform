import os
from .credential_manager import (
     CredentialManager,
     EarthdataUnavailableError,
     TokenValidationResult,
     TokenCacheMissingError
)

from .discovery_manager import (DiscoveryManager)

print(os.getenv("PYTHONPATH"))

def authenticate_earthdata() -> str: 
    """Ensures a valid NASA EarthData authentication token is cached on file. Retrieves a new one if existing
        one is invalid or expired.

    The operation assumes that the configured validation endpoint can
    authenticate bearer tokens. Access is serialized per manager instance
    so concurrent threads do not perform duplicate validation or login.
    An invalid cached token is replaced; an indeterminate validation does
    not trigger login because the cached token may still be usable.

    Raises:
        TokenCacheError: If an existing cache is malformed or cannot be
            written.
        EarthdataUnavailableError: If token validation remains unknown
            after all retries.
        CredentialConfigurationError: If replacement requires login and
            login credentials are missing.
        TokenAcquisitionError: If a replacement token cannot be acquired.
    """

    # TODO: Ensure we fail early if token filepath missing -> check manager __init__
    discover = DiscoveryManager()
    validation_url = discover.retrieve_validation_granule_url()
    print(validation_url)
    manager = CredentialManager(
         validation_url=validation_url
    ) # See if default validation url is in environment variable and access and set right

    try:
        token = manager.get_cached_token()
    except TokenCacheMissingError as e:
            token = None

    if token is not None:   
        token_state = manager.validate_token(token)
        if token_state is TokenValidationResult.UNKNOWN:
            raise EarthdataUnavailableError(
                "Earthdata server availability prevented token validation."
            )
        elif token_state is TokenValidationResult.VALID:
            return None

    token = manager.get_token_from_login()
    manager.update_cached_token(token)

    return token

if __name__ == "__main__":
    authenticate_earthdata()
    print(f"Program completed without error")

    # Does the default variables set at the top of credential_manager.py get stored in memory and used when instantiating the class?
    