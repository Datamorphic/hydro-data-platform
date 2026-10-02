import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values, load_dotenv
from minio import Minio

from nldas_ingestion.processes.authenticate_with_earthdata import (
    authenticate_with_earthdata,
)


@pytest.fixture
def e2e_minio_target(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Minio, str, str]]:
    
    config_path_value = os.getenv("HDP_CONFIG")
    if not config_path_value:
        pytest.fail("HDP_CONFIG must point to the E2E dotenv configuration file.")

    config_path = Path(config_path_value).expanduser().resolve()
    if not config_path.is_file():
        pytest.fail("HDP_CONFIG does not point to an existing configuration file.")

    load_dotenv(dotenv_path=config_path, override=False)
    config = dotenv_values(config_path)

    run_e2e = os.getenv("RUN_E2E_TESTS") or config.get("RUN_E2E_TESTS")
    if run_e2e != "1":
        pytest.skip("Set RUN_E2E_TESTS=1 in the environment or HDP_CONFIG to run live E2E tests.")

    earthdata_username = config.get("EARTHDATA_USERNAME")
    earthdata_password = config.get("EARTHDATA_PASSWORD")
    if not earthdata_username or not earthdata_password:
        pytest.fail("HDP_CONFIG must define Earthdata login credentials for E2E tests.")

    endpoint = os.getenv("MINIO_TEST_ENDPOINT") or config.get("MINIO_TEST_ENDPOINT")
    access_key = os.getenv("MINIO_TEST_ACCESS_KEY") or config.get("MINIO_TEST_ACCESS_KEY")
    secret_key = os.getenv("MINIO_TEST_SECRET_KEY") or config.get("MINIO_TEST_SECRET_KEY")
    if not endpoint or not access_key or not secret_key:
        pytest.fail("MINIO_TEST_ENDPOINT, MINIO_TEST_ACCESS_KEY, and MINIO_TEST_SECRET_KEY are required.")

    monkeypatch.setenv("HDP_CONFIG", str(config_path))
    monkeypatch.setenv("EARTHDATA_USERNAME", earthdata_username)
    monkeypatch.setenv("EARTHDATA_PASSWORD", earthdata_password)
    monkeypatch.setenv("OBJECT_STORE_ENDPOINT", endpoint)
    monkeypatch.setenv("OBJECT_STORE_ACCESS_KEY", access_key)
    monkeypatch.setenv("OBJECT_STORE_SECRET_KEY", secret_key)

    bucket_name = f"nldas-e2e-{uuid4().hex}"
    object_key = f"earthdata/token-{uuid4().hex}.json"

    minio_client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )
    bucket_created = False
    try:
        minio_client.make_bucket(bucket_name)
        bucket_created = True

        monkeypatch.setenv("EARTHDATA_TOKEN_BUCKET", bucket_name)
        monkeypatch.setenv("EARTHDATA_TOKEN_KEY", object_key)

        yield minio_client, bucket_name, object_key
    finally:
        if bucket_created:
            minio_client.remove_object(bucket_name, object_key)
            minio_client.remove_bucket(bucket_name)


@pytest.mark.e2e
def test_authenticates_with_earthdata_and_caches_token(
    e2e_minio_target: tuple[Minio, str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    minio_client, bucket_name, object_key = e2e_minio_target

    authenticate_with_earthdata()

    assert "Earthdata authentication succeeded." in capsys.readouterr().out
    object_size = minio_client.stat_object(bucket_name, object_key).size
    assert object_size is not None and object_size > 0