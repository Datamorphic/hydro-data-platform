# NLDAS Ingestion

## Activity Diagram
- - - 
```mermaid
flowchart TB
    Start["Start"] --> n1["Authenticate with NASA"]
    n1 --> n2["Authenticated?"]
    n2 -- Yes --> n4["Locate NASA Granules"]
    n2 -- No --> n3["Attempts Remaining?"]
    n3 -- Yes --> n1
    n3 -- No --> n25["Throw Authentication Error"]
    n25 --> End["End"]
    n4 --> n5["Search Successful?"]
    n5 -- No --> n26["Retryable?"]
    n26 -- Yes --> n4
    n26 -- No --> n27["Throw Search Error"]
    n27 --> End
    n5 -- Yes --> n6["Granules Found?"]
    n6 -- No --> n7["Throw No Data Error"]
    n7 --> End
    n6 -- Yes --> n8["Select Granules"]
    n8 --> n9["Spatial Subsetting?"]
    n9 -- No --> n10["Prepare Full Granule Requests"]
    n9 -- Yes --> n11["Prepare Subset Granule Requests"]
    n10 --> n12["Fork Granule Requests"]
    n11 --> n12
    n12 --> n13["Request Granule"]
    n13 --> n14["Await Granule Response"]
    n14 --> n15["Successful Request?"]
    n15 -- No --> n16["Retryable?"]
    n16 -- Yes --> n13
    n16 -- No --> n17["Record Granule Failure"]
    n15 -- Yes --> n18["Download NetCDF"]
    n18 --> n19["Download Complete?"]
    n19 -- No --> n16
    n19 -- Yes --> n20["Validate NetCDF"]
    n20 --> n21["Valid NetCDF?"]
    n21 -- No --> n22["Retryable?"]
    n22 -- Yes --> n13
    n22 -- No --> n17
    n21 -- Yes --> n23["Record Granule Success"]
    n17 --> n24["Join Granule Results"]
    n23 --> n24
    n24 --> n25a["Calculate Ingestion Success Rate"]
    n25a --> n26a{"At Least 80% Successful?"}
    n26a -- Yes --> n27a["Record Ingestion Metadata"]
    n26a -- No --> n28a["Record Ingestion Failure"]
    n27a --> End
    n28a --> End

    Start@{ shape: start}
    n1@{ shape: proc}
    n2@{ shape: diam}
    n4@{ shape: proc}
    n3@{ shape: diam}
    n25@{ shape: proc}
    End@{ shape: stop}
    n5@{ shape: diam}
    n26@{ shape: diam}
    n27@{ shape: proc}
    n6@{ shape: diam}
    n7@{ shape: proc}
    n8@{ shape: proc}
    n9@{ shape: diam}
    n10@{ shape: proc}
    n11@{ shape: proc}
    n12@{ shape: fork}
    n13@{ shape: proc}
    n14@{ shape: collate}
    n15@{ shape: diam}
    n16@{ shape: diam}
    n17@{ shape: proc}
    n18@{ shape: proc}
    n19@{ shape: diam}
    n20@{ shape: proc}
    n21@{ shape: diam}
    n22@{ shape: diam}
    n23@{ shape: proc}
    n24@{ shape: fork}
```

