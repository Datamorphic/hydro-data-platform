import argparse
import dotenv
import os
from pathlib import Path
from typing import (Dict)
from dataclasses import dataclass

import nldas_ingestion.infrastructure.config.settings as progset
from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore

from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_provider import (
    EarthDataTokenStore,
    EarthDataTokenValidator,
    EarthDataTokenRetriever,
    EarthDataTokenProvider
)

def build_earthdata_token_provider(settings: progset.Settings) -> EarthDataTokenProvider:
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
        bucket_name=settings.earthdata_token_bucket
    )

    earthdata_token_store = EarthDataTokenStore(
        object_store=minio_store,
        object_key=settings.earthdata_token_key
    )

    earthdata_token_validator = EarthDataTokenValidator()

    earthdata_token_retriever = EarthDataTokenRetriever()
    
    return EarthDataTokenProvider(
        token_store=earthdata_token_store,
        token_validator=earthdata_token_validator,
        token_retriever=earthdata_token_retriever
    )
    

def authenticate_with_earthdata(): # main entry point
    ###############################################
    # 1. Input Handling / Environment Configuration
    ###############################################
    
    # TODO: Implement orchestration job details from command line arguements
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--run-id", required=True)
    # parser.add_argument("--job_id", required=True)
    # args = parser.parse_args()
    progset.load_dotenv_config() # load settings configuration into environment
    settings = progset.load_settings() # let settings from environment

    ################
    # 2. Composition
    ################
    earthdata_token_provider = build_earthdata_token_provider(settings=settings)

    #############################################
    # Run Process (Get token from token provider)
    #############################################
    _ = earthdata_token_provider.get_token()

    print("Earthdata authentication succeeded. A valid token is cached.")


# TODO: Consider putting logic for authentication into the nldas client
if __name__ == "__main__":
    authenticate_with_earthdata()
    