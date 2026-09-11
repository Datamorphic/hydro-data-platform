from pathlib import Path
import json
import earthaccess
import pytest
import requests
from pytest_mock import MockerFixture
from json import JSONDecodeError

import nldas_ingestion.credential_manager as credential_manager_module
from nldas_ingestion.credential_manager import (
    CredentialManager,
    CredentialManagerError,
    CredentialConfigurationError,
    TokenCacheMissingError,
    TokenCacheError,
    TokenAcquisitionError,
    TokenValidationResult,
)


@pytest.fixture
def manager(tmp_path: Path) -> CredentialManager:
    return CredentialManager(token_filepath=tmp_path / "token.json")


class TestCredentialManager:

    class TestResolvePath:

        @pytest.fixture
        def fake_project_root(self, tmp_path: Path):
            project_root = tmp_path / "project"
            project_root.mkdir()
            return project_root

        def test_relative_path_with_parent_toml(self, manager: CredentialManager, monkeypatch, fake_project_root: Path):
            # Arrange
            filepath = "path/to/file.json"
            (fake_project_root / "pyproject.toml").touch()
            fake_module_file = fake_project_root / "src" / "nldas_ingestion" / "credential_manager.py"
            fake_module_file.parent.mkdir(parents=True)

            monkeypatch.setattr(
                credential_manager_module,
                "__file__",
                str(fake_module_file),
            )

            # Act
            result = manager._resolve_path(filepath)

            # Assert
            assert result == fake_project_root / filepath

        def test_relative_path_without_parent_toml(self, manager: CredentialManager, monkeypatch, fake_project_root: Path):
            # Arrange
            filepath = "path/to/file.json"
            fake_module_file = fake_project_root / "src" / "nldas_ingestion" / "credential_manager.py"
            fake_module_file.parent.mkdir(parents=True)

            monkeypatch.setattr(
                credential_manager_module,
                "__file__",
                str(fake_module_file),
            )

            monkeypatch.chdir(fake_project_root)

            # Act
            result = manager._resolve_path(filepath)

            # Assert
            assert result == fake_project_root / filepath

        def test_invalid_input_type(self, manager: CredentialManager):
            with pytest.raises(TypeError):
                manager._resolve_path(1)  # type: ignore[arg-type]

        def test_absolute_path(self, manager: CredentialManager):
            filepath = "C:/Users/User/project_root/secrets/file.json"

            result = manager._resolve_path(filepath)

            assert result == Path(filepath)

    class TestReadCachedToken:

        @pytest.fixture
        def token_folder(self, tmp_path: Path) -> Path:
            folder = tmp_path / "secrets"
            folder.mkdir()
            return folder

        class UnexpectedJsonLoadError(RuntimeError):
            pass

        def test_missing_file_exception(self, manager: CredentialManager, token_folder: Path):            
            manager._token_filepath = token_folder / "token.json"

            with pytest.raises(TokenCacheMissingError):
                manager._read_cached_token()

        def test_non_json_file_exception(self, manager: CredentialManager, token_folder: Path):
            manager._token_filepath = token_folder / "token.txt"
            manager._token_filepath.touch()

            with pytest.raises(TokenCacheError):
                manager._read_cached_token()

        def test_json_os_error(self, manager: CredentialManager, token_folder: Path, mocker: MockerFixture):
            manager._token_filepath = token_folder / "token.json"
            manager._token_filepath.touch()
            mock_json_load = mocker.patch("nldas_ingestion.credential_manager.json.load")
            mock_json_load.side_effect = OSError()
            
            with pytest.raises(TokenCacheError) as raised:
                manager._read_cached_token()

            assert isinstance(raised.value.__cause__, OSError)
            opened_file = mock_json_load.call_args.args[0]
            mock_json_load.assert_called_once()
            assert opened_file.name == str(manager._token_filepath)
            assert opened_file.mode == "r"

        def test_json_decode_error(self, manager: CredentialManager, token_folder: Path, mocker: MockerFixture):
            manager._token_filepath = token_folder / "token.json"
            manager._token_filepath.touch()
            mock_json_load = mocker.patch("nldas_ingestion.credential_manager.json.load")
            mock_json_load.side_effect = JSONDecodeError("","",0)
            
            with pytest.raises(TokenCacheError) as raised:
                manager._read_cached_token()

            assert isinstance(raised.value.__cause__,JSONDecodeError)
            mock_json_load.assert_called_once()

        def test_unexpected_json_load_exception(self, manager: CredentialManager, token_folder: Path, mocker: MockerFixture):
            """How 'SUT' handles errors other than OSError and josn.JSONDecodeError caused by json.load()"""
            manager._token_filepath = token_folder / "token.json"
            manager._token_filepath.touch()
            mock_json_load = mocker.patch("nldas_ingestion.credential_manager.json.load")
            mock_json_load.side_effect = self.UnexpectedJsonLoadError()
            
            with pytest.raises(TokenCacheError) as raised:
                manager._read_cached_token()

            assert isinstance(raised.value.__cause__, self.UnexpectedJsonLoadError)
            mock_json_load.assert_called_once()

        def test_invalid_type_for_cached_token_exception(self, manager: CredentialManager, token_folder: Path, mocker: MockerFixture):
            """Catches non string tokens as an exception"""

            manager._token_filepath = token_folder / "token.json"
            manager._token_filepath.touch()
            mock_json_load = mocker.patch("nldas_ingestion.credential_manager.json.load")
            mock_json_load.return_value = {"access_token": 1234}

            with pytest.raises(TokenCacheError) as raised:
                manager._read_cached_token()

            assert isinstance(raised.value, TokenCacheError)
            assert raised.value.__cause__ is None
            mock_json_load.assert_called_once()

        @pytest.mark.parametrize(
            "payload",
            [
                {},
                {"access_token": None},
                {"access_token": 1234},
                {"access_token": ""},
                {"access_token": "   "},
                [],
                "token",
            ],
        )
        def test_invalid_cached_token_payloads(self, manager: CredentialManager, payload):
            manager._token_filepath.write_text(json.dumps(payload), encoding="utf-8")

            with pytest.raises(TokenCacheError):
                manager.get_cached_token()

        def test_valid_cached_token_is_read_and_stripped(self, manager: CredentialManager):
            manager._token_filepath.write_text(
                '{"access_token": "  Y123ZX70  "}', encoding="utf-8"
            )

            assert manager.get_cached_token() == "Y123ZX70"

    class TestWriteCachedToken:
        def test_writes_json_and_creates_parent_directory(self, manager: CredentialManager):
            manager._token_filepath = manager._token_filepath.parent / "nested" / "token.json"

            manager.update_cached_token("Y123ZX70")

            assert json.loads(manager._token_filepath.read_text(encoding="utf-8")) == {
                "token_type": "Bearer",
                "access_token": "Y123ZX70",
            }
            assert not list(manager._token_filepath.parent.glob("*.tmp"))

        def test_replace_failure_is_wrapped_and_temporary_file_removed(
            self, manager: CredentialManager, mocker: MockerFixture
        ):
            replace = mocker.patch(
                "nldas_ingestion.credential_manager.os.replace",
                side_effect=OSError("replace failed"),
            )

            with pytest.raises(TokenCacheError) as raised:
                manager.update_cached_token("Y123ZX70")

            assert isinstance(raised.value.__cause__, OSError)
            replace.assert_called_once()
            assert not list(manager._token_filepath.parent.glob("*.tmp"))

        def test_permission_failure_does_not_prevent_replacement(
            self, manager: CredentialManager, mocker: MockerFixture
        ):
            mocker.patch(
                "nldas_ingestion.credential_manager.os.chmod",
                side_effect=OSError("chmod unsupported"),
            )

            manager.update_cached_token("Y123ZX70")

            assert manager.get_cached_token() == "Y123ZX70"

    class TestValidateTokenInternal:
        @pytest.mark.parametrize(
            ("status_code", "expected"),
            [
                (200, TokenValidationResult.VALID),
                (401, TokenValidationResult.INVALID),
                (403, TokenValidationResult.INVALID),
                (404, TokenValidationResult.UNKNOWN),
                (500, TokenValidationResult.UNKNOWN),
            ],
        )
        def test_status_codes(self, manager: CredentialManager, mocker: MockerFixture, status_code, expected):
            response = mocker.Mock(status_code=status_code)
            request = mocker.patch.object(requests, "get", return_value=response)

            assert manager._validate_token("token") is expected
            request.assert_called_once_with(
                manager._validation_url,
                params={"page_size": 1},
                headers={
                    "Authorization": "Bearer token",
                    "Accept": "application/json",
                },
                timeout=manager._request_timeout,
            )

        def test_request_failure_returns_unknown(self, manager: CredentialManager, mocker: MockerFixture):
            mocker.patch.object(requests, "get", side_effect=requests.RequestException)

            assert manager._validate_token("token") is TokenValidationResult.UNKNOWN

    class TestGetNewTokenViaLogin:
        def test_missing_credentials(self, monkeypatch):
            monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
            monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)

            with pytest.raises(CredentialConfigurationError):
                CredentialManager._get_new_token_via_login()

        def test_missing_one_credential(self, monkeypatch):
            monkeypatch.setenv("EARTHDATA_USERNAME", "user")
            monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)

            with pytest.raises(CredentialConfigurationError, match="EARTHDATA_PASSWORD"):
                CredentialManager._get_new_token_via_login()

        def test_successful_login_strips_token(self, monkeypatch, mocker: MockerFixture):
            monkeypatch.setenv("EARTHDATA_USERNAME", "user")
            monkeypatch.setenv("EARTHDATA_PASSWORD", "password")
            login = mocker.patch.object(
                earthaccess,
                "login",
                return_value=mocker.Mock(token={"access_token": "  token  "}),
            )

            assert CredentialManager._get_new_token_via_login() == "token"
            login.assert_called_once_with(strategy="environment")

        @pytest.mark.parametrize("token", [None, "", "   ", 1234])
        def test_login_without_usable_token(self, monkeypatch, mocker: MockerFixture, token):
            monkeypatch.setenv("EARTHDATA_USERNAME", "user")
            monkeypatch.setenv("EARTHDATA_PASSWORD", "password")
            mocker.patch.object(
                earthaccess,
                "login",
                return_value=mocker.Mock(token={"access_token": token}),
            )

            with pytest.raises(TokenAcquisitionError):
                CredentialManager._get_new_token_via_login()

        def test_login_failure_is_wrapped(self, monkeypatch, mocker: MockerFixture):
            monkeypatch.setenv("EARTHDATA_USERNAME", "user")
            monkeypatch.setenv("EARTHDATA_PASSWORD", "password")
            mocker.patch.object(
                earthaccess, "login", side_effect=RuntimeError("network error")
            )

            with pytest.raises(TokenAcquisitionError) as raised:
                CredentialManager._get_new_token_via_login()

            assert isinstance(raised.value.__cause__, RuntimeError)

    class TestValidateTokenPublic:
        def test_valid_token_does_not_retry(self, manager: CredentialManager, mocker: MockerFixture):
            validate = mocker.patch.object(
                manager, "_validate_token", return_value=TokenValidationResult.VALID
            )
            sleep = mocker.Mock()
            manager._sleep = sleep

            assert manager.validate_token("token") is TokenValidationResult.VALID
            validate.assert_called_once_with("token")
            sleep.assert_not_called()

        def test_invalid_token_does_not_retry(self, manager: CredentialManager, mocker: MockerFixture):
            validate = mocker.patch.object(
                manager, "_validate_token", return_value=TokenValidationResult.INVALID
            )

            assert manager.validate_token("token") is TokenValidationResult.INVALID
            validate.assert_called_once_with("token")

        def test_unknown_retries_with_exponential_backoff_and_jitter(self, manager: CredentialManager, mocker: MockerFixture):
            manager._max_validation_attempts = 3
            manager._random_value = lambda: 0.0
            validate = mocker.patch.object(
                manager, "_validate_token", return_value=TokenValidationResult.UNKNOWN
            )
            sleep = mocker.Mock()
            manager._sleep = sleep

            assert manager.validate_token("token") is TokenValidationResult.UNKNOWN
            assert validate.call_count == 3
            assert [call.args[0] for call in sleep.call_args_list] == [0.5, 1.0]

        def test_unknown_stops_when_later_attempt_succeeds(self, manager: CredentialManager, mocker: MockerFixture):
            manager._max_validation_attempts = 3
            manager._random_value = lambda: 0.0
            validate = mocker.patch.object(
                manager,
                "_validate_token",
                side_effect=[TokenValidationResult.UNKNOWN, TokenValidationResult.VALID],
            )
            sleep = mocker.Mock()
            manager._sleep = sleep

            assert manager.validate_token("token") is TokenValidationResult.VALID
            assert validate.call_count == 2
            sleep.assert_called_once_with(0.5)
            
        