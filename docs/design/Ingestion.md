# Ingestion

Below is an example system architecture for a data platform using the same toolset as we aim to use.

![](https://t14291595.p.clickup-attachments.com/t14291595/b85a4425-2102-4b10-9850-5ba42a357372/image.png)

# Upstream Data Sources

## Point Timeseries Datasets
Timeseries data linked to a single point in space.
### NOAA Gage Precipitation
*   Description: Observed (sensor) daily and hourly precipitation intensity timeseries sensed by NOAA precipitation network.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Precipitation \[inches/hour | inches/day\]: Precipitation depth recorded for a specified time interval.
    *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
*   API documentation: ...
### CDEC Gage Precipitation
*   Description: Observed (sensor) daily precipitation intensity timeseries sensed by CDEC precipitation network.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Precipitation \[inches/day\]: Precipitation depth recorded for a specified time interval.
    *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
*   API documentation: ...
### RAWS Gage Precipitation
*   Description: Observed (sensor) daily precipitation intensity timeseries sensed by RAWS precipitation network.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Precipitation \[inches/day\]: Precipitation depth recorded for a specified time interval.
    *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
*   API documentation: ...
### LCD Gage Precipitation
*   No public API, can exclude for now.
### USGS Streamflow
*   Description: Observed (sensor) daily/hourly streamflow volume timeseries sensed by USGS streamflow network.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Streamflow \[inches/hour | inches/day\]: Precipitation depth recorded for a specified time interval.
    *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
*   API documentation: ...
### \*Other Streamflow Gages
*   No public API, can exclude for now.
### \*eWRIMS Points of Diversion
*   Now public API, can exclude for now.
* * *

## Gridded Timeseries Datasets
Gridded timeseries are multi-dimensional data arrays (typically 3D), where 2-dimensions represent geolocation, and a third dimension represents time slices.
![](https://t14291595.p.clickup-attachments.com/t14291595/f725ca50-7d01-41c0-a645-b1d3bb1ef38c/image.png)
NetCDF file storage structure explained for gridded timeseries data.
### PRISM Gridded Precipitation
*   Description: Gridded monthly precipitation dataset derived from interpolating observed (sensors) precipitation gage networks (e.g. NOAA, USGS) and digital elevation maps.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Precipitation \[inches/hour | inches/day\]: Precipitation depth recorded for a specified time interval.
    *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
*   API Documentation: [https://prism.oregonstate.edu/downloads/](https://prism.oregonstate.edu/downloads/)
### NASA-NOAA NLDAS Gridded Meteorological
*   Description: Gridded hourly meteorological and land-surface water/energy forcing dataset derived from a combination of ground-based observation data, regional atmospheric models, and satellite dataset. from interpolating observed (sensors) precipitation gage networks (e.g. NOAA, USGS) and digital elevation maps.
*   Schema:
    *   Timestamp \[date | datetime\]: The date or time of the record
    *   Precipitation \[inches/hour | inches/day\]: Precipitation depth recorded for a specified time interval.
    *   *   Quality Flag \[int | str\]: Record quality flag (e.g. missing, interpolated)
    *   API Documentation:
        *   [https://ntrs.nasa.gov/api/citations/20230000065/downloads/AMS2023\_HDISC\_final.pdf](https://ntrs.nasa.gov/api/citations/20230000065/downloads/AMS2023_HDISC_final.pdf)
        *   [https://registry.opendata.aws/nasa-nldas/](https://registry.opendata.aws/nasa-nldas/)
*   
* * *
## Geospatial Vector Datasets
Geospatial vector data that does not vary with time.
### USGS Watershed Delineations
*   ()
### USGS Stream Delineations
*   ()

* * *
## Geospatial Gridded Datasets
Geospatial gridded data that does not vary with time.
### USGS Soil Classification Maps
*   (SURGO/STATSGO)
### USGS Landuse Classification Maps
*   ()
### USGS Digital Elevation Maps
*   ()
### USGS Imperviousness Maps
*   ()
### USGS Vegetation Maps
*   ()
##