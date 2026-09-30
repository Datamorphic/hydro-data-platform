```
nldas-ingestion/
│
├── applications/        ← WHAT the system does
│
├── domain/              ← WHAT the system knows about
│
├── infrastructure/      ← HOW it talks to the outside world
│
├── contracts/           ← HOW processes communicate
│
├── orchestration/       ← WHEN / IN WHAT ORDER things run
│
├── schemas/              ← Formal definitions of artifact formats
│
├── cli/                  ← How humans/process launchers invoke applications
│
├── tests/
└── docs/
```

# The resulting runtime architecture

The codebase then maps nicely onto your runtime architecture:

```
                    ┌──────────────────────────┐
                    │         DAGSTER          │
                    │                          │
                    │ orchestration/dagster/   │
                    └────────────┬─────────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             │                   │                    │
             ▼                   ▼                    ▼
       Authenticate          Discover               Plan
       Application           Application          Application
             │                   │                    │
             │                   │                    │
             │             Discovery Artifact         │
             │                   │                    │
             │                   └───────────────────►│
             │                                        │
             │                                  Download Plan
             │                                        │
             │                              ┌─────────┼─────────┐
             │                              ▼         ▼         ▼
             │                          Download  Download  Download
             │                           Process    Process    Process
             │                              │         │         │
             │                              ▼         ▼         ▼
             │                            Raw A     Raw B     Raw C
             │                              │         │         │
             │                              └─────────┼─────────┘
             │                                        ▼
             │                                     Validate
             │                                        │
             │                                        ▼
             │                                     Publish
             │                                        │
             └────────────────────────────────────────┼───────
                                                      ▼
                                             ┌─────────────────┐
                                             │      MinIO      │
                                             │    / Iceberg    │
                                             └─────────────────┘
```

And each application internally looks like:
```
              APPLICATION PROCESS
                      
External input
      │
      ▼
┌─────────────┐
│   Handler   │  ← process boundary
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Service   │  ← application logic
└──────┬──────┘
       │
   ┌───┴────┬─────────────┐
   ▼        ▼             ▼
 Client   Repository   ObjectStore
   │        │             │
   ▼        ▼             ▼
 NASA     Database       MinIO
```

That gives you a very clean three-level architecture:
```
┌──────────────────────────────────────────┐
│  WORKFLOW                                │
│  Dagster                                 │
│  "When and in what order?"               │
├──────────────────────────────────────────┤
│  APPLICATION                             │
│  Handler → Service                       │
│  "What operation should be performed?"   │
├──────────────────────────────────────────┤
│  INFRASTRUCTURE                          │
│  Clients / Repositories / Adapters       │
│  "How do I interact with external stuff?"│
├──────────────────────────────────────────┤
│  ARTIFACT CONTRACTS                      │
│  Discovery / Plan / Raw                  │
│  "How do processes communicate?"         │
└──────────────────────────────────────────┘
```