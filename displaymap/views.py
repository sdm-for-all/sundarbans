from django.shortcuts import render

# Create your views here.
# under the Habitat Prediction and Analysis Using GEE cell of the Species_Distribution_Modeling.ipynb notebook
import os, ee 
ee.Initialize(project=os.environ["EE_PROJECT"])
"""  Note: Later on I will NOT need to initialize in this view
because it'll just display the map   """

def index(request):
    image = ee.Image("USGS/SRTMGL1_003")  # elevation
    vis = {"min": 0, "max": 3000, "palette": ["green", "yellow", "brown", "white"]}
    tile_url = image.getMapId(vis)["tile_fetcher"].url_format
    return render(request, "index.html", {"tile_url": tile_url})