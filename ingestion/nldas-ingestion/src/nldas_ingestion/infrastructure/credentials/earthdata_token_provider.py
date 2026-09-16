from __future__ import annotations
import logging
from pathlib import Path

# Applicaiton Imports
from nldas_ingestion.infrastructure.credentials.earthdata_token_store import EarthDataTokenStore
from nldas_ingestion.infrastructure.credentials.earthdata_token_validator import EarthDataTokenValidator
from nldas_ingestion.infrastructure.credentials.earthdata_token_retriever import EarthDataTokenRetriever
from nldas_ingestion.infrastructure.credentials.protocols import TokenValidationResult
import nldas_ingestion.infrastructure.credentials.errors as err


LOGGER = logging.getLogger(__name__)

class EarthDataTokenProvider:

    def __init__(self,
        token_store: EarthDataTokenStore, # EarthdataJsonTokenStore(token_path)
        token_validator: EarthDataTokenValidator, # EarthdataTokenValidator(validation_url)
        token_retriever: EarthDataTokenRetriever # EarthdataTokenRetriever(username, password)
    ):
        self._token_store = token_store
        self._token_validator = token_validator
        self._token_retriever = token_retriever

    def get_token(self) -> str:
        """
        Retrieves a valid EarthData token. 
        
        First checks for a cached token on file and validating it against EarthData Servers.
        If the cache is empty or does not exist, uses Earth Data login credentials to retrieve
        a valid authentication token and then caches in storage.

        Returns [str]: Token

        Raises:
            `EarthDataUnavailableError`: If EarthData server used for validation is offline or misbehaving.
            `TokenValidationError`: If EarthData Authentication server is not responding with a valid token.
            `TokenStoreError: If there is an issue related to reading a cached token or writing a new token to the cache.
                Example 1: The token cache file is missing (set in the TokenStore).
                Example 2: I/O error related to writing the new token to cache file. 
            

        """
        try:
            token = self._token_store.get_token() # TODO: Specify custom errors to destinguish between whether the cash is empty (except and set token to None) vs if it is missing (throw error for misconfiguration)
        except Exception as error:
            token = None

        if token is not None:   
            token_state = self._token_validator.validate_token(token)
            if token_state is TokenValidationResult.UNKNOWN:
                raise err.TokenValidationServerError(
                    "Earthdata server availability prevented token validation."
                )
            elif token_state is TokenValidationResult.VALID:
                return token

        token = self._token_retriever.retrieve_token()
        self._token_store.put_token(token)
        return token
            

if __name__ == "__main__":
    #####################
    # Example composition
    #####################
    earthdata_token_store = EarthDataTokenStore(Path("path/to/store"))
    earthdata_token_validator = EarthDataTokenValidator()
    earthdata_token_retriever = EarthDataTokenRetriever("username", "password")
    earthdata_token_provider = EarthDataTokenProvider(
        token_store=earthdata_token_store,
        token_validator=earthdata_token_validator,
        token_retriever=earthdata_token_retriever
    )

    token = earthdata_token_provider.get_token()
    print(token)
    