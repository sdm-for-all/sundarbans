import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Bird
from .gbif import get_gbif_species_data


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


@require_POST
def run_model(request):
    payload = json.loads(request.body or "{}")
    bird = Bird.objects.filter(pk=payload.get("species_id")).first()
    if bird is None:
        return JsonResponse({"status": "error", "message": "No species selected"}, status=400)

    df = get_gbif_species_data(bird.scientific_name)
    # TODO: send df points + payload["env"] into the GEE/SDM step
    return JsonResponse({"status": "ok", "n_records": len(df), "env": payload.get("env")})