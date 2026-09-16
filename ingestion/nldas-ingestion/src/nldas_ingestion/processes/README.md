applications/ contains your independent processes

# download_nldas_granules.py
We could alternatively make this it's own application folder @ 
```
.../application/download_nldas_granule/
    __init__.py
    download_nldas_granule.py
    └── main() # process entry point

    download_nldas_granule_handler.py
        ├── load_download_job()
        └── record_success()

    download_nldas_granule_service.py
        └── download_nldas_granule()
```