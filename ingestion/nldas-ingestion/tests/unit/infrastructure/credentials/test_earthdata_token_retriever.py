import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock
import builtins
import os
from nldas_ingestion.infrastructure.credentials.earthdata_token_retriever import EarthDataTokenRetriever
import nldas_ingestion.infrastructure.credentials.exceptions as TokenError


@pytest.fixture
def token_retriever(mocker: MockerFixture) -> EarthDataTokenRetriever:
    return EarthDataTokenRetriever()

class TestEarthDataTokenRetriever:

    """
    Unit tests for the Earthdata token retriever class.
    """

    class TestRetrieveToken:

        # Happy Paths
        def test_valid_credentials_returns_valid_token(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):  
            """
            Q: What happens if valid earthdata login credentials exist in environment during token retrieval request?
            A: A valid earthdata token is returned with stripped whitespace.
            """
            expected_token = 'token123'
            mock_auth: Mock = mocker.Mock()
            mock_auth.token = {'access_token': expected_token}
            mock_login: Mock = mocker.Mock(return_value=mock_auth)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            result = token_retriever.retrieve_token()

            assert result == expected_token


        # Unhappy Paths (exceptions raised)
        def test_missing_earth_access_library_raises_token_configuration_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            token_retriever: EarthDataTokenRetriever):
            """
            Q: What happens if the required `earthaccess` library is not an importable module at runtime?
            A: TokenconfigurationError is raised.
            """
            _import = builtins.__import__

            def _import_earthaccess_raises(name, *args, **kwargs):
                if name == "earthaccess":
                    raise ImportError("earthaccess module is missing.")
                return _import(name, *args, **kwargs)
            
            monkeypatch.setattr(builtins, "__import__", _import_earthaccess_raises)
            
            with pytest.raises(TokenError.TokenConfigurationError):
                token_retriever.retrieve_token()


        def test_missing_credentials_raises_token_configuration_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            token_retriever: EarthDataTokenRetriever):
            """
            Q: What happens if login credentials, `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`, are missing environment variables?
            A: TokenConfigurationError is raised.
            """
            if os.environ.get("EARTHDATA_USERNAME") is not None:
                monkeypatch.delenv("EARTHDATA_USERNAME")

            if os.environ.get("EARTHDATA_PASSWORD") is not None:
                monkeypatch.delenv("EARTHDATA_PASSWORD")

            with pytest.raises(TokenError.TokenConfigurationError):
                token_retriever.retrieve_token()


        def test_invalid_credentials_raises_token_configuration_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever):
            """
            Q: What happens if the earthdata login credentials are invalid?
            A: TokenConfigurationError is raised.
            """
            from earthaccess.exceptions import LoginAttemptFailure
            mock_login = mocker.Mock()
            mock_login.side_effect = LoginAttemptFailure
            monkeypatch.setattr(
                "earthaccess.login",
                mock_login
            )
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")
            
            with pytest.raises(TokenError.TokenConfigurationError):
                token_retriever.retrieve_token()

            mock_login.assert_called_once()

        
        def test_unexpected_server_login_error_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):                        
            """
            Q: What happens if requests to Earthdata servers fail unexpectedly?
            A: TokenServiceUnavailableError is raised.
            """
            UnexpectedServerError = RuntimeError
            mock_login = mocker.Mock(side_effect=UnexpectedServerError)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")            

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()
            

        def test_empty_login_response_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            token_retriever: EarthDataTokenRetriever
            ):                
            """
            Q: What happens if the earthaccess login procedure returns an empty token response instead of `Mapping[str, str]`?
            A: TokenServiceUnavailableError is raised.
            """
            
            monkeypatch.setattr("earthaccess.login", None)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()

        def test_token_missing_from_login_response_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):         
            """
            Q: What happens if the earthaccess login response is missing the required `access_token` attribute?
            A: TokenServiceUnavailableError is raised.
            """
            mock_auth: Mock = mocker.Mock()
            mock_auth.token = None
            mock_login: Mock = mocker.Mock(return_value=mock_auth)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()

        def test_invalid_access_token_type_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):      
            """
            Q: What happens if the earthaccess login request returns a response with an non string `access_token` attribute?
            A: TokenServiceUnavailable is raised.
            """
            mock_auth: Mock = mocker.Mock()
            mock_auth.token = {'access_token': 123}
            mock_login: Mock = mocker.Mock(return_value=mock_auth)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()            

        def test_missing_access_token_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):  
            """
            Q: What happens if the earthaccess login response token is missing an `access_token` attribute to contain the token?
            A: TokenServiceUnavailable is raised.
            """
            mock_auth: Mock = mocker.Mock()
            mock_auth.token = {'access_token': None}
            mock_login: Mock = mocker.Mock(return_value=mock_auth)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()

        def test_empty_string_access_token_raises_token_service_unavailable_error(
            self,
            monkeypatch: pytest.MonkeyPatch,
            mocker: MockerFixture,
            token_retriever: EarthDataTokenRetriever
            ):  
            """
            Q: What happens if the earthaccess login response token `access_token` attribute only contains whitespace?
            A: TokenServiceUnavailable is raised.
            """
            mock_auth: Mock = mocker.Mock()
            mock_auth.token = {'access_token': '   '}
            mock_login: Mock = mocker.Mock(return_value=mock_auth)
            monkeypatch.setattr("earthaccess.login", mock_login)
            monkeypatch.setenv("EARTHDATA_USERNAME","USERNAME")
            monkeypatch.setenv("EARTHDATA_PASSWORD","PASSWORD")

            with pytest.raises(TokenError.TokenServiceUnavailableError):
                token_retriever.retrieve_token()