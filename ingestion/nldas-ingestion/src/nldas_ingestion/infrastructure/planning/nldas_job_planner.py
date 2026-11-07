"""
Its planning function coordinates the work and applies the planning rules.
- Read the discovery report through the object-store dependency.
- Determine which granules need downloading.
- Create download-job records.
- Write the resulting job plan through the object-store dependency.
"""

"""
What is the best way to compare discovery report granules against existing granules in object store?
    Option 1: Create datatables/dataframes and use table operations
    Option 2: Create domain objects and compare them that way
    Option 3: Create domain object collections that have a method that transforms them into a dataframe for comparision 

How will we do the comparision?
    1. Check for the correct spatial subset partition
        /: raw files not subset (no subdirectory)
        /ca: subset to the extent of california
        /sd: subset to extent of san diego
    2. Match granules by granule_id (never changes whereas granule_name does on Earthdata)
    3. Compare `last_updated_at` attribute. 
        a. If the new granule is a more recent datetime
            then we keep the granule discovery and create a download job for it that will 
            replace the current granule in the object store.
        b. If the new granule is not more recent, then remove this
            granule from granule list to be used to make the job plan.

            
So what type of object is best for doing this comparision? Something with table
transformation capabilities such as a pandas dataframe, pyarrow table, duckdb table, etc.
--> Pandas dataframe

Discovery Granules:
schema: {
    granule_id: str,
    last_updated_at: datetime
}

Storage Granules:
schema: {
    granule_id: str,
    last_updated_at: datetime
}

Then join discovery <- storage on `granule_id` to get:
schema: {
    granule_id: str
    discovery_last_updated_at: datetime,
    storage_last_updated_at: datetime | NaN
}

Then filter out records where there is no storage granule
    (storage_last_updated_at is Nan)

Then flag records where discovery_last_updated_at > storage_last_updated_at

Then drop records that are not flagged, this gives us only records that
that have new data compared to storage.
"""


from typing import (Dict, List, Tuple, Optional, Union, Any)
from dataclasses import dataclass
from datetime import (datetime, timezone)
import json
import pandas as pd
import pandera.pandas as pa
from pandera.typing.pandas import DataFrame

import nldas_ingestion.domain.artifacts as dom
import nldas_ingestion.domain.schemas as sch
import nldas_ingestion.infrastructure.storage.protocols as sproto

DTFORMAT = '%Y-%m-%dT%H:%M:%SZ'
# NLDASPREFIX = 'nldas/ca' # TODO: Change this to an environment variable

def load_discovery_report_from_object_store(
    object_key: str,
    object_store: sproto.ObjectStore
) -> dom.DiscoveryReport:
    """
    Retrieves the discovery report at the specified `object_key`, deserializes the data,
    and then creates and returns a discovery report domain object.
    """
    try:
        payload: bytes = object_store.get(key=object_key)
    except Exception as exc:
        raise RuntimeError(f"Error retrieving {object_key} from object store") from exc

    try:
        discovery: dom.DiscoveryReportDict = json.loads(payload)
    except Exception as exc:
        raise RuntimeError(f"Error deserializing {object_key} content from object store to python dictionary. Check if {object_key} is in json format.")

    meta: dom.DiscoveryMeta = dom.DiscoveryMeta(
        provider_id=discovery['meta']['provider_id'],
        collection_id=discovery['meta']['collection_id'],
        discovered_at=datetime.strptime(discovery['meta']['discovered_at'], DTFORMAT)
    )
    
    granules: List[dom.Granule] = [] # NOTE: Index position preservation matters when doing comparision
    for g in discovery['granules']:
        spat = g['spatial_extent']
        acc = g['access']
        granules.append(
            dom.Granule(
                granule_id=g['granule_id'],
                granule_name=g['granule_name'],
                date_time=datetime.strptime(g['date_time'], DTFORMAT),
                version=g['version'],
                last_updated_at=datetime.strptime(g['last_updated_at'], DTFORMAT),
                spatial_extent=dom.SpatialExtent(
                    spat['north'], spat['east'], spat['south'], spat['west']
                ),
                access=dom.GranuleAccess(
                    acc['raw_url'], acc.get('opendap_url')
                )
            )
        )

    return dom.DiscoveryReport(meta=meta,granules=granules)


def create_granules_table_from_discovery_report(
    discovery_report: dom.DiscoveryReport
) -> DataFrame[sch.DiscoveredGranuleTableSchema]:
    """
    Extracts granules data from discovery report to create a
    dataframe table with schema `GranuleTableSchema`.
    """
    records = {
        'discovery_id': [],
        'granule_id': [], 
        'last_updated_at': []
    }
    
    for idx, g in enumerate(discovery_report.granules):
        records['discovery_id'].append(idx)
        records['granule_id'].append(g.granule_id)
        records['last_updated_at'].append(g.last_updated_at)

    return DataFrame[sch.DiscoveredGranuleTableSchema](records) # TODO: Should I add a try block for this to catch and translate errors or let it pass throgy


