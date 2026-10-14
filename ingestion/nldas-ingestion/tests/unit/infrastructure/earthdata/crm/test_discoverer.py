import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock
import builtins
import os
import requests
from pathlib import Path
import json
from datetime import datetime
from typing import (Callable, Dict)

import nldas_ingestion.infrastructure.earthdata.cmr.discoverer as discover
import nldas_ingestion.domain.artifacts as dom

@pytest.fixture
def granule_extractor() -> discover.GranuleExtractor:
    return discover.GranuleExtractor()


@pytest.fixture
def valid_discovery_granule() -> dom.DiscoveryGranuleUmm:
    return {
        "meta": {
            "provider-id": "GES_DISC",
            "collection-concept-id": "C1234567890-GES_DISC",
            "concept-id": "G1234567890-GES_DISC",
            "native-id": "NLDAS_FORA0125_H.A20260101.0000.020",
            "revision-id": "2",
        },
        "umm": {
            "TemporalExtent": {
                "RangeDateTime": {
                    "BeginningDateTime": "2026-01-01T00:00:00Z",
                },
            },
            "ProviderDates": [{"Date": "2026-01-02T03:04:05.123Z"}],
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [{
                            "NorthBoundingCoordinate": 40.0,
                            "SouthBoundingCoordinate": 30.0,
                            "EastBoundingCoordinate": -100.0,
                            "WestBoundingCoordinate": -120.0,
                        }],
                    },
                },
            },
            "RelatedUrls": [
                {"Type": "GET DATA", "URL": "https://example.test/granule.nc"},
                {
                    "Type": "USE SERVICE API",
                    "Subtype": "OPENDAP DATA",
                    "URL": "https://example.test/opendap",
                },
            ],
        },
    }


