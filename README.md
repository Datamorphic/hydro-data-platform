# hydro-data-platform

**[Link to Documentation Website](https://datamorphic.github.io/hydro-data-platform/)**

Data platform for data used as input for hydrologic modeling

This repository is the product of a fictional data engineering consulting project. It includes both the source code and project documentation for a data platform built to serve the business needs of a fictional Water Resources consultant firm specializing in hydrologic modeling and ananlysis.



# High-Level Architecture (Draft)

## Storage
The data platform will feature a lakehouse architecture built atop local object storage. Apache Iceberg will serve as the open table format to manage metadata, while a centralized catalog will handle table discovery and atomic state changes. The data architecture will follow a medallion structure (bronze, silver, and gold layers) supplemented by a raw landing zone.

### Storage Zone Breakdown
**Landing:** _Raw data preserved from upstream source._<br>
**Bronze:** _Validated data that is safe for downstream processing._<br>
**Silver:** _Cleansed, standardized, curated and integrated enterprise data._<br>
**Gold:** _Business-ready data that has been modeled and optimized for analyics and hydrologic modeling._<br>

### Conceptual Diagram

```mermaid
---
config:
  layout: elk
  theme: redux
---
flowchart TD

    %% =========================
    %% Upstream
    %% =========================

    subgraph upstream["Upstream Scientific Datasets"]
        u1["Gridded Meteorological<br>Datasets"]
        u2["Point Meteorological<br>Datasets"]
    end

    %% =========================
    %% Ingestion
    %% =========================

    subgraph ingestion["Ingestion"]
        i1["Discovery"]
        i2["Ingestion Pipelines"]
    end

    %% =========================
    %% Storage
    %% =========================

    subgraph storage["Storage"]
        s1["Raw Landing"]

        subgraph lakehouse["Lakehouse"]
            sl1["Bronze"]
            sl2["Silver"]
            sl3["Gold"]
        end
    end

    %% =========================
    %% Processing
    %% =========================

    subgraph processing["Processing"]
        p1["Raw → Bronze<br>Validation & Registration"]
        p2["Bronze → Silver<br>Cleansing, Standardization & Integration"]
        p3["Silver → Gold<br>Curation, Modeling & Optimization"]
    end

    %% =========================
    %% Downstream
    %% =========================

    subgraph downstream["Downstream Users"]
        d1["Hydrologic Analytics"]
        d2["Hydrologic Modeling"]
    end

    %% =========================
    %% Control Plane
    %% =========================

    subgraph control["Platform Operations & Control"]
        c1["Orchestration"]
        c2["Observability"]
    end

    %% =========================
    %% Metadata & Governance
    %% =========================

    subgraph governance["Metadata & Governance"]
        g1["Metadata & Catalog"]
        g2["Data Quality"]
        g3["Data Lineage"]
        g4["Access Control"]
    end

    %% =========================
    %% Primary Data Flow
    %% =========================

    upstream --> ingestion
    ingestion --> s1

    s1 --> p1
    p1 --> sl1

    sl1 --> p2
    p2 --> sl2

    sl2 --> p3
    p3 --> sl3

    sl3 --> downstream

    %% =========================
    %% Control Plane Relationships
    %% =========================

    c1 -. controls .-> ingestion
    c1 -. controls .-> processing
    c1 -. controls .-> governance

    c2 -. monitors .-> ingestion
    c2 -. monitors .-> processing
    c2 -. monitors .-> storage

    %% =========================
    %% Metadata & Governance Relationships
    %% =========================

    g1 -. describes .-> storage
    g2 -. validates .-> processing
    g3 -. tracks .-> processing
    g4 -. governs .-> downstream
```

### Implementation Diagram
```mermaid
---
config:
  layout: elk
  theme: redux
---
flowchart TB

    %% =========================
    %% UPSTREAM
    %% =========================

    subgraph upstream["Upstream Scientific Datasets"]
        subgraph gridded["Gridded Meteorological Datasets"]
            ug1["NASA"]
            ug2["CA DWR"]
            ug3["OSU"]
        end

        subgraph point["Point Meteorological Datasets"]
            up1["NOAA"]
            up4["CA DWR"]
            up5["NIFC"]
        end
    end

    


    %% =========================
    %% ORCHESTRATION
    %% =========================

    subgraph orchestration["Orchestration"]
        o1["Dagster / Airflow"]
    end


    %% =========================
    %% INGESTION
    %% =========================

    subgraph ingestion["Ingestion"]
        i1["Discovery<br>Python + Source APIs"]
        i2["Ingestion Pipelines<br>Python"]
    end


    %% =========================
    %% STORAGE
    %% =========================

    subgraph storage["Storage — MinIO"]

        r1["Raw Landing"]

        subgraph lakehouse["Lakehouse"]
            sl1["Bronze<br>Apache Iceberg Tables"]
            sl2["Silver<br>Apache Iceberg Tables"]
            sl3["Gold<br>Apache Iceberg Tables"]
        end

    end


    %% =========================
    %% PROCESSING
    %% =========================

    subgraph processing["Processing"]

        subgraph spark["Spark Application"]
            sp["Apache Spark<br>Compute Engine"]
            ir["Apache Iceberg Runtime"]
        end

        py["Python<br>Validation"]
    end


    %% =========================
    %% CATALOG
    %% =========================

    subgraph catalog["Lakehouse Catalog"]
        c1["Iceberg Catalog"]
    end


    %% =========================
    %% ANALYTICS
    %% =========================

    subgraph analytics["Analytics & Query"]
        a1["DuckDB"]
        a2["Apache Spark"]
    end


    %% =========================
    %% DOWNSTREAM
    %% =========================

    subgraph downstream["Downstream Users"]
        d1["Hydrologic Analytics"]
        d2["Hydrologic Modeling"]
    end


    %% =========================
    %% PRIMARY DATA FLOW
    %% =========================

    upstream --> i1
    i1 --> i2
    i2 --> r1

    r1 --> py
    py --> sl1

    sl1 --> sp
    sp --> sl2

    sl2 --> sp
    sp --> sl3

    sl3 --> a1
    sl3 --> a2

    a1 --> downstream
    a2 --> downstream


    %% =========================
    %% ICEBERG RELATIONSHIPS
    %% =========================

    sp --> ir

    ir -->|"Reads / writes"| sl1
    ir -->|"Reads / writes"| sl2
    ir -->|"Reads / writes"| sl3

    c1 -. "Catalogs" .-> sl1
    c1 -. "Catalogs" .-> sl2
    c1 -. "Catalogs" .-> sl3


    %% =========================
    %% ORCHESTRATION
    %% =========================

    o1 -. "Orchestrates" .-> ingestion
    o1 -. "Orchestrates" .-> processing
```