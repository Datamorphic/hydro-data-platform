import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock
from dataclasses import replace
from pathlib import Path
import json
from datetime import datetime
from typing import (Callable, Dict, Iterator, cast, BinaryIO, List, Union, Tuple)
from io import BytesIO

import nldas_ingestion.infrastructure.planning.nldas_job_planner as planner
import nldas_ingestion.domain.artifacts as dom
import nldas_ingestion.domain.schemas as sch
import nldas_ingestion.infrastructure.storage.protocols as sproto
from pandera.typing import (DataFrame)
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.datatypes import Object
import json

from pandera.errors import SchemaError

DictType = Dict[str, Union[str, List[str], Tuple[str]]]

@pytest.fixture
def mio_client() -> Iterator[Minio]:

    mio = Minio(
        endpoint='10.0.0.41:9000',
        access_key='minioadmin',
        secret_key='D@t@2Knowledge',
        secure=False
    )

    if not mio.bucket_exists('test'):
        mio.make_bucket('test')

    try:
        for x in range(3):
            
            metadata: DictType = {
                'last_updated_on': '2026-10-01T00:00:00Z',
                'collection-id': f"collection-id",
                'granule-id': f"granule-id-{x}"
            }

            payload = b'This is a dummy NetCDF file.'

            mio.put_object(
                bucket_name='test',
                object_name=f'nldas/conus/test-nldas-object-{x}.nc',
                data=BytesIO(payload),
                length=len(payload),
                metadata=metadata,
                content_type="application/x-netcdf"
            )

        yield mio
    finally:
        delete_objects = []
        
        for obj in mio.list_objects(bucket_name='test', prefix='nldas/conus/'):
            delete_objects.append(
                DeleteObject(name=cast(str, obj.object_name))
            )

        for delete_error in mio.remove_objects(
            bucket_name='test',
            delete_object_list=delete_objects,
            bypass_governance_mode=True
        ):
            print(f"Error: {delete_error}.")


@pytest.fixture
def stored_granules_table()-> DataFrame[sch.StoredGranuleTableSchema]:
    return DataFrame[sch.StoredGranuleTableSchema](
        {
            'granule_id': ["a","b","c"],
            'last_updated_at': [datetime(2025,1,1,0,0,0)] * 3
        }
    )


@pytest.fixture
def granule() -> dom.Granule:
    return dom.Granule(
        granule_id="granule-1",
        granule_name="NLDAS granule 1",
        date_time=datetime(2026, 10, 1, 0, 0, 0),
        version="1",
        last_updated_at=datetime(2026, 10, 2, 0, 0, 0),
        spatial_extent=dom.SpatialExtent(
            north=50.0,
            east=-90.0,
            south=25.0,
            west=-125.0,
        ),
        access=dom.GranuleAccess(
            raw_url="https://example.test/granule-1.nc",
            opendap_url="https://example.test/granule-1",
        ),
    )


