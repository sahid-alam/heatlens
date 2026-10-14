# Bengaluru Ward-Level Heat Risk

Mapping urban heat risk across BBMP wards using satellite data and machine learning.

## Problem

Bengaluru has no ward-level heat risk assessment. Heat adaptation spending (tree planting, cool roofs, shade structures) is not targeted because nobody knows which wards are worst off or why. We build that assessment from open satellite and census data.

## Approach

1. Pull summer land surface temperature from Landsat 8/9 thermal imagery
2. Pull vegetation (NDVI) and built-up density (NDBI) from Sentinel-2
3. Join with Census 2011 population and housing data per ward
4. Compute a risk index using the IPCC framework: hazard x exposure x vulnerability
5. Train a model to predict ward temperature from its physical features, then use SHAP to explain which factor drives heat in each specific ward
6. Serve it as an interactive map

The SHAP step is the point. Anyone can make a heat map. Telling a ward officer "your ward is hot because of low tree cover, not building density" is the useful part.

## Setup

```bash
pip install -r requirements.txt
earthengine authenticate
```

Set your GEE project id in `.env`:

```
EE_PROJECT=your-project-id
```

## Running

```bash
python src/fetch_lst.py       # pulls LST + NDVI + NDBI per ward -> data/processed/wards.csv
python src/build_index.py     # computes risk index
python src/model.py           # trains model, writes SHAP values
uvicorn src.api:app --reload  # serves the map
```

## Layout

```
data/raw/         downloaded files, never edited
data/processed/   everything we generate
src/              pipeline code
notebooks/        exploration only, nothing important lives here
frontend/         map UI
```

## Data sources

| Source | Used for |
|---|---|
| Landsat 8/9 C2 L2 | Land surface temperature |
| Sentinel-2 SR | NDVI, NDBI |
| BBMP ward boundaries | Spatial units |
| Census 2011 | Population density, housing quality |
| DST/CSTEP district risk assessment | Validation |

## Team

BMS Institute of Technology and Management, Department of AI and ML.
