import os, dotenv
import argparse
from pathlib import Path
from typing import (List, Tuple, Dict, Mapping)
from datetime import (datetime, timezone, timedelta)

import nldas_ingestion.infrastructure.config.settings as progset
import nldas_ingestion.infrastructure.earthdata.cmr.discoverer as discover
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore

DTFORMAT = "%Y-%m-%dT%H:%M:%SZ" # NASA uses UTC time zone so append with "Z"

def build_object_store(settings: progset.Settings) -> MinioObjectStore:
    """Composes `EarthDataTokenProvider` and all dependencies from settings"""
    
    ########################
    # Dependency Composition
    ########################
    minio_client = MinioStorageClient(
            endpoint= settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key
        )

    minio_store = MinioObjectStore(
        client=minio_client,
        bucket_name="raw" # TODO: Add to settings
        # bucket_name=settings.earthdata_token_bucket
    )

    return minio_store

def build_granule_extractor() -> discover.GranuleExtractor:
    return discover.GranuleExtractor()


def load_input_arguments() -> dict[str, str]:
    """Retrieves input arguments from a command line call, deserializes the data, and stores it into memory."""
    parser = argparse.ArgumentParser()
    _now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    default_startdtime = (_now - timedelta(days=7)).strftime(DTFORMAT) # NOTE: NOAA --NLDAS--> NASA has ~4-5 day lag time
    default_enddtime = (_now - timedelta(days=6,seconds=1)).strftime(DTFORMAT)
    parser.add_argument("--startdtime", type=str, default=default_startdtime)
    parser.add_argument("--enddtime", type=str, default=default_enddtime)
    args, _unknown_args = parser.parse_known_args()
    return vars(args)


def discover_nldas_granules():
    """
    Searches the Earthdata Common Metadata Repository (CMR) 
        for available NLDAS datasets that coincide with provide
        input parameters constraints, ingest the results, and 
        write them to storage as a discovery report artifact.
    """

    progset.load_dotenv_config()
    settings = progset.load_settings()
    progargs = load_input_arguments()
    object_store = build_object_store(settings=settings)
    granule_extractor = build_granule_extractor()

    start_dtime = datetime.strptime(progargs['startdtime'],DTFORMAT)
    end_dtime = datetime.strptime(progargs['enddtime'],DTFORMAT)

    cmr_request = discover.create_discovery_request_for_cmr(
        startdtime=start_dtime,
        enddtime=end_dtime
    )
    
    discovery_response = discover.request_discovery_from_cmr(cmr_request)
    discovery_report = discover.create_discovery_report(
        discovery=discovery_response,
        extractor=granule_extractor
    )

    discover.write_discovery_report_to_object_store(
        discovery_report=discovery_report,
        object_store=object_store
    )


if __name__ == '__main__':
    discover_nldas_granules()
    