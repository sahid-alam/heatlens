"""
Pull per-ward land surface temperature, NDVI and NDBI from Google Earth Engine.

Default: starts an Export.table task to Google Drive (folder in config.DRIVE_FOLDER).
Download the CSV from Drive to data/processed/gee_wards.csv when it finishes.

    python src/fetch_lst.py              # all 198 wards, export to Drive
    python src/fetch_lst.py --limit 5    # first 5 wards only (cheap test)
    python src/fetch_lst.py --quick      # skip Drive, pull the table straight back

--quick uses getInfo(). Fine for testing and for 198 small polygons,
but if it times out, use the default export path.
"""

import argparse
import time

import geopandas as gpd
import pandas as pd

from config import (
    DRIVE_FOLDER,
    END_DATE,
    GEE_CSV,
    MAX_CLOUD,
    PROCESSED,
    SCALE,
    START_DATE,
    SUMMER_MONTHS,
    WARDS_GEOJSON,
    init_ee,
)

ee = init_ee()

COLUMNS = ["ward_id", "ward_name", "lst_c", "ndvi", "ndbi"]

# Landsat QA_PIXEL bits 0-4: fill, dilated cloud, cirrus, cloud, cloud shadow.
LANDSAT_BAD_BITS = 0b11111
# Sentinel-2 SCL classes to drop: no data, saturated, cloud shadow,
# cloud medium/high probability, thin cirrus, snow.
S2_BAD_CLASSES = [0, 1, 3, 8, 9, 10, 11]


def get_wards(limit=None):
    """198 BBMP wards as an ee.FeatureCollection with only ward_id and ward_name."""
    g = gpd.read_file(WARDS_GEOJSON)
    g = g.assign(ward_id=g["WARD_NO"].astype(int), ward_name=g["WARD_NAME"].str.strip())
    g = g[["ward_id", "ward_name", "geometry"]].sort_values("ward_id")
    if limit:
        g = g.head(limit)
    print(f"Loaded {len(g)} wards from {WARDS_GEOJSON.name}")
    # Bounding box computed here, so Earth Engine never has to union 198 polygons.
    aoi = ee.Geometry.Rectangle(list(g.total_bounds))
    return ee.FeatureCollection(g.__geo_interface__), aoi


def landsat_composite(aoi):
    """Median summer LST in Celsius from Landsat 8/9 Collection 2 Level-2.

    ST_B10 is already a surface temperature product (USGS applies emissivity and
    atmospheric correction), so no extra emissivity step here.
    Scale factors from the C2 L2 spec: ST_B10 * 0.00341802 + 149.0 = Kelvin.
    """
    col = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterBounds(aoi)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.calendarRange(SUMMER_MONTHS[0], SUMMER_MONTHS[1], "month"))
        .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD))
    )
    print(f"Landsat images in window: {col.size().getInfo()}")

    def prep(img):
        st = img.select("ST_B10")
        clear = img.select("QA_PIXEL").bitwiseAnd(LANDSAT_BAD_BITS).eq(0).And(st.gt(0))
        lst = st.multiply(0.00341802).add(149.0).subtract(273.15).rename("lst_c")
        return lst.updateMask(clear).clip(aoi)

    return col.map(prep).median()


def sentinel_indices(aoi):
    """Median summer NDVI (green cover) and NDBI (built-up) from Sentinel-2 SR."""
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.calendarRange(SUMMER_MONTHS[0], SUMMER_MONTHS[1], "month"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD))
    )
    print(f"Sentinel-2 images in window: {col.size().getInfo()}")

    def prep(img):
        bad = img.select("SCL").remap(S2_BAD_CLASSES, [1] * len(S2_BAD_CLASSES), 0)
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndbi = img.normalizedDifference(["B11", "B8"]).rename("ndbi")
        return ndvi.addBands(ndbi).updateMask(bad.eq(0)).clip(aoi)

    return col.map(prep).median()


def ward_stats(wards, aoi):
    # ponytail: clip to the bounding box, not the 198-polygon union; same pixels
    # reach reduceRegions, far cheaper per image.
    stack = landsat_composite(aoi).addBands(sentinel_indices(aoi))
    return stack.reduceRegions(
        collection=wards,
        reducer=ee.Reducer.mean(),
        scale=SCALE,  # explicit on purpose, never leave it to the default
        tileScale=4,
    )


def quick(stats):
    rows = [f["properties"] for f in stats.getInfo()["features"]]
    df = pd.DataFrame(rows).reindex(columns=COLUMNS).sort_values("ward_id")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.round(4).to_csv(GEE_CSV, index=False)
    print(f"\nWrote {len(df)} rows to {GEE_CSV}")
    print(df.describe().round(2).to_string())


def export(stats):
    task = ee.batch.Export.table.toDrive(
        collection=stats,
        description="heatlens_wards",
        folder=DRIVE_FOLDER,
        fileFormat="CSV",
        selectors=COLUMNS,
    )
    task.start()
    print(f"Started export task {task.id}. Polling every 30 s...")
    while (state := task.status()["state"]) in ("READY", "RUNNING"):
        time.sleep(30)
        print(f"  {state}")
    if state != "COMPLETED":
        raise SystemExit(f"Export {state}: {task.status().get('error_message')}")
    print(f"Done. Download heatlens_wards.csv from Drive folder '{DRIVE_FOLDER}' to {GEE_CSV}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, help="only the first N wards")
    p.add_argument("--quick", action="store_true", help="getInfo instead of Drive export")
    args = p.parse_args()

    stats = ward_stats(*get_wards(args.limit))
    quick(stats) if args.quick else export(stats)


if __name__ == "__main__":
    main()
