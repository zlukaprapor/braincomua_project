from django.db import models


class Product(models.Model):

    title = models.CharField(max_length=1024, null=True, blank=True)
    color = models.CharField(max_length=256, null=True, blank=True)
    memory = models.CharField(max_length=256, null=True, blank=True)
    vendor = models.CharField(max_length=512, null=True, blank=True)
    price = models.CharField(max_length=128, null=True, blank=True)
    discount_price = models.CharField(max_length=128, null=True, blank=True)
    photos = models.JSONField(null=True, blank=True)
    code = models.CharField(max_length=256, null=True, blank=True)
    reviews_count = models.IntegerField(null=True, blank=True)
    article = models.CharField(max_length=256, null=True, blank=True)
    diagonal = models.CharField(max_length=128, null=True, blank=True)
    resolution = models.CharField(max_length=128, null=True, blank=True)
    specifications = models.JSONField(null=True, blank=True)
    link = models.URLField(max_length=2048, null=True, blank=True)


updated_at = models.DateTimeField(auto_now=True)


def __str__(self):
    return self.title or str(self.pk)