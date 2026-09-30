domain/ contains concepts intrinsic to NLDAS ingestion
```
domain/
├── granule.py
├── download_job.py
└── artifacts.py
```
These aren't necessarily processes.

They're concepts your application reasons about.

For example:

```
Granule
   │
   ├── granule_id
   ├── time
   ├── URL
   └── spatial information

DownloadJob
   │
   ├── job_id
   ├── granule
   ├── destination
   └── download parameters
```