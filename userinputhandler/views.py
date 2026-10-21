import json
import math

import ee
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .gee_stats import build_presets, build_scenarios, get_env_vars, get_scenario_vars
from .models import Bird
from .sdm_model import (VIS, ModelNotFound, get_model, run_scenario, run_sdm,
                        scenario_ready, slugify)


def species_search(request):
    q = request.GET.get("q", "").strip()
    qs = Bird.objects.all()
    if q:
        qs = qs.filter(common_name__icontains=q) | qs.filter(scientific_name__icontains=q)
    birds = qs.order_by("common_name")[:50]
    return JsonResponse({"results": [
        {"id": b.pk, "common_name": b.common_name, "scientific_name": b.scientific_name}
        for b in birds
    ]})


def _resolve(species_id):
    """-> (Bird, {"asset": ..., "variables": [...], "n_models": int}) or raises ModelNotFound."""
    try:
        bird = Bird.objects.filter(pk=int(species_id)).first()
    except (TypeError, ValueError):
        bird = None
    if bird is None:
        raise ModelNotFound("Pick a species first")
    return bird, get_model(bird.scientific_name)


def env_config(request):
    """Everything the panels need for one species, as JSON."""
    try:
        bird, model = _resolve(request.GET.get("species_id"))
    except ModelNotFound as e:
        return JsonResponse({"error": str(e)}, status=400)

    env_vars = get_env_vars(model["asset"], model["variables"])
    scenario_vars = get_scenario_vars(model["variables"])

    reason = ""
    if model["n_models"] <= 0:
        reason = ("This species has no saved models yet. Re-run its notebook with "
                  "SAVE_MODELS = True to enable Scenario mode.")
    elif not scenario_vars:
        reason = "None of this species' variables can be shifted."

    return JsonResponse({
        "species": bird.common_name,
        "env_vars": env_vars,
        "presets": build_presets(env_vars, slugify(bird.scientific_name)),
        "scenario": {
            "available": not reason,
            "reason": reason,
            "vars": scenario_vars,
            "presets": build_scenarios(scenario_vars),
        },
        "legend": {"min": VIS["min"], "max": VIS["max"],
                   "palette": ["#" + c for c in VIS["palette"]]},
    })


def _bad(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _run_filter(body, model):
    ranges = body.get("ranges")
    if not isinstance(ranges, dict):
        return _bad("Bad request")

    clean = {}
    for v in get_env_vars(model["asset"], model["variables"]):
        try:
            lo, hi = sorted(float(x) for x in ranges[v["key"]])
        except (KeyError, TypeError, ValueError):
            return _bad(f"Invalid value for {v['key']}")
        lo, hi = max(lo, v["min"]), min(hi, v["max"])   # never trust the browser
        if lo > hi:
            return _bad(f"{v['key']} is outside the allowed range")
        clean[v["key"]] = [lo, hi]

    return JsonResponse({"tile_url": run_sdm(clean, model["asset"])})


def _run_scenario(body, bird, model):
    shifts = body.get("shifts")
    if not isinstance(shifts, dict):
        return _bad("Bad request")
    if model["n_models"] <= 0 or not scenario_ready(model["asset"]):
        return _bad(f"Scenario mode needs the saved models for {bird.common_name}. "
                    "Re-run its notebook with SAVE_MODELS = True.")

    clean = {}
    for v in get_scenario_vars(model["variables"]):
        try:
            s = float(shifts.get(v["key"], 0))
        except (TypeError, ValueError):
            return _bad(f"Invalid value for {v['key']}")
        if not math.isfinite(s):
            return _bad(f"Invalid value for {v['key']}")
        s = max(v["min"], min(v["max"], s))             # never trust the browser
        if s:
            clean[v["key"]] = s

    return JsonResponse({"tile_url": run_scenario(
        clean, model["asset"], model["variables"], model["n_models"])})


@require_POST
def run(request):
    try:
        body = json.loads(request.body)
        mode = body.get("mode", "filter")
    except (ValueError, AttributeError, TypeError):
        return _bad("Bad request")
    if mode not in ("filter", "scenario"):
        return _bad("Bad request")

    try:
        bird, model = _resolve(body.get("species_id"))
    except ModelNotFound as e:
        return _bad(str(e))

    try:
        if mode == "scenario":
            return _run_scenario(body, bird, model)
        return _run_filter(body, model)
    except ee.EEException as e:
        return _bad(f"Earth Engine error: {e}", status=502)
