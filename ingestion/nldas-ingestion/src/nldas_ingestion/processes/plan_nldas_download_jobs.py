"""
    The goal here is to parse a nldas discovery artifact, extract granules,
and then create a job artifact for each granule that can be used by 
a downstream download program to download the granule.

What information is required for each job (in the form of questions)?
- Is it a full download or a subset job (Raw vs OpenDAP subset)?
- What is the base URL for the granule to be downloaded from the API server?
- What is the datetime associated with the granule?
- If this is a subset job, what is the spatial extent of the subset and is it within the bounds of the granule?
    --> Alternatively, you could hard code either full granule or particular subset that the downloader has to handle (CA, SD, etc)
    --> This is business logic though, perhaps the downloader is Niave and just needs coordinates and the job planner translates CA, SD, etc into boundary coordinates
- What is the crucial meta-data that should pass through, such as provider_id, collection_id, granule_id, granule_name, version_id, last_update, boundary coordinates, etc
    --> it might make sense to let it all percolate and get passed to the downloader as metadata attributes
- Does the granule/version already exist in the object store?

How will discovery jobs be stored?
- as individual json files in their own folder that the orchestrator can parse through?
- as a single json file that the orchestrator has to parse/loop through?


***CRITICAL DECISION*** 
We will not turn on Object Store Versioning so as to save on storage space.
This means that meta-data will mark which version of the data a user is using, but
only the latest version will be kept in storage. Any new versions will overwrite old
existing versions of data.

Things to do:
[x] Update the object store abstractions to allow for meta-data attributes to be passed
[ ] Design the program flow for the job planner
    a. read target discovery object for granules
    b. apply business logic such as subsetting instructions and checks
    c. read object store for available corresponding granules (decide on how they are compared, perhaps by date?)
    d. compare discovery granules against existing granules, if a granule is new keep it, if it already exists
        compare the provider date to see if it is newer or the same date. If newer, replace what is is the object store.
    e. create job artifacts (one per job with required data to run a job)
    f. create a job report artifact (all jobs) that can be stored on disk and passed to orchestrator

"""

import os, dotenv
import argparse
from pathlib import Path
from typing import (List, Tuple, Dict, Mapping)
from datetime import (datetime, timezone, timedelta)

import nldas_ingestion.infrastructure.config.settings as progset
import nldas_ingestion.infrastructure.planning.nldas_job_planner as plan
import nldas_ingestion.domain.artifacts as dom
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore


DTFORMAT = "%Y-%m-%dT%H:%M:%SZ" # NASA uses UTC time zone so append with "Z"


def build_object_stores(settings: progset.Settings) -> Tuple[MinioObjectStore, MinioObjectStore, MinioObjectStore]:
    """Composes `MinioObjectStore`, `MinioObjectStore`, and `MinioObjectStore` and all dependencies from settings"""
    
    discovery_bucket: str = settings.discovery_bucket
    planning_bucket: str = settings.planning_bucket
    raw_storage_bucket: str = settings.raw_storage_bucket

    minio_client = MinioStorageClient(
            endpoint= settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key
        )

    for bucket in (discovery_bucket, planning_bucket, raw_storage_bucket):
        if not minio_client._mio.bucket_exists(bucket):
            minio_client._mio.make_bucket(bucket)

    discovery_store = MinioObjectStore(
        client=minio_client,
        bucket_name=discovery_bucket
    )

    planning_store = MinioObjectStore(
        client=minio_client,
        bucket_name=planning_bucket
    )

    raw_store = MinioObjectStore(
        client=minio_client,
        bucket_name=raw_storage_bucket
    )

    return discovery_store, planning_store, raw_store

def build_raw_storage_parser():
    ...

def load_input_arguments() -> dict[str, str]:
    """Retrieves input arguments from a command line call, deserializes the data, and stores it into memory."""
    parser = argparse.ArgumentParser()
    _now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    default_startdtime = (_now - timedelta(days=7)).strftime(DTFORMAT) # NOTE: NOAA --NLDAS--> NASA has ~4-5 day lag time
    default_enddtime = (_now - timedelta(days=6,seconds=1)).strftime(DTFORMAT)
    parser.add_argument("--startdtime", type=str, default=default_startdtime)
    parser.add_argument("--enddtime", type=str, default=default_enddtime)
    parser.add_argument(
        "--spatial-subset",
        choices=("conus", "ca", "sd"),
        default="conus",
    )
    parser.add_argument("--discovery-report-key", required=True)
    args, _unknown_args = parser.parse_known_args()
    return vars(args)

def get_spatial_subset_from_name(name: str) -> dom.SpatialExtent:
    """Creates a spatial subset from valid spatial subset name options"""
    # TODO: Convert name from [str] to an [enum] class to limit possible choices
    
    subsets = {
        'conus': None,
        'ca': dom.SpatialExtent(
            name='ca',
            north=42.002, west=-124.410, 
            south=32.534, east=-114.131
        ),
        'sd': dom.SpatialExtent(
            name='sd',
            north=33.505, west=-117.83,
            south=32.529, east=-116.081
        )
    }
    try:
        subset = subsets[name]
    except:
        raise ValueError(f"subset name {name} is not a valid option. Select from (`conus`, `ca`, `sd`)")

    return subset
    
def plan_nldas_download_jobs():
    """
    Creates a download job report artifact and writes it to the linked object store
    by comparing available granules from the granule discovery report (pass via cmd-line arg) 
    and existing object storage. Each download job in the download jobs report includes all 
    instructions and data necessary for downstream downloading processes to download an NLDAS 
    granule from NASA Earthdata servers. They also include critical metadata for the granule 
    (e.g. Earthdata identifiers and versioning) as well as domain information regarding spatial 
    area of extent and whether or not the granule is being subset.

    Returns: Artifact is written from memory to the object store
    """

    progset.load_dotenv_config()
    settings = progset.load_settings()
    args = load_input_arguments()

    time_range: Tuple[datetime, datetime] = (
        datetime.strptime(args['startdtime'], DTFORMAT),
        datetime.strptime(args['enddtime'], DTFORMAT),
    )

    spatial_subset_name: str = args['spatial_subset']
    spatial_subset: dom.SpatialExtent = get_spatial_subset_from_name(
        name = spatial_subset_name
    )

    discovery_store, planning_store, raw_store = build_object_stores(settings)

    discovery_report = plan.load_discovery_report_from_object_store(
        object_key=args['discovery_report_key'],
        object_store=discovery_store
    )

    discovered_granules_table = plan.create_granules_table_from_discovery_report(
        discovery_report=discovery_report
    ) # TODO: Implement method that generates pandas dataframe of granuels with critical info | have a typed structure for the table, maybe use pandera

    search_prefix = f"nldas/{spatial_subset.name}"
    stored_granules_table = plan.get_granules_table_from_object_store(
        object_store=raw_store,
        object_prefix=search_prefix,
        time_range=time_range
    )

    new_granules_table = plan.identify_new_granules(
        discovered=discovered_granules_table,
        stored=stored_granules_table
    )

    new_granules = [
        discovery_report.granules[id]
        for id in new_granules_table['discovery_id']
    ]

    download_job_plan = plan.create_download_job_plan(
        granules=new_granules,
        spatial_extent=spatial_subset
    )

    plan.write_download_job_plan_to_object_store(
        job_plan=download_job_plan,
        object_store=planning_store
    )
    
