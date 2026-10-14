"""
Build data/processed/wards.csv: one row per ward, census + housing + satellite.

Satellite columns (lst_c, ndvi, ndbi) come from gee_wards.csv if it exists,
otherwise they are left empty so the rest of the pipeline can still run.

Run: python src/build_wards.py
"""

import geopandas as gpd
import pandas as pd

from config import (
    BBMP_TOWN_CODE,
    CENSUS_CSV,
    GEE_CSV,
    HOUSING_CSV,
    METRIC_CRS,
    PROCESSED,
    WARDS_CSV,
    WARDS_GEOJSON,
)

# Roofs that trap heat: metal/asbestos sheets, plastic, thatch.
HEAT_ROOFS = [
    "Roof - G.I./Metal/ Asbestos sheets",
    "Roof - Plastic/ Polythene",
    "Roof - Grass/ Thatch/ Bamboo/ Wood/Mud etc.",
]

COLUMNS = [
    "ward_id", "ward_name", "lst_c", "ndvi", "ndbi",
    "population", "area_km2", "pop_density",
    "pct_dilapidated", "pct_heat_roof", "housing_vuln",
]


def minmax(s):
    return (s - s.min()) / (s.max() - s.min())


def load_wards():
    g = gpd.read_file(WARDS_GEOJSON)
    g["ward_id"] = g["WARD_NO"].astype(int)
    g["ward_name"] = g["WARD_NAME"].str.strip()
    # The file's own AREA_SQ_KM column is wrong (sums to ~35,000 km2), so compute it.
    g["area_km2"] = g.to_crs(METRIC_CRS).area / 1e6
    return g[["ward_id", "ward_name", "area_km2"]]


def load_population():
    # The geojson's POP_TOTAL is the 2001-based delimitation figure; use Census 2011.
    c = pd.read_csv(CENSUS_CSV)
    return c.rename(columns={"Ward Num": "ward_id", "Population": "population"})[
        ["ward_id", "population"]
    ]


def load_housing():
    h = pd.read_csv(HOUSING_CSV)
    h.columns = [c.strip().replace("\n", " ") for c in h.columns]
    h = h[(h["Town Code/Village code"] == BBMP_TOWN_CODE) & h["Ward No"].between(1, 198)]
    # Census reports these as percentages of households; store fractions.
    return pd.DataFrame({
        "ward_id": h["Ward No"].astype(int),
        "pct_dilapidated": h["HH Condition - Dilapidated"] / 100,
        "pct_heat_roof": h[HEAT_ROOFS].sum(axis=1) / 100,
    })


def build():
    df = load_wards().merge(load_population(), on="ward_id").merge(load_housing(), on="ward_id")
    df["pop_density"] = df["population"] / df["area_km2"]
    # Equal-weight mix of the two housing signals, 0 = best ward, 1 = worst.
    df["housing_vuln"] = minmax(minmax(df["pct_dilapidated"]) + minmax(df["pct_heat_roof"]))

    if GEE_CSV.exists():
        sat = pd.read_csv(GEE_CSV)[["ward_id", "lst_c", "ndvi", "ndbi"]]
        df = df.merge(sat, on="ward_id", how="left")
    else:
        print(f"No {GEE_CSV.name} yet, satellite columns left empty.")
        df[["lst_c", "ndvi", "ndbi"]] = float("nan")

    return df[COLUMNS].sort_values("ward_id").reset_index(drop=True)


def check(df):
    assert len(df) == 198 and df["ward_id"].is_unique, "expected 198 unique wards"
    assert df["ward_id"].tolist() == list(range(1, 199))
    census_cols = ["population", "area_km2", "pop_density", "housing_vuln"]
    assert df[census_cols].notna().all().all(), "census columns have gaps"
    assert df["population"].sum() == 8_443_675, "BBMP 2011 population total changed"
    assert 690 < df["area_km2"].sum() < 760, "area off: CRS problem?"
    assert df["housing_vuln"].between(0, 1).all()


def main():
    df = build()
    check(df)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.round(4).to_csv(WARDS_CSV, index=False)
    print(f"Wrote {len(df)} wards to {WARDS_CSV}")
    print(f"Total area {df.area_km2.sum():.1f} km2, population {df.population.sum():,}")
    print("\nDensest wards:")
    print(df.nlargest(5, "pop_density")[["ward_id", "ward_name", "pop_density"]].to_string(index=False))


if __name__ == "__main__":
    main()
