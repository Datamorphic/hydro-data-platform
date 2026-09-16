import nldas_ingestion.infrastructure.credentials.errors as err

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
        except ImportError as error:
            raise EnvironmentError(
                "`earthaccess` package is required to acquire a new Earthdata token."
            ) from error

        try:
            auth = earthaccess.login(strategy="environment")
        except Exception as error:
            raise err.TokenRetrievalServerError("Earthdata login failed.") from error

        try:
            token = auth.token.get("access_token")
        except Exception as error:
            raise err.TokenRetrievalServerError("Earthdata failed to provide an access token.")

        if not isinstance(token, str) or not token.strip():
            raise err.TokenRetrievalServerError("Earthdata login returned no access token.")
        return token.strip()