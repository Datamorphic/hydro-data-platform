import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock
import builtins
import os
from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_validator import EarthDataTokenValidator
import nldas_ingestion.infrastructure.earthdata.auth.exceptions as TokenError
from nldas_ingestion.infrastructure.earthdata.auth.protocols import TokenValidationResult


@pytest.fixture
def token_validator() -> EarthDataTokenValidator:
    return EarthDataTokenValidator()

class TestEarthDataTokenValidator:

    class TestValidateTokenRoutine:

        def test_missing_request_library_returns_unknown(
            self,
            monkeypatch: pytest.MonkeyPatch,
            token_validator: EarthDataTokenValidator,
        ):
            """
            Q: What happens if the `requests` library can not be imported from sys.modules?
            A: TokenValidationResult.UNKNOWN should be returned.
            """
            real_import = builtins.__import__

            def _import_raises(name, *args, **kwargs):
                if name == "requests":
                    raise ImportError("requests library is missing.")
                return real_import(name, *args, **kwargs)

            monkeypatch.setattr(builtins, "__import__", _import_raises)

            result = token_validator.validate_token_routine(token="token123")

            assert result == TokenValidationResult.UNKNOWN

        @pytest.mark.parametrize(
            ("response_status", "validation_result"),
            [
                (200,TokenValidationResult.VALID),
                (300,TokenValidationResult.UNKNOWN),
                (401,TokenValidationResult.INVALID),
                (403,TokenValidationResult.INVALID),
                (500,TokenValidationResult.UNKNOWN),
            ]
        )
        def test_valid_network_response_status_returns_validation_result(
            self,
            response_status: int,
            validation_result: TokenValidationResult,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_validator: EarthDataTokenValidator
        ):
            """
            Q: How does the unit handle different network responses (i.e. 401, 403, 200).
            A: Valid network responses map to the TokenValidationResult enum.
            """
            token = 'token123'
            mock_response = mocker.Mock()
            mock_response.status_code = response_status
            mock_get = mocker.Mock(return_value=mock_response)
            monkeypatch.setattr("requests.get", mock_get)

            result = token_validator.validate_token_routine(token=token)

            assert result == validation_result

        
        def test_failed_validation_request_raises_unknown(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_validator: EarthDataTokenValidator
        ):
            """
            Q: What happens if the token validation network request raises an error without a returning a response?
            A: TokenValidationResult.UNKNOWN is returned.
            """
            from requests import RequestException
            mock_get = mocker.Mock(side_effect=RequestException)
            monkeypatch.setattr("requests.get", mock_get)
            token = "token123"

            result = token_validator.validate_token_routine(token=token)

            assert result == TokenValidationResult.UNKNOWN


    class TestValidateToken:

        def test_valid_token_returns_valid_result(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_validator: EarthDataTokenValidator
        ):
            """
            Q: What happens if a valid token is validated by an online Earthdata validation server?
            A: TokenValidationResult.VALID should be returned.
            """
            mock_validate = mocker.Mock(return_value=TokenValidationResult.VALID)
            monkeypatch.setattr(token_validator, "validate_token_routine", mock_validate)

            result = token_validator.validate_token(token="token123")

            assert result == TokenValidationResult.VALID
            mock_validate.assert_called_once_with("token123")

        def test_invalid_token_returns_invalid_result(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_validator: EarthDataTokenValidator
        ):
            """
            Q: What happens if a token is rejected by the Earthdata validation server?
            A: TokenValidationResult.INVALID should be returned.
            """
            mock_validate = mocker.Mock(return_value=TokenValidationResult.INVALID)
            monkeypatch.setattr(token_validator, "validate_token_routine", mock_validate)

            result = token_validator.validate_token(token="token123")

            assert result == TokenValidationResult.INVALID
            mock_validate.assert_called_once_with("token123")

        def test_unknown_validation_result_retries_until_success(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_validator: EarthDataTokenValidator
        ):
            """
            Q: What happens if the validation routine returns UNKNOWN because the API is temporarily unavailable?
            A: The method should retry until a terminal result is reached or the retry budget is exhausted.
            """
            mock_validate = mocker.Mock(
                side_effect=[
                    TokenValidationResult.UNKNOWN,
                    TokenValidationResult.UNKNOWN,
                    TokenValidationResult.VALID,
                ] # mock calls iterate through side effects list
            )
            sleep_mock = mocker.Mock()
            monkeypatch.setattr(token_validator, "validate_token_routine", mock_validate)
            monkeypatch.setattr("time.sleep", sleep_mock)
            monkeypatch.setattr("random.random", lambda: 0)

            result = token_validator.validate_token(token="token123")

            assert result == TokenValidationResult.VALID
            assert mock_validate.call_count == 3
            assert sleep_mock.call_count == 2

        def test_unknown_validation_result_after_retry_budget_is_exhausted_returns_unknown(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
        ):
            """
            Q: What happens if validation remains UNKNOWN after all allowed retries are exhausted?
            A: TokenValidationResult.UNKNOWN should be returned.
            """
            token_validator = EarthDataTokenValidator(max_attempts=3)
            mock_validate = mocker.Mock(return_value=TokenValidationResult.UNKNOWN)
            sleep_mock = mocker.Mock()
            monkeypatch.setattr(token_validator, "validate_token_routine", mock_validate)
            monkeypatch.setattr("time.sleep", sleep_mock)
            monkeypatch.setattr("random.random", lambda: 0)

            result = token_validator.validate_token(token="token123")

            assert result == TokenValidationResult.UNKNOWN
            assert mock_validate.call_count == 3
            assert sleep_mock.call_count == 2

        def test_validation_retry_waits_before_retrying(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
        ):
            """
            Q: How does the validator behave when a validation result is indeterminate and a retry is scheduled?
            A: The method should wait before retrying using its backoff policy.
            """
            token_validator = EarthDataTokenValidator(max_attempts=2)
            mock_validate = mocker.Mock(
                side_effect=[
                    TokenValidationResult.UNKNOWN,
                    TokenValidationResult.VALID,
                ]
            )
            sleep_mock = mocker.Mock()
            monkeypatch.setattr(token_validator, "validate_token_routine", mock_validate)
            monkeypatch.setattr("time.sleep", sleep_mock)
            monkeypatch.setattr("random.random", lambda: 0)

            result = token_validator.validate_token(token="token123")

            assert result == TokenValidationResult.VALID
            sleep_mock.assert_called_once()
            assert sleep_mock.call_args.args[0] > 0