class TestGranuleExtractor:

    class TestCatchAttributeError:

        def test_returns_wrapped_function(self,
            mocker: MockerFixture,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: When a function is provided what is returned?
            A: A wrapped version of the function (callable).
            """
            mock_fxn: Mock = mocker.Mock()
            wrapped_fxn = (
                granule_extractor
                .catch_attribute_error(mock_fxn)
            )

            assert isinstance(wrapped_fxn, Callable)
        
        def test_func_returns_without_exception(self,
            mocker: MockerFixture,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the wrapped function does not produce an exception?
            A: The wrapped functions return value is returned.
            """
            expected_result = "value"
            mock_fxn: Mock = mocker.Mock()
            mock_fxn.return_value = expected_result
            wrapped_fxn: Callable = (
                granule_extractor
                .catch_attribute_error(mock_fxn)
            )

            result = wrapped_fxn(attr="attr")

            assert result == expected_result
            mock_fxn.assert_called_once_with(attr="attr")

        @pytest.mark.parametrize(
                ("kwargs", "attr"),
                [
                    ({'attr': 'attr'}, 'attr'),
                    ({'arg': 'arg'}, 'UNKNOWN')
                ]
        )
        def test_func_error_raises_with_attribute(self,
            kwargs: Dict[str, str],
            attr: str,                                   
            mocker: MockerFixture,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if a function called with an `attr` arguement raises error?
            A: A runtime error is raised with the attribute embedded in the message.
            """
            
            expected_err_msg = f"Discovery is missing `{attr}` attribute."
            mock_fxn: Mock = mocker.Mock()
            mock_fxn.side_effect = RuntimeError()
            wrapped_fxn: Callable = (
                granule_extractor
                .catch_attribute_error(mock_fxn)
            )

            with pytest.raises(RuntimeError) as exc:
                wrapped_fxn(**kwargs)
            
            assert exc.match(expected_err_msg)
            mock_fxn.assert_called_once_with(**kwargs)

    # Make example of a happy, sad, and error scenario for one unit
    class TestGetFirstLevelUmm:
        
        def test_existing_attribute_returns_string(self,
            mocker: MockerFixture,
            granule_extractor: discover.GranuleExtractor
            ):
            """
            Q: What happens when the requested attribute for the provided granule is valid? 
            A: A string corresponding to the attribute is returned.
            """
            mock_umm = mocker.MagicMock()
            mock_granule = mocker.MagicMock()

            mock_umm_getitem = mocker.Mock(side_effect = {"attr": "attr"}.__getitem__)
            mock_umm.__getitem__ = mock_umm_getitem

            mock_granule_getitem = mocker.Mock(side_effect= {"umm": mock_umm}.__getitem__)
            mock_granule.__getitem__ = mock_granule_getitem

            response = granule_extractor.get_first_level_umm(
                granule=mock_granule,
                attr='attr'
            )

            assert response == 'attr'
            mock_umm_getitem.assert_called_once_with('attr')
            mock_granule_getitem.assert_called_once_with('umm')

        def test_misisng_attribute_raises_runtime_error(self,
            mocker: MockerFixture,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the requested attribute is missing from the provided granule?
            A: A runtime error specifies that attriute is missing.
            """
            mock_umm = mocker.MagicMock()
            mock_granule = mocker.MagicMock()

            mock_umm.__getitem__.side_effect = {"attr": "attr"}.__getitem__
            mock_granule.__getitem__.side_effect = {"umm": mock_umm}.__getitem__

            with pytest.raises(RuntimeError) as exc:
                granule_extractor.get_first_level_umm(
                    granule=mock_granule,
                    attr="attr1"
                )

            assert exc.match(r"^.*attr1.*$")
            mock_granule.__getitem__.assert_called_once_with('umm')
            mock_umm.__getitem__.assert_called_once_with('attr1')



    class TestGetFirstLevelMeta:

        def test_existing_attribute_returns_string(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the requested metadata attribute exists?
            A: The metadata attribute value is returned as a string.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {"provider-id": "PROVIDER"},
                "umm": {},
            }

            result = granule_extractor.get_first_level_meta(
                granule=granule,
                attr="provider-id",
            )

            assert result == "PROVIDER"

        def test_missing_attribute_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the requested metadata attribute is missing?
            A: A runtime error identifies the missing attribute.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {},
            }

            with pytest.raises(RuntimeError, match="provider-id"):
                granule_extractor.get_first_level_meta(
                    granule=granule,
                    attr="provider-id",
                )

    class TestGetGranuleDatetime:

        def test_fractional_seconds_datetime_returns_datetime(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule datetime includes fractional seconds?
            A: The datetime string is converted to a datetime value.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "TemporalExtent": {
                        "RangeDateTime": {
                            "BeginningDateTime": "2026-01-02T03:04:05.123Z",
                        },
                    },
                },
            }

            result = granule_extractor.get_granule_datetime(granule=granule)

            assert result == datetime(2026, 1, 2, 3, 4, 5, 123000)

        def test_whole_seconds_datetime_returns_datetime(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule datetime has no fractional seconds?
            A: The datetime string is converted to a datetime value.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "TemporalExtent": {
                        "RangeDateTime": {
                            "BeginningDateTime": "2026-01-02T03:04:05Z",
                        },
                    },
                },
            }

            result = granule_extractor.get_granule_datetime(granule=granule)

            assert result == datetime(2026, 1, 2, 3, 4, 5)

        def test_invalid_datetime_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the requested granule datetime cannot be parsed?
            A: A runtime error identifies the missing datetime attribute.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "TemporalExtent": {
                        "RangeDateTime": {
                            "BeginningDateTime": "not-a-datetime",
                        },
                    },
                },
            }

            with pytest.raises(
                RuntimeError,
                match="BeginningDateTime",
            ):
                granule_extractor.get_granule_datetime(
                    granule=granule,
                    attr="BeginningDateTime",
                )

    class TestGetLastUpdateDatetime:

        def test_empty_provider_dates_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule has no provider dates?
            A: A runtime error reports that the latest dataset update cannot be extracted.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {"ProviderDates": []},
            }

            with pytest.raises(
                RuntimeError,
                match="Missing ProviderDates",
            ):
                granule_extractor.get_last_update_datetime(granule=granule)

        def test_last_provider_date_returns_datetime(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule has a valid final provider date?
            A: The final provider date is converted to a datetime value.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "ProviderDates": [
                        {"Date": "2026-01-02T03:04:05Z"},
                        {"Date": "2026-01-03T04:05:06.789Z"},
                    ],
                },
            }

            result = granule_extractor.get_last_update_datetime(granule=granule)

            assert result == datetime(2026, 1, 3, 4, 5, 6, 789000)

    class TestGetCoordinate:

        def test_existing_coordinate_returns_float(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the requested bounding coordinate exists?
            A: The coordinate value is returned as a float.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "SpatialExtent": {
                        "HorizontalSpatialDomain": {
                            "Geometry": {
                                "BoundingRectangles": [
                                    {"SouthBoundingCoordinate": 32.5},
                                ],
                            },
                        },
                    },
                },
            }

            result = granule_extractor.get_coordinate(
                granule=granule,
                attr="SouthBoundingCoordinate",
            )

            assert result == 32.5

        def test_missing_coordinate_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the requested bounding coordinate is missing?
            A: A runtime error identifies the missing coordinate.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "SpatialExtent": {
                        "HorizontalSpatialDomain": {
                            "Geometry": {"BoundingRectangles": [{}]},
                        },
                    },
                },
            }

            with pytest.raises(
                RuntimeError,
                match="WestBoundingCoordinate",
            ):
                granule_extractor.get_coordinate(
                    granule=granule,
                    attr="WestBoundingCoordinate",
                )

    class TestGetRawUrl:

        def test_get_data_url_returns_raw_url(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule contains a GET DATA URL?
            A: The raw data URL is returned.
            """
            expected_url = "https://example.test/granule.nc"
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "RelatedUrls": [
                        {"Type": "GET RELATED VISUALIZATION", "URL": "https://example.test/preview"},
                        {"Type": "GET DATA", "URL": expected_url},
                    ],
                },
            }

            result = granule_extractor.get_raw_url(granule=granule)

            assert result == expected_url

        def test_missing_get_data_url_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the granule has no GET DATA URL?
            A: A runtime error reports that the raw access URL is missing.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "RelatedUrls": [
                        {"Type": "GET RELATED VISUALIZATION", "URL": "https://example.test/preview"},
                    ],
                },
            }

            with pytest.raises(
                RuntimeError,
                match="raw access url",
            ):
                granule_extractor.get_raw_url(granule=granule)

    class TestGetOpendapUrl:

        def test_opendap_service_url_returns_url(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens when the granule contains an OPENDAP DATA service URL?
            A: The OPENDAP URL is returned.
            """
            expected_url = "https://example.test/opendap"
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "RelatedUrls": [
                        {"Type": "GET DATA", "URL": "https://example.test/granule.nc"},
                        {
                            "Type": "USE SERVICE API",
                            "Subtype": "OPENDAP DATA",
                            "URL": expected_url,
                        },
                    ],
                },
            }

            result = granule_extractor.get_opendap_url(granule=granule)

            assert result == expected_url

        def test_missing_opendap_service_url_raises_runtime_error(
            self,
            granule_extractor: discover.GranuleExtractor
        ):
            """
            Q: What happens if the granule has no OPENDAP DATA service URL?
            A: A runtime error reports that the OPENDAP access URL is missing.
            """
            granule: dom.DiscoveryGranuleUmm = {
                "meta": {},
                "umm": {
                    "RelatedUrls": [
                        {"Type": "GET DATA", "URL": "https://example.test/granule.nc"},
                        {
                            "Type": "USE SERVICE API",
                            "Subtype": "OTHER SERVICE",
                            "URL": "https://example.test/other",
                        },
                    ],
                },
            }

            with pytest.raises(
                RuntimeError,
                match="opendap access url",
            ):
                granule_extractor.get_opendap_url(granule=granule)


