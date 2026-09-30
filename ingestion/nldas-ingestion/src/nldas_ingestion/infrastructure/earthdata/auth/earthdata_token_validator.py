from nldas_ingestion.infrastructure.earthdata.auth.protocols import TokenValidationResult

DEFAULT_VALIDATION_URL = "https://cmr.earthdata.nasa.gov/search/collections"


class EarthDataTokenValidator:

    def __init__(self,
        validation_url: str = DEFAULT_VALIDATION_URL,
        max_attempts: int = 3,
        request_timeout: float = 10.0
    ):
        self._validation_url = validation_url
        self._max_attempts = max_attempts
        self._request_timeout = request_timeout

    def validate_token_routine(self, token: str) -> TokenValidationResult:
        """
        Check whether an access token is accepted by the validation API.

        The configured endpoint is assumed to require Earthdata bearer
        authentication; a public endpoint returning HTTP 200 cannot prove
        token validity. Network failures and unexpected status codes are
        treated as indeterminate so the caller can retry without refreshing a
        potentially usable token.

        Raises:
            No network exception is propagated; request failures return
            ``TokenValidationResult.UNKNOWN``. An import failure for
            ``requests`` is also treated as unknown.

        Returns:
            ``VALID`` for HTTP 200, ``INVALID`` for HTTP 401 or 403, and
            ``UNKNOWN`` for network, dependency, or other HTTP failures.
        """
        try:
            import requests
        except ImportError:
            # LOGGER.warning("requests is required to validate an Earthdata token.")
            return TokenValidationResult.UNKNOWN

        try:
            response = requests.get(
                self._validation_url,
                params={"page_size": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
        except requests.RequestException:
            # LOGGER.warning("Earthdata token validation request failed.", exc_info=True)
            return TokenValidationResult.UNKNOWN

        if response.status_code in (401, 403): # TODO: Handle any and all 4xx (Client Errors) responses, as well as 3xx (Redirection) and 5xx (Server Error)
            return TokenValidationResult.INVALID
        elif response.status_code == 200: # (Success)
            return TokenValidationResult.VALID
        else:
            return TokenValidationResult.UNKNOWN

    def validate_token(self, token: str) -> TokenValidationResult:
        """
        Extends validation via retry capabilities with delays.
        """
        from time import sleep
        from random import random

        for attempt in range(self._max_attempts):
            state = self.validate_token_routine(token)
            if state is not TokenValidationResult.UNKNOWN:
                return state
            if attempt + 1 < self._max_attempts:
                delay = min(8.0, 0.5 * (2**attempt))
                sleep(delay + random() * 0.25)
        return TokenValidationResult.UNKNOWN
