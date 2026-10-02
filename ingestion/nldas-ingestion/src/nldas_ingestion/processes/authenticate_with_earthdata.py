import argparse
import dotenv
import os
from pathlib import Path
from typing import (Dict)
from dataclasses import dataclass

from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient
from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore

from nldas_ingestion.infrastructure.earthdata.auth.earthdata_token_provider import (
    EarthDataTokenStore,
    EarthDataTokenValidator,
    EarthDataTokenRetriever,
    EarthDataTokenProvider
)

@dataclass
class Settings:
    object_store_endpoint: str
    object_store_access_key: str
    object_store_secret_key: str
    earthdata_username: str
    earthdata_password: str
    earthdata_token_bucket: str
    earthdata_token_key: str

def load_dotenv_config():
    """
    Searches for an environmental configuration file path in the following locations
    and loads it:
    1. First look in system environmental variables for `HDP_CONFIG`
    2. Fallback by looking in current working directory. 
    """
    import os

    env_path = os.getenv("HDP_CONFIG")

    if not env_path:
        raise RuntimeError(f"Missing required environment variable `HDP_CONFIG`. Can not load settings.")
    
    env_path = Path(env_path)
    if not env_path.exists():
        raise RuntimeError(f"Configuration settings do not exist at path specified by environment variable `HDP_CONFIG`.")

    dotenv.load_dotenv(dotenv_path=env_path)    

def load_settings() -> Settings:
    return Settings(
        earthdata_username=get_required_env_var("EARTHDATA_USERNAME"),
        earthdata_password=get_required_env_var("EARTHDATA_PASSWORD"),
        object_store_endpoint=get_required_env_var("OBJECT_STORE_ENDPOINT"),
        object_store_access_key=get_required_env_var("OBJECT_STORE_ACCESS_KEY"),
        object_store_secret_key=get_required_env_var("OBJECT_STORE_SECRET_KEY"),
        earthdata_token_bucket=get_required_env_var("EARTHDATA_TOKEN_BUCKET"),
        earthdata_token_key=get_required_env_var("EARTHDATA_TOKEN_KEY")        
    )

def get_required_env_var(sys_var: str) -> str:
    sys_val = os.getenv(sys_var)
    if not sys_val:
        raise RuntimeError(f"Missing system variable `{sys_var}`.")
    return sys_val

def build_earthdata_token_provider(settings: Settings) -> EarthDataTokenProvider:
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

    load_dotenv_config() # load settings configuration into environment
    settings = load_settings() # let settings from environment

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
    