class TestIdentifyNewGranules:

    @pytest.mark.parametrize(
        ('discovery', 'expected_discovery_ids'),
        [
            (# all same-same
                ([0,1,2], ["a","b","c"], [datetime(2025,1,1,0,0,0)] * 3),                 
                []
            ), 
            (# all new-update
                ([0,1,2], ["a","b","c"], [datetime(2026,1,1,0,0,0)] * 3),                 
                [0,1,2]
            ),
            (# all new-new
                ([0,1,2], ["d","e","f"], [datetime(2025,1,1,0,0,0)] * 3),                 
                [0,1,2]
            ),
            (# all old-old
                ([0,1,2], ["a","b","c"], [datetime(2024,1,1,0,0,0)] * 3),                 
                []
            ),
            (# all new-new | not seq order
                ([1,0,2], ["e","d","f"], [datetime(2025,1,1,0,0,0)] * 3),                 
                [0,1,2]
            ),
            (# same, new-new, old-old, new-update | not seq order | tests original order is preserved 
                ([2,3,1,0],
                 ["c","d","b","a"],
                 [datetime(2025,1,1,0,0,0)]
                    + [datetime(2026,1,1,0,0,0)]
                    + [datetime(2024,1,1,0,0,0)]
                    + [datetime(2026,1,1,0,0,0)]
                ),
                [0,3]
            ),
            (# empty
                ([],[],[]), []
            )
        ]
    )
    def test_new_granules_returned_with_existing_storage(self,
        discovery: Tuple[List[int], List[str], List[datetime]],
        expected_discovery_ids: List[int],
        stored_granules_table: DataFrame[sch.StoredGranuleTableSchema]
    ):
        """Q: Which discovered granules qualify when stored granules exist?

        A: Include granules whose IDs are not stored or whose discovered timestamps are newer; exclude unchanged or older granules and return qualifying rows in discovery_id order.
        """
        discovered_granules_table = DataFrame[sch.DiscoveredGranuleTableSchema](
            {
                'discovery_id': discovery[0],
                'granule_id': discovery[1],
                'last_updated_at': discovery[2]
            }
        )

        targets = discovered_granules_table['discovery_id'].isin(expected_discovery_ids)
        
        expected_granules_table = (
            discovered_granules_table
            .loc[targets]
            .copy(deep=True)
            .sort_values(by='discovery_id', ascending=True)
        )

        result_granules_table = planner.identify_new_granules(
            discovered=discovered_granules_table,
            stored=stored_granules_table
        )

        assert result_granules_table.equals(expected_granules_table)

    @pytest.mark.parametrize(
        ('discovery', 'expected_discovery_ids'),
        [
            (# all new-new
                ([0,1,2], ["a","b","c"], [datetime(2025,1,1,0,0,0)] * 3),                 
                [0,1,2]
            ), 
            (# all new-new | not seq order
                ([1,0,2], ["e","d","f"], [datetime(2025,1,1,0,0,0)] * 3),                 
                [0,1,2]
            ),
            (# empty
                ([],[],[]), []
            )
        ]
    )   
    def test_new_granules_returned_with_empty_storage(self,
        discovery: Tuple[List[int], List[str], List[datetime]],
        expected_discovery_ids: List[int],
    ):
        """Q: Which discovered granules qualify when no granules are stored?

        A: Every discovered granule is new and is returned in discovery_id order; if discovery is empty, the result is empty.
        """
        stored_granules_table = DataFrame[sch.StoredGranuleTableSchema](
            {
                'granule_id': [],
                'last_updated_at': []
            }
        )

        discovered_granules_table = DataFrame[sch.DiscoveredGranuleTableSchema](
            {
                'discovery_id': discovery[0],
                'granule_id': discovery[1],
                'last_updated_at': discovery[2]
            }
        )

        targets = discovered_granules_table['discovery_id'].isin(expected_discovery_ids)
        
        expected_granules_table = (
            discovered_granules_table
            .loc[targets]
            .copy(deep=True)
            .sort_values(by='discovery_id', ascending=True)
        )

        result_granules_table = planner.identify_new_granules(
            discovered=discovered_granules_table,
            stored=stored_granules_table
        )

        assert result_granules_table.equals(expected_granules_table)
        

