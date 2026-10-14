"""

NOTE: NLDAS data is released from NOAA to NASA at ~4 day lag time, so we can only get data from 4 days ago every day we run CHRON jobs

1. What will trigger discovery jobs, time-based (cron) or event-based (reactive)?
2. How do we determine what is `new` data that need to be retrieved? 
    a. What do we compare against to determine if data already exists in our system or not?
        - manifest/inventory database (sqlite db)?
        - metadata tables (iceberg)?
    b. If upstream data has been updated how do we determine we need to replace it in our system?
        a. Do we check hashkeys?
        b. Do we archive the old data and download the new?
        c. What is considered the data coverage if we have multiple versions of the same data?
"""

""" Patterns

(Easiest/Niave) Every day we search the CRM for new (latest) datasets / datapoints, and once we have located
    it, we ingest it into our raw storage system.

(Intermediate) Every day we search the CRM for new (latest) datasets / datapoints, once we have them located
    we compare them to an living manifest/inventory of our raw assets to see if we already have them downloaded.
    If we are missing those datapoints, we download the new assets, but if they do exist, we skip them.

(Sophisticated) Every day we search the CRM for available dataset as well as search a living
    manifest/inventory of our raw assets to see which datapoint to compare which datapoints we have missing.
    We then mark all datapoints from the server that where missing in our system and retrieve those assests.

Thoughts:
- Make the crm discovery simple, give it search parameters like a date range and dataset
    and recovery all records on the CRM that fall within the parameterization.
- Have separate application logic handle the business logic that determines which
    datasets should be kept vs omitted. (Perhaps the job planner? or should this happen in the discovery process?).
- Have another component search a manifest/inventory of raw data to compare against
    discovery results before making jobs.

Provided Parameters:
    - CRM dataset (NLDAS FORA Hourly in our case)
    - date range bounds

**Note start with functions instead of a class because the module can "act" as a class in a sense
"""
import requests
import json
from typing import (List, Callable, ParamSpec, TypeVar)
from functools import wraps
from datetime import datetime, timezone
from nldas_ingestion.infrastructure.storage.protocols import ObjectStore
import nldas_ingestion.domain.artifacts as dom

DTFORMAT = "%Y-%m-%dT%H:%M:%SZ" # NASA uses UTC time zone so append with "Z"
BASEURL = "https://cmr.earthdata.nasa.gov/search/granules"
SHORTNAME = "NLDAS_FORA0125_H"
P = ParamSpec("P") # Allows for static type-checker to recognize decorators with inherited signature 
T = TypeVar("T")   # Allows for static type-checker to recognize decorators with inherited signature


