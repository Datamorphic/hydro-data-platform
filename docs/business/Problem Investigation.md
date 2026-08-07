# Problem Investigation

This document explains the processes and findings of the problem investigation for <client>. The goal of the investigation was to determine the problems with the existing data platform used by <client>'s operations team (engineering). Issues experienced by several stakeholders are recorded from their perspective.

## Problems Identified by Stakeholders (eventually need to classify these, such as quality, lineage, interoperability, accessibility, etc)

**Engineer 1:** _"If I'm not the one who processed data for a project, I don't know where to find the data I need to build a hydrologic model."_<br>

**Engineer 2:** _"Employees are processing the same dataset for different projects in different ways. This is inefficient, and it makes it difficult to validate processed data."_<br>

**Engineer 3:** _"The projects I work on have several versions of the same dataset, but I don't know which is the most up-to-date authoritative version, nor do I know the steps taken to process these data without talking to the person who did the work."_<br>

**Manager 1:** _"I have trouble performing quality control checks on datasets because it's unclear what steps were taken to process the data."_<br> (lineage)

**Analyst 1:** _"I always have to update my data processing scripts to accommodate different data schemas or storage structures when I work on projects with other people. We don't have an SOP for data storage and handling."_<br>

**Manager 2:** "I often have to ask my team to translate data into more accessible storage formats (e.g. csv, Excel) because I don't know how to retrieve/access data from custom scripting languages like Python or R ... I only know basic SQL and Excel.

**Analyst 2:** _"It takes me forever to compare datasets from different sources or different projects. I never know where to find the authoritative copy, and when I do, the data is rarely in a consistent schema."_<br>

**Engineer 1:** "If I am pulled onto a project in active development, then I find it difficult to determine which datasets have already been processed and which still need to be processed to build our hydrologic models.

**Engineer 2:** _"We do not have an SOP or unified automation framework in place for processing model inputs, so I never know if I'm using the same business logic as other engineers processing the same data for another project."_<br>

**Manager 1:** _"We spend too much time processing model input data. Several team members' time cards show significant time spent developing new data-processing scripts for datasets we reuse across projects rather than using existing workflows. It's very inefficient."_<br>

**Engineer 3:** _"When upstream data providers update their data, it is very time-consuming to integrate these updates into our existing datasets and therefore our models. Also, when these data providers change their data schema, it tends to break our data processing workflows."_<br>

**Manager 2:** _"I often find invalid, duplicate, or missing data records when performing quality control checks on data. Our models need continuous timeseries data void of duplicate records and missing values."_<br>