class TestCreateDiscoveryRequestForCmr:
    def test_valid_range_returns_cmr_get_request(self) -> None:
        """
        Q: What happens when the start and end datetimes form a valid range?
        A: A GET request for the CMR granule search endpoint is returned.
        """
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2, 3, 4, 5)

        request = discover.create_discovery_request_for_cmr(start, end)

        assert request.method == "GET"
        assert request.url == discover.BASEURL
        assert request.headers["Accept"] == "application/vnd.nasa.cmr.umm_results+json"
        assert request.params == {
            "short_name": discover.SHORTNAME,
            "temporal": "2026-01-01T00:00:00Z,2026-01-02T03:04:05Z",
        }

    def test_start_after_end_raises_value_error(self) -> None:
        """
        Q: What happens when the start datetime is later than the end datetime?
        A: A ValueError is raised.
        """
        with pytest.raises(ValueError, match="StartDtime"):
            discover.create_discovery_request_for_cmr(
                datetime(2026, 1, 2),
                datetime(2026, 1, 1),
            )


class TestRequestDiscoveryFromCmr:
    def test_valid_json_response_returns_content(self, mocker: MockerFixture) -> None:
        """
        Q: What happens when CMR returns a successful response with JSON content?
        A: The response content is returned as a discovery response.
        """
        cmr_request = mocker.Mock(spec=requests.Request)
        prepared_request = mocker.Mock()
        response = mocker.MagicMock()
        content = {"hits": 1, "took": 2, "items": []}
        response.json.return_value = content
        session = mocker.MagicMock()
        session.__enter__.return_value = session
        session.prepare_request.return_value = prepared_request
        session.send.return_value = response
        mock_session = mocker.patch("requests.Session", return_value=session)

        result = discover.request_discovery_from_cmr(cmr_request)

        assert result == content
        mock_session.assert_called_once_with()
        session.prepare_request.assert_called_once_with(cmr_request)
        session.send.assert_called_once_with(prepared_request)
        response.raise_for_status.assert_called_once_with()
        response.json.assert_called_once_with()

    def test_http_error_propagates(self, mocker: MockerFixture) -> None:
        """
        Q: What happens when the CMR response has an unsuccessful HTTP status?
        A: The response status error propagates to the caller.
        """
        cmr_request = mocker.Mock(spec=requests.Request)
        response = mocker.MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("bad response")
        session = mocker.MagicMock()
        session.__enter__.return_value = session
        session.send.return_value = response
        mocker.patch("requests.Session", return_value=session)
        with pytest.raises(requests.HTTPError, match="bad response"):
            discover.request_discovery_from_cmr(cmr_request)

        response.json.assert_not_called()

    def test_non_dictionary_json_raises_value_error(self, mocker: MockerFixture) -> None:
        """
        Q: What happens when the response JSON is not a dictionary?
        A: A ValueError reports that the response is not in UMM+JSON format.
        """
        cmr_request = mocker.Mock(spec=requests.Request)
        response = mocker.MagicMock()
        response.json.return_value = ["not", "a", "dictionary"]
        session = mocker.MagicMock()
        session.__enter__.return_value = session
        session.send.return_value = response
        mocker.patch("requests.Session", return_value=session)

        with pytest.raises(ValueError, match=r"UMM\+JSON"):
            discover.request_discovery_from_cmr(cmr_request)


