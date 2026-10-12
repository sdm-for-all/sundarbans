import requests
import pandas as pd

# Rough placeholder box around the Sundarbans (counter-clockwise, as GBIF requires). Refine later.
SUNDARBANS_WKT = "POLYGON((88.0 21.5, 90.0 21.5, 90.0 22.7, 88.0 22.7, 88.0 21.5))"


def get_gbif_species_data(species_name, geometry=SUNDARBANS_WKT, max_records=3000):
    """GBIF human observations for a species inside a WKT polygon."""
    url = "https://api.gbif.org/v1/occurrence/search"
    rows, offset = [], 0
    while offset < max_records:
        params = {
            "scientificName": species_name,
            "geometry": geometry,
            "hasCoordinate": "true",
            "basisOfRecord": "HUMAN_OBSERVATION",
            "limit": 300,
            "offset": offset,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"GBIF request failed: {e}")
            break
        data = r.json()
        rows.extend(data.get("results", []))
        if data.get("endOfRecords", True):
            break
        offset += 300
    return pd.json_normalize(rows) if rows else pd.DataFrame()