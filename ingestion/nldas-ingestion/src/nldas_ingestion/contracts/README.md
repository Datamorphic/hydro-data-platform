contracts/ is particularly important for your architecture

This is where I'd put the definitions of the artifacts passed between processes:

```
contracts/
├── discovery.py
├── download_plan.py
└── raw_artifact.py
```

Your architecture becomes:
```
Discover Process
      │
      │ produces
      ▼
┌──────────────────────┐
│ Discovery Contract   │
│        v1            │
└──────────────────────┘
      │
      │ stored in MinIO
      ▼
Plan Process
```

and ...

```
Plan Process
      │
      │ produces
      ▼
┌──────────────────────┐
│ Download Plan        │
│        v1            │
└──────────────────────┘
      │
      │ references
      ▼
 Download Jobs
```

The contract should be more stable than the implementation.

That's one of the strongest architectural benefits of your design.