class TestExtractCollectionMetadataFromDiscoveryGranule:
    def test_valid_granule_returns_collection_metadata(
        self, granule_extractor: discover.GranuleExtractor
    ) -> None:
        """
        Q: What happens when the granule contains the required collection metadata?
        A: A DiscoveryMeta object is returned with the provider and collection IDs.
        """
        granule: dom.DiscoveryGranuleUmm = {
            "meta": {
                "provider-id": "GES_DISC",
                "collection-concept-id": "C1234567890-GES_DISC",
            },
            "umm": {},
        }

        result = discover.extract_collection_metadata_from_discovery_granule(
            granule,
            granule_extractor,
        )

        assert isinstance(result, dom.DiscoveryMeta)
        assert result.provider_id == "GES_DISC"
        assert result.collection_id == "C1234567890-GES_DISC"
        assert isinstance(result.discovered_at, datetime)
        assert result.discovered_at.tzinfo is not None

    def test_missing_provider_id_raises_runtime_error(
        self, granule_extractor: discover.GranuleExtractor
    ) -> None:
        """
        Q: What happens when the granule is missing its provider ID?
        A: A RuntimeError reports that the provider ID cannot be set.
        """
        granule: dom.DiscoveryGranuleUmm = {
            "meta": {"collection-concept-id": "C1234567890-GES_DISC"},
            "umm": {},
        }

        with pytest.raises(RuntimeError, match="provider_id"):
            discover.extract_collection_metadata_from_discovery_granule(
                granule,
                granule_extractor,
            )

    def test_missing_collection_id_raises_runtime_error(
        self, granule_extractor: discover.GranuleExtractor
    ) -> None:
        """
        Q: What happens when the granule is missing its collection ID?
        A: A RuntimeError reports that the collection ID cannot be set.
        """
        granule: dom.DiscoveryGranuleUmm = {
            "meta": {"provider-id": "GES_DISC"},
            "umm": {},
        }

        with pytest.raises(RuntimeError, match="collection_id"):
            discover.extract_collection_metadata_from_discovery_granule(
                granule,
                granule_extractor,
            )


