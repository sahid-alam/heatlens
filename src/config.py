"""Shared settings. Everything tunable lives here, nothing else hardcodes these."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

EE_PROJECT = os.getenv("EE_PROJECT")

# Summer months in Bengaluru. March to May is the pre-monsoon hot season.
SUMMER_MONTHS = (3, 5)

# Multi-year window so one freak year doesn't skew the composite.
START_DATE = "2021-01-01"
END_DATE = "2026-06-30"

MAX_CLOUD = 20

# Landsat thermal native resolution. Never leave this to the default.
SCALE = 30

# 198-ward boundaries (2009 delimitation, used by Census 2011).
# Source: DataMeet Municipal_Spatial_Data, CC BY-SA 2.5 India.
WARDS_GEOJSON = RAW / "wards" / "BBMP_oldWards.geojson"

# Census 2011 ward tables. Source: data.opencity.in "Bengaluru Data - Census 2011".
CENSUS_CSV = RAW / "census" / "ward_census_2011.csv"
HOUSING_CSV = RAW / "census" / "housing_houselisting_2011.csv"
BBMP_TOWN_CODE = 803162  # BBMP's code in the housing table; wards 199+ there are outgrowths

# Metre-based CRS for areas and distances (UTM zone 43N covers Bengaluru).
METRIC_CRS = "EPSG:32643"

GEE_CSV = PROCESSED / "gee_wards.csv"  # Earth Engine export, downloaded from Drive
DRIVE_FOLDER = "heatlens"
WARDS_CSV = PROCESSED / "wards.csv"


def init_ee():
    """Authenticate once, then this just initializes."""
    import ee

    if not EE_PROJECT:
        raise RuntimeError("EE_PROJECT not set. Copy .env.example to .env and fill it in.")
    ee.Initialize(project=EE_PROJECT)
    return ee
