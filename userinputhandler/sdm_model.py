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
# Sundarbans study area. Identical to REGION_BBOX in the notebook CONFIG cell.
REGION_BBOX = [88.0, 21.4, 90.2, 22.8]   # west, south, east, north
def region():
    return ee.Geometry.Rectangle(REGION_BBOX, geodesic=False)


# Models exported BEFORE the convention existed (no "variables" property).
# Delete an entry once that species has been re-exported with the new notebook.
LEGACY = {
    "pitta_nympha": {
        "asset": f"{ASSET_ROOT}/sdm_suitability",
        "variables": ["bio09", "bio14", "elevation", "slope", "TCC"],
        "n_models": 0,          # no saved models yet, so Scenario mode is unavailable
    },
}

# Scenario mode re-scores with models rebuilt from the saved training points
# (<asset>__train_0, __train_1, ...) and the map's "seeds" property, exactly as the notebooks save them.
# Each one is a 500-tree forest evaluated on every map tile, so lower this
# (for example to 5) if scenario maps are slow to draw or Earth Engine times out.
SCENARIO_MODELS_USED = 10

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
        try:
            n_models = int(props.get("n_models", 0) or 0)
        except (TypeError, ValueError):
            n_models = 0
        seeds = [int(x) for x in str(props.get("seeds", "")).split(",") if x.strip().lstrip("-").isdigit()]
        info = {"asset": asset, "variables": keys, "n_models": min(n_models, len(seeds)), "seeds": seeds}
        cache.set(cache_key, info, 600)     # failures are not cached, so a finished export shows up at once
    return info


def build_predictors(keys):
    """The chosen variables as one image, in the same units the sliders use."""
    bands = [VARIABLES[k]["build"]().rename(k) for k in keys]
    land = ee.Image("USGS/SRTMGL1_003").select("elevation").gt(0)   # same ocean mask as the notebooks
    return ee.Image.cat(bands).updateMask(land).clip(region())


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


# ---------------------------------------------------------------------------
# Scenario mode: re-score with the saved models, using shifted conditions
# ---------------------------------------------------------------------------
TRAIN_SCALE = 1000   # same grain_size the notebooks used when sampling predictors


def scenario_ready(asset):
    """True if the first saved training table exists in Earth Engine."""
    try:
        ee.data.getAsset(f"{asset}__train_0")
        return True
    except ee.EEException:
        return False


def build_model_inputs(keys, shifts):
    """
    The predictors exactly as the models were trained on them (same band names, same
    order, same units), with each shift applied in slider units first.
    """
    bands = []
    for k in keys:
        v = VARIABLES[k]
        img = v["build"]()
        s = shifts.get(k, 0)
        if s:
            img = img.add(s)
        lo, hi = v.get("bounds", (None, None))
        if lo is not None:
            img = img.max(lo)
        if hi is not None:
            img = img.min(hi)
        bands.append(img.multiply(v.get("model_scale", 1)).rename(k))
    land = ee.Image("USGS/SRTMGL1_003").select("elevation").gt(0)
    return ee.Image.cat(bands).updateMask(land).clip(region())


def rebuild_classifier(asset, i, keys, seed):
    """Retrain run i's forest (probability mode) from its saved training points, as in the notebook."""
    pts = ee.FeatureCollection(f"{asset}__train_{i}")
    train = build_model_inputs(keys, {}).sampleRegions(
        collection=pts, properties=["PresAbs"], scale=TRAIN_SCALE, geometries=True)
    return (ee.Classifier.smileRandomForest(
                numberOfTrees=500, variablesPerSplit=None, minLeafPopulation=10,
                bagFraction=0.5, maxNodes=None, seed=seed)
            .setOutputMode("PROBABILITY")
            .train(train, "PresAbs", keys))


def run_scenario(shifts, asset, keys, n_models, seeds):
    """
    shifts = {"bio01": 2.0, ...} (slider units; missing = no change)  ->  tile URL.
    Every saved model re-scores every place with the shifted conditions, and the
    scores are averaged. Nothing is retrained.
    """
    inputs = build_model_inputs(keys, shifts)
    n = min(n_models, SCENARIO_MODELS_USED, len(seeds))
    maps = [inputs.classify(rebuild_classifier(asset, i, keys, seeds[i])) for i in range(n)]
    image = (ee.ImageCollection.fromImages(maps).mean()
             .updateMask(ee.Image(asset).mask()))     # only where the saved Sundarbans map exists
    return image.getMapId(VIS)["tile_fetcher"].url_format