def get_granules_table_from_object_store(
    object_store: sproto.ObjectStore,
    object_prefix: str,
    time_range: Tuple[datetime, datetime]
) -> DataFrame[sch.StoredGranuleTableSchema]:
    """
    Retrieves metadata for existing nldas granules in the provided object store

    It's unclear what format to return the data. It needs to be easily compareable to the discovery data.
    
    Creates an existing granules table

    Determine other required parameters such as folder paths or something "nldas/conus/"
    """
    if time_range[0] > time_range[1]: # TODO: Implement this filtering
        raise ValueError("The minimum time {time_range[0]} is greater than maximum time {time_range[1]}.")

    search_results = object_store.search(prefix=object_prefix)

    records: Dict[str, List[str]] = {
        'granule_id': [],
        'last_updated_at': [] # datatime
    }
    
    for result in search_results:
        try:
            granule_id = result['metadata']['granule_id']
        except Exception as exc:
            raise ValueError(
                f"Object {result['object_name']} is missing metadata key granule_id."
            ) from exc

        try:
            last_updated_at = result['metadata']['last_updated_at']
        except Exception as exc:
            raise ValueError(
                f"Object {result['object_name']} is missing metadata key last_updated_at."
            ) from exc

        try:
            last_updated_at_dttm = datetime.strptime(last_updated_at, DTFORMAT)
        except Exception as exc:
            raise ValueError(
                f"Metadata attribute `last_updated_at` for object "
                f"`{result['object_name']}` is not a valid datetime string "
                f"with expected format `{DTFORMAT}`"
            ) from exc

        if (last_updated_at_dttm < time_range[0]) or (last_updated_at_dttm > time_range[1]):
            continue

        records['granule_id'].append(granule_id)
        records['last_updated_at'].append(last_updated_at)

    return DataFrame[sch.StoredGranuleTableSchema](
        {
            'granule_id': records['granule_id'],
            'last_updated_at': pd.to_datetime(records['last_updated_at'], format=DTFORMAT)            
        } 
    )
         

def identify_new_granules(
        discovered: DataFrame[sch.DiscoveredGranuleTableSchema],
        stored: DataFrame[sch.StoredGranuleTableSchema]
) -> DataFrame[sch.DiscoveredGranuleTableSchema]:
    """
    Compares discovered granules with stored granules to identify newly discovered
    granules with a version update date (last_updated_at) that is newer than what already
    exists in the list of stored granules. Any discovered granule that does not already
    exist in hte stored granules table is kept as well.

    new granules include all granules that are not currently stored in object store (new-new)
    as well as all granules that are already stored, but the data is updated based on
    `last_updated_at` (new-update)
    """

    comparison = pd.merge(
        left = discovered
            .rename(
                columns={'last_updated_at': 'discovered'}
            ),
        right = stored.rename(
            columns={'last_updated_at': 'stored'}
            ),
        how='left',
        on=['granule_id']
    )

    is_new = comparison['stored'].isna()
    is_update = comparison['discovered'] > comparison['stored']
    
    new_granules = (
        comparison
        .loc[
            is_new | is_update,
            ["discovery_id","granule_id","discovered"]
        ]
        .rename(columns={'discovered':'last_updated_at'})
        .sort_values(by='discovery_id', ascending=True)
    )

    return sch.DiscoveredGranuleTableSchema.validate(new_granules)

def create_download_job(
        granule: dom.Granule,
        spatial_subset: Optional[dom.SpatialExtent]
) -> dom.GranuleDownloadJob:

    is_subset = False
    base_url = granule.access.raw_url
    if spatial_subset:
        is_subset = True
        base_url = granule.access.opendap_url
        if base_url is None:
            raise ValueError(
                f"Spatial subset provided without OpenDAP URL for granule id {granule.granule_id}"
            )
    
    return dom.GranuleDownloadJob(
        job_id=granule.granule_id,
        base_url=base_url,
        subset=is_subset,
        granule_id=granule.granule_id,
        granule_name=granule.granule_name,
        date_time=granule.date_time,
        version=granule.version,
        last_updated_at=granule.last_updated_at,
        subset_extent=spatial_subset
    )

 
def create_download_job_plan(
    download_jobs: List[dom.GranuleDownloadJob],
    spatial_extent: Optional[dom.SpatialExtent] = None
) -> dom.GranuleDownloadJobPlan:
    """
    Generates a granule job plan from a list of granule download jobs
    """

    if not spatial_extent:
        spatial_extent = dom.SpatialExtent(
            name='conus',
            north=53.0,
            west=-125.0,
            south=25.0,
            east=-67.0
        )

    return dom.GranuleDownloadJobPlan(
        spatial_extent=spatial_extent,
        jobs=download_jobs
    )

def write_download_job_to_object_store(
    job: dom.GranuleDownloadJob,
    object_store: sproto.ObjectStore,
    object_prefix: str
):
    """
    Writes a granule download job to object storage.
    """
    key=f"{object_prefix}job_{job.job_id}.json"
    
    job_dict = job.to_dict()
    payload = json.dumps(
        job_dict,
        indent=10
    ).encode("UTF-8")

    _datetime = datetime.now(tz=timezone.utc).strftime(DTFORMAT)
    metadata: sproto.MetaDict = {
            "creation_datetime": _datetime,
            "artifact_type": "job"
        }
    
    object_store.put(
            key=key,
            data=payload,
            content_type='application/json',
            metadata=metadata
        )


def write_download_job_plan_to_object_store(
    job_plan: dom.GranuleDownloadJobPlan,
    object_store: sproto.ObjectStore,
    object_prefix: str
):
    """
    Writes a granule download job plan to object storage.
    """
    
    # _datetime = datetime.now(tz=timezone.utc).strftime(DTFORMAT).replace(":","p")
    key=f"{object_prefix}job_plan.json"
    
    job_plan_dict = job_plan.to_dict()
    payload = json.dumps(
        job_plan_dict, 
        indent=10
    ).encode("UTF-8")

    _datetime = datetime.now(tz=timezone.utc).strftime(DTFORMAT)
    metadata: sproto.MetaDict = {
        "creation_datetime": _datetime,
        "artifact_type": "job-plan"
    }

    object_store.put(
        key=key,
        data=payload,
        content_type='application/json',
        metadata=metadata
    )

