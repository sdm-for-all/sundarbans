import logging
import os

import ee
from django.core.cache import cache

from .variables import VARIABLES

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Where species models live. Convention: each notebook exports its suitability
# image to  <ASSET_ROOT>/<scientific_name_with_underscores>, e.g.
#   projects/.../assets/sdm/columba_livia
# and records the predictors it used in the image's "variables" property.
# So adding a species = run its notebook + add a Bird row. No code changes.
# ---------------------------------------------------------------------------
ASSET_ROOT = f"projects/{os.environ['EE_PROJECT']}/assets/sdm"   # project id comes from .env

# Models exported BEFORE the convention existed (no "variables" property).
# Delete an entry once that species has been re-exported with the new notebook.
LEGACY = {
    "pitta_nympha": {
        "asset": f"{ASSET_ROOT}/sdm_suitability",
        "variables": ["bio09", "bio14", "elevation", "slope", "TCC"],
    },
}

# Map styling for the returned tiles (0 = unsuitable, 1 = highly suitable)
VIS = {"min": 0, "max": 1,
       "palette": ["440154", "3b528b", "21918c", "5ec962", "fde725"]}


class ModelNotFound(Exception):
    """Raised with a message that is safe to show to the user."""


def slugify(scientific_name):
    return "_".join(scientific_name.strip().lower().split())


def get_model(scientific_name):
    """-> {"asset": "<asset id>", "variables": ["bio01", ...]} for this species."""
    slug = slugify(scientific_name)
    if slug in LEGACY:
        return LEGACY[slug]

    asset = f"{ASSET_ROOT}/{slug}"
    cache_key = f"sdm_model:{asset}"
    info = cache.get(cache_key)
    if info is None:
        try:
            props = ee.data.getAsset(asset).get("properties", {})
        except ee.EEException:
            raise ModelNotFound(
                f"No model has been exported for {scientific_name} yet "
                f"(expected asset: {asset}).")
        declared = [k.strip() for k in str(props.get("variables", "")).split(",") if k.strip()]
        keys = [k for k in declared if k in VARIABLES]
        for k in declared:
            if k not in VARIABLES:
                log.warning("Model %s uses variable %r which is not in variables.py", asset, k)
        if not keys:
            raise ModelNotFound(
                f"The model for {scientific_name} has no usable 'variables' property.")
        info = {"asset": asset, "variables": keys}
        cache.set(cache_key, info, 600)     # failures are not cached, so a finished export shows up at once
    return info


def build_predictors(keys):
    """The chosen variables as one image, in the same units the sliders use."""
    bands = [VARIABLES[k]["build"]().rename(k) for k in keys]
    land = ee.Image("USGS/SRTMGL1_003").select("elevation").gt(0)   # same ocean mask as the notebooks
    return ee.Image.cat(bands).updateMask(land)


def get_region(asset):
    """Footprint of the species' suitability asset (used for slider min/max)."""
    return ee.Image(asset).geometry()


def run_sdm(ranges, asset):
    """
    ranges = {"bio01": [lo, hi], ...}  ->  tile URL for Leaflet.
    Masks the pre-trained suitability map to pixels inside every slider range.
    No retraining happens here.
    """
    predictors = build_predictors(list(ranges))
    mask = ee.Image.constant(1)
    for band, (lo, hi) in ranges.items():
        b = predictors.select(band)
        mask = mask.And(b.gte(lo)).And(b.lte(hi))

    image = ee.Image(asset).updateMask(mask)
    return image.getMapId(VIS)["tile_fetcher"].url_format
