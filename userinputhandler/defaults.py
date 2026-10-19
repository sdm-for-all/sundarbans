# Preset "fractions" are positions inside each variable's min-max range for the
# selected species (0.0 = slider minimum, 1.0 = slider maximum). A variable that
# is missing from a preset keeps its full range, and fractions for variables a
# species doesn't use are ignored.

# Used for every species that has no entry in SPECIES_PRESETS below.
PRESETS = {
    "default":  {"label": "Default",  "fractions": {}},   # {} = full range, i.e. no filtering
    "preset_1": {"label": "Preset 1", "fractions": {
        "bio09": [0.5, 1.0], "bio14": [0.0, 0.4], "elevation": [0.0, 0.3],
        "slope": [0.0, 0.5], "TCC": [0.4, 1.0]}},
}

# Optional species-specific presets, keyed by scientific name in lower case with
# underscores. A species listed here uses ONLY these presets (so include "default").
SPECIES_PRESETS = {
    "columba_livia": {
        "default":      {"label": "Default", "fractions": {}},
        "urban_core":   {"label": "Urban core", "fractions": {
            "popdens": [0.3, 1.0], "ntl": [0.3, 1.0], "ndvi": [0.0, 0.5]}},
        "green_suburb": {"label": "Green suburbs", "fractions": {
            "popdens": [0.05, 0.4], "ntl": [0.05, 0.4], "ndvi": [0.4, 1.0]}},
    },
}
