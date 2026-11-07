import json
import os
import sys
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

import pytest
from dotenv import dotenv_values, load_dotenv
from minio import Minio
from minio.deleteobjects import DeleteObject

import nldas_ingestion.processes.plan_nldas_download_jobs as process
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient


class E2EMinioTarget(TypedDict):
    client: Minio
    discovery_object_store: MinioObjectStore
    discovery_bucket_name: str
    discovery_report_key: str
    planning_object_store: MinioObjectStore
    planning_bucket_name: str
    raw_object_store: MinioObjectStore
    raw_bucket_name: str
    run_id: str


def destroy_bucket(minio_client: Minio, bucket_name: str) -> None:

    objects = minio_client.list_objects(bucket_name, recursive=True)
    
    delete_objects = [
        DeleteObject(name=obj.object_name)
        for obj in objects
        if obj.object_name is not None
    ]
    
    if delete_objects:
        delete_errors = list(
            minio_client.remove_objects(
                bucket_name=bucket_name,
                delete_object_list=delete_objects,
                bypass_governance_mode=True,
            )
        )
        
        if delete_errors:
            details = "; ".join(
                f"{error.name}: {error.message}" for error in delete_errors
            )
            raise RuntimeError(f"Failed to clean up E2E bucket objects: {details}")
    
    minio_client.remove_bucket(bucket_name)

@pytest.fixture
def e2e_minio_target(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[E2EMinioTarget]:
    """Provide an isolated real MinIO bucket for the opt-in planning E2E test."""
    config_path_value = os.getenv("HDP_CONFIG")
    if not config_path_value:
        if os.getenv("RUN_E2E_TESTS") == "1":
            pytest.fail("HDP_CONFIG must point to the E2E dotenv configuration file.")
        pytest.skip(
            "Set RUN_E2E_TESTS=1 and HDP_CONFIG to run the planning E2E test."
        )

    config_path = Path(config_path_value).expanduser().resolve()
    if not config_path.is_file():
        pytest.fail("HDP_CONFIG does not point to an existing configuration file.")

    config = dotenv_values(config_path)
    run_e2e = os.getenv("RUN_E2E_TESTS") or config.get("RUN_E2E_TESTS")
    if run_e2e != "1":
        pytest.skip(
            "Set RUN_E2E_TESTS=1 in the environment or HDP_CONFIG to run E2E tests."
        )

    pipeline_run_id = "abc123"
    endpoint = os.getenv("MINIO_TEST_ENDPOINT") or config.get("MINIO_TEST_ENDPOINT")
    access_key = os.getenv("MINIO_TEST_ACCESS_KEY") or config.get("MINIO_TEST_ACCESS_KEY")
    secret_key = os.getenv("MINIO_TEST_SECRET_KEY") or config.get("MINIO_TEST_SECRET_KEY")
    if not endpoint or not access_key or not secret_key:
        pytest.fail(
            "MINIO_TEST_ENDPOINT, MINIO_TEST_ACCESS_KEY, and "
            "MINIO_TEST_SECRET_KEY must be configured for E2E tests."
        )

    discovery_bucket_name = f"nldas-discover-e2e-{uuid4().hex}"
    planning_bucket_name = f"nldas-plan-e2e-{uuid4().hex}"
    raw_bucket_name = f"nldas-raw-e2e-{uuid4().hex}"

    discovery_report_key = f"nldas/run_{pipeline_run_id}/discovery_report.json"
    
    monkeypatch.setenv("HDP_CONFIG", str(config_path))
    monkeypatch.setenv("OBJECT_STORE_ENDPOINT", endpoint)
    monkeypatch.setenv("OBJECT_STORE_ACCESS_KEY", access_key)
    monkeypatch.setenv("OBJECT_STORE_SECRET_KEY", secret_key)
    monkeypatch.setenv("DISCOVERY_BUCKET", discovery_bucket_name)
    monkeypatch.setenv("PLANNING_BUCKET", planning_bucket_name)
    monkeypatch.setenv("RAW_STORAGE_BUCKET", raw_bucket_name)
    monkeypatch.setenv("PIPELINE_RUN_ID", pipeline_run_id)

    load_dotenv(dotenv_path=config_path, override=False)

    # TODO: Impose shorter timeout for when server is unavailable
    minio_client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )
    
    minio_client.make_bucket(discovery_bucket_name)
    minio_client.make_bucket(planning_bucket_name)
    minio_client.make_bucket(raw_bucket_name)
    
    discovery_object_store = MinioObjectStore(
        client=MinioStorageClient.from_client(minio_client),
        bucket_name=discovery_bucket_name,
    )
    
    planning_object_store = MinioObjectStore(
        client=MinioStorageClient.from_client(minio_client),
        bucket_name=planning_bucket_name,
    
    )

    raw_object_store = MinioObjectStore(
        client=MinioStorageClient.from_client(minio_client),
        bucket_name=raw_bucket_name,
    
    )

    try:
        yield {
            "client": minio_client,
            "discovery_object_store": discovery_object_store,
            "discovery_bucket_name": discovery_bucket_name,
            "discovery_report_key": discovery_report_key,
            "planning_object_store": planning_object_store,
            "planning_bucket_name": planning_bucket_name,
            "raw_object_store": raw_object_store,
            "raw_bucket_name": raw_bucket_name,
            "run_id": pipeline_run_id
        }
    finally:
        destroy_bucket(minio_client, discovery_bucket_name)
        destroy_bucket(minio_client, planning_bucket_name)
        destroy_bucket(minio_client, raw_bucket_name)


