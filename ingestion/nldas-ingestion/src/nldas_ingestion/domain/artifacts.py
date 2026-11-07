from typing import (List, Dict, TypedDict)
from dataclasses import dataclass
from datetime import datetime
from typing import (Optional)

DTFORMAT = '%Y-%m-%dT%H:%M:%SZ'

class ObjectStoreObjectMeta(TypedDict):
    bucket_name: str
    object_name: str
    metadata: Dict[str,str]

class DiscoveryGranuleUmm(TypedDict):
    meta: dict
    umm: dict

class DiscoveryResponseUmm(TypedDict):
    hits: int
    took: int
    items: List[DiscoveryGranuleUmm]

class DiscoveryReportDict(TypedDict):
    meta: dict
    granules: List[dict]

@dataclass
class SpatialExtent:
    north: float
    east: float
    south: float
    west: float
    name: Optional[str] = None

@dataclass
class GranuleAccess:
    raw_url: str
    opendap_url: str | None

@dataclass
class Granule:
    granule_id: str
    granule_name: str
    date_time: datetime
    version: str
    last_updated_at: datetime
    spatial_extent: SpatialExtent
    access: GranuleAccess

@dataclass
class DiscoveryMeta:
    provider_id: str
    collection_id: str
    discovered_at: datetime

@dataclass
class DiscoveryReport:
    meta: DiscoveryMeta
    granules: List[Granule]

    def to_dict(self) -> dict:
        report_dict = to_dict(self)
        if not isinstance(report_dict, dict):
            report_dict = {'report': report_dict}
        return report_dict


@dataclass
class GranuleDownloadJob:
    job_id: str
    base_url: str
    subset: bool
    granule_id: str
    granule_name: str
    date_time: datetime
    version: str
    last_updated_at: datetime
    subset_extent: SpatialExtent | None

    def to_dict(self):
        return to_dict(self)

@dataclass
class GranuleDownloadJobPlan:
    spatial_extent: SpatialExtent
    jobs: List[GranuleDownloadJob]

    def to_dict(self):
        return to_dict(self)


def to_dict(obj):
    if hasattr(obj, "__dict__"):
        return {key: to_dict(val) for key, val in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: to_dict(val) for key, val in obj.items()}
    elif isinstance(obj, datetime):
        return obj.strftime(DTFORMAT)
    elif isinstance(obj, (str, int, float)):
        return obj
    else:
        return str(obj)
        

if __name__ == "__main__":

    report = DiscoveryReport(
        meta = DiscoveryMeta(
            provider_id="source",
            collection_id="collection",
            discovered_at=datetime.now()
        ),

        granules= [
            Granule(
                granule_id="id",
                granule_name="name",
                date_time=datetime.now(),
                version="version",
                last_updated_at=datetime.now(),
                spatial_extent=SpatialExtent(
                    north=1.1,
                    south=1.1,
                    east=1.1,
                    west=1.1
                ),
                access=GranuleAccess(
                    raw_url="url",
                    opendap_url="url"
                )
            )
        ]
    )

    import json
    with open("test_report.json","w") as f:
        json.dump(report.to_dict(), f, indent=10)
    