class TestLoadDiscoveryReportFromObjectStore:
    
    def test_load_report_returns_discovery_report(self, 
        mocker: MockerFixture
    ) -> None:
        """
        Q: What does loading a valid report return?
        A: Given `object_key: str` and `object_store: sproto.ObjectStore`
        containing valid report JSON, return a populated `dom.DiscoveryReport` with its metadata, granules, and timestamps deserialized.
        """
        payload = {
            "meta": {
                "provider_id": "NASA",
                "collection_id": "NLDAS",
                "discovered_at": "2026-10-01T00:00:00Z",
            },
            "granules": [
                {
                    "granule_id": "granule-1",
                    "granule_name": "NLDAS granule 1",
                    "date_time": "2026-09-30T00:00:00Z",
                    "version": "1",
                    "last_updated_at": "2026-10-01T00:00:00Z",
                    "spatial_extent": {
                        "north": 50.0,
                        "east": -90.0,
                        "south": 25.0,
                        "west": -125.0,
                    },
                    "access": {
                        "raw_url": "https://example.test/granule-1",
                        "opendap_url": "https://example.test/granule-1-opendap",
                    },
                },
                {
                    "granule_id": "granule-2",
                    "granule_name": "NLDAS granule 2",
                    "date_time": "2026-09-30T01:00:00Z",
                    "version": "2",
                    "last_updated_at": "2026-10-01T01:00:00Z",
                    "spatial_extent": {
                        "north": 51.0,
                        "east": -89.0,
                        "south": 26.0,
                        "west": -124.0,
                    },
                    "access": {
                        "raw_url": "https://example.test/granule-2",
                        "opendap_url": None,
                    },
                },
            ],
        }
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.get.return_value = json.dumps(payload).encode("utf-8")
        object_key = "reports/discovery.json"

        result = planner.load_discovery_report_from_object_store(
            object_key=object_key,
            object_store=object_store,
        )

        assert result == dom.DiscoveryReport(
            meta=dom.DiscoveryMeta(
                provider_id="NASA",
                collection_id="NLDAS",
                discovered_at=datetime(2026, 10, 1, 0, 0, 0),
            ),
            granules=[
                dom.Granule(
                    granule_id="granule-1",
                    granule_name="NLDAS granule 1",
                    date_time=datetime(2026, 9, 30, 0, 0, 0),
                    version="1",
                    last_updated_at=datetime(2026, 10, 1, 0, 0, 0),
                    spatial_extent=dom.SpatialExtent(
                        north=50.0, east=-90.0, south=25.0, west=-125.0
                    ),
                    access=dom.GranuleAccess(
                        raw_url="https://example.test/granule-1",
                        opendap_url="https://example.test/granule-1-opendap",
                    ),
                ),
                dom.Granule(
                    granule_id="granule-2",
                    granule_name="NLDAS granule 2",
                    date_time=datetime(2026, 9, 30, 1, 0, 0),
                    version="2",
                    last_updated_at=datetime(2026, 10, 1, 1, 0, 0),
                    spatial_extent=dom.SpatialExtent(
                        north=51.0, east=-89.0, south=26.0, west=-124.0
                    ),
                    access=dom.GranuleAccess(
                        raw_url="https://example.test/granule-2",
                        opendap_url=None,
                    ),
                ),
            ],
        )
        object_store.get.assert_called_once_with(key=object_key)

    def test_object_store_failure_is_wrapped(self, 
        mocker: MockerFixture
    ):
        """
        Q: How is an object-store read failure reported?
        A: If `object_store: sproto.ObjectStore` raises while retrieving
        `object_key: str`, raise `RuntimeError` with the original error chained.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        original_error = OSError("storage unavailable")
        object_store.get.side_effect = original_error
        object_key = "reports/discovery.json"

        with pytest.raises(RuntimeError, match="Error retrieving") as exc_info:
            planner.load_discovery_report_from_object_store(
                object_key=object_key,
                object_store=object_store,
            )

        assert exc_info.value.__cause__ is original_error
        object_store.get.assert_called_once_with(key=object_key)

    def test_invalid_json_is_wrapped(self, 
        mocker: MockerFixture
    ) -> None:
        """
        Q: How is a report payload that is not valid JSON reported?
        A: Given `object_store: sproto.ObjectStore` returning invalid JSON bytes for `object_key: str`, raise `RuntimeError`.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.get.return_value = b"not valid JSON"
        object_key = "reports/discovery.json"

        with pytest.raises(RuntimeError, match="Error deserializing"):
            planner.load_discovery_report_from_object_store(
                object_key=object_key,
                object_store=object_store,
            )

        object_store.get.assert_called_once_with(key=object_key)


