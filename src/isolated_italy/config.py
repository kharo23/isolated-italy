"""Constants and paths shared by the pipeline stages."""

from __future__ import annotations

from pathlib import Path

OVERTURE_RELEASE = "2026-10-21.0"
OVERTURE_BASE = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}"
OVERTURE_REGION = "us-west-2"

# GHS-POP R2023A, epoch 2025, 30 arc-second, EPSG:4326 (public bucket of the EU Joint Research Centre).
GHS_POP_URL = "/vsis3/jrc-ghsl/ghs-pop/r2023a/4326/30asec/2025/GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif"

# (lon_min, lat_min, lon_max, lat_max)
ITALY_BBOX = (6.5, 35.3, 18.9, 47.2)
BUILDINGS_BBOX = (6.6, 35.4, 18.6, 47.1)

EARTH_RADIUS_KM = 6371.0088
THRESHOLD_KM = 5.0
MIN_CONFIDENCE = 0.3

# Overture place taxonomy -> service category.
SERVICE_TAXONOMY: dict[str, list[str]] = {
    "pharmacy": ["pharmacy"],
    "health": [
        "hospital",
        "emergency_department",
        "urgent_care_clinic",
        "public_health_clinic",
        "doctors_office",
    ],
    "school": ["school", "elementary_school", "middle_school", "public_school", "high_school"],
    "grocery": ["grocery_store", "supermarket"],
    "post": ["post_office"],
    "train": ["train_station"],
}
ESSENTIAL = ("pharmacy", "health", "school", "grocery", "post")
SITE_CATEGORIES = ("pharmacy", "health", "school")
THRESHOLD_STEPS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20)

# Building footprints kept as dwellings, in square metres, and outbuilding classes that are dropped.
FOOTPRINT_M2 = (20, 60_000)
OUTBUILDING_CLASSES = (
    "garage",
    "garages",
    "shed",
    "barn",
    "cowshed",
    "stable",
    "sty",
    "greenhouse",
    "farm_auxiliary",
    "carport",
    "service",
    "roof",
    "hut",
    "kiosk",
    "toilets",
    "transformer_tower",
    "static_caravan",
    "silo",
    "storage_tank",
)
OUTBUILDING_SUBTYPES = ("agricultural", "industrial", "outbuilding", "service", "transportation", "military")

DATA_DIR = Path("data")
WEB_DATA_DIR = Path("web/public/data")
REGISTER_CSV = DATA_DIR / "official_farmacie" / "farmacie.csv"
