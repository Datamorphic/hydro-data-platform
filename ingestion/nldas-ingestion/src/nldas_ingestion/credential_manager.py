"""Earthdata credential acquisition and cached-token management."""

from __future__ import annotations

import json
import logging
import os
import random
import tempfile
# import threading
import time
from enum import Enum, auto
from pathlib import Path
from typing import Callable

LOGGER = logging.getLogger(__name__)
DEFAULT_VALIDATION_URL = "https://cmr.earthdata.nasa.gov/search/collections"


class TokenValidationResult(Enum):
    VALID = auto()
    INVALID = auto()
    UNKNOWN = auto()


class CredentialManagerError(RuntimeError):
    """Base exception for credential-manager failures."""


class CredentialConfigurationError(CredentialManagerError):
    """Raised when required credential configuration is missing or invalid."""

class TokenCacheMissingError(CredentialManagerError):
    """The configured cache file does not exist."""

class TokenCacheError(CredentialManagerError):
    """Raised when the cached token cannot be read or written safely."""

class EarthdataUnavailableError(CredentialManagerError):
    """Raised when Earthdata availability prevents token validation."""


class TokenAcquisitionError(CredentialManagerError):
    """Raised when a new token cannot be acquired."""


class CredentialManager:
    """Load, validate, and refresh an Earthdata access token.

    ``validation_url`` must be an authenticated Earthdata endpoint. A public
    endpoint returning HTTP 200 cannot prove that a bearer token is valid.
    """

    def __init__(
        self,
        token_filepath: str | Path | None = None,
        validation_url: str | None = None,
        max_validation_attempts: int = 3,
        request_timeout: float = 10.0,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        """Configure token storage, validation, retry, and synchronization behavior.

        The token path is taken from ``token_filepath`` or
        ``EARTHDATA_TOKEN_FILEPATH`` and relative paths are resolved from the
        repository root when one can be found. Login credentials are not
        required until a cached token must be replaced.

        Raises:
            CredentialConfigurationError: If no token path is configured.
            ValueError: If retry attempts or request timeout are invalid.

        Returns:
            None. The manager is initialized with no validated token.
        """
        if max_validation_attempts < 1:
            raise ValueError("max_validation_attempts must be at least 1")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")

        configured_path = token_filepath or os.getenv("EARTHDATA_TOKEN_FILEPATH")
        if not configured_path:
            raise CredentialConfigurationError(
                "Set EARTHDATA_TOKEN_FILEPATH or pass token_filepath."
            )

        self._token_filepath = self._resolve_path(configured_path)
        self._validation_url = validation_url or os.getenv(
            "EARTHDATA_VALIDATION_URL", DEFAULT_VALIDATION_URL
        )
        self._max_validation_attempts = max_validation_attempts
        self._request_timeout = request_timeout
        self._sleep = sleep
        self._random_value = random_value

    # Private Access
    @staticmethod
    def _resolve_path(filepath: str | Path) -> Path:
        """Resolve a token path while preserving explicitly absolute paths.

        Relative paths are assumed to be repository-relative when a parent
        containing ``.git`` can be found; otherwise they are resolved against
        the current working directory.

        Raises:
            TypeError: If ``filepath`` cannot be converted to ``Path``.

        Returns:
            The expanded and resolved token-cache path. The path need not
            exist yet.
        """
        path = Path(filepath).expanduser()
        if path.is_absolute():
            return path

        project_root = Path(__file__).resolve()
        for parent in project_root.parents:
            if (parent / ".git").exists():
                return parent / path
        return Path.cwd() / path

    def _read_cached_token(self) -> str:
        """Read and validate the access token stored in the JSON cache.

        The cache is assumed to contain an object with a non-empty string
        ``access_token`` field. A missing cache is treated as no cached token,
        while an existing malformed or unreadable cache is considered an
        error rather than a reason to silently log in.

        Raises:
            TokenCacheError: If the cache has the wrong suffix, cannot be
                read, contains invalid JSON, or lacks a usable token.

        Returns:
            The stripped cached access-token string, or ``None`` if the file
            does not exist.
        """
        if not self._token_filepath.exists():
            raise TokenCacheMissingError(f"No token cache file exists at {self._token_filepath}.")
        if self._token_filepath.suffix.lower() != ".json":
            raise TokenCacheError("The token cache path must have a .json suffix.")

        try:
            with self._token_filepath.open("r", encoding="utf-8") as token_file:
                payload = json.load(token_file)
        except (OSError, json.JSONDecodeError) as error:
            raise TokenCacheError(
                f"Unable to read token cache {self._token_filepath}."
            ) from error

        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise TokenCacheError(
                f"Token cache {self._token_filepath} lacks a valid access_token."
            )
        return token.strip()

    def _write_cached_token(self, token: str) -> None:
        """Atomically write an access token to the JSON cache.

        The parent directory is assumed to be writable. The token is written
        to a unique temporary file in the target directory, flushed to disk,
        assigned restrictive permissions where supported, and atomically
        replaced into the configured cache path.

        Raises:
            OSError: If the parent directory cannot be created. Internal file
                errors are converted to ``TokenCacheError``.
            TokenCacheError: If the cache cannot be written or replaced.

        Returns:
            None. The configured cache contains the new token on success.
        """
        self._token_filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = {"token_type": "Bearer", "access_token": token}
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._token_filepath.parent,
                prefix=f".{self._token_filepath.name}.",
                suffix=".tmp",
                delete=False,
            ) as token_file:
                temporary_path = Path(token_file.name) # This looks to create a filepath that only has the name of the temp file as opposed to the location, why?
                json.dump(payload, token_file)
                token_file.flush()
                os.fsync(token_file.fileno())

            try:
                os.chmod(temporary_path, 0o600)
            except OSError:
                LOGGER.debug("Could not restrict token-cache permissions.", exc_info=True)

            os.replace(temporary_path, self._token_filepath)
            temporary_path = None
        except OSError as error:
            raise TokenCacheError(
                f"Unable to write token cache {self._token_filepath}."
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    LOGGER.warning("Could not remove temporary token cache file.")

    def _validate_token(self, token: str) -> TokenValidationResult:
        """Check whether an access token is accepted by the validation API.

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
            LOGGER.warning("requests is required to validate an Earthdata token.")
            return TokenValidationResult.UNKNOWN

        try:
            response = requests.get(
                self._validation_url,
                params={"page_size": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=self._request_timeout,
            )
        except requests.RequestException:
            LOGGER.warning("Earthdata token validation request failed.", exc_info=True)
            return TokenValidationResult.UNKNOWN

        if response.status_code in (401, 403):
            return TokenValidationResult.INVALID
        elif response.status_code == 200:
            return TokenValidationResult.VALID
        else:
            return TokenValidationResult.UNKNOWN

    @staticmethod
    def _get_new_token_via_login() -> str: # rename so it's clear we are using login credentials to retrievw a new token from earth data token manager API
        """Acquire a new Earthdata token using environment credentials.

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
            raise TokenAcquisitionError(
                "earthaccess is required to acquire a new Earthdata token."
            ) from error

        missing = [
            name
            for name in ("EARTHDATA_USERNAME", "EARTHDATA_PASSWORD")
            if not os.getenv(name)
        ]

        if missing:
            raise CredentialConfigurationError(
                "Missing Earthdata login environment variables: " + ", ".join(missing)
            )

        try:
            auth = earthaccess.login(strategy="environment")
            token = auth.token.get("access_token")
        except Exception as error:
            raise TokenAcquisitionError("Earthdata login failed.") from error

        if not isinstance(token, str) or not token.strip():
            raise TokenAcquisitionError("Earthdata login returned no access token.")
        return token.strip()

    # Public Access
    def get_cached_token(self) -> str:
        """Read a cached NASA EarthData token from disk storage without network validation."""
        return self._read_cached_token()

    def get_token_from_login(self) -> str:
        """Acquire a new token using Earthdata login credentials."""
        return self._get_new_token_via_login()

    def validate_token(self, token: str) -> TokenValidationResult:
          """Validate a cached token with bounded exponential backoff.
  
          Validation is assumed to be transiently retryable when the result is
          ``UNKNOWN``. Invalid tokens are not retried, and an indeterminate
          result after all attempts is returned to the caller without login.
  
          Raises:
              Exceptions from the injected sleep or random-value functions may
                  propagate if those test or scheduling hooks fail.
  
          Returns:
              The first ``VALID`` or ``INVALID`` result, or ``UNKNOWN`` after
              all configured validation attempts fail to determine validity.
          """
          for attempt in range(self._max_validation_attempts):
              state = self._validate_token(token)
              if state is not TokenValidationResult.UNKNOWN:
                  return state
              if attempt + 1 < self._max_validation_attempts:
                  delay = min(8.0, 0.5 * (2**attempt))
                  self._sleep(delay + self._random_value() * 0.25)
          return TokenValidationResult.UNKNOWN

    def update_cached_token(self, token: str) -> None:
        """Atomically write a token to the cache."""
        self._write_cached_token(token=token)

if __name__ == "__main__":
    # Test the module
    print("Testing credntial_manager.py")
    