class TestCreateGranulesTableFromDiscoveryReport:
    def test_report_granules_become_discovered_table_rows(self) -> None:
        """
        Q: How are granules in a `dom.DiscoveryReport` represented in a table?
        A: Return `DataFrame[sch.DiscoveredGranuleTableSchema]` with one row per report granule, preserving report order in `discovery_id` and copying the granule ID and update timestamp.
        """
        report = dom.DiscoveryReport(
            meta=dom.DiscoveryMeta(
                provider_id="NASA",
                collection_id="NLDAS",
                discovered_at=datetime(2026, 10, 1),
            ),
            granules=[
                dom.Granule(
                    granule_id="granule-1",
                    granule_name="NLDAS granule 1",
                    date_time=datetime(2026, 9, 30),
                    version="1",
                    last_updated_at=datetime(2026, 10, 1),
                    spatial_extent=dom.SpatialExtent(
                        north=50.0, east=-90.0, south=25.0, west=-125.0
                    ),
                    access=dom.GranuleAccess(raw_url="https://example.test/1", opendap_url=None),
                ),
                dom.Granule(
                    granule_id="granule-2",
                    granule_name="NLDAS granule 2",
                    date_time=datetime(2026, 9, 30, 1),
                    version="2",
                    last_updated_at=datetime(2026, 10, 1, 1),
                    spatial_extent=dom.SpatialExtent(
                        north=51.0, east=-89.0, south=26.0, west=-124.0
                    ),
                    access=dom.GranuleAccess(raw_url="https://example.test/2", opendap_url=None),
                ),
            ],
        )

        result = planner.create_granules_table_from_discovery_report(report)

        expected = DataFrame[sch.DiscoveredGranuleTableSchema](
            {
                "discovery_id": [0, 1],
                "granule_id": ["granule-1", "granule-2"],
                "last_updated_at": [datetime(2026, 10, 1), datetime(2026, 10, 1, 1)],
            }
        )
        assert result.equals(expected)

    def test_empty_report_produces_empty_discovered_table(self) -> None:
        """
        Q: What table is produced when `dom.DiscoveryReport.granules` is empty?
        A: Return an empty `DataFrame[sch.DiscoveredGranuleTableSchema]` with the schema's required columns and dtypes.
        """
        report = dom.DiscoveryReport(
            meta=dom.DiscoveryMeta(
                provider_id="NASA",
                collection_id="NLDAS",
                discovered_at=datetime(2026, 10, 1),
            ),
            granules=[],
        )

        result = planner.create_granules_table_from_discovery_report(report)

        assert result.empty
        assert list(result.columns) == [
            "discovery_id",
            "granule_id",
            "last_updated_at",
        ]
        sch.DiscoveredGranuleTableSchema.validate(result)


class TestGetGranulesTableFromObjectStore:
    def test_object_metadata_becomes_stored_table_rows(self, 
        mocker: MockerFixture
    ):
        """
        Q: How are matching object-store results represented in the stored table?
        A: Given `object_store: sproto.ObjectStore` and a valid
        `time_range: Tuple[datetime, datetime]`, return `DataFrame[sch.StoredGranuleTableSchema]` with each granule ID and parsed` last_updated_at` timestamp.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.search.return_value = [
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/granule-1.nc",
                "metadata": {
                    "granule_id": "granule-1",
                    "last_updated_at": "2026-10-01T00:00:00Z",
                },
            },
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/granule-2.nc",
                "metadata": {
                    "granule_id": "granule-2",
                    "last_updated_at": "2026-10-02T12:30:00Z",
                },
            },
        ]
        time_range = (datetime(2026, 10, 1), datetime(2026, 10, 3))

        result = planner.get_granules_table_from_object_store(
            object_store=object_store,
            object_prefix="nldas/conus",
            time_range=time_range,
        )

        expected = DataFrame[sch.StoredGranuleTableSchema](
            {
                "granule_id": ["granule-1", "granule-2"],
                "last_updated_at": [
                    datetime(2026, 10, 1),
                    datetime(2026, 10, 2, 12, 30),
                ],
            }
        )
        assert result.equals(expected)
        object_store.search.assert_called_once_with(prefix="nldas/conus")

    def test_time_range_filters_granules_inclusively(
        self,
        mocker: MockerFixture,
    ):
        """
        Q: Which stored granules are returned for a requested time range?
        A: Return granules with `last_updated_at` equal to either endpoint or between the endpoints; exclude granules outside the range.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.search.return_value = [
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/before.nc",
                "metadata": {
                    "granule_id": "before",
                    "last_updated_at": "2026-09-30T23:59:59Z",
                },
            },
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/start.nc",
                "metadata": {
                    "granule_id": "start",
                    "last_updated_at": "2026-10-01T00:00:00Z",
                },
            },
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/inside.nc",
                "metadata": {
                    "granule_id": "inside",
                    "last_updated_at": "2026-10-02T12:30:00Z",
                },
            },
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/end.nc",
                "metadata": {
                    "granule_id": "end",
                    "last_updated_at": "2026-10-03T00:00:00Z",
                },
            },
            {
                "bucket_name": "test",
                "object_name": "nldas/conus/after.nc",
                "metadata": {
                    "granule_id": "after",
                    "last_updated_at": "2026-10-03T00:00:01Z",
                },
            },
        ]
        time_range = (datetime(2026, 10, 1), datetime(2026, 10, 3))

        result = planner.get_granules_table_from_object_store(
            object_store=object_store,
            object_prefix="nldas/conus",
            time_range=time_range,
        )

        expected = DataFrame[sch.StoredGranuleTableSchema](
            {
                "granule_id": ["start", "inside", "end"],
                "last_updated_at": [
                    datetime(2026, 10, 1),
                    datetime(2026, 10, 2, 12, 30),
                    datetime(2026, 10, 3),
                ],
            }
        )
        assert result.equals(expected)
        object_store.search.assert_called_once_with(prefix="nldas/conus")

    def test_empty_object_store_results_produce_empty_stored_table(self,
        mocker: MockerFixture
    ):
        """
        Q: What table is returned when the object store has no matching granules?
        A: Return an empty `DataFrame[sch.StoredGranuleTableSchema]` with the schema's required columns and dtypes.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.search.return_value = []

        result = planner.get_granules_table_from_object_store(
            object_store=object_store,
            object_prefix="nldas/conus",
            time_range=(datetime(2026, 10, 1), datetime(2026, 10, 3)),
        )

        assert result.empty
        assert list(result.columns) == ["granule_id", "last_updated_at"]
        sch.StoredGranuleTableSchema.validate(result)
        object_store.search.assert_called_once_with(prefix="nldas/conus")

    def test_reversed_time_range_raises_value_error(self, 
        mocker: MockerFixture
    ):
        """
        Q: What happens when `time_range: Tuple[datetime, datetime]` is reversed?
        A: Raise `ValueError` before searching `object_store: sproto.ObjectStore`.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        time_range = (datetime(2026, 10, 3), datetime(2026, 10, 1))

        with pytest.raises(ValueError):
            planner.get_granules_table_from_object_store(
                object_store=object_store,
                object_prefix="nldas/conus",
                time_range=time_range,
            )

        object_store.search.assert_not_called()

    def test_missing_object_metadata_raises_value_error(self, 
        mocker: MockerFixture
    ):
        """
        Q: What happens when a stored object lacks required granule metadata?
        A: Raise `ValueError` identifying the object and missing metadata key, rather than returning an incomplete `DataFrame[sch.StoredGranuleTableSchema]`.
        """
        object_name = "nldas/conus/granule-without-timestamp.nc"
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        object_store.search.return_value = [
            {
                "bucket_name": "test",
                "object_name": object_name,
                "metadata": {"granule_id": "granule-1"},
            }
        ]

        with pytest.raises(ValueError, match=f"{object_name} is missing metadata key last_updated_at"):
            planner.get_granules_table_from_object_store(
                object_store=object_store,
                object_prefix="nldas_conus",
                time_range=(datetime(2026, 10, 1), datetime(2026, 10, 3)),
            )
        

