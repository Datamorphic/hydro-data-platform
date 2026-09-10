from pathlib import Path
import pytest
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
    EarthdataUnavailableError
)


@pytest.fixture
def manager() -> CredentialManager:
    return CredentialManager()


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

            monkeypatch.setattr(
                Path,
                "cwd",
                classmethod(lambda cls: fake_project_root)
            )

            # Act
            result = manager._resolve_path(filepath)

            # Assert
            assert result == fake_project_root / filepath

        def test_invalid_input_type(self, manager: CredentialManager):
            with pytest.raises(TypeError):
                manager._resolve_path(1)

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

        def test_valid_cached_token_success(self, manager: CredentialManager, token_folder: Path, mocker: MockerFixture):
            manager._token_filepath = token_folder / "token.json"
            manager._token_filepath.touch()
            mock_json_load = mocker.patch("nldas_ingestion.credential_manager.json.load")
            mock_json_load.return_value = {"access_token": "Y123ZX70"}

            result = manager._read_cached_token()

            mock_json_load.assert_called_once()
            assert result == mock_json_load.return_value.get("access_token")

    class TestWriteCachedToken:
        ...

    class TestValidateTokenInternal:
        ...

    class TestGetNewTokenViaLogin:
        ...

    class TestValidateTokenPublic:
        ...
            
        