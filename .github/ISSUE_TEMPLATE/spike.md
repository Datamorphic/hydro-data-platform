---
name: Spike
about: What do we need to learn or decide before we can confidently proceed?
title: "[Determine Credential Architecture for Distributed Ingestion]"
labels: ''
assignees: ''
type: Spike

---

A Spike is different because the desired output isn't necessarily code. It's knowledge or a decision.

This is particularly important when making architectural decisions about things like credentials, distributed workers, Earthaccess, MinIO, Iceberg, and orchestration.

___***The goal is to gather enough information to produce a decision, rather than become an expert in the topic.***___

## Question / Problem
What uncertainty are we trying to resolve?

***Example***: How should NASA Earthdata credentials be made available to distributed ingestion workers?

## Why It Matters
Why can't we simply proceed without answering it?

***Example***: Discovery, retrieval, and transformation may eventually execute as separate processes or workers. We need to establish where authentication occurs and how credentials are safely made available.

## Investigation Scope
What specifically will be investigated or tested?

***Example***:
- Earthaccess authentication behavior
- Credential lifetime and refresh
- Orchestrator vs. worker authentication
- Shared credential libraries
- Secret-management options
- Failure/retry scenarios

## Questions to Answer
The concrete questions the investigation should resolve.

***Example***:
- Should every worker authenticate independently?
- Should authentication occur centrally?
- Can credentials safely be handed off between processes?
- What happens when a worker starts independently?
- How would this change when moving from local MinIO to AWS?

## Deliverable
What artifact constitutes completion—decision, design, prototype, benchmark, etc.?

***Example***: Document the recommended credential architecture and rationale.

## Decision / Findings
The conclusions reached after investigation.

***Example***: TBD

## Follow-up Work
Tasks/issues created as a result of the investigation.

***Example***: TBD — create implementation tasks after the decision.
