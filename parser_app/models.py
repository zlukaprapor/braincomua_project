from django.db import models

class TestItem(models.Model):
    name = models.CharField(max_length=255)
    value = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} - {self.name}"
