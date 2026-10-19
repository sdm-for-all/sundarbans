import logging
import math

import ee
from django.core.cache import cache

from .defaults import PRESETS, SPECIES_PRESETS
from .sdm_model import build_predictors, get_region
from .variables import VARIABLES

log = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24      # how long GEE-derived ranges are reused
FALLBACK_SECONDS = 60             # retry GEE after a minute if it failed


def _compute_stats(asset, keys):
    """Min/max of each variable over the area the species' asset covers."""
    r = build_predictors(keys).reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=get_region(asset),
        scale=5000,
        maxPixels=1e10,
        bestEffort=True,
    ).getInfo()

    stats = {}
    for k in keys:
        lo, hi = r.get(k + "_min"), r.get(k + "_max")
        stats[k] = (lo, hi) if lo is not None and hi is not None else VARIABLES[k]["fallback"]
    return stats


def get_env_vars(asset, keys):
    """Slider definitions for one species, with GEE-derived min/max (cached)."""
    cache_key = f"gee_env_stats:{asset}:{','.join(keys)}"
    stats = cache.get(cache_key)
    if stats is None:
        try:
            stats = _compute_stats(asset, keys)
            cache.set(cache_key, stats, CACHE_SECONDS)
        except Exception:
            log.exception("Could not compute slider ranges for %s; using fallbacks", asset)
            stats = {k: VARIABLES[k]["fallback"] for k in keys}
            cache.set(cache_key, stats, FALLBACK_SECONDS)

    env_vars = []
    for k in keys:
        v = VARIABLES[k]
        lo, hi = stats[k]
        c_lo, c_hi = v.get("clamp", (None, None))
        if c_lo is not None:
            lo = max(lo, c_lo)
        if c_hi is not None:
            hi = min(hi, c_hi)
        step = v["step"]
        vmin = round(math.floor(lo / step) * step, 6)
        vmax = round(math.ceil(hi / step) * step, 6)
        if vmax <= vmin:
            vmax = round(vmin + step, 6)
        env_vars.append({
            "key": k, "label": v["label"], "unit": v["unit"], "step": step,
            "min": vmin, "max": vmax, "text": v["text"],
        })
    return env_vars


def build_presets(env_vars, species_slug):
    """Turn preset fractions into real slider values for these env_vars."""
    defs = SPECIES_PRESETS.get(species_slug, PRESETS)
    presets = {}
    for key, p in defs.items():
        vals = {}
        for v in env_vars:
            f_lo, f_hi = p["fractions"].get(v["key"], [0, 1])
            span, s = v["max"] - v["min"], v["step"]
            snap = lambda f: round(round((v["min"] + f * span) / s) * s, 4)
            vals[v["key"]] = [snap(f_lo), snap(f_hi)]
        presets[key] = {"label": p["label"], "values": vals}
    return presets
