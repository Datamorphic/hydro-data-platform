import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock

from nldas_ingestion.infrastructure.credentials.earthdata_token_provider import EarthDataTokenProvider
import nldas_ingestion.infrastructure.credentials.exceptions as TokenError
from nldas_ingestion.infrastructure.credentials.earthdata_token_store import EarthDataTokenStore
from nldas_ingestion.infrastructure.credentials.earthdata_token_validator import EarthDataTokenValidator
from nldas_ingestion.infrastructure.credentials.earthdata_token_retriever import EarthDataTokenRetriever
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore
from nldas_ingestion.infrastructure.credentials.protocols import TokenValidationResult


@pytest.fixture
def token_store(mocker: MockerFixture) -> Mock:  
    return Mock(
        spec=EarthDataTokenStore
    )

@pytest.fixture
def token_validator(mocker: MockerFixture) -> Mock:
    return Mock(
        spec=EarthDataTokenValidator
    )

@pytest.fixture
def token_retriever(mocker: MockerFixture) -> Mock:
    return Mock(
        spec=EarthDataTokenRetriever
    )

@pytest.fixture
def token_provider(
    token_store: Mock,
    token_validator: Mock,
    token_retriever: Mock
):
    return EarthDataTokenProvider(
        token_store=token_store,
        token_validator=token_validator,
        token_retriever=token_retriever
    )


class TestEarthdataTokenProvider:

    class TestGetToken:

        def test_missing_cache_retrieves_and_caches_new_token(self,
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens when no token is found in the cache?
            A: The provider should retrieve a fresh token, write it to cache, and return it.
            """
            token = 'token123'
            token_store.get_token.side_effect = TokenError.TokenCacheMissingError
            token_retriever.retrieve_token.return_value = token

            result = token_provider.get_token()

            assert result == token
            token_store.get_token.assert_called_once()
            token_retriever.retrieve_token.assert_called_once()
            token_store.put_token.assert_called_with(token)
            token_validator.assert_not_called()


        def test_valid_cached_token_is_returned_without_retrieval(self,
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens when a cached token exists and validates successfully?
            A: The provider should return the cached token without calling the retriever or recaching.
            """
            token = 'token123'
            token_store.get_token.return_value = token
            token_validator.validate_token.return_value = TokenValidationResult.VALID

            result = token_provider.get_token()

            assert result == token
            token_store.get_token.assert_called_once()
            token_validator.validate_token.assert_called_with(token)
            token_retriever.assert_not_called()
            token_store.put_token.assert_not_called()

        def test_invalid_cached_token_triggers_token_retrieval_and_cache_refresh(self,
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens when a cached token exists but fails validation?
            A: The provider should discard it, retrieve a new token, cache it, and return it.
            """
            invalid_token = 'InvalidToken123'
            valid_token = 'ValidToken123'
            token_store.get_token.return_value = invalid_token
            token_validator.validate_token.return_value = TokenValidationResult.INVALID
            token_retriever.retrieve_token.return_value = valid_token

            result = token_provider.get_token()

            assert result == valid_token
            token_store.get_token.assert_called_once()
            token_validator.validate_token.assert_called_with(invalid_token)
            token_retriever.retrieve_token.assert_called_once()
            token_store.put_token.assert_called_with(valid_token)

        def test_unknown_cached_token_validation_raises_token_service_unavailable_error(self,
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens when cached token validation is indeterminate because the validation service is unavailable?
            A: TokenServiceUnavailableError should be raised instead of silently continuing.
            """
            token = 'token123'
            token_store.get_token.return_value = token
            token_validator.validate_token.return_value = TokenValidationResult.UNKNOWN

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_provider.get_token()
            
            token_store.get_token.assert_called_once()
            token_validator.validate_token.assert_called_with(token)
            token_retriever.retrieve_token.assert_not_called()
            token_store.put_token.assert_not_called()

        def test_missing_cache_exception_is_treated_as_empty_cache(self,
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens when the cache raises a missing-token error?
            A: The provider should treat it as no cached token and continue to retrieve a fresh one.
            """
            token = 'token123'
            token_store.get_token.side_effect = TokenError.TokenCacheMissingError
            token_validator.validate_token.return_value = TokenValidationResult.VALID
            token_retriever.retrieve_token.return_value = token

            result = token_provider.get_token()
            
            assert result == token
            token_store.get_token.assert_called_once()            
            token_validator.validate_token.assert_not_called()
            token_retriever.retrieve_token.assert_called_once()
            token_store.put_token.assert_called_with(token)

        @pytest.mark.parametrize(
            "store_error",
            [
                TokenError.TokenConfigurationError,
                TokenError.TokenServiceUnavailableError,
            ]
        )
        def test_token_store_write_failure_propagates_after_retrieval(self,
            store_error: type[TokenError.TokenError],
            token_store: Mock,
            token_retriever: Mock,
            token_validator: Mock,
            token_provider: EarthDataTokenProvider):
            """
            Q: What happens if the provider successfully retrieves a token but cannot write it to cache?
            A: The underlying write error should propagate because the provider does not swallow storage failures.
            """
            token = 'token123'
            token_store.get_token.return_value = None
            token_retriever.retrieve_token.return_value = token
            token_store.put_token.side_effect = store_error
            
            with pytest.raises(store_error):
                token_provider.get_token()
            
            token_store.get_token.assert_called_once()
            token_validator.validate_token.assert_not_called()
            token_retriever.retrieve_token.assert_called_once()
            token_store.put_token.assert_called_with(token)