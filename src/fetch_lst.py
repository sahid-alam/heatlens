"""
Pull per-ward land surface temperature, NDVI and NDBI from Google Earth Engine.

Writes data/processed/wards.csv. One row per ward.

Run: python src/fetch_lst.py
"""

import pandas as pd

from config import (
    END_DATE,
    FALLBACK_DISTRICT,
    MAX_CLOUD,
    PROCESSED,
    SCALE,
    START_DATE,
    SUMMER_MONTHS,
    WARDS_CSV,
    WARDS_SHP,
    init_ee,
)

ee = init_ee()


def get_wards():
    """BBMP wards if we have the shapefile, otherwise the whole district as one unit.

    The fallback exists so the pipeline runs end to end on day one. Swap in the
    real shapefile and everything downstream keeps working.
    """
    if WARDS_SHP.exists():
        import geemap

        fc = geemap.shp_to_ee(str(WARDS_SHP))
        print(f"Loaded BBMP wards from {WARDS_SHP.name}")
        return fc

    print("No ward shapefile yet. Falling back to Bangalore Urban district.")
    return ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.eq("ADM2_NAME", FALLBACK_DISTRICT)
    )


def landsat_composite(aoi):
    """Median summer composite with LST in Celsius.

    Scale factors come from the Landsat Collection 2 Level 2 spec:
    ST_B10 * 0.00341802 + 149.0 gives Kelvin.
    SR_B* * 0.0000275 - 0.2 gives surface reflectance.
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
        lst = (
            img.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("lst")
        )
        return lst.clip(aoi)

    return col.map(prep).median()


def sentinel_indices(aoi):
    """NDVI for green cover, NDBI for built-up density."""
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.calendarRange(SUMMER_MONTHS[0], SUMMER_MONTHS[1], "month"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD))
    )

    print(f"Sentinel-2 images in window: {col.size().getInfo()}")

    def prep(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndbi = img.normalizedDifference(["B11", "B8"]).rename("ndbi")
        return ndvi.addBands(ndbi).clip(aoi)

    return col.map(prep).median()


def main():
    wards = get_wards()
    aoi = wards.geometry()

    stack = landsat_composite(aoi).addBands(sentinel_indices(aoi))

    # One mean value per ward per band. scale is explicit on purpose.
    stats = stack.reduceRegions(
        collection=wards,
        reducer=ee.Reducer.mean(),
        scale=SCALE,
    )

    rows = stats.getInfo()["features"]
    df = pd.DataFrame([f["properties"] for f in rows])

    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(WARDS_CSV, index=False)

    print(f"\nWrote {len(df)} rows to {WARDS_CSV}")
    print(df.head())


if __name__ == "__main__":
    main()