class TestCreateDownloadJob:
    def test_without_subset_uses_raw_url(self, granule: dom.Granule) -> None:
        """
        Q: What download job is created when no spatial subset is requested?
        A: Return a non-subset job using the granule's raw URL, metadata, and no subset extent.
        """
        result = planner.create_download_job(granule=granule, spatial_subset=None)

        assert result == dom.GranuleDownloadJob(
            base_url="https://example.test/granule-1.nc",
            subset=False,
            granule_id="granule-1",
            granule_name="NLDAS granule 1",
            date_time=datetime(2026, 10, 1, 0, 0, 0),
            version="1",
            last_updated_at=datetime(2026, 10, 2, 0, 0, 0),
            subset_extent=None,
        )

    def test_with_subset_uses_opendap_url_and_extent(
        self,
        granule: dom.Granule,
    ) -> None:
        """
        Q: What download job is created when a spatial subset is requested?
        A: Return a subset job using the OpenDAP URL and the exact requested extent.
        """
        subset = dom.SpatialExtent(
            north=45.0,
            east=-115.0,
            south=32.0,
            west=-125.0,
        )

        result = planner.create_download_job(granule=granule, spatial_subset=subset)

        assert result == dom.GranuleDownloadJob(
            base_url="https://example.test/granule-1",
            subset=True,
            granule_id="granule-1",
            granule_name="NLDAS granule 1",
            date_time=datetime(2026, 10, 1, 0, 0, 0),
            version="1",
            last_updated_at=datetime(2026, 10, 2, 0, 0, 0),
            subset_extent=subset,
        )

    def test_subset_without_opendap_url_raises_value_error(
        self,
        granule: dom.Granule,
    ) -> None:
        """
        Q: What happens when a subset is requested but the granule has no OpenDAP URL?
        A: Raise ValueError identifying the granule ID instead of creating an unusable job.
        """
        granule_without_opendap = replace(
            granule,
            access=dom.GranuleAccess(
                raw_url=granule.access.raw_url,
                opendap_url=None,
            ),
        )
        subset = dom.SpatialExtent(north=45.0, east=-115.0, south=32.0, west=-125.0)

        with pytest.raises(ValueError, match="granule-1"):
            planner.create_download_job(
                granule=granule_without_opendap,
                spatial_subset=subset,
            )


