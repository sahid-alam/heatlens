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

# Fallback AOI if we don't have the BBMP shapefile yet.
# FAO GAUL level 2 has Bangalore Urban as a district polygon.
FALLBACK_DISTRICT = "Bangalore Urban"

WARDS_SHP = RAW / "bbmp_wards.shp"
WARDS_CSV = PROCESSED / "wards.csv"


def init_ee():
    """Authenticate once, then this just initializes."""
    import ee

    if not EE_PROJECT:
        raise RuntimeError("EE_PROJECT not set. Copy .env.example to .env and fill it in.")
    ee.Initialize(project=EE_PROJECT)
    return ee