class TestExtractGranuleFromDiscoveryGranule:
    def test_valid_granule_returns_domain_granule(
        self,
        valid_discovery_granule: dom.DiscoveryGranuleUmm,
        granule_extractor: discover.GranuleExtractor,
    ) -> None:
        """
        Q: What happens when the discovery granule contains its required attributes?
        A: A Granule object is returned with its metadata, extent, and access URLs.
        """
        result = discover.extract_granule_from_discovery_granule(
            valid_discovery_granule,
            granule_extractor,
        )

        assert isinstance(result, dom.Granule)
        assert result.granule_id == "G1234567890-GES_DISC"
        assert result.granule_name == "NLDAS_FORA0125_H.A20260101.0000.020"
        assert result.version == "2"
        assert result.date_time == datetime(2026, 1, 1)
        assert result.last_updated_at == datetime(2026, 1, 2, 3, 4, 5, 123000)
        assert result.spatial_extent == dom.SpatialExtent(
            40.0,-100.0,30.0,-120.0,
        )
        assert result.access == dom.GranuleAccess(
            "https://example.test/granule.nc",
            "https://example.test/opendap",
        )

    def test_missing_opendap_url_returns_granule_without_opendap_access(
        self,
        valid_discovery_granule: dom.DiscoveryGranuleUmm,
        granule_extractor: discover.GranuleExtractor,
    ) -> None:
        """
        Q: What happens when the granule has no OPENDAP URL?
        A: A Granule is returned with its OPENDAP URL set to None.
        """
        valid_discovery_granule["umm"]["RelatedUrls"] = [
            {"Type": "GET DATA", "URL": "https://example.test/granule.nc"}
        ]

        result = discover.extract_granule_from_discovery_granule(
            valid_discovery_granule,
            granule_extractor,
        )

        assert result.access.raw_url == "https://example.test/granule.nc"
        assert result.access.opendap_url is None

    def test_missing_required_attribute_raises_runtime_error(
        self,
        valid_discovery_granule: dom.DiscoveryGranuleUmm,
        granule_extractor: discover.GranuleExtractor,
    ) -> None:
        """
        Q: What happens when a required granule attribute is missing?
        A: A RuntimeError is raised while extracting the granule.
        """
        del valid_discovery_granule["meta"]["concept-id"]

        with pytest.raises(RuntimeError, match="concept-id"):
            discover.extract_granule_from_discovery_granule(
                valid_discovery_granule,
                granule_extractor,
            )


