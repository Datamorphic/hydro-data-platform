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
Shows interactions between key system components as well as the dependency of that interaction.
> e.g. ***Ingestion Orchestrator*** relies on *planning logic* in the ***Retrieval Planner***, denoted by `plan()`.

```mermaid
---
config:
  theme: redux
---
graph TD

    %% =========================
    %% External NASA Services
    %% =========================

    subgraph external["External Services (NASA)"]

        e1["NASA Earthdata<br>(Authentication)"]
        e2["NASA CMR<br>(Catalog Search)"]
        e3["NASA Earthdata<br>(Full Granules)"]
        e4["GES DISC<br>(Subset Granules)"]

    end


    %% =========================
    %% Internal Components
    %% =========================

    subgraph internal["Internal"]

        subgraph orchestration["Orchestration"]

            i1["Ingestion Orchestrator"]
            i2["Retrieval Planner"]
            i3["Retrieval Executor"]
            i4["Ingestion Evaluator"]

        end


        subgraph client["NASA Clients"]

            c1["Authentication Client"]
            c2["Catalog Client"]
            c3["Data Client"]

        end


        subgraph processing["Data Processing"]

            p1["Granule Processor"]
            p2["NetCDF Validator"]

        end


        subgraph metadata["Metadata / Persistence"]

            m1["Ingestion Recorder"]

        end

    end


    %% =========================
    %% Internal Storage
    %% =========================

    subgraph storage["Internal Storage"]

        s1["Raw Landing<br>NetCDF Files"]
        s2["Ingestion Metadata"]

    end


    %% =========================
    %% Orchestration Interactions
    %% =========================

    i1 -->|"authenticate()"| c1
    i1 -->|"search()"| c2
    i1 -->|"plan()"| i2
    i1 -->|"execute()"| i3
    i1 -->|"evaluate()"| i4
    i1 -->|"record ingestion"| m1


    %% =========================
    %% Retrieval Execution
    %% =========================

    i3 -->|"process jobs concurrently"| p1


    %% =========================
    %% Granule Processing
    %% =========================

    p1 -->|"retrieve()"| c3
    p1 -->|"validate()"| p2
    p1 -->|"record granule result"| m1


    %% =========================
    %% NASA Client Interactions
    %% =========================

    c1 -->|"authenticate()"| e1
    c2 -->|"search catalog"| e2
    c3 -->|"retrieve full granule"| e3
    c3 -->|"retrieve subset granule"| e4


    %% =========================
    %% Data Landing
    %% =========================

    c3 -->|"write retrieved data"| s1


    %% =========================
    %% Metadata Persistence
    %% =========================

    m1 -->|"write ingestion records"| s2


    %% =========================
    %% Storage Shapes
    %% =========================

    s1@{ shape: lin-cyl}
    s2@{ shape: lin-cyl}
```

## Sequence Diagram
Shows the flow of a program between components over time. The order of event happen from top to bottom.

