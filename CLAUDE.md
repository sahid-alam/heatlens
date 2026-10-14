# Project

Ward-level urban heat risk map for Bengaluru. College project, BMSIT&M, Dept of AI & ML.

Risk = hazard (land surface temperature) + exposure (population) + vulnerability (low green cover, high built-up, housing quality), scored per BBMP ward.

## Stack

- Google Earth Engine (Python API) for satellite data
- geopandas / rasterio for spatial joins
- scikit-learn + SHAP for the model
- FastAPI backend, Leaflet frontend

## Rules

- Write our own code. Read other repos for reference only, never copy files in.
- Clip to Bengaluru before computing, always. GEE quota is 150 EECU-hours/month.
- Export tables (CSV), not rasters.
- Pass `scale=30` explicitly on every reduceRegions call.
- Raw downloads go in `data/raw/`, never edited. Everything derived goes in `data/processed/`.
- Keep `wards.csv` as the single source of truth. One row per ward, one column per feature.

## Data sources

- Landsat 8/9 Collection 2 L2 — thermal band ST_B10 for LST
- Sentinel-2 SR — NDVI (green cover), NDBI (built-up)
- BBMP ward boundaries — shapefile
- Census 2011 ward data — population, housing
- DST/CSTEP district climate risk assessment — validation reference
