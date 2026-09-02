---
name: Task
about: What concrete piece of engineering work needs to happen?
title: "[Implement NLDAS Granule Discovery]"
labels: ''
assignees: ''
type: Task

---

A Task is the workhorse of your project. It should represent a discrete piece of engineering work that can be implemented, tested, reviewed, and completed.

## Objective
What specifically needs to be accomplished?

***Example***: Implement a component that identifies the 24 hourly NLDAS granules required to process a given day.


## Context
Information necessary to understand the task and its relationship to the larger feature.

***Example***: The ingestion workflow processes NLDAS data in daily batches. Discovery should be separated from downloading so that the workflow can determine what data is required before initiating retrieval.

## Scope
What work is included/excluded.

***Example***:
- Query NASA Earthdata
- Identify hourly granules for a specified date
- Return granule metadata required by the downloader
- Detect missing granules

## Acceptance Criteria
Specific, testable conditions that determine whether the task is complete.

***Example***:
- [ ] Given a valid date, the component identifies the expected hourly granules.
- [ ] A complete day returns 24 granules.
- [ ] Missing granules are detected.
- [ ] Returned metadata contains the information required by the retrieval component.
- [ ] Discovery logic has automated test coverage.

## Technical Considerations
Architectural constraints, conventions, technologies, or implementation considerations.

***Example***:
- Use earthaccess.
- Do not download data from this component.
- Do not implement credential retrieval here.
- Component should be usable by the orchestration layer.

## Dependencies
Work that must happen before this task can be completed.

***Example***:
- NLDAS dataset configuration
