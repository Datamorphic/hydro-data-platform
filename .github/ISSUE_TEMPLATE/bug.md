---
name: Bug
about: What existing behavior is incorrect, and what should it do instead?
title: "[NLDAS ingestion silently accepts missing hourly granules]"
labels: ''
assignees: ''
type: Bug

---

A Bug describes a discrepancy between actual behavior and expected behavior.

## Problem
What is wrong?

***Example***: The daily ingestion process produces output when one or more hourly NLDAS granules are missing.

## Expected Behavior
What should happen?

***Example***: The ingestion job should detect an incomplete 24-hour input set and fail or explicitly mark the ingestion as incomplete.

## Actual Behavior
What happens instead?

***Example***: The transformation proceeds using the available granules.

## Steps to Reproduce
How can someone reliably reproduce the problem?

***Example***:
1. Remove the 14:00 UTC granule from a day's input.
2. Run the daily ingestion job.
3. Inspect the resulting dataset.

## Environment / Context
Relevant versions, inputs, configuration, OS, dataset, etc.

***Example***:
- NLDAS ingestion pipeline
- Local MinIO
- xarray
- Python 3.x

## Evidence
Logs, error messages, screenshots, failing tests, sample data, etc.

***Example***:
```
Expected 24 hourly files
Found 23
Job completed successfully
```

## Acceptance Criteria
What must be true for the bug to be considered fixed?

***Example***:
Missing hourly granules are detected.
- [ ] The ingestion does not produce a falsely complete dataset.
- [ ] The failure/incomplete state is communicated to the orchestrator.
- [ ] A regression test reproduces the original failure.

## Impact / Severity
How significantly does the bug affect the system?

***Example***: High — incomplete environmental data could propagate into downstream modeling.
