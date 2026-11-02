from typing import (Optional)
from datetime import datetime
import pandera.pandas as pa
from pandera.typing.pandas import (Index, DataFrame, Series)


class StoredGranuleTableSchema(pa.DataFrameModel):
    """
    Schema for critical granule metadata required for job planning, 
    stored as pandas dataframes
    """
    granule_id: Series[str] = pa.Field(required=True, nullable=False, unique=True)
    last_updated_at: Series[datetime] = pa.Field(required=True, nullable=False)

class DiscoveredGranuleTableSchema(pa.DataFrameModel):
    """
    Schema for critical granule metadata required for job planning, 
    stored as pandas dataframes
    """
    discovery_id: Series[int] = pa.Field(required=True, nullable=False, unique=True)
    granule_id: Series[str] = pa.Field(required=True, nullable=False, unique=True)
    last_updated_at: Series[datetime] = pa.Field(required=True, nullable=False)