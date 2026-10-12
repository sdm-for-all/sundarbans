from django.contrib import admin

# Register your models here.
from .models import Bird

class BirdAdmin(admin.ModelAdmin):
    list_display = ("scientific_name", "common_name",)

admin.site.register(Bird, BirdAdmin)