@pytest.mark.e2e
def test_plan_nldas_download_jobs_writes_partitioned_plan(
    e2e_minio_target: E2EMinioTarget,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Q: Does the complete planning process turn a stored discovery report and stored
    granule metadata into the correct spatially partitioned job-plan artifact?
    A: The real process reads both inputs from the isolated MinIO bucket, includes
    only new or newer granules, preserves discovery order, creates CA subset jobs,
    and writes one valid JSON plan to the `nldas/ca/` partition.
    """
    discovery_object_store = e2e_minio_target["discovery_object_store"]
    discovery_bucket_name = e2e_minio_target["discovery_bucket_name"]
    discovery_report_key = e2e_minio_target["discovery_report_key"]

    planning_object_store = e2e_minio_target["planning_object_store"]
    planning_bucket_name = e2e_minio_target["planning_bucket_name"]
    
    raw_object_store = e2e_minio_target["raw_object_store"]
    raw_bucket_name = e2e_minio_target["raw_bucket_name"]
    run_id = e2e_minio_target["run_id"]
    
    discovery_report = {
        "meta": {
            "provider_id": "NASA",
            "collection_id": "NLDAS",
            "discovered_at": "2026-10-05T00:00:00Z",
        },
        "granules": [
            {
                "granule_id": "granule-new",
                "granule_name": "new-granule.nc",
                "date_time": "2026-10-01T00:00:00Z",
                "version": "1",
                "last_updated_at": "2026-10-03T00:00:00Z",
                "spatial_extent": {
                    "north": 53.0,
                    "east": -67.0,
                    "south": 25.0,
                    "west": -125.0,
                },
                "access": {
                    "raw_url": "https://example.test/granule-new.nc",
                    "opendap_url": "https://example.test/granule-new",
                },
            },
            {
                "granule_id": "granule-updated",
                "granule_name": "updated-granule.nc",
                "date_time": "2026-10-02T00:00:00Z",
                "version": "2",
                "last_updated_at": "2026-10-04T00:00:00Z",
                "spatial_extent": {
                    "north": 53.0,
                    "east": -67.0,
                    "south": 25.0,
                    "west": -125.0,
                },
                "access": {
                    "raw_url": "https://example.test/granule-updated.nc",
                    "opendap_url": "https://example.test/granule-updated",
                },
            },
            {
                "granule_id": "granule-unchanged",
                "granule_name": "unchanged-granule.nc",
                "date_time": "2026-10-03T00:00:00Z",
                "version": "1",
                "last_updated_at": "2026-10-02T00:00:00Z",
                "spatial_extent": {
                    "north": 53.0,
                    "east": -67.0,
                    "south": 25.0,
                    "west": -125.0,
                },
                "access": {
                    "raw_url": "https://example.test/granule-unchanged.nc",
                    "opendap_url": "https://example.test/granule-unchanged",
                },
            },
            {
                "granule_id": "granule-older",
                "granule_name": "older-granule.nc",
                "date_time": "2026-10-04T00:00:00Z",
                "version": "1",
                "last_updated_at": "2026-10-01T00:00:00Z",
                "spatial_extent": {
                    "north": 53.0,
                    "east": -67.0,
                    "south": 25.0,
                    "west": -125.0,
                },
                "access": {
                    "raw_url": "https://example.test/granule-older.nc",
                    "opendap_url": "https://example.test/granule-older",
                },
            },
        ],
    }
    discovery_payload = json.dumps(discovery_report).encode("utf-8")
    discovery_object_store.put(
        key=discovery_report_key,
        data=discovery_payload,
        content_type="application/json",
    )

    stored_granules = [
        ("granule-updated", "2026-10-02T00:00:00Z"),
        ("granule-unchanged", "2026-10-02T00:00:00Z"),
        ("granule-older", "2026-10-02T00:00:00Z"),
    ]
    
    for granule_id, last_updated_at in stored_granules:
        raw_object_store.put(
            key=f"nldas/ca/{granule_id}.nc",
            data=b"test granule payload",
            content_type="application/x-netcdf",
            metadata={
                "granule_id": granule_id,
                "last_updated_at": last_updated_at,
            },
        )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "plan_nldas_download_jobs",
            "--startdtime",
            "2026-10-01T00:00:00Z",
            "--enddtime",
            "2026-10-05T00:00:00Z",
            "--spatial-subset",
            "ca",
            "--discovery-report-key",
            discovery_report_key,
        ],
    )


    process.plan_nldas_download_jobs()

    written_plans = planning_object_store.search(prefix=f"nldas/ca/run_{run_id}/job_plan")
    assert len(written_plans) == 1
    plan_object = written_plans[0]
    assert plan_object["bucket_name"] == planning_bucket_name
    # assert plan_object["object_name"].startswith("nldas/ca/nldas-job-plan_")
    # assert plan_object["object_name"].endswith(".json")
    assert plan_object["object_name"] == f"nldas/ca/run_{run_id}/job_plan.json"
    assert plan_object["metadata"]["artifact_type"] == "job-plan"

    plan_payload = planning_object_store.get(key=plan_object["object_name"])
    job_plan = json.loads(plan_payload)
    assert job_plan["spatial_extent"] == {
        "north": 42.002,
        "east": -114.131,
        "south": 32.534,
        "west": -124.41,
        "name": "ca",
    }
    assert [job["granule_id"] for job in job_plan["jobs"]] == [
        "granule-new",
        "granule-updated",
    ]
    assert all(job["subset"] is True for job in job_plan["jobs"])
    assert [job["base_url"] for job in job_plan["jobs"]] == [
        "https://example.test/granule-new",
        "https://example.test/granule-updated",
    ]
    assert all(
        job["subset_extent"]["name"] == "ca"
        for job in job_plan["jobs"]
    )
