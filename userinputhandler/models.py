from django.db import models

# Create your models here.

class Bird(models.Model):
    scientific_name = models.CharField(max_length=255)
    common_name = models.CharField(max_length=255)

    def __str__(self):
        return self.common_name