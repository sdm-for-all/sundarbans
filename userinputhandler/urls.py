from django.urls import path
from . import views

app_name = "userinputhandler"
urlpatterns = [
    path("species/", views.species_search, name="species_search"),
    path("run/", views.run_model, name="run"),
]