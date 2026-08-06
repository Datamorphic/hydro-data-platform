# hydro-data-platform
Data platform for data used as input for hydrologic modeling

This repository is the product of a fictional data engineering consulting project. It includes both the source code and project documentation for a data platform built to serve the business needs of a fictional Water Resources consultant firm specializing in hydrologic modeling and ananlysis.

# High-Level Architecture (Draft)

## Storage
The data platform will feature a lakehouse architecture built atop local object storage. Apache Iceberg will serve as the open table format to manage metadata, while a centralized catalog will handle table discovery and atomic state changes. The data architecture will follow a medallion structure (bronze, silver, and gold layers) supplemented by a raw landing zone.

### Storage Zone Breakdown
**Landing:** _Raw data preserved from upstream source._<br>
**Bronze:** _Validated data that is safe for downstream processing._<br>
**Silver:** _Cleansed, standardized, and integrated enterprise data._<br>
**Gold:** _Business-ready data that has been modeled and optimized for analyics and hydrologic modeling._<br>

```mermaid
flowchart TB

    %% ============================================================
    %% UPSTREAM SOURCES
    %% ============================================================

    subgraph SOURCES["Upstream Data Sources"]
        GOV_GIS["Government<br/>Geospatial APIs"]
        GOV_TS["Government<br/>Hydrologic APIs"]
        GOV_MD["Government<br/>Multidimensional Data<br/>(NetCDF, Raster, etc.)"]
    end


    %% ============================================================
    %% CONTROL / INGESTION PLANE
    %% ============================================================

    subgraph CONTROL["Control Plane"]
        AIRFLOW["Apache Airflow<br/>Scheduling & Orchestration"]
        PYTHON["Python Control &<br/>Pipeline Layer"]
    end

    AIRFLOW --> PYTHON


    %% ============================================================
    %% RAW LANDING
    %% ============================================================

    subgraph OBJECT["Object Storage — MinIO"]
        RAW["Raw Landing Zone<br/><i>Immutable upstream data</i>"]

        subgraph LAKEHOUSE["Lakehouse"]
            BRONZE["Bronze<br/><i>Raw → Parquet + Iceberg</i>"]
            SILVER["Silver<br/><i>Cleaned, Standardized,<br/>QC'd Data</i>"]

            subgraph GOLD["Gold — Consumer Data Products"]
                MODEL["Modeler Data Model<br/><i>Hydrologic model inputs</i>"]
                ANALYST["Analyst Data Model<br/><i>Statistical analysis<br/>& exploration</i>"]
            end
        end
    end


    %% ============================================================
    %% TRANSACTIONAL GIS SYSTEM
    %% ============================================================

    subgraph GIS["Transactional GIS System"]
        POSTGIS["PostGIS"]
        KART["Kart<br/><i>Versioned Geospatial Data</i>"]
        GIS_USERS["GIS Analysts"]
    end

    GIS_USERS -->|"Edit / transform"| POSTGIS
    KART <-->|"Version control"| POSTGIS


    %% ============================================================
    %% ICEBERG
    %% ============================================================

    subgraph ICEBERG["Lakehouse Metadata & Transaction Layer"]
        CATALOG["Apache Iceberg<br/>Catalog"]
        METADATA["Iceberg Metadata<br/>Snapshots / Manifests / Schemas"]
    end

    CATALOG --> METADATA
    CATALOG -.-> BRONZE
    CATALOG -.-> SILVER
    CATALOG -.-> MODEL
    CATALOG -.-> ANALYST


    %% ============================================================
    %% COMPUTE
    %% ============================================================

    subgraph COMPUTE["Compute / Analytics Layer"]
        SPARK["Apache Spark<br/><i>Distributed Processing<br/>& Transformations</i>"]
    end


    %% ============================================================
    %% INGESTION FLOWS
    %% ============================================================

    GOV_GIS -->|"API ingestion"| PYTHON
    GOV_TS -->|"API ingestion"| PYTHON
    GOV_MD -->|"API ingestion"| PYTHON

    PYTHON -->|"Raw ingestion"| RAW

    %% Geospatial path
    RAW -->|"Validate / QC"| PYTHON
    PYTHON -->|"Geospatial ingestion"| POSTGIS

    POSTGIS -->|"Current source of truth"| RAW
    RAW -->|"Register / transform"| BRONZE

    %% Hydrologic / multidimensional path
    RAW -->|"Validate / QC / transform"| BRONZE


    %% ============================================================
    %% LAKEHOUSE TRANSFORMATIONS
    %% ============================================================

    BRONZE -->|"Clean / standardize / QC"| SPARK
    SPARK --> SILVER

    SILVER -->|"Apply business logic<br/>& consumer modeling"| SPARK

    SPARK --> MODEL
    SPARK --> ANALYST


    %% ============================================================
    %% DOWNSTREAM USERS
    %% ============================================================

    subgraph USERS["Downstream Consumers"]
        MODELERS["Hydrologic Modelers"]
        ANALYSTS["Hydrologic Analysts"]
    end

    MODEL -->|"SQL / Data Access"| MODELERS
    ANALYST -->|"SQL / Data Access"| ANALYSTS


    %% ============================================================
    %% SERVICE / ACCESS LAYER
    %% ============================================================

    subgraph ACCESS["Service & Access Layer — TBD"]
        SQL["SQL Interface / Query Engine"]
        API["Application / API Layer"]
    end

    MODELERS --> SQL
    ANALYSTS --> SQL
    SQL --> MODEL
    SQL --> ANALYST

    API -.-> SQL


    %% ============================================================
    %% CROSS-CUTTING PLATFORM SERVICES
    %% ============================================================

    subgraph PLATFORM["Cross-Cutting Platform Services — TBD"]
        GOVERNANCE["Governance & Security"]
        DISCOVERY["Accessibility & Discoverability"]
        MONITORING["Monitoring & Observability"]
    end

    GOVERNANCE -.-> SOURCES
    GOVERNANCE -.-> GIS
    GOVERNANCE -.-> OBJECT
    GOVERNANCE -.-> USERS

    DISCOVERY -.-> CATALOG
    DISCOVERY -.-> OBJECT
    DISCOVERY -.-> USERS

    MONITORING -.-> CONTROL
    MONITORING -.-> COMPUTE
    MONITORING -.-> OBJECT
    MONITORING -.-> GIS
```