class TestCreateDiscoveryReport:
    
    def test_empty_discovery_raises_runtime_error(
        self, granule_extractor: discover.GranuleExtractor
    ) -> None:
        """
        Q: What happens when the discovery response contains no granules?
        A: A RuntimeError reports that discovery has no granules.
        """
        
        discovery_response: dom.DiscoveryResponseUmm = {
            "hits": 1,
            "took": 1,
            "items": []
        }
        with pytest.raises(RuntimeError, match="no granules"):
            discover.create_discovery_report(
                discovery_response,
                granule_extractor,
            )

    def test_missing_granule_data_raises_runtime_error(
        self, granule_extractor: discover.GranuleExtractor
    ) -> None:
        """
        Q: What happens when the first discovery granule is missing required data?
        A: A RuntimeError reports that the granule data is missing.
        """
        granule: dom.DiscoveryGranuleUmm = {"meta": {}, 'umm': {}}
        discovery_response: dom.DiscoveryResponseUmm = {
            "hits": 1,
            "took": 1,
            "items": [granule]
        }
        with pytest.raises(RuntimeError, match="missing"):
            discover.create_discovery_report(
                discovery_response,
                granule_extractor,
            )

    def test_valid_discovery_returns_report(
        self,
        valid_discovery_granule: dom.DiscoveryGranuleUmm,
        granule_extractor: discover.GranuleExtractor,
    ) -> None:
        """
        Q: What happens when discovery contains valid granules?
        A: A DiscoveryReport is returned with collection metadata and granules.
        """
        discovery_response: dom.DiscoveryResponseUmm = {
            "hits": 1,
            "took": 1,
            "items": [valid_discovery_granule]
        }
        
        result = discover.create_discovery_report(
            discovery_response,
            granule_extractor,
        )

        assert isinstance(result, dom.DiscoveryReport)
        assert result.meta.provider_id == "GES_DISC"
        assert result.meta.collection_id == "C1234567890-GES_DISC"
        assert len(result.granules) == 1
        assert result.granules[0].granule_id == "G1234567890-GES_DISC"


class TestWriteDiscoveryReportToObjectStore:
    def test_report_is_serialized_and_written_to_object_store(
        self, mocker: MockerFixture
    ) -> None:
        """
        Q: What happens when a discovery report is written to the object store?
        A: The report is serialized as JSON and written with the JSON content type.
        """
        report = mocker.MagicMock()
        report.to_dict.return_value = {
            "meta": {"provider_id": "GES_DISC"},
            "granules": [],
        }
        object_store = mocker.Mock()

        discover.write_discovery_report_to_object_store(report, object_store)

        report.to_dict.assert_called_once()
        object_store.put.assert_called_once()
        call = object_store.put.call_args.kwargs
        assert call["key"].startswith(
            "discovery/nldas/nldas-discovery-report_"
        )
        assert call["key"].endswith(".json")
        assert json.loads(call["data"]) == report.to_dict.return_value
        assert call["content_type"] == "application/json"

    def test_object_store_failure_propagates(self, mocker: MockerFixture) -> None:
        """
        Q: What happens if the object store fails while writing the discovery report?
        A: The storage error propagates to the caller.
        """
        report = mocker.MagicMock()
        report.to_dict.return_value = {
            "meta": {"provider_id": "GES_DISC"},
            "granules": [],
        }
        storage_error = OSError("object store unavailable")
        object_store = mocker.Mock()
        object_store.put.side_effect = storage_error

        with pytest.raises(OSError) as exc:
            discover.write_discovery_report_to_object_store(report, object_store)

        object_store.put.assert_called_once()
        call = object_store.put.call_args.kwargs
        assert json.loads(call["data"]) == report.to_dict.return_value
        assert call["content_type"] == "application/json"