```mermaid

---
config:
  theme: redux
---
sequenceDiagram

    actor User

    participant O as Ingestion Orchestrator
    participant A as Authentication Client
    participant C as Catalog Client
    participant P as Retrieval Planner
    participant E as Retrieval Executor
    participant G as Granule Processor
    participant D as NASA Data Client
    participant V as NetCDF Validator
    participant R as Ingestion Recorder
    participant I as Ingestion Evaluator

    participant Auth as NASA Earthdata<br/>Authentication
    participant CMR as NASA CMR<br/>Catalog
    participant Full as NASA Earthdata<br/>Full Granules
    participant Subset as GES DISC<br/>Subset Granules


    %% =========================================================
    %% Ingestion Initialization
    %% =========================================================

    User->>O: Start ingestion(user input)

    %% =========================================================
    %% Authentication
    %% =========================================================

    O->>A: authenticate(credentials)

    loop Until authenticated or attempts exhausted

        A->>Auth: Authenticate
        Auth-->>A: Authentication response

        alt Authentication successful
            A-->>O: Authenticated session
        else Authentication failed
            A->>A: Check retry attempts

            alt Attempts remaining
                A-->>O: Authentication retry required
            else No attempts remaining
                A-->>O: Authentication error
                O-->>User: Ingestion failed
            end
        end

    end


    %% =========================================================
    %% Catalog Search
    %% =========================================================

    O->>C: search(search criteria, session)

    loop Until search succeeds or retry exhausted

        C->>CMR: Search catalog
        CMR-->>C: Catalog response

        alt Search successful
            C-->>O: Granule metadata
        else Search failed
            C->>C: Evaluate retry policy

            alt Retryable
                C->>CMR: Retry catalog search
            else Not retryable
                C-->>O: Search error
                O-->>User: Ingestion failed
            end
        end

    end


    %% =========================================================
    %% Granule Planning
    %% =========================================================

    O->>P: plan(granule metadata, ingestion requirements)

    alt No granules found
        P-->>O: No data
        O-->>User: No data found
    else Granules found

        P->>P: Select granules
        P->>P: Determine retrieval strategy

        alt Full granule retrieval

            P->>P: Create full GranuleJobs
            P-->>O: GranuleJobs[]

        else Spatial subset retrieval

            P->>P: Create subset GranuleJobs
            P-->>O: GranuleJobs[]

        end

    end


    %% =========================================================
    %% Concurrent Granule Processing
    %% =========================================================

    O->>E: execute(GranuleJobs[])

    par Granule Job 1

        E->>G: process(GranuleJob 1)

        G->>D: retrieve(request)

        alt Full granule

            D->>Full: Request full granule
            Full-->>D: Granule response

        else Spatial subset

            D->>Subset: Request subset granule
            Subset-->>D: Granule response

        end

        alt Request successful

            D->>D: Download NetCDF
            D->>D: Write NetCDF to raw landing
            D-->>G: Data reference

            G->>V: validate(data reference)
            V-->>G: Validation result

            alt NetCDF valid

                G->>R: record granule success
                R-->>G: Record confirmed
                G-->>E: Granule success

            else NetCDF invalid

                alt Validation failure retryable

                    G->>D: retry retrieval

                else Validation failure not retryable

                    G->>R: record granule failure
                    R-->>G: Record confirmed
                    G-->>E: Granule failure

                end

            end

        else Request failed

            alt Request failure retryable

                G->>D: retry retrieval

            else Request failure not retryable

                G->>R: record granule failure
                R-->>G: Record confirmed
                G-->>E: Granule failure

            end

        end


    and Granule Job 2

        E->>G: process(GranuleJob 2)

        G->>D: retrieve(request)

        alt Full granule

            D->>Full: Request full granule
            Full-->>D: Granule response

        else Spatial subset

            D->>Subset: Request subset granule
            Subset-->>D: Granule response

        end

        D-->>G: Data reference
        G->>V: validate(data reference)
        V-->>G: Validation result
        G->>R: record granule result
        G-->>E: Granule result


    and Granule Job N

        E->>G: process(GranuleJob N)

        G->>D: retrieve(request)

        alt Full granule

            D->>Full: Request full granule
            Full-->>D: Granule response

        else Spatial subset

            D->>Subset: Request subset granule
            Subset-->>D: Granule response

        end

        D-->>G: Data reference
        G->>V: validate(data reference)
        V-->>G: Validation result
        G->>R: record granule result
        G-->>E: Granule result

    end


    %% =========================================================
    %% Evaluate Overall Ingestion
    %% =========================================================

    E-->>O: GranuleResults[]

    O->>I: evaluate(GranuleResults[])

    I->>I: Calculate success rate

    alt At least 80% successful

        I-->>O: Successful ingestion
        O->>R: record ingestion metadata
        R-->>O: Record confirmed
        O-->>User: Ingestion successful

    else Less than 80% successful

        I-->>O: Failed ingestion
        O->>R: record ingestion failure
        R-->>O: Record confirmed
        O-->>User: Ingestion failed

    end
```