class TestCreateDownloadJobPlan:
    def test_creates_job_for_each_granule(
        self,
        granule: dom.Granule,
    ) -> None:
        """
        Q: What plan is returned for multiple granules without a subset?
        A: Return one non-subset download job per granule, preserving the input order.
        """
        second_granule = replace(
            granule,
            granule_id="granule-2",
            granule_name="NLDAS granule 2",
            access=dom.GranuleAccess(
                raw_url="https://example.test/granule-2.nc",
                opendap_url="https://example.test/granule-2",
            ),
        )

        result = planner.create_download_job_plan([granule, second_granule])

        assert result == dom.GranuleDownloadJobPlan(
            spatial_extent=dom.SpatialExtent(
                name="conus",
                north=53.0,
                west=-125.0,
                south=25.0,
                east=-67.0,
            ),
            jobs=[
                dom.GranuleDownloadJob(
                    base_url="https://example.test/granule-1.nc",
                    subset=False,
                    granule_id="granule-1",
                    granule_name="NLDAS granule 1",
                    date_time=datetime(2026, 10, 1),
                    version="1",
                    last_updated_at=datetime(2026, 10, 2),
                    subset_extent=None,
                ),
                dom.GranuleDownloadJob(
                    base_url="https://example.test/granule-2.nc",
                    subset=False,
                    granule_id="granule-2",
                    granule_name="NLDAS granule 2",
                    date_time=datetime(2026, 10, 1),
                    version="1",
                    last_updated_at=datetime(2026, 10, 2),
                    subset_extent=None,
                ),
            ]
        )

    def test_empty_granule_list_returns_empty_plan(self) -> None:
        """
        Q: What plan is returned when there are no granules?
        A: Return an empty GranuleDownloadJobPlan with the default CONUS spatial extent.
        """
        assert planner.create_download_job_plan([]) == dom.GranuleDownloadJobPlan(
            spatial_extent=dom.SpatialExtent(
                name="conus",
                north=53.0,
                west=-125.0,
                south=25.0,
                east=-67.0,
            ),
            jobs=[],
        )

    def test_subset_is_applied_to_each_granule(self, granule: dom.Granule) -> None:
        """
        Q: Is the requested spatial subset applied consistently to each granule?
        A: Each generated job is marked as a subset job and carries the requested extent.
        """
        second_granule = replace(
            granule,
            granule_id="granule-2",
            access=dom.GranuleAccess(
                raw_url="https://example.test/granule-2.nc",
                opendap_url="https://example.test/granule-2",
            ),
        )
        subset = dom.SpatialExtent(
            name="ca",
            north=45.0,
            east=-115.0,
            south=32.0,
            west=-125.0,
        )

        result = planner.create_download_job_plan(
            [granule, second_granule],
            spatial_extent=subset,
        )

        assert result.spatial_extent == subset
        assert len(result.jobs) == 2
        assert all(job.subset for job in result.jobs)
        assert all(job.subset_extent == subset for job in result.jobs)

    def test_missing_opendap_url_propagates_value_error(
        self,
        granule: dom.Granule,
    ) -> None:
        """
        Q: What happens if any granule cannot satisfy the requested subset?
        A: Propagate ValueError rather than return a partial download plan.
        """
        granule_without_opendap = replace(
            granule,
            access=dom.GranuleAccess(
                raw_url=granule.access.raw_url,
                opendap_url=None,
            ),
        )
        subset = dom.SpatialExtent(
            name="ca",
            north=45.0,
            east=-115.0,
            south=32.0,
            west=-125.0,
        )

        with pytest.raises(ValueError, match="granule-1"):
            planner.create_download_job_plan(
                [granule, granule_without_opendap],
                spatial_extent=subset,
            )


