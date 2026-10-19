from django.urls import path
from . import views

app_name = "userinputhandler"
urlpatterns = [
    path("species/", views.species_search, name="species_search"),
    path("env/", views.env_config, name="env_config"),
    path("run/", views.run, name="run"),
]
