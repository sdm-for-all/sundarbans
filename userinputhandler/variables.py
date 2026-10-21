"""
Catalog of every environmental variable the app knows how to build and display.

HOW IT FITS TOGETHER
  * A species' notebook exports its suitability image with a "variables" property
    (comma-separated keys, e.g. "bio01,popdens,ntl"). Those keys must exist here.
  * FILTER mode: the app builds each layer below, draws a range slider, and hides
    the map wherever a variable falls outside its range.
  * SCENARIO mode: the app feeds the saved models shifted copies of these layers
    and re-scores every place.

TO SUPPORT A BRAND-NEW VARIABLE
  Add one entry. The key must equal the band name used in the notebook.
    label        slider heading
    unit         shown next to the numbers
    step         range-slider step (Filter mode)
    fallback     (min, max) used only if Earth Engine can't be reached
    clamp        optional (min, max) limits for the Filter sliders (layers with outliers)
    text         sentence for the info panel; {lo} {hi} {unit} are filled in
    build        function returning the layer as ONE band, in the slider's units
    shift        Scenario slider as (min, max, step), or None if this variable
                 cannot sensibly be shifted (terrain)
    bounds       optional (min, max) the shifted value is kept inside (None = no limit)
    model_scale  multiply the slider-unit value by this to get the units the model was
                 TRAINED on (default 1). WorldClim temperatures are trained as degrees x 10,
                 so they use 10. Never rescale bands in a notebook without updating this.
"""
import ee


def _srtm():
    return ee.Image("USGS/SRTMGL1_003")


def _bio(band, scale=1.0):
    return ee.Image("WORLDCLIM/V1/BIO").select(band).multiply(scale)


def _median(collection_id, band, start, end):
    return (ee.ImageCollection(collection_id)
            .filterDate(start, end)
            .select(band)
            .median())


VARIABLES = {
    # --- climate (WorldClim stores temperatures as degrees C x 10) ---------------
    "bio01": {
        "label": "Annual mean temperature", "unit": "°C", "step": 0.5, "fallback": (-5, 20),
        "text": "Annual mean temperature between {lo} and {hi} {unit}.",
        "build": lambda: _bio("bio01", 0.1),
        "shift": (-5, 5, 0.5), "model_scale": 10,
    },
    "bio09": {
        "label": "Mean temp, driest quarter", "unit": "°C", "step": 0.5, "fallback": (-15, 30),
        "text": "Mean temperature in the driest quarter between {lo} and {hi} {unit}.",
        "build": lambda: _bio("bio09", 0.1),
        "shift": (-5, 5, 0.5), "model_scale": 10,
    },
    "bio12": {
        "label": "Annual precipitation", "unit": "mm", "step": 10, "fallback": (0, 3000),
        "text": "Annual precipitation between {lo} and {hi} {unit}.",
        "build": lambda: _bio("bio12"),
        "shift": (-300, 300, 10), "bounds": (0, None),
    },
    "bio14": {
        "label": "Precip, driest month", "unit": "mm", "step": 1, "fallback": (0, 100),
        "text": "Precipitation in the driest month between {lo} and {hi} {unit}.",
        "build": lambda: _bio("bio14"),
        "shift": (-30, 30, 1), "bounds": (0, None),
    },
    # --- terrain (not shiftable) --------------------------------------------------
    "elevation": {
        "label": "Elevation", "unit": "m", "step": 10, "fallback": (0, 2000),
        "text": "Elevation between {lo} and {hi} {unit}.",
        "build": lambda: _srtm().select("elevation"),
        "shift": None,
    },
    "slope": {
        "label": "Slope", "unit": "°", "step": 1, "fallback": (0, 60),
        "text": "Slope between {lo} and {hi} {unit}.",
        "build": lambda: ee.Algorithms.Terrain(_srtm()).select("slope"),
        "shift": None,
    },
    # --- vegetation ---------------------------------------------------------------
    "TCC": {
        "label": "Tree canopy cover", "unit": "%", "step": 1, "fallback": (0, 100),
        "text": "Tree canopy cover between {lo} and {hi} {unit}.",
        "build": lambda: _median("NASA/MEASURES/GFCC/TC/v3", "tree_canopy_cover",
                                 "2000-01-01", "2015-12-31"),
        "shift": (-30, 30, 1), "bounds": (0, 100),
    },
    "ndvi": {
        "label": "Greenness (NDVI)", "unit": "", "step": 0.05, "fallback": (0, 1),
        "clamp": (0, 1),
        "text": "Vegetation greenness (NDVI) between {lo} and {hi}.",
        "build": lambda: _median("MODIS/061/MOD13A2", "NDVI", "2020-01-01", "2020-12-31")
                         .multiply(0.0001),
        "shift": (-0.3, 0.3, 0.05), "bounds": (-1, 1),
    },
    # --- human footprint ----------------------------------------------------------
    "popdens": {
        "label": "Population density", "unit": "people/km²", "step": 100, "fallback": (0, 20000),
        "clamp": (0, 20000),
        "text": "Human population density between {lo} and {hi} {unit}.",
        "build": lambda: _median("CIESIN/GPWv411/GPW_Population_Density", "population_density",
                                 "2020-01-01", "2020-12-31"),
        "shift": (-5000, 5000, 100), "bounds": (0, None),
    },
    "ntl": {
        "label": "Night-time light", "unit": "nW/cm²/sr", "step": 1, "fallback": (0, 60),
        "clamp": (0, 60),
        "text": "Night-time light intensity between {lo} and {hi} {unit}.",
        "build": lambda: _median("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG", "avg_rad",
                                 "2020-01-01", "2020-12-31"),
        "shift": (-10, 10, 1), "bounds": (0, None),
    },
}
