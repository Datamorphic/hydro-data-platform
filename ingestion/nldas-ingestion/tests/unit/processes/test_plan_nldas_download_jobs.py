import sys
from datetime import datetime, timedelta
from typing import Optional, List

import pytest
from pytest_mock import MockerFixture
from unittest.mock import call

import nldas_ingestion.domain.artifacts as dom
import nldas_ingestion.infrastructure.config.settings as progset
import nldas_ingestion.infrastructure.planning.nldas_job_planner as plan
import nldas_ingestion.infrastructure.storage.protocols as sproto
import nldas_ingestion.processes.plan_nldas_download_jobs as process
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore


@pytest.fixture
def settings() -> progset.Settings:
    return progset.Settings(
        run_id="abc123",
        object_store_endpoint="localhost:9000",
        object_store_access_key="test-access",
        object_store_secret_key="test-secret",
        earthdata_username="test-user",
        earthdata_password="test-password",
        earthdata_token_bucket="tokens",
        earthdata_token_key="credentials/token.json",
        discovery_bucket="discovery",
        planning_bucket="planning",
        raw_storage_bucket="raw-data",
    )


@pytest.fixture
def sample_granules() -> list[dom.Granule]:
    return [
        dom.Granule(
            granule_id=f"granule-{index}",
            granule_name=f"NLDAS granule {index}",
            date_time=datetime(2026, 10, index, 0, 0, 0),
            version="1",
            last_updated_at=datetime(2026, 10, index, 1, 0, 0),
            spatial_extent=dom.SpatialExtent(
                north=53.0,
                east=-67.0,
                south=25.0,
                west=-125.0,
            ),
            access=dom.GranuleAccess(
                raw_url=f"https://example.test/granule-{index}.nc",
                opendap_url=f"https://example.test/granule-{index}",
            ),
        )
        for index in range(1, 4)
    ]


class TestBuildObjectStore:
    @pytest.mark.parametrize(("bucket_exists", "expected_make_bucket_calls"), [(True, 0), (False, 3)])
    def test_builds_store_using_planning_bucket(
        self,
        mocker: MockerFixture,
        settings: progset.Settings,
        bucket_exists: bool,
        expected_make_bucket_calls: int,
    ) -> None:
        """
        Q: How does the process build its object-store adapter?
        A: Build a MinIO adapter using the configured connection and planning bucket,
        creating that bucket only when it does not already exist.
        """
        storage_client = mocker.Mock()
        storage_client._mio.bucket_exists.return_value = bucket_exists
        storage_client_factory = mocker.patch.object(
            process,
            "MinioStorageClient",
            return_value=storage_client,
        )

        result = process.build_object_stores(settings)

        storage_client_factory.assert_called_with(
            endpoint=settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key,
        )

        storage_client._mio.bucket_exists.assert_has_calls(
            [
                call(settings.discovery_bucket),
                call(settings.planning_bucket),
                call(settings.raw_storage_bucket)
            ]
        )
        
        assert storage_client._mio.make_bucket.call_count == expected_make_bucket_calls
        
        if not bucket_exists:
            storage_client._mio.make_bucket.assert_has_calls(
                [
                    call(settings.discovery_bucket),
                    call(settings.planning_bucket),
                    call(settings.raw_storage_bucket),
                ]
            )
    
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all([isinstance(r, MinioObjectStore) for r in result])
        assert all([r._client is storage_client for r in result])
        assert result[0]._bucket_name == settings.discovery_bucket
        assert result[1]._bucket_name == settings.planning_bucket
        assert result[2]._bucket_name == settings.raw_storage_bucket

    def test_bucket_creation_failure_is_propagated(
        self,
        mocker: MockerFixture,
        settings: progset.Settings,
    ) -> None:
        """
        Q: What happens when the planning bucket cannot be created?
        A: Propagate the object-store client's original exception.
        """
        storage_client = mocker.Mock()
        storage_client._mio.bucket_exists.return_value = False
        storage_error = OSError("bucket creation failed")
        storage_client._mio.make_bucket.side_effect = storage_error
        mocker.patch.object(process, "MinioStorageClient", return_value=storage_client)

        with pytest.raises(OSError, match="bucket creation failed") as exc_info:
            process.build_object_stores(settings)

        assert exc_info.value is storage_error


class TestLoadInputArguments:
    def test_explicit_date_arguments_are_parsed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Q: How are explicit start and end date arguments returned?
        A: Return the supplied values under `startdtime` and `enddtime`.
        """
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "plan_nldas_download_jobs",
                "--startdtime",
                "2026-10-01T00:00:00Z",
                "--enddtime",
                "2026-10-02T00:00:00Z",
                "--spatial-subset",
                "ca",
                "--discovery-report-key",
                "reports/discovery.json",
            ],
        )

        result = process.load_input_arguments()

        assert result == {
            "startdtime": "2026-10-01T00:00:00Z",
            "enddtime": "2026-10-02T00:00:00Z",
            "spatial_subset": "ca",
            "discovery_report_key": "reports/discovery.json",
        }

    def test_default_date_range_is_recent_and_ordered(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Q: What date range is used when no date arguments are supplied?
        A: Return a valid default interval with start before end and a duration of
        23 hours, 59 minutes, and 59 seconds.
        """
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "plan_nldas_download_jobs",
                "--discovery-report-key",
                "reports/discovery.json",
            ],
        )

        result = process.load_input_arguments()
        start = datetime.strptime(result["startdtime"], process.DTFORMAT)
        end = datetime.strptime(result["enddtime"], process.DTFORMAT)

        assert start < end
        assert end - start == timedelta(hours=23, minutes=59, seconds=59)
        assert result["spatial_subset"] == "conus"