class TestWriteDownloadJobPlanToObjectStore:
    @pytest.mark.parametrize("spatial_name", ["conus", "ca", "sd"])
    def test_serializes_and_uploads_job_plan(
        self,
        mocker: MockerFixture,
        spatial_name: str,
    ) -> None:
        """
        Q: How is a populated job plan written to object storage?
        A: Upload its JSON representation under the spatial partition, with application/json content type, job-plan metadata, and a timestamped key.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        spatial_extent = dom.SpatialExtent(
            name=spatial_name,
            north=53.0,
            east=-67.0,
            south=25.0,
            west=-125.0,
        )
        job_plan = dom.GranuleDownloadJobPlan(
            spatial_extent=spatial_extent,
            jobs=[
                dom.GranuleDownloadJob(
                    base_url="https://example.test/granule-1.nc",
                    subset=False,
                    granule_id="granule-1",
                    granule_name="NLDAS granule 1",
                    date_time=datetime(2026, 10, 1),
                    version="1",
                    last_updated_at=datetime(2026, 10, 2),
                    subset_extent=None,
                )
            ]
        )

        planner.write_download_job_plan_to_object_store(
            job_plan=job_plan,
            object_store=object_store,
        )

        object_store.put.assert_called_once()
        call = object_store.put.call_args.kwargs
        assert call["key"].startswith(
            f"nldas/{spatial_name}/nldas-job-plan_"
        )
        assert call["key"].endswith(".json")
        timestamp = call["key"].removeprefix(
            f"nldas/{spatial_name}/nldas-job-plan_"
        ).removesuffix(".json")
        assert datetime.strptime(timestamp, "%Y-%m-%dT%Hp%Mp%SZ")
        assert call["data"] == json.dumps(job_plan.to_dict(), indent=10).encode("UTF-8")
        assert call["content_type"] == "application/json"
        assert call["metadata"]["artifact_type"] == "job-plan"
        datetime.strptime(
            call["metadata"]["creation_datetime"],
            "%Y-%m-%dT%H:%M:%S",
        )

    def test_empty_job_plan_is_written_as_empty_jobs_list(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Q: What is uploaded for a plan with no jobs?
        A: Upload a valid JSON job plan whose jobs list is empty under its named spatial partition.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        job_plan = dom.GranuleDownloadJobPlan(
            spatial_extent=dom.SpatialExtent(
                name="conus",
                north=53.0,
                east=-67.0,
                south=25.0,
                west=-125.0,
            ),
            jobs=[],
        )

        planner.write_download_job_plan_to_object_store(
            job_plan=job_plan,
            object_store=object_store,
        )

        object_store.put.assert_called_once()
        assert json.loads(object_store.put.call_args.kwargs["data"]) == job_plan.to_dict()
        assert object_store.put.call_args.kwargs["key"].startswith("nldas/conus/")

    def test_object_store_put_failure_is_propagated(self, mocker: MockerFixture) -> None:
        """
        Q: What happens when object storage fails to save the plan?
        A: Propagate the original exception to the caller.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        storage_error = OSError("storage unavailable")
        object_store.put.side_effect = storage_error
        job_plan = dom.GranuleDownloadJobPlan(
            spatial_extent=dom.SpatialExtent(
                name="conus",
                north=53.0,
                east=-67.0,
                south=25.0,
                west=-125.0,
            ),
            jobs=[],
        )

        with pytest.raises(OSError, match="storage unavailable") as exc_info:
            planner.write_download_job_plan_to_object_store(
                job_plan=job_plan,
                object_store=object_store,
            )

        assert exc_info.value is storage_error
        object_store.put.assert_called_once()

    def test_missing_spatial_extent_name_raises_without_upload(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Q: What happens when the plan's spatial extent has no partition name?
        A: Raise ValueError and do not write an object because its destination partition is unknown.
        """
        object_store = mocker.Mock(spec=sproto.ObjectStore)
        job_plan = dom.GranuleDownloadJobPlan(
            spatial_extent=dom.SpatialExtent(
                north=53.0,
                east=-67.0,
                south=25.0,
                west=-125.0,
            ),
            jobs=[],
        )

        with pytest.raises(ValueError, match="missing spatial extent name"):
            planner.write_download_job_plan_to_object_store(
                job_plan=job_plan,
                object_store=object_store,
            )

        object_store.put.assert_not_called()
