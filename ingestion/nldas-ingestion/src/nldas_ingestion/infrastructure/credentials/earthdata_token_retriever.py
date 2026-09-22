from typing import (Mapping)
import nldas_ingestion.infrastructure.credentials.exceptions as err

class EarthDataTokenRetriever:

    def __init__(self, 
            earthdata_username: str, 
            earthdata_password: str
    ):
        self._username = earthdata_username
        self._password = earthdata_password

    def retrieve_token(self) -> str:
        """Acquire a valid Earthdata token using login credentials.

        The ``earthaccess`` library is assumed to support
        ``strategy="environment"`` and to return an authentication object
        containing ``token.access_token``. The username and password are read
        from ``EARTHDATA_USERNAME`` and ``EARTHDATA_PASSWORD`` environmental variables only when this
        method is needed.

        Raises:
            CredentialConfigurationError: If either login environment
                variable is missing.
            TokenAcquisitionError: If ``earthaccess`` is unavailable, login
                fails, or no usable access token is returned.

        Returns:
            A stripped, non-empty Earthdata access-token string.
        """
        try:
            import earthaccess
            from earthaccess.exceptions import LoginAttemptFailure
        except ImportError as exc:
            raise err.TokenConfigurationError(
                "`earthaccess` package is required for `EarthdataTokenRetriever` to acquire a new Earthdata token."
            ) from exc

        try:
            auth: earthaccess.Auth = earthaccess.login(strategy="environment")
            
        except LoginAttemptFailure as exc:
            raise err.TokenConfigurationError(
                "Token retrieval failed due to invalid login credentials. " +
                "Check `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` in environment."
            ) from exc
        except Exception as exc: # TODO: Destinguish between bad credentails and server issue
            raise err.TokenServiceUnavailableError(
                "Token retrieval failed expectedly due to unexpected Earthdata server failure"
            ) from exc


        try:        
            token_response: Mapping[str, str] | None = auth.token
            if token_response is None:
                raise ValueError("Earthdata authentication server responded without a token.")
            
            token = token_response.get("access_token")
            if token is None:
                raise ValueError("Earthdata authentication server responded with empty token.")
            if not isinstance(token, str) or not token.strip():
                raise TypeError("Provided Earthdata token is not a string.")

        except Exception as exc: # TODO: More specific error translation?
            raise err.TokenServiceUnavailableError(
                "Token retrieval service failed unexpectedly with invalid token response."
            ) from exc

        return token.strip()