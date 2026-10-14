"""
Serve ward data and the map.

Run from the repo root:
    uvicorn api:app --app-dir src --reload
Then open http://127.0.0.1:8000
"""

import json

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from config import ROOT, WARDS_CSV, WARDS_GEOJSON

# Plain-words names for SHAP drivers, shown in the map popup.
DRIVER_LABELS = {
    "shap_ndvi": "Green cover",
    "shap_ndbi": "Built-up density",
    "shap_pop_density": "Population density",
}

app = FastAPI(title="HeatLens Bengaluru")


def load():
    df = pd.read_csv(WARDS_CSV)
    g = gpd.read_file(WARDS_GEOJSON)
    g = gpd.GeoDataFrame({"ward_id": g["WARD_NO"].astype(int)}, geometry=g.geometry, crs=g.crs)
    # ~1 m tolerance in degrees: keeps shapes, shrinks the payload.
    g["geometry"] = g.to_crs("EPSG:4326").simplify(0.00001, preserve_topology=True)
    missing = set(g.ward_id) ^ set(df.ward_id)
    if missing:
        print(f"WARNING: ward_ids in only one of geojson/csv: {sorted(missing)}")
    merged = g.merge(df, on="ward_id", how="left")
    # to_json writes NaN as null, which keeps the JSON valid.
    return df.set_index("ward_id"), json.loads(merged.to_json())


WARDS, GEOJSON = load()


@app.get("/api/wards")
def wards():
    return GEOJSON


@app.get("/api/wards/{ward_id}")
def ward(ward_id: int):
    if ward_id not in WARDS.index:
        raise HTTPException(404, f"No ward {ward_id}")
    row = WARDS.loc[ward_id]
    # pandas' to_json turns numpy types into plain JSON and NaN into null.
    out = {"ward_id": ward_id, **json.loads(row.to_json())}
    drivers = [
        {"feature": col.removeprefix("shap_"), "label": label, "effect_c": round(float(row[col]), 2)}
        for col, label in DRIVER_LABELS.items()
        if col in row and pd.notna(row[col])
    ]
    out["drivers"] = sorted(drivers, key=lambda d: abs(d["effect_c"]), reverse=True)
    return out


# Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
