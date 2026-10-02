import os, dotenv
from pathlib import Path
from collections.abc import Iterator

from uuid import uuid4
from unittest.mock import Mock

import pytest
from minio import Minio

from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_store import (
    EarthDataTokenStore,
)
from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_provider import (
    EarthDataTokenProvider,
)
from nldas_ingestion.infrastructure.earthdata.auth.exceptions import (
    TokenCacheMissingError,
)
from nldas_ingestion.infrastructure.earthdata.auth.protocols import (
    TokenRetriever,
    TokenValidationResult,
    TokenValidator,
)
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient

# Environment Setup
env_path = os.getenv("HDP_CONFIG")
if not env_path:
        raise RuntimeError(f"Missing required environment variable `HDP_CONFIG`. Can not load settings.")

env_path = Path(env_path)
if not env_path.exists():
    raise RuntimeError(f"Configuration settings do not exist at path specified by environment variable `HDP_CONFIG`.")

dotenv.load_dotenv(dotenv_path=env_path) 


@pytest.fixture
def minio_token_store() -> Iterator[EarthDataTokenStore]:
   
    endpoint = os.getenv("MINIO_TEST_ENDPOINT")
    access_key = os.getenv("MINIO_TEST_ACCESS_KEY")
    secret_key = os.getenv("MINIO_TEST_SECRET_KEY")
    bucket_name = f"nldas-it-{uuid4().hex}"
    object_key = "credentials/earthdata/token.json"
    if endpoint is None or access_key is None or secret_key is None:
        pytest.skip(
            "Set MINIO_TEST_ENDPOINT, MINIO_TEST_ACCESS_KEY, and "
            "MINIO_TEST_SECRET_KEY to run MinIO integration tests."
        )

    try:
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        client.make_bucket(bucket_name)

        token_store = EarthDataTokenStore(
            object_store=MinioObjectStore(
                client=MinioStorageClient(
                    endpoint=endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                ),
                bucket_name=bucket_name,
            ),
            object_key=object_key,
        )
        yield token_store
    finally:
        client.remove_object(bucket_name, object_key)
        client.remove_bucket(bucket_name)


def test_token_store_round_trips_token_through_minio(
    minio_token_store: EarthDataTokenStore,
) -> None:
    token = "integration-test-token"

    with pytest.raises(TokenCacheMissingError):
        minio_token_store.get_token()

    minio_token_store.put_token(token)

    assert minio_token_store.get_token() == token


def test_provider_reuses_token_persisted_in_minio(
    minio_token_store: EarthDataTokenStore,
) -> None:
    token = "integration-test-provider-token"
    first_retriever = Mock(spec=TokenRetriever)
    first_retriever.retrieve_token.return_value = token
    first_validator = Mock(spec=TokenValidator)

    first_provider = EarthDataTokenProvider(
        token_store=minio_token_store,
        token_validator=first_validator,
        token_retriever=first_retriever,
    )

    assert first_provider.get_token() == token
    first_retriever.retrieve_token.assert_called_once_with()
    first_validator.validate_token.assert_not_called()

    second_validator = Mock(spec=TokenValidator)
    second_validator.validate_token.return_value = TokenValidationResult.VALID
    second_retriever = Mock(spec=TokenRetriever)
    second_provider = EarthDataTokenProvider(
        token_store=minio_token_store,
        token_validator=second_validator,
        token_retriever=second_retriever,
    )

    assert second_provider.get_token() == token
    second_validator.validate_token.assert_called_once_with(token)
    second_retriever.retrieve_token.assert_not_called()