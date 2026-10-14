import os
import pytest
from dotenv import dotenv_values, load_dotenv
from pathlib import Path
from uuid import uuid4
from typing import (Iterator, cast)
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

import urllib3

import nldas_ingestion.processes.discover_nldas_granules as main
import nldas_ingestion.infrastructure.config.settings as progset
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient

def minio_server_is_active(
    client: Minio
) -> bool:

    try:
        # We look for a random bucket name; we only care if the server responds,
        # not whether the bucket actually exists.
        client.bucket_exists("probe-connection-bucket-xyz")
        return True
    except S3Error as e:
        # If S3Error is raised (like 403 Forbidden or 404 Not Found), 
        # the server IS online and responding to API requests.
        return True
    except urllib3.exceptions.MaxRetryError:
        # print("Server is offline or the endpoint URL is incorrect.")
        return False
    except Exception as e:
        # print(f"Connection failed due to an unexpected error: {e}")
        return False


@pytest.fixture
def object_store(
    monkeypatch: pytest.MonkeyPatch
) -> Iterator[MinioObjectStore]:

    progset.load_dotenv_config()

    if os.getenv("RUN_E2E_TESTS") != "1":
        pytest.skip("Set `RUN_E2E_TESTS=1` in the environment to run live E2E tests.")

    settings = progset.load_settings()
    endpoint = progset.get_required_env_var("MINIO_TEST_ENDPOINT")
    access_key = progset.get_required_env_var("MINIO_TEST_ACCESS_KEY")
    secret_key = progset.get_required_env_var("MINIO_TEST_SECRET_KEY")

    monkeypatch.setenv("OBJECT_STORE_ENDPOINT", endpoint)
    monkeypatch.setenv("OBJECT_STORE_ACCESS_KEY", access_key)
    monkeypatch.setenv("OBJECT_STORE_SECRET_KEY", secret_key)

    bucket_name = f"discovery-{uuid4().hex}"

    minio_client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False
    )

    # Test connection to Object Store Server
    if not minio_server_is_active(minio_client):
        raise RuntimeError(
            "Minio Object Server is offline or not responsive, cannot perform E2E test"
        )

    bucket_created = False
    try:
        minio_client.make_bucket(bucket_name)
        bucket_created=True
        storage_client = MinioStorageClient.from_client(minio_client)
        yield MinioObjectStore(
            client=storage_client,
            bucket_name=bucket_name
        )
    except Exception as exc:
        raise RuntimeError("Minio client failed unexpectedly, check server.") from exc
    finally:
        if bucket_created:
            
            objects_to_delete = minio_client.list_objects(
                bucket_name=bucket_name,
                recursive=True
            )

            delete_list = [
                DeleteObject(name=cast(str, obj.object_name))
                for obj in objects_to_delete
            ]

            if delete_list:
                delete_errors = minio_client.remove_objects(
                    bucket_name=bucket_name,
                    delete_object_list=delete_list,
                    bypass_governance_mode=True
                )

                delete_error_messages = []
                for delete_error in delete_errors:
                    delete_error_messages.append(
                        f"{cast(str, delete_error)}: {delete_error.message}"
                    )

                if delete_error_messages:
                    raise ValueError(f'Error deleting objects:\n {"\n".join(delete_error_messages)}')                

            minio_client.remove_bucket(bucket_name)
        
        print("Completed Fixture")


def test_e2e_discover_nldas_granules(
    monkeypatch: pytest.MonkeyPatch,
    object_store: Iterator[MinioObjectStore]
):
    monkeypatch.setattr(
        main,"build_object_store", 
        lambda settings: object_store
    )

    main.discover_nldas_granules()

    assert True