class GranuleExtractor:

    @staticmethod
    def catch_attribute_error(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def catch_and_raise(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)            
            except Exception as exc:
                attr = "UNKNOWN"
                if kwargs.get("attr"):
                    attr = kwargs.get("attr")
                raise RuntimeError(f"Discovery is missing `{attr}` attribute.")
        return catch_and_raise

    
    @staticmethod
    @catch_attribute_error
    def get_first_level_umm(
        granule: dom.DiscoveryGranuleUmm, 
        attr: str
    ) -> str:
        try:
            return granule['umm'][attr]
        except Exception as exc:
            raise RuntimeError(
                f"Could not extract first level umm attribute {attr} from granule"
            ) from exc            

    @staticmethod
    @catch_attribute_error
    def get_first_level_meta(
        granule: dom.DiscoveryGranuleUmm, 
        attr: str
    ) -> str:
        try:
            return granule['meta'][attr]
        except Exception as exc:
            raise RuntimeError(
                f"Could not extract first level metadata attribute {attr} from granule"
            ) from exc

    @staticmethod
    @catch_attribute_error
    def get_granule_datetime(
        granule: dom.DiscoveryGranuleUmm, 
        attr: str = "BeginningDateTime"
    ) -> datetime:

        try:
            dttm = granule['umm']['TemporalExtent']\
                ['RangeDateTime'][attr]
        except Exception as exc:
            raise RuntimeError(
                f"Can not extract `{attr}` from granule"
            ) from exc
        try:
            return datetime.strptime(dttm, '%Y-%m-%dT%H:%M:%S.%fZ')
        except:
            pass
        try:
            return datetime.strptime(dttm, '%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            raise RuntimeError(f"Attribute `{attr}` with datetime string {dttm} could not be converted to datetime format")

    @staticmethod
    def get_last_update_datetime(
        granule: dom.DiscoveryGranuleUmm,
    ) -> datetime:

        events = granule['umm']['ProviderDates']
        if len(events) == 0:
            raise RuntimeError("Missing ProviderDates, can not extract latest dataset update.")

        try:
            latest_event_date = events[-1]['Date']
        except Exception as exc:
            raise RuntimeError(
                f"Can not extract latest `ProviderDate` from granule"
            ) from exc
        try:
            return datetime.strptime(
                latest_event_date,
                '%Y-%m-%dT%H:%M:%S.%fZ'
            )
        except Exception:
            pass
        try:
            return datetime.strptime(
                latest_event_date,
                '%Y-%m-%dT%H:%M:%SZ'
            )
        except Exception:            
            raise RuntimeError(f"`ProviderDate` with datetime string {latest_event_date} could not be converted to datetime format")

    @staticmethod
    @catch_attribute_error
    def get_coordinate(
        granule: dom.DiscoveryGranuleUmm,
        attr: str = "NorthBoundingCoordinate"
    ) -> float:
        try:
            return granule['umm']['SpatialExtent']\
                ['HorizontalSpatialDomain']\
                ['Geometry']['BoundingRectangles'][0][attr]
        except Exception as exc:
            raise RuntimeError(
                f"Can not extract coordinate {attr} from granule"
            ) from exc

    @staticmethod
    def get_raw_url(granule: dom.DiscoveryGranuleUmm) -> str:
        try:
            urls = granule['umm']['RelatedUrls']
            for url in urls:
                if url["Type"] == "GET DATA":
                    return url["URL"]
            raise RuntimeError("No raw access url found")         
        except Exception as exc:
            raise RuntimeError(
                "Discovery is missing `raw access url`."
            ) from exc
        
    @staticmethod
    def get_opendap_url(granule: dom.DiscoveryGranuleUmm) -> str:
        try:
            urls = granule['umm']['RelatedUrls']
            for url in urls:
                if url["Type"] == "USE SERVICE API":
                    if url["Subtype"] == "OPENDAP DATA":
                        return url["URL"]
            raise RuntimeError("No opendap access url found")         
        except Exception as exc:
            raise RuntimeError(
                "Discovery is missing `opendap access url`."
            ) from exc


def create_discovery_request_for_cmr(startdtime: datetime, enddtime: datetime) -> requests.Request:
    """
    Create an http request object that can be sent to NASA
    CMR server to discover available NLDAS granules

    StartDtime [datetime]: Starting datetime boundary in UTC time zone
    EndDtime [datetime]: Ending datetime boundary in UTC time zone
    """
    if startdtime > enddtime:
        raise ValueError("`StartDtime` can not be greater than `EndDtime`")

    params = {
        "short_name": SHORTNAME,
        "temporal": (
            startdtime.strftime(DTFORMAT) + ","
            + enddtime.strftime(DTFORMAT)
            )
    } # TODO: Test/validate dates are valid, perhaps earlier when looking at argv inputs?

    headers = {
        "Accept": "application/vnd.nasa.cmr.umm_results+json"
    }

    return requests.Request(
        method="GET",
        url=BASEURL,
        headers=headers,
        params=params
    )
    

def request_discovery_from_cmr(cmr_request: requests.Request) -> dom.DiscoveryResponseUmm:
    """
    Sends a network request to NASA CMR server to discover available NLDAS granules, 
        receive response, validates it by raising for failure status, and extracts
        response content as a dictionary (json).

    **Excepted content format is `umm+json`**
    """

    with requests.Session() as session:
        prepared_request= session.prepare_request(cmr_request)
        response = session.send(prepared_request)

    response.raise_for_status()
    content: dom.DiscoveryResponseUmm = response.json()
    if not isinstance(content, dict): # TODO: Make more robust verification check
        raise ValueError("CMR response content was not returned in UMM+JSON format")
    return content


def extract_collection_metadata_from_discovery_granule(
        granule: dom.DiscoveryGranuleUmm,
        extractor: GranuleExtractor) -> dom.DiscoveryMeta:
    """Extracts collection metadata from raw NLDAS discovery response item and
    converts it to into domain object.

    Assumes discovery is DiscoveryResponseUmm format -- verification should be done externally.
    """

    meta = dict()

    for var, key in (
        ('provider_id','provider-id'), 
        ('collection_id','collection-concept-id')
    ):
        try:
            meta[var] = extractor.get_first_level_meta(
                granule=granule,
                attr=key
            )
        except Exception as exc:
            raise RuntimeError(
                f"Can not set `{var}` attribute of `DiscoveryMeta` because Discovery is missing `{key}` attribute."
            ) from exc
    
    return dom.DiscoveryMeta(
        provider_id=meta['provider_id'],
        collection_id=meta['collection_id'],
        discovered_at=datetime.now(timezone.utc)
    )


def extract_granule_from_discovery_granule(
    granule: dom.DiscoveryGranuleUmm,
    extractor: GranuleExtractor) -> dom.Granule:
    """
    Extracts granule data from a raw NLDAS discovery response item and
    converts it into domain object.
    """

    granule_data = dict()    
    
    for response_attr, granule_attr in (
        ('concept-id', 'granule_id'),
        ('native-id', 'granule_name'),
        ('revision-id', 'version')
    ):
        granule_data[granule_attr] = extractor.get_first_level_meta(
            granule=granule,
            attr=response_attr
        )

    granule_data['date_time'] = (
        extractor.get_granule_datetime(
            granule=granule, attr='BeginningDateTime'
        )
    )

    granule_data['last_updated_at'] = (
        extractor.get_last_update_datetime(granule=granule)
    )

    granule_data['spatial_extent'] = dom.SpatialExtent(
        
        north=extractor.get_coordinate(
            granule=granule,
            attr='NorthBoundingCoordinate'
        ),
        south=extractor.get_coordinate(
            granule=granule,
            attr='SouthBoundingCoordinate'
        ),
        east=extractor.get_coordinate(
            granule=granule,
            attr='EastBoundingCoordinate'
        ),
        west=extractor.get_coordinate(
            granule=granule,
            attr='WestBoundingCoordinate'
        )
    )

    raw_url = extractor.get_raw_url(
        granule=granule
    )

    try:
        opendap_url = extractor.get_opendap_url(
            granule=granule
        )
    except Exception as exc: 
        opendap_url = None # NOTE: Is this the best way to handle it? What if the response is malformed instead of missing the url?

    granule_data['access'] = dom.GranuleAccess(
        raw_url=raw_url,
        opendap_url=opendap_url
    )

    return dom.Granule(**granule_data)


def create_discovery_report(
        discovery: dom.DiscoveryResponseUmm, 
        extractor: GranuleExtractor
) -> dom.DiscoveryReport:
    """
    Creates a discovery report from a NASA CMR discovery response.

    Assumptions:
        - Discovery response is in umm+json format
        - Report only contains one unique collection with common metadata attributes,
            such as: `collection-concept-id`, `spatial_extent`, `provider-id`.
    """

    if len(discovery['items']) == 0:
        raise RuntimeError("Discovery has no granules")

    first_granule = discovery['items'][0]

    for attr in ('meta', 'umm'):
        if first_granule.get(attr) is None:
            raise RuntimeError("Discovery granules are missing `{attr}` attribute or data")

    meta = extract_collection_metadata_from_discovery_granule(
        granule=first_granule,
        extractor=extractor
    )
    
    granules = []
    
    for response_granule in discovery['items']:
        granules.append(
            extract_granule_from_discovery_granule(
                granule=response_granule,
                extractor=extractor
            )
        )

    return dom.DiscoveryReport(
        meta=meta,
        granules=granules
    )


def write_discovery_report_to_object_store(
        discovery_report: dom.DiscoveryReport, 
        object_store: ObjectStore):
    """
    Writes the discovery report as a JSON object in the object store.

    Dependencies:
    - Object Store (Minio Client)
    """
    key=f"discovery/nldas/nldas-discovery-report_{datetime.now(tz=timezone.utc).strftime(DTFORMAT)}.json".replace(":","p")
    discovery_report_dict = discovery_report.to_dict()
    payload = json.dumps(
        discovery_report_dict, 
        indent=10
    ).encode("UTF-8")

    object_store.put(
        key=key,
        data=payload,
        content_type='application/json'
    )