class TestGetSpatialSubsetFromName:
    @pytest.mark.parametrize(
        ("name", "expected_extent"),
        [
            ("conus", None),
            (
                "ca",
                dom.SpatialExtent(
                    name="ca",
                    north=42.002,
                    west=-124.410,
                    south=32.534,
                    east=-114.131,
                ),
            ),
            (
                "sd",
                dom.SpatialExtent(
                    name="sd",
                    north=33.505,
                    west=-117.83,
                    south=32.529,
                    east=-116.081,
                ),
            ),
        ],
    )
    def test_supported_names_return_their_spatial_extent(
        self,
        name: str,
        expected_extent: Optional[dom.SpatialExtent],
    ) -> None:
        """
        Q: What spatial extent is selected for each supported name?
        A: `conus` selects no subset, while `ca` and `sd` return their named bounds.
        """
        assert process.get_spatial_subset_from_name(name) == expected_extent

    def test_unsupported_name_raises_value_error(self) -> None:
        """
        Q: What happens when the requested spatial subset name is unsupported?
        A: Raise ValueError explaining the supported names.
        """
        with pytest.raises(ValueError, match="conus.*ca.*sd"):
            process.get_spatial_subset_from_name("unknown")


class TestPlanNldasDownloadJobs:
    @pytest.fixture
    def workflow(self, 
        mocker: MockerFixture, 
        sample_granules: list[dom.Granule]
    ):
        run_id = "abc123"
        spatial_extent = dom.SpatialExtent(
            name='ca',
            north=42.002, west=-124.410, 
            south=32.534, east=-114.131
        )
        
        settings = mocker.Mock(spec=progset.Settings)
        settings.run_id = run_id
        discovery_object_store = mocker.Mock(spec=sproto.ObjectStore)
        planning_object_store = mocker.Mock(spec=sproto.ObjectStore)
        raw_object_store = mocker.Mock(spec=sproto.ObjectStore)
        
        report = dom.DiscoveryReport(
            meta=dom.DiscoveryMeta(
                provider_id="NASA",
                collection_id="NLDAS",
                discovered_at=datetime(2026, 10, 5),
            ),
            granules=sample_granules,
        )

        mocker.patch.object(process.progset, "load_dotenv_config")
        
        mocker.patch.object(process.progset, "load_settings", return_value=settings)
        
        mocker.patch.object(
            process,
            "load_input_arguments",
            return_value={
                "startdtime": "2026-10-01T00:00:00Z",
                "enddtime": "2026-10-05T00:00:00Z",
                "spatial_subset": "ca",
                "discovery_report_key": "reports/discovery.json",
            },
        )
        
        mocker.patch.object(process, "build_object_stores", 
            return_value=(
                discovery_object_store,
                planning_object_store,
                raw_object_store
            )
        )

        mocker.patch.object(
            process,
            "get_spatial_subset_from_name",
            return_value=spatial_extent
        )
        
        mocker.patch.object(
            process.plan,
            "load_discovery_report_from_object_store",
            return_value=report,
        )
        
        discovered_table = mocker.sentinel.discovered_table
        stored_table = mocker.sentinel.stored_table
        
        mocker.patch.object(
            process.plan,
            "create_granules_table_from_discovery_report",
            return_value=discovered_table,
        )

        mocker.patch.object(
            process.plan,
            "get_granules_table_from_object_store",
            return_value=stored_table,
        )

        new_table = mocker.Mock()
        new_table.__getitem__ = mocker.Mock(return_value=[2, 0])
        
        mocker.patch.object(
            process.plan,
            "identify_new_granules",
            return_value=new_table,
        )

        job = mocker.sentinel.job

        create_job = mocker.patch.object(
            process.plan,
            "create_download_job",
            return_value=job,
        )
        
        job_plan = mocker.sentinel.job_plan

        write_job = mocker.patch.object(
            process.plan,
            "write_download_job_to_object_store",
        )

        create_plan = mocker.patch.object(
            process.plan,
            "create_download_job_plan",
            return_value=job_plan,
        )
        
        write_plan = mocker.patch.object(
            process.plan,
            "write_download_job_plan_to_object_store",
        )

        return {
            "settings": settings,
            "discovery_object_store": discovery_object_store,
            "planning_object_store": planning_object_store,
            "raw_object_store": raw_object_store,
            "report": report,
            "discovered_table": discovered_table,
            "stored_table": stored_table,
            "new_table": new_table,
            "create_job": create_job,
            "spatial_extent": spatial_extent,
            "run_id": run_id,
            "job": job,
            "write_job": write_job,
            "create_plan": create_plan,
            "job_plan": job_plan,
            "write_plan": write_plan,

        }

    def test_orchestrates_plan_for_selected_granules(
        self,
        mocker: MockerFixture,
        workflow,
        sample_granules: list[dom.Granule],
    ) -> None:
        """
        Q: How does the process coordinate planning for qualifying granules?
        A: Load the report and stored table, identify new rows, map discovery IDs
        back to report granules, create jobs for the CA subset, and write the plan.
        """
        process.plan_nldas_download_jobs()

        process.progset.load_dotenv_config.assert_called_once_with()
        process.progset.load_settings.assert_called_once_with()
        process.build_object_stores.assert_called_once_with(workflow["settings"])
        process.plan.load_discovery_report_from_object_store.assert_called_once_with(
            object_key="reports/discovery.json",
            object_store=workflow["discovery_object_store"],
        )
        process.plan.create_granules_table_from_discovery_report.assert_called_once_with(
            discovery_report=workflow["report"],
        )
        process.plan.get_granules_table_from_object_store.assert_called_once_with(
            object_store=workflow["raw_object_store"],
            object_prefix="nldas/ca",
            time_range=(datetime(2026, 10, 1), datetime(2026, 10, 5)),
        )
        process.plan.identify_new_granules.assert_called_once_with(
            discovered=workflow["discovered_table"],
            stored=workflow["stored_table"],
        )

        workflow["create_job"].assert_has_calls(
            [
                call(granule=sample_granules[2], spatial_subset=workflow['spatial_extent']),
                call(granule=sample_granules[0], spatial_subset=workflow['spatial_extent']),
            ]
        )

        object_prefix = (
            f"nldas/{workflow['spatial_extent'].name}/"
            + f"run_{workflow['run_id']}/"
            + f"jobs/"
        )

        workflow["write_job"].assert_has_calls(
            [
                call(
                    job=workflow["job"],
                    object_store=workflow["planning_object_store"],
                    object_prefix=object_prefix
                )
            ] * 2

        )

        workflow["create_plan"].assert_called_once_with(
            download_jobs=[workflow['job'],workflow['job']],
            spatial_extent=workflow['spatial_extent']
        )

        object_prefix = (
            f"nldas/{workflow["spatial_extent"].name}/"
            + f"run_{workflow["run_id"]}/"
        )

        workflow["write_plan"].assert_called_once_with(
            job_plan=workflow["job_plan"],
            object_store=workflow["planning_object_store"],
            object_prefix=object_prefix
        )

    def test_no_qualifying_granules_writes_an_empty_plan(
        self,
        mocker: MockerFixture,
        workflow,
    ) -> None:
        """
        Q: What does the process do when comparison finds no new granules?
        A: Create a plan with an empty granule list and still write that plan.
        """
        workflow["new_table"].__getitem__.return_value = []
        
        empty_job_plan = dom.GranuleDownloadJobPlan(
            spatial_extent=workflow['spatial_extent'],
            jobs=[]
        )

        workflow["create_plan"].return_value = empty_job_plan

        process.plan_nldas_download_jobs()

        workflow['create_job'].assert_not_called()

        workflow['write_job'].assert_not_called()
        
        workflow["create_plan"].assert_called_once_with(
            download_jobs=[],
            spatial_extent=workflow['spatial_extent'],
        )

        object_prefix = (
            f"nldas/{workflow['spatial_extent'].name}/"
            + f"run_{workflow['run_id']}/"
        )

        workflow["write_plan"].assert_called_once_with(
            job_plan=empty_job_plan,
            object_store=workflow["planning_object_store"],
            object_prefix=object_prefix
        )

    def test_invalid_subset_fails_before_building_store(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Q: What happens when the process receives an unsupported subset name?
        A: Raise ValueError before building an object store or reading the report.
        """
        mocker.patch.object(process.progset, "load_dotenv_config")
        mocker.patch.object(process.progset, "load_settings")
        mocker.patch.object(
            process,
            "load_input_arguments",
            return_value={
                "startdtime": "2026-10-01T00:00:00Z",
                "enddtime": "2026-10-05T00:00:00Z",
                "spatial_subset": "invalid",
                "discovery_report_key": "reports/discovery.json",
            },
        )
        build_stores = mocker.patch.object(process, "build_object_stores")

        with pytest.raises(ValueError, match="not a valid option"):
            process.plan_nldas_download_jobs()

        build_stores.assert_not_called()

    def test_discovery_load_failure_stops_planning(
        self,
        mocker: MockerFixture,
        workflow,
    ) -> None:
        """
        Q: What happens when the discovery report cannot be loaded?
        A: Propagate the failure and do not continue comparison, job creation, or writing.
        """
        load_error = RuntimeError("report unavailable")
        process.plan.load_discovery_report_from_object_store.side_effect = load_error

        with pytest.raises(RuntimeError, match="report unavailable"):
            process.plan_nldas_download_jobs()

        process.plan.identify_new_granules.assert_not_called()
        workflow["create_plan"].assert_not_called()
        workflow["write_plan"].assert_not_called()
