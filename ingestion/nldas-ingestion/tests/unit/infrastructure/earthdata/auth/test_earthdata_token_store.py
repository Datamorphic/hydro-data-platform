import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock
import json
from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_store import EarthDataTokenStore
from nldas_ingestion.infrastructure.storage.protocols import ObjectStore
import nldas_ingestion.infrastructure.earthdata.auth.exceptions as TokenError
import nldas_ingestion.infrastructure.storage.exceptions as StorageError

"""
Define Test Scenarios
Cover different categories of inputs and code paths to ensure thorough logic validation:
- Positive / Happy Path: Test with valid, expected inputs to verify standard calculations or operations.
- Negative Path: Test with invalid inputs or incorrect states to ensure proper error handling or failure messages.
- Boundary Checks: Test extreme values, such as minimum and maximum limits, empty strings, or null values.
- Exception Scenarios: Verify that exceptions are correctly thrown when the code encounters illegal states.
"""

@pytest.fixture
def object_store(mocker: MockerFixture) -> Mock:
    return mocker.Mock(spec=ObjectStore)

@pytest.fixture
def token_store(object_store: Mock) -> EarthDataTokenStore:
    return EarthDataTokenStore(
        object_store=object_store,
        object_key="object_key"
    )

class TestEarthDataTokenStore:

    class TestGetToken:

        def test_valid_token_returns_token(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            If the object store returns a valid token store
            byte object does the function decode the json
            correctly, extract the token string, and return it?
            """
            return_value = {
                "token_type": "Bearer",
                "access_token": "abc123"
                }
            object_store.get.return_value = json.dumps(return_value).encode("utf-8")

            result = token_store.get_token()

            assert result == return_value["access_token"]

        def test_empty_bytes_raises_TokenCacheMissingError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What happens if the object store returns an empty byte object?
            A: It should raise a TokenCacheMissingError
            """
            object_store.get.return_value = b''   

            with pytest.raises(TokenError.TokenCacheMissingError):
                token_store.get_token()

        def test_non_json_raises_TokenCacheMalformedError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What if the returned bytes are not representing json?
            A: This should throw a `TokenCacheMalformedError`.
            """
            object_store.get.return_value = 'not a json object'.encode('utf-8')

            with pytest.raises(TokenError.TokenCacheMalformedError):
                token_store.get_token() 

        def test_empty_token_raises_TokenCacheMissingError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What happens when the object store returns a json that has an empty token? 
            A: The empty token should raise a `TokenCacheMissingError`.
            """
            return_value = {
                "token_type": "Bearer",
                "access_token": None
            }
            object_store.get.return_value = json.dumps(return_value).encode("utf-8")

            with pytest.raises(TokenError.TokenCacheMissingError):
                result = token_store.get_token()

        def test_all_whitespace_token_raises_TokenCacheMissingError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What happens when the object store returns a json with a token that is just white space? 
            A: The empty token should raise a `TokenCacheMissingError`.
            """
            return_value = {
                "token_type": "Bearer",
                "access_token": '   '
            }
            object_store.get.return_value = json.dumps(return_value).encode("utf-8")

            with pytest.raises(TokenError.TokenCacheMissingError):
                result = token_store.get_token()

        def test_missing_access_token_field_raises_TokenCacheMissingError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What happens when the object store returns a json with a token that is just white space? 
            A: The empty token should raise a `TokenCacheMissingError`.
            """
            return_value = {
                "token_type": "Bearer",
            }
            object_store.get.return_value = json.dumps(return_value).encode("utf-8")

            with pytest.raises(TokenError.TokenCacheMissingError):
                result = token_store.get_token()

        def test_non_UTF8_encoding_raises_TokenCacheMalformedError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: What happens when the object store returns a json with a token that is just white space? 
            A: The empty token should raise a `TokenCacheMissingError`.
            """
            return_value = {
                "token_type": "Bearer",
                "access_token": "abc123"
            }
            object_store.get.return_value = json.dumps(return_value).encode("UTF-16")

            with pytest.raises(TokenError.TokenCacheMalformedError):
                result = token_store.get_token()

        # multiple inputs changing scenario | Error handling
        @pytest.mark.parametrize(
            ("storage_error", "token_error"),
            [
                (
                    StorageError.StorageObjectMissingError,
                    TokenError.TokenCacheMissingError
                ),
                (
                    StorageError.StoragePermissionError,
                    TokenError.TokenConfigurationError
                ),
                (
                    StorageError.StorageRequestError,
                    TokenError.TokenConfigurationError
                ),
                (
                    StorageError.StorageUnavailableError,
                    TokenError.TokenServiceUnavailableError
                ),
                (
                    StorageError.StorageServiceError,
                    TokenError.TokenServiceUnavailableError
                )
            ]
        )
        def test_StorageError_raises_TokenError(self, 
            storage_error,
            token_error,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Are storage errors handled and correctly translated to
            TokenErrors?
            """

            object_store_get: Mock = object_store.get
            object_store_get.side_effect = storage_error

            with pytest.raises(token_error):
                token_store.get_token()
                

    class TestPutToken:

        def test_no_edge_whitespace_token_is_written(
            self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: Will a valid token string with no edge whitespace be written as is?
            A: Yes it will be.
            """
            object_store_put: Mock = object_store.put
            object_store_put.return_value = None
            token = "abc123"

            token_data = json.dumps(
                {
                    "token_type": "Bearer",
                    "access_token": token
                }
            )

            token_store.put_token(token)

            object_store_put.assert_called_once_with(
                key=token_store._object_key,
                data=token_data.encode("utf-8"),
                content_type="application/json"
            )

        def test_yes_edge_whitespace_token_is_written(
            self,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Q: Will a valid token string with edge whitespace be written without edge whitespace?
            A: Yes it will be.
            """
            object_store_put: Mock = object_store.put
            object_store_put.return_value = None
            token = "    abc123  "

            token_data = json.dumps(
                {
                    "token_type": "Bearer",
                    "access_token": token.strip()
                }
            )

            token_store.put_token(token)

            object_store_put.assert_called_once_with(
                key=token_store._object_key,
                data=token_data.encode("utf-8"),
                content_type="application/json"
            )
        
        def test_all_whitespace_token_raises_TokenConfigurationError(self,
            object_store: Mock,
            token_store: EarthDataTokenStore
            ):
            """
            Q: What happens if we pass a token with all whitespace?
            A: TokenConfigurationError should be raised.
            """

            token = '    '

            with pytest.raises(TokenError.TokenConfigurationError):
                token_store.put_token(token)


        @pytest.mark.parametrize(
            ("storage_error", "token_error"),
            [
                (
                    StorageError.StorageObjectMissingError,
                    TokenError.TokenConfigurationError
                ),
                (
                    StorageError.StoragePermissionError,
                    TokenError.TokenConfigurationError
                ),
                (
                    StorageError.StorageRequestError,
                    TokenError.TokenConfigurationError
                ),
                (
                    StorageError.StorageUnavailableError,
                    TokenError.TokenServiceUnavailableError
                ),
                (
                    StorageError.StorageServiceError,
                    TokenError.TokenServiceUnavailableError
                )
            ]
        )
        def test_StorageError_raises_TokenError(self, 
            storage_error,
            token_error,
            object_store: Mock,
            token_store: EarthDataTokenStore
        ):
            """
            Are storage errors handled and correctly translated to
            TokenErrors?
            """

            object_store_put: Mock = object_store.put
            object_store_put.side_effect = storage_error

            with pytest.raises(token_error):
                token_store.put_token(token="abc123")
