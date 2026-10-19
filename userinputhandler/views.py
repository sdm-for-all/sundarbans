import json

import ee
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .gee_stats import build_presets, get_env_vars
from .models import Bird
from .sdm_model import ModelNotFound, get_model, run_sdm, slugify


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
    """-> (Bird, {"asset": ..., "variables": [...]}) or raises ModelNotFound."""
    try:
        bird = Bird.objects.filter(pk=int(species_id)).first()
    except (TypeError, ValueError):
        bird = None
    if bird is None:
        raise ModelNotFound("Pick a species first")
    return bird, get_model(bird.scientific_name)


def env_config(request):
    """Sliders and presets for one species, as JSON (drawn by envvar.html)."""
    try:
        bird, model = _resolve(request.GET.get("species_id"))
    except ModelNotFound as e:
        return JsonResponse({"error": str(e)}, status=400)
    env_vars = get_env_vars(model["asset"], model["variables"])
    return JsonResponse({
        "species": bird.common_name,
        "env_vars": env_vars,
        "presets": build_presets(env_vars, slugify(bird.scientific_name)),
    })


@require_POST
def run(request):
    try:
        body = json.loads(request.body)
        ranges = body["ranges"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Bad request"}, status=400)

    try:
        bird, model = _resolve(body.get("species_id"))
    except ModelNotFound as e:
        return JsonResponse({"error": str(e)}, status=400)

    clean = {}
    for v in get_env_vars(model["asset"], model["variables"]):
        try:
            lo, hi = sorted(float(x) for x in ranges[v["key"]])
        except (KeyError, TypeError, ValueError):
            return JsonResponse({"error": f"Invalid value for {v['key']}"}, status=400)
        lo, hi = max(lo, v["min"]), min(hi, v["max"])   # never trust the browser
        if lo > hi:
            return JsonResponse({"error": f"{v['key']} is outside the allowed range"}, status=400)
        clean[v["key"]] = [lo, hi]

    try:
        return JsonResponse({"tile_url": run_sdm(clean, model["asset"])})
    except ee.EEException as e:
        return JsonResponse({"error": f"Earth Engine error: {e}"}, status=502)