# Mapping Responsibility~Activity
- - -
| Activity / Decision              | Responsibility                                           | Proposed Component                           | Inputs                                 | Outputs                     |
| -------------------------------- | -------------------------------------------------------- | -------------------------------------------- | -------------------------------------- | --------------------------- |
| Authenticate with NASA           | Establish authenticated NASA session                     | **NASA Authentication Client**               | NASA credentials/configuration         | Authenticated session       |
| Authenticated?                   | Determine whether authentication succeeded               | **NASA Authentication Client**               | Authentication response                | Success/failure             |
| Attempts Remaining?              | Apply authentication retry policy                        | **NASA Authentication Client**               | Attempt count, retry policy            | Retry / fail                |
| Locate NASA Granules             | Search NASA catalog for matching granules                | **NASA Catalog Client**                      | Search criteria                        | Granule metadata            |
| Search Successful?               | Determine whether catalog request succeeded              | **NASA Catalog Client**                      | Catalog response                       | Success/failure             |
| Retryable?                       | Determine whether failed operation should be retried     | **NASA Catalog Client / Retrieval Executor** | Error, retry policy                    | Retry / fail                |
| Granules Found?                  | Determine whether search produced usable granules        | **Retrieval Planner**                        | Granule metadata                       | Continue / no-data          |
| Select Granules                  | Select granules relevant to ingestion                    | **Retrieval Planner**                        | Granule metadata, ingestion criteria   | Selected granules           |
| Spatial Subsetting?              | Determine retrieval strategy                             | **Retrieval Planner**                        | Ingestion configuration                | Full/subset strategy        |
| Prepare Full Granule Requests    | Construct full-granule jobs                              | **Retrieval Planner**                        | Selected granules                      | Full `GranuleJob`s          |
| Prepare Subset Granule Requests  | Construct spatial-subset jobs                            | **Retrieval Planner**                        | Selected granules, spatial extent      | Subset `GranuleJob`s        |
| Fork Granule Requests            | Submit independent granule jobs for concurrent execution | **Retrieval Executor**                       | Collection of `GranuleJob`s            | Concurrent executions       |
| Request Granule                  | Retrieve requested NASA data                             | **NASA Data Client**                         | `GranuleJob` retrieval information     | NASA response/data          |
| Await Granule Response           | Manage completion of NASA request                        | **NASA Data Client / Retrieval Executor**    | Active request                         | Response/result             |
| Successful Request?              | Determine whether NASA request succeeded                 | **NASA Data Client**                         | NASA response                          | Success/failure             |
| Retryable?                       | Determine whether retrieval failure should be retried    | **Retrieval Executor**                       | Error/result, retry policy             | Retry / record failure      |
| Download NetCDF                  | Retrieve NetCDF content                                  | **NASA Data Client**                         | NASA granule/request                   | Local/temporary NetCDF      |
| Download Complete?               | Determine whether transfer completed                     | **NASA Data Client**                         | Download result                        | Complete/incomplete         |
| Validate NetCDF                  | Verify retrieved dataset is usable                       | **NetCDF Validator**                         | NetCDF file/data                       | Validation result           |
| Valid NetCDF?                    | Determine whether dataset passed validation              | **NetCDF Validator**                         | Validation result                      | Valid/invalid               |
| Record Granule Success           | Record successful granule processing                     | **Ingestion Recorder**                       | Granule result, metadata               | Success record              |
| Record Granule Failure           | Record unsuccessful granule processing                   | **Ingestion Recorder**                       | Granule result, error information      | Failure record              |
| Join Granule Results             | Wait for all concurrent granule jobs to finish           | **Retrieval Executor**                       | Individual job results                 | Complete result set         |
| Calculate Ingestion Success Rate | Calculate batch-level success percentage                 | **Ingestion Evaluator**                      | Granule results                        | Success rate                |
| At Least 80% Successful?         | Apply ingestion acceptance criterion                     | **Ingestion Evaluator**                      | Success rate, threshold                | Successful/failed ingestion |
| Record Ingestion Metadata        | Record overall ingestion/provenance information          | **Ingestion Recorder**                       | Ingestion results, job metadata        | Ingestion record            |
| Record Ingestion Failure         | Record failed ingestion outcome                          | **Ingestion Recorder**                       | Evaluation result, failure information | Failure record              |
| Overall workflow coordination    | Coordinate the entire ingestion lifecycle                | **Ingestion Orchestrator**                   | Configuration, component results       | Ingestion completion/status |

# Component Diagram
Shows interactions between key system components

```mermaid
---
config:
  theme: redux
---
graph TD
    %% Containers
    subgraph external["External Services (NASA)"]
        e1["Authentication"]
        e2["NASA CMR<br>(Catalog Search)"]
        e3["NASA Earthdata<br>(Full Granules)"]
        e4["GES DISC<br>(Subset Granules)"]
    end

    subgraph internal["Internal"]
        subgraph Orchestration["Orchestration"]
            i1["Ingestion Orchestrator"]
            i2["Job Planner"]
            i3["Job Executor"]
            i4["Ingestion Evaluator"]
        end

        subgraph client["NASA Client"]
            c1["Authentication Client"]
            c2["Catalog Client"]
            c3["Data Client"]
        end

        subgraph processing["Data Processing"]
            p1["Granule Processor"]
            p2["NetCDF Validator"]
        end

        subgraph metadata["Metadata/Persistance"]
            m1["Ingestion Recorder"]
        end
    end

    subgraph storage["Internal Storage"]
        subgraph object["Raw Landing"]
            so1["NetCDF File"]
            so2["NetCDF File"]
            so3["NetCDF File"]
        end
        s1["Job Log"]
    end

    %% Relationships
    i1 --> c1 & c2 & m1
    c1 & c2 --> i2
    i2 --> i3
    i3 --> p1
    p1 --> c3 & p2 & m1 & storage
    c3 <--> e3 & e4
    c1 --> e1
    c2 --> e2
    m1 --> s1

    %% Styles
    so1@{ shape: lin-cyl}
    so2@{ shape: lin-cyl}
    so3@{ shape: lin-cyl}
    s1@{ shape: lin-cyl}
```