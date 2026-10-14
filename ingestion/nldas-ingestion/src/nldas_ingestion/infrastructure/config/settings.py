import argparse
import dotenv
import os
from pathlib import Path
from typing import (Dict)
from dataclasses import dataclass


@dataclass
class Settings:
    object_store_endpoint: str
    object_store_access_key: str
    object_store_secret_key: str
    earthdata_username: str
    earthdata_password: str
    earthdata_token_bucket: str
    earthdata_token_key: str


def get_required_env_var(sys_var: str) -> str:
    sys_val = os.getenv(sys_var)
    if not sys_val:
        raise RuntimeError(f"Missing system variable `{sys_var}`.")